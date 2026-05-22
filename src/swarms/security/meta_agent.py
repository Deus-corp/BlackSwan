#!/usr/bin/env python3
"""Production-ready Security MetaAgent.

Responsibilities:
- Aggregate swarm-wide security signals
- Evaluate policy state
- Coordinate security nodes
- Emit CRDT-compatible commands
- Maintain event lineage
- Operate safely under partial failures
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from src.swarms.security.meta_agent_core import (
    SecurityDecision,
    SecurityMetaPolicy,
    SecurityStrategist,
)

from src.swarms.security.node_core import (
    SecurityCommand,
    SecurityMemory,
    make_security_command,
    new_gid,
    now_ts,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)

logger = logging.getLogger("SecurityMetaAgent")


MAIN_LOOP_SLEEP = 1.0
MAX_BACKOFF_SECONDS = 30.0


class SecurityMetaAgent:
    """Top-level coordinator for the security swarm."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Path = Path("./data/security_meta_memory.sqlite3"),
    ) -> None:
        self.node_id = node_id or f"sec-meta-{uuid.uuid4().hex[:8]}"

        self.crdt = CRDTAdapter(
            node_id=self.node_id,
            db_path=config.crdt_db_path,
        )

        self.memory = SecurityMemory(memory_db)

        self.llm = LLMClient(n_ctx=4096)

        self.policy = SecurityMetaPolicy.from_env()

        self.strategist = SecurityStrategist(
            node_id=self.node_id,
            memory=self.memory,
            policy=self.policy,
            llm=self.llm,
        )

        self.step = 0
        self.idle_backoff_s = MAIN_LOOP_SLEEP

        logger.info("🔐 SecurityMetaAgent initialized: %s", self.node_id)

    async def run(self) -> None:
        """Main orchestration loop."""

        logger.info("🔐 SecurityMetaAgent started: %s", self.node_id)

        while True:
            self.step += 1

            try:
                did_work = await self.reflect()

                if did_work:
                    self.idle_backoff_s = MAIN_LOOP_SLEEP
                else:
                    self.idle_backoff_s = min(
                        self.idle_backoff_s * 1.5,
                        MAX_BACKOFF_SECONDS,
                    )

            except asyncio.CancelledError:
                raise

            except Exception as e:
                logger.error(
                    "SecurityMetaAgent loop failure: %s",
                    e,
                    exc_info=True,
                )

                self.idle_backoff_s = min(
                    self.idle_backoff_s * 2.0,
                    MAX_BACKOFF_SECONDS,
                )

            await asyncio.sleep(self.idle_backoff_s)

    async def reflect(self) -> bool:
        """Collect swarm state and evaluate policy."""

        heartbeats = self._collect_heartbeats()
        incidents = self._collect_incidents()
        commands = self._collect_commands()

        if not heartbeats and not incidents and not commands:
            return False

        decision = await self.strategist.evaluate(
            heartbeats=heartbeats,
            incidents=incidents,
            commands=commands,
        )

        self._persist_decision(decision)

        if decision.command_required:
            await self._issue_command(decision)

        return True

    def _collect_heartbeats(self) -> List[Dict[str, Any]]:
        """Collect active node heartbeats from CRDT."""

        result: List[Dict[str, Any]] = []

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") != "security_heartbeat":
                continue

            result.append(value)

            try:
                self.memory.upsert_heartbeat(
                    node_id=str(value.get("node_id", "unknown")),
                    source_gid=str(value.get("gid", "")),
                    blocked_ips=int(value.get("blocked_ips", 0)),
                    status=str(value.get("status", "unknown")),
                    provenance=value.get("provenance", {}),
                )
            except Exception as e:
                logger.warning("Failed heartbeat persistence: %s", e)

        return result

    def _collect_incidents(self) -> List[Dict[str, Any]]:
        """Collect incident signals from CRDT."""

        incident_types = {
            "file_integrity_alert",
            "vulnerability_alert",
            "open_ports_detected",
            "ip_blocked",
            "integrity_alert",
            "threat_detected",
        }

        result: List[Dict[str, Any]] = []

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            event_type = str(value.get("type", ""))

            if event_type not in incident_types:
                continue

            result.append(value)

            try:
                self.memory.record_incident(
                    event_gid=str(value.get("gid") or new_gid("sec_evt")),
                    source_gid=str(value.get("source_gid") or self.node_id),
                    parent_gid=value.get("parent_gid"),
                    incident_type=event_type,
                    severity=float(value.get("severity", 0.5)),
                    details=value,
                    provenance=value.get("provenance", {}),
                )
            except Exception as e:
                logger.warning("Incident persistence failed: %s", e)

        return result

    def _collect_commands(self) -> List[Dict[str, Any]]:
        """Collect issued commands for coordination awareness."""

        result: List[Dict[str, Any]] = []

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") != "sec_command":
                continue

            result.append(value)

        return result

    def _persist_decision(self, decision: SecurityDecision) -> None:
        """Persist evaluated decision into memory."""

        self.memory.record_policy_decision(
            event_gid=decision.event_gid,
            parent_gid=decision.parent_gid,
            decision=decision.decision,
            confidence=decision.confidence,
            rationale=decision.rationale,
            model_name=decision.model_name,
            prompt_hash=decision.prompt_hash,
            provenance=decision.provenance,
        )

        self.memory.record_event_chain(
            event_gid=decision.event_gid,
            parent_gid=decision.parent_gid,
            source_gid=self.node_id,
            event_type="policy_evaluated",
            action=decision.decision,
            status="evaluated",
            details={
                "confidence": decision.confidence,
                "rationale": decision.rationale,
            },
            provenance=decision.provenance,
        )

    async def _issue_command(self, decision: SecurityDecision) -> None:
        """Issue distributed command to the swarm."""

        cmd: SecurityCommand = make_security_command(
            action=decision.decision,
            source_gid=self.node_id,
            parent_gid=decision.event_gid,
            expires_at=now_ts() + self.policy.command_ttl_seconds,
            provenance={
                "agent": self.node_id,
                "confidence": decision.confidence,
                "strategy": decision.rationale,
            },
            data={
                "decision": decision.decision,
                "confidence": decision.confidence,
                "rationale": decision.rationale,
            },
        )

        await self.crdt.add_genome(cmd)

        self.memory.record_command(
            event_gid=cmd["gid"],
            parent_gid=decision.event_gid,
            command_type="security_command",
            target_node_id=None,
            action=decision.decision,
            expires_at=int(cmd["expires_at"]),
            provenance=cmd["provenance"],
        )

        self.memory.record_event_chain(
            event_gid=cmd["gid"],
            parent_gid=decision.event_gid,
            source_gid=self.node_id,
            event_type="command_issued",
            action=decision.decision,
            status="issued",
            details=cmd["data"],
            provenance=cmd["provenance"],
        )

        logger.info(
            "🔐 Issued command: %s | confidence=%.2f",
            decision.decision,
            decision.confidence,
        )


async def main() -> None:
    agent = SecurityMetaAgent()
    await agent.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent interrupted by user.")
    except Exception as e:
        logger.critical(
            "Fatal SecurityMetaAgent error: %s",
            e,
            exc_info=True,
        )
