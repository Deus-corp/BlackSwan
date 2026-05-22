#!/usr/bin/env python3
"""Security MetaAgent – policy-aware coordinator using shared security runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from src.swarms.security.shared_runtime import (
    SecurityMemory,
    SecurityPolicy,
    SecurityCommand,
    new_gid,
    now_ts,
    parse_json_loose,
    prompt_hash,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("SecurityMetaAgent")

# Constants
LLM_MAX_TOKENS = 120
LLM_TEMPERATURE = 0.1

class SecurityMetaAgent:
    """Aggregates security signals and emits policy commands."""

    def __init__(self, node_id: Optional[str] = None, memory_db: Path = Path("./data/security_meta_memory.sqlite3")) -> None:
        self.node_id = node_id or f"sec-meta-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient(n_ctx=4096)
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.memory = SecurityMemory(memory_db)
        self.policy = SecurityPolicy.from_env()
        self.step = 0
        self.idle_backoff_s = 1.0
        logger.info("🔐 SecurityMetaAgent initialized: %s", self.node_id)

    async def run(self) -> None:
        """Main orchestration loop for security analysis."""
        logger.info("🔐 SecurityMetaAgent %s started", self.node_id)
        while True:
            self.step += 1
            try:
                did_work = await self.reflect()
                self.idle_backoff_s = 1.0 if did_work else min(self.idle_backoff_s * 1.5, 30.0)
            except Exception as e:
                logger.error("SecurityMetaAgent loop error: %s", e, exc_info=True)
                self.idle_backoff_s = min(self.idle_backoff_s * 2.0, 60.0)
            await asyncio.sleep(self.idle_backoff_s)

    async def reflect(self) -> bool:
        """Collects signals and evaluates security policy."""
        heartbeats = self._collect_heartbeats_from_crdt()
        incidents = self._collect_incidents_from_crdt()
        if not heartbeats and not incidents:
            return False

        decision = self._evaluate_policy(heartbeats, incidents)
        self.memory.record_policy_decision(**decision)
        self.memory.record_event_chain(
            event_gid=decision["event_gid"],
            parent_gid=decision.get("parent_gid"),
            source_gid=decision["event_gid"],
            event_type="policy_evaluated",
            action=decision["decision"],
            status="evaluated",
            details={"confidence": decision["confidence"], "rationale": decision["rationale"]},
            provenance=decision["provenance"],
        )

        if decision["decision"] in {"UNBLOCK_ALL", "PARTIAL_UNBLOCK", "EMERGENCY_FLUSH_INPUT"}:
            await self._issue_command(decision)
        return True

    def _collect_heartbeats_from_crdt(self) -> List[Dict[str, Any]]:
        """Processes security heartbeats from the shared CRDT state."""
        heartbeats = []
        for v in self.crdt.state.values():
            if isinstance(v, dict) and v.get("type") == "security_heartbeat":
                node_id = str(v.get("node_id") or v.get("gid") or "").strip()
                if node_id:
                    hb = {
                        "node_id": node_id,
                        "source_gid": str(v.get("gid") or node_id),
                        "blocked_ips": int(v.get("blocked_ips", 0) or 0),
                        "status": str(v.get("status", "") or ""),
                        "timestamp": float(v.get("timestamp", 0.0) or 0.0),
                        "provenance": v.get("provenance") if isinstance(v.get("provenance"), dict) else {},
                    }
                    heartbeats.append(hb)
        return heartbeats

    def _collect_incidents_from_crdt(self) -> List[Dict[str, Any]]:
        """Processes security incidents from the shared CRDT state."""
        incidents = []
        for v in self.crdt.state.values():
            if isinstance(v, dict) and v.get("type") in {"file_integrity_alert", "vulnerability_alert", "open_ports_detected", "ip_blocked", "all_ips_unblocked"}:
                gid = str(v.get("gid") or new_gid("sec_inc"))
                incident = {
                    "event_gid": gid,
                    "source_gid": str(v.get("source_gid") or gid),
                    "parent_gid": str(v.get("parent_gid") or "") or None,
                    "incident_type": str(v.get("type")),
                    "severity": self._severity_for_incident(v),
                    "details": {k: v[k] for k in v.keys() if k not in {"type", "gid", "timestamp"}},
                    "timestamp": float(v.get("timestamp", 0.0) or 0.0),
                    "provenance": v.get("provenance") if isinstance(v.get("provenance"), dict) else {},
                }
                incidents.append(incident)
        return incidents

    def _severity_for_incident(self, v: Dict[str, Any]) -> float:
        t = str(v.get("type", ""))
        if t == "file_integrity_alert": return 0.95
        if t == "vulnerability_alert": return min(1.0, 0.6 + 0.05 * len(v.get("vulnerabilities", [])))
        if t == "open_ports_detected": return min(1.0, 0.4 + 0.05 * len(v.get("ports", [])))
        if t == "ip_blocked": return 0.2
        if t == "all_ips_unblocked": return 0.85
        return 0.5

    def _evaluate_policy(self, heartbeats: List[Dict[str, Any]], incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        blocked_ips = sum(int(h.get("blocked_ips", 0)) for h in heartbeats)
        max_severity = max((float(i.get("severity", 0.0)) for i in incidents), default=0.0)
        stale_nodes = sum(1 for h in heartbeats if time.time() - float(h.get("timestamp", 0.0) or 0.0) > self.policy.heartbeat_staleness_seconds)

        if incidents and max_severity >= 0.9 and self.policy.allow_emergency_flush_input and blocked_ips < self.policy.max_blocked_ips_soft:
            decision, confidence, rationale = "EMERGENCY_FLUSH_INPUT", 0.9, "High severity incident detected with manual override capabilities."
        elif len(heartbeats) >= self.policy.unblock_threshold_heartbeats and blocked_ips <= self.policy.max_blocked_ips_soft and stale_nodes == 0:
            decision, confidence, rationale = ("UNBLOCK_ALL" if self.policy.allow_global_unblock else "MAINTAIN"), 0.8, "System stable."
        else:
            decision, confidence, rationale = "MAINTAIN", 0.84, "Standard operating state."

        prompt = self._build_llm_prompt(len(heartbeats), blocked_ips, stale_nodes, max_severity, decision, rationale)
        if self.policy.require_llm_confirmation:
            response = self.llm.generate(prompt, max_tokens=LLM_MAX_TOKENS, temperature=LLM_TEMPERATURE)
            parsed = parse_json_loose(response or "")
            if isinstance(parsed, dict):
                decision = str(parsed.get("decision", decision)).upper()
                confidence = float(parsed.get("confidence", confidence))
                rationale = str(parsed.get("rationale", rationale))

        return {
            "event_gid": new_gid("sec_policy"),
            "parent_gid": None,
            "decision": decision,
            "confidence": confidence,
            "rationale": rationale,
            "model_name": getattr(self.llm, "model_name", "llm"),
            "prompt_hash": prompt_hash(prompt),
            "provenance": {"agent": self.node_id, "policy": asdict(self.policy)}
        }

    def _build_llm_prompt(self, hc: int, bi: int, sn: int, sev: float, d: str, r: str) -> str:
        return json.dumps({
            "task": "Verify security posture.",
            "status": {"hc": hc, "blocked_ips": bi, "stale": sn, "severity": sev, "proposed": d, "rationale": r},
            "output_schema": {"decision": "str", "confidence": "float", "rationale": "str"}
        })

    async def _issue_command(self, decision: Dict[str, Any]) -> None:
        command_gid = new_gid("sec_cmd")
        cmd: SecurityCommand = {
            "type": "sec_command",
            "event_type": "command_issued",
            "gid": command_gid,
            "source_gid": decision["event_gid"],
            "parent_gid": decision.get("parent_gid"),
            "timestamp": time.time(),
            "expires_at": now_ts() + 600,
            "provenance": {"agent": self.node_id},
            "data": {"action": decision["decision"], "rationale": decision["rationale"]}
        }
        await self.crdt.add_genome(cmd)
        logger.info("🔐 Issued security command: %s", decision["decision"])

if __name__ == "__main__":
    try:
        asyncio.run(SecurityMetaAgent().run())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent stopped.")