#!/usr/bin/env python3
"""Security MetaAgent – policy-aware coordinator using shared security runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

from src.swarms.security.shared_runtime import (
    SecurityMemory,
    SecurityPolicy,
    SecurityEvent,
    make_security_command,
    make_security_event,
    new_gid,
    now_ts,
    parse_json_loose,
    prompt_hash,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("SecurityMetaAgent")

REFLECTION_INTERVAL_STEPS = 100
MAIN_LOOP_SLEEP_SECONDS = 1.0
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
        self.last_reflection_ts = 0.0
        self.idle_backoff_s = 1.0
        logger.info("🔐 SecurityMetaAgent initialized: %s", self.node_id)

    async def run(self) -> None:
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
        self.last_reflection_ts = time.time()
        heartbeats = self._collect_heartbeats_from_crdt()
        incidents = self._collect_incidents_from_crdt()
        if not heartbeats and not incidents:
            return False

        decision = self._evaluate_policy(heartbeats, incidents)
        self.memory.record_policy_decision(
            event_gid=decision["event_gid"],
            parent_gid=decision.get("parent_gid"),
            decision=decision["decision"],
            confidence=decision["confidence"],
            rationale=decision["rationale"],
            model_name=decision["model_name"],
            prompt_hash=decision["prompt_hash"],
            provenance=decision["provenance"],
        )
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
        heartbeats: List[Dict[str, Any]] = []
        for v in self.crdt.state.values():
            if not isinstance(v, dict) or v.get("type") != "security_heartbeat":
                continue
            node_id = str(v.get("node_id") or v.get("gid") or "").strip()
            if not node_id:
                continue
            hb = {
                "node_id": node_id,
                "source_gid": str(v.get("gid") or node_id),
                "blocked_ips": int(v.get("blocked_ips", 0) or 0),
                "status": str(v.get("status", "") or ""),
                "timestamp": float(v.get("timestamp", 0.0) or 0.0),
                "provenance": v.get("provenance") if isinstance(v.get("provenance"), dict) else {},
            }
            self.memory.upsert_heartbeat(
                node_id=node_id,
                source_gid=hb["source_gid"],
                blocked_ips=hb["blocked_ips"],
                status=hb["status"],
                provenance=hb["provenance"],
            )
            self.memory.record_event_chain(
                event_gid=hb["source_gid"],
                parent_gid=hb["provenance"].get("parent_gid") if isinstance(hb["provenance"], dict) else None,
                source_gid=hb["source_gid"],
                event_type="heartbeat_received",
                action="heartbeat",
                status=hb["status"],
                details={"blocked_ips": hb["blocked_ips"]},
                provenance=hb["provenance"],
            )
            heartbeats.append(hb)
        return heartbeats

    def _collect_incidents_from_crdt(self) -> List[Dict[str, Any]]:
        incidents: List[Dict[str, Any]] = []
        for v in self.crdt.state.values():
            if not isinstance(v, dict) or v.get("type") not in {"file_integrity_alert", "vulnerability_alert", "open_ports_detected", "ip_blocked", "all_ips_unblocked"}:
                continue
            gid = str(v.get("gid") or new_gid("sec_inc"))
            details = {k: v[k] for k in v.keys() if k not in {"type", "gid", "timestamp"}}
            incident = {
                "event_gid": gid,
                "source_gid": str(v.get("source_gid") or gid),
                "parent_gid": str(v.get("parent_gid") or "") or None,
                "incident_type": str(v.get("type")),
                "severity": self._severity_for_incident(v),
                "details": details,
                "timestamp": float(v.get("timestamp", 0.0) or 0.0),
                "provenance": v.get("provenance") if isinstance(v.get("provenance"), dict) else {},
            }
            self.memory.record_incident(
                event_gid=incident["event_gid"],
                source_gid=incident["source_gid"],
                parent_gid=incident["parent_gid"],
                incident_type=incident["incident_type"],
                severity=incident["severity"],
                details=incident["details"],
                provenance=incident["provenance"],
            )
            self.memory.record_event_chain(
                event_gid=incident["event_gid"],
                parent_gid=incident["parent_gid"],
                source_gid=incident["source_gid"],
                event_type="incident_observed",
                action=incident["incident_type"],
                status="observed",
                details={"severity": incident["severity"], **incident["details"]},
                provenance=incident["provenance"],
            )
            incidents.append(incident)
        return incidents

    def _severity_for_incident(self, v: Dict[str, Any]) -> float:
        t = str(v.get("type", ""))
        if t == "file_integrity_alert":
            return 0.95
        if t == "vulnerability_alert":
            vulns = v.get("vulnerabilities", [])
            try:
                return min(1.0, 0.6 + 0.05 * len(vulns))
            except Exception:
                return 0.7
        if t == "open_ports_detected":
            ports = v.get("ports", [])
            try:
                return min(1.0, 0.4 + 0.05 * len(ports))
            except Exception:
                return 0.5
        if t == "ip_blocked":
            return 0.2
        if t == "all_ips_unblocked":
            return 0.85
        return 0.5

    def _evaluate_policy(self, heartbeats: List[Dict[str, Any]], incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        heartbeats_count = len(heartbeats)
        blocked_ips = sum(int(h.get("blocked_ips", 0)) for h in heartbeats)
        recent_incident_severity = max((float(i.get("severity", 0.0)) for i in incidents), default=0.0)
        stale_nodes = sum(1 for h in heartbeats if time.time() - float(h.get("timestamp", 0.0) or 0.0) > self.policy.heartbeat_staleness_seconds)

        if incidents and recent_incident_severity >= 0.9:
            decision = "LOCKDOWN"
            if self.policy.allow_emergency_flush_input and blocked_ips < self.policy.max_blocked_ips_soft:
                decision = "EMERGENCY_FLUSH_INPUT"
        elif heartbeats_count >= self.policy.unblock_threshold_heartbeats and blocked_ips <= self.policy.max_blocked_ips_soft and stale_nodes == 0:
            decision = "UNBLOCK_ALL" if self.policy.allow_global_unblock else "MAINTAIN"
        elif blocked_ips > 0 and recent_incident_severity < 0.3:
            decision = "PARTIAL_UNBLOCK"
        else:
            decision = "MAINTAIN"

        confidence = 0.72 if decision != "MAINTAIN" else 0.84
        rationale = (
            f"heartbeats={heartbeats_count}, blocked_ips={blocked_ips}, "
            f"stale_nodes={stale_nodes}, max_incident_severity={recent_incident_severity:.2f}"
        )
        model_name = getattr(self.llm, "model_name", "llm")
        prompt = self._build_llm_prompt(heartbeats_count, blocked_ips, stale_nodes, recent_incident_severity, decision, rationale)
        ph = prompt_hash(prompt)

        if self.policy.require_llm_confirmation:
            response = self.llm.generate(prompt, max_tokens=LLM_MAX_TOKENS, temperature=LLM_TEMPERATURE)
            parsed = parse_json_loose(response or "")
            if isinstance(parsed, dict):
                llm_decision = str(parsed.get("decision", decision)).strip().upper()
                llm_confidence = self._clamp_float(parsed.get("confidence", confidence), 0.0, 1.0)
                llm_rationale = str(parsed.get("rationale", rationale))[:800]
                if llm_decision in {"UNBLOCK_ALL", "PARTIAL_UNBLOCK", "LOCKDOWN", "EMERGENCY_FLUSH_INPUT", "MAINTAIN"}:
                    decision = llm_decision
                    confidence = llm_confidence
                    rationale = llm_rationale

        return {
            "event_gid": new_gid("sec_policy"),
            "parent_gid": None,
            "decision": decision,
            "confidence": confidence,
            "rationale": rationale,
            "model_name": model_name,
            "prompt_hash": ph,
            "provenance": {
                "agent": self.node_id,
                "heartbeats_count": heartbeats_count,
                "blocked_ips": blocked_ips,
                "stale_nodes": stale_nodes,
                "max_incident_severity": recent_incident_severity,
                "policy": asdict(self.policy),
            },
        }

    def _build_llm_prompt(self, heartbeats_count: int, blocked_ips: int, stale_nodes: int, max_incident_severity: float, decision: str, rationale: str) -> str:
        payload = {
            "task": "Review the proposed security posture decision.",
            "status": {
                "heartbeats_count": heartbeats_count,
                "blocked_ips": blocked_ips,
                "stale_nodes": stale_nodes,
                "max_incident_severity": round(max_incident_severity, 2),
                "proposed_decision": decision,
                "local_rationale": rationale,
            },
            "allowed_decisions": ["MAINTAIN", "UNBLOCK_ALL", "PARTIAL_UNBLOCK", "LOCKDOWN", "EMERGENCY_FLUSH_INPUT"],
            "output_schema": {
                "decision": "MAINTAIN|UNBLOCK_ALL|PARTIAL_UNBLOCK|LOCKDOWN|EMERGENCY_FLUSH_INPUT",
                "confidence": 0.0,
                "rationale": "short rationale",
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    async def _issue_command(self, decision: Dict[str, Any]) -> None:
        command_gid = new_gid("sec_cmd")
        expires_at = now_ts() + 600
        action = decision["decision"]
        data: Dict[str, Any] = {
            "action": action,
            "confidence": decision["confidence"],
            "rationale": decision["rationale"],
            "policy": decision["provenance"].get("policy", {}),
        }
        if action in {"LOCKDOWN", "EMERGENCY_FLUSH_INPUT"}:
            data["requires_manual_enable"] = True
        if action == "PARTIAL_UNBLOCK":
            data["scope"] = "targeted"

        cmd: SecurityCommand = {
            "type": "sec_command",
            "event_type": "command_issued",
            "gid": command_gid,
            "source_gid": decision["event_gid"],
            "parent_gid": decision.get("parent_gid"),
            "timestamp": time.time(),
            "expires_at": expires_at,
            "provenance": {
                "agent": self.node_id,
                "decision_event_gid": decision["event_gid"],
                "confidence": decision["confidence"],
                "rationale": decision["rationale"],
                "manual_override_required": action == "EMERGENCY_FLUSH_INPUT",
            },
            "data": data,
        }
        await self.crdt.add_genome(cmd)
        self.memory.record_command(
            event_gid=command_gid,
            parent_gid=decision["event_gid"],
            command_type="sec_command",
            target_node_id=None,
            action=action,
            expires_at=expires_at,
            provenance=cmd["provenance"],
        )
        self.memory.record_event_chain(
            event_gid=command_gid,
            parent_gid=decision["event_gid"],
            source_gid=decision["event_gid"],
            event_type="command_issued",
            action=action,
            status="issued",
            details={"expires_at": expires_at, **data},
            provenance=cmd["provenance"],
        )
        logger.info("🔐 Issued security command: %s", action)

    @staticmethod
    def _clamp_float(value: Any, low: float, high: float) -> float:
        try:
            x = float(value)
        except Exception:
            x = low
        return max(low, min(high, x))


if __name__ == "__main__":
    node = SecurityMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical("SecurityMetaAgent encountered a fatal error: %s", e, exc_info=True)