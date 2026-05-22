"""Orchestration service for the security meta-agent."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from ..node_core.memory import SecurityMemory, SecurityPolicy
from .collector import SecurityCollector
from .models import SecurityCycleResult, SecurityDecision
from .parser import parse_json_loose
from .policy import SecurityPolicyEngine
from .prompts import build_security_prompt
from .utils import now_ts, prompt_hash, strip_to_dict

logger = logging.getLogger(__name__)

DEFAULT_LOOP_SLEEP_SECONDS = 3.0
DEFAULT_IDLE_BACKOFF_SECONDS = 1.0
MAX_IDLE_BACKOFF_SECONDS = 30.0
LLM_MAX_TOKENS = 120
LLM_TEMPERATURE = 0.1


class SecurityMetaAgent:
    """Main decision service for the security meta-layer."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Optional[Path] = None,
    ) -> None:
        self._repo_root = Path(__file__).resolve().parents[3]
        self.node_id = node_id or f"sec-meta-{uuid.uuid4().hex[:8]}"

        if memory_db is None:
            memory_db = self._repo_root / "data" / "security_meta_memory.sqlite3"

        self.llm = LLMClient(n_ctx=4096)
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.memory = SecurityMemory(memory_db)
        self.policy = SecurityPolicy.from_env()

        self.collector = SecurityCollector(self.crdt, self.memory)
        self.policy_engine = SecurityPolicyEngine()

        self.step = 0
        self.idle_backoff_s = DEFAULT_IDLE_BACKOFF_SECONDS

    async def run(self) -> None:
        logger.info("🔐 SecurityMetaAgent %s started", self.node_id)
        while True:
            self.step += 1
            try:
                did_work = await self.reflect()
                self.idle_backoff_s = DEFAULT_IDLE_BACKOFF_SECONDS if did_work else min(self.idle_backoff_s * 1.5, MAX_IDLE_BACKOFF_SECONDS)
            except asyncio.CancelledError:
                logger.info("SecurityMetaAgent %s cancelled.", self.node_id)
                raise
            except Exception as exc:
                logger.error("SecurityMetaAgent loop error: %s", exc, exc_info=True)
                self.idle_backoff_s = min(self.idle_backoff_s * 2.0, 60.0)

            await asyncio.sleep(self.idle_backoff_s)

    async def reflect(self) -> bool:
        snapshot = self.collector.collect()
        if snapshot.heartbeats == 0 and snapshot.incidents == 0 and snapshot.recent_commands == 0:
            return False

        hard = self.policy_engine.evaluate_hard_rules(snapshot)
        llm = await self._ask_llm(snapshot, hard)
        final = self.policy_engine.merge(hard, llm)

        self._log_cycle(snapshot, hard, final, llm)

        result = SecurityCycleResult(
            snapshot=snapshot,
            hard_decision=hard,
            final_decision=final,
            llm_suggestion=strip_to_dict(llm),
        )

        await self._persist_cycle(result)
        await self._maybe_issue_command(result)

        return True

    async def _ask_llm(self, snapshot, hard: SecurityDecision) -> Dict[str, Any]:
        prompt = build_security_prompt(
            snapshot,
            policy_context={
                "allow_emergency_flush_input": self.policy.allow_emergency_flush_input,
                "allow_global_unblock": self.policy.allow_global_unblock,
                "require_llm_confirmation": self.policy.require_llm_confirmation,
                "hard_action": hard.action,
            },
        )

        try:
            response = await asyncio.to_thread(
                self.llm.generate,
                prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
            )
        except Exception as exc:
            logger.warning("LLM generation failed: %s", exc)
            return {}

        return parse_json_loose(response)

    async def _persist_cycle(self, result: SecurityCycleResult) -> None:
        decision = result.final_decision
        snapshot = result.snapshot

        event_gid = f"sec_meta_{uuid.uuid4().hex}"
        self.memory.record_policy_decision(
            event_gid=event_gid,
            parent_gid=None,
            decision=decision.action,
            confidence=decision.confidence,
            rationale=decision.rationale,
            model_name=getattr(self.llm, "model_name", "llm"),
            prompt_hash=prompt_hash(str(snapshot)),
            provenance={
                "agent": self.node_id,
                "source": decision.source,
                "metadata": decision.metadata,
            },
        )

        self.memory.record_event_chain(
            event_gid=event_gid,
            parent_gid=None,
            source_gid=self.node_id,
            event_type="policy_evaluated",
            action=decision.action,
            status="evaluated",
            details={
                "confidence": decision.confidence,
                "rationale": decision.rationale,
            },
            provenance={"agent": self.node_id, "source": decision.source},
        )

    async def _maybe_issue_command(self, result: SecurityCycleResult) -> None:
        decision = result.final_decision

        if decision.action not in {
            "UNBLOCK_ALL",
            "PARTIAL_UNBLOCK",
            "EMERGENCY_FLUSH_INPUT",
            "BLOCK_MORE",
            "ESCALATE",
        }:
            return

        cmd = {
            "type": "sec_command",
            "event_type": "command_issued",
            "gid": f"sec_cmd_{uuid.uuid4().hex}",
            "source_gid": self.node_id,
            "parent_gid": None,
            "timestamp": float(now_ts()),
            "expires_at": now_ts() + 600,
            "provenance": {"agent": self.node_id, "source": "meta_agent"},
            "data": {
                "action": decision.action,
                "rationale": decision.rationale,
                "allow_global_unblock": decision.allow_global_unblock,
                "allow_partial_unblock": decision.allow_partial_unblock,
                "allow_emergency_flush_input": decision.allow_emergency_flush_input,
                "block_new_ips": decision.block_new_ips,
            },
        }
        await self.crdt.add_genome(cmd)
        self.memory.record_command(
            event_gid=cmd["gid"],
            parent_gid=None,
            command_type="sec_command",
            target_node_id=None,
            action=decision.action,
            expires_at=int(cmd["expires_at"]),
            provenance=cmd["provenance"],
        )
        logger.info("🔐 Issued security meta command: %s", decision.action)

    def _log_cycle(self, snapshot, hard: SecurityDecision, final: SecurityDecision, llm: Dict[str, Any]) -> None:
        logger.info(
            "Security snapshot: heartbeats=%d, blocked_ips=%d, active_blocks=%d, incidents=%d, critical=%d",
            snapshot.heartbeats,
            snapshot.blocked_ips,
            snapshot.active_blocks,
            snapshot.incidents,
            snapshot.critical_incidents,
        )
        logger.info("Hard decision: %s (%s)", hard.action, hard.rationale)
        logger.info("Final decision: %s (%s), llm=%s", final.action, final.rationale, llm)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        asyncio.run(SecurityMetaAgent().run())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent stopped.")