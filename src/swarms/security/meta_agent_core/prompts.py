"""Prompt builders for the security meta-agent."""

from __future__ import annotations

import json
from typing import Any, Dict

from .models import SecuritySnapshot


def build_security_prompt(snapshot: SecuritySnapshot, policy_context: Dict[str, Any]) -> str:
    payload = {
        "snapshot": {
            "heartbeats": snapshot.heartbeats,
            "blocked_ips": snapshot.blocked_ips,
            "active_blocks": snapshot.active_blocks,
            "incidents": snapshot.incidents,
            "critical_incidents": snapshot.critical_incidents,
            "stale_nodes": snapshot.stale_nodes,
            "suspicious_ips": snapshot.suspicious_ips,
            "recent_commands": snapshot.recent_commands,
            "resource_notes": snapshot.resource_notes,
        },
        "policy_context": policy_context,
    }

    return (
        "You are BlackSwan Security Meta-Agent.\n"
        "Return ONLY valid JSON with keys:\n"
        "action, confidence, rationale, allow_global_unblock, allow_partial_unblock, "
        "allow_emergency_flush_input, block_new_ips.\n"
        "Action must be one of: MAINTAIN, UNBLOCK_ALL, PARTIAL_UNBLOCK, EMERGENCY_FLUSH_INPUT, BLOCK_MORE, ESCALATE.\n"
        "Use conservative security-first decisions.\n"
        f"State: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"
        "Answer:"
    )