"""Build retry proposals from replay lifecycle timeout recommendations."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping


def build_replay_lifecycle_retry_proposals_from_brief(
    brief: Any,
    *,
    source: str = "overseer",
) -> list[dict[str, Any]]:
    """Build pending replay lifecycle retry proposals from global brief actions."""
    proposals: list[dict[str, Any]] = []

    actions = getattr(brief, "recommended_actions", []) or []
    if not isinstance(actions, list):
        return proposals

    for action in actions:
        if not isinstance(action, Mapping):
            continue

        payload = action.get("payload")
        if not isinstance(payload, Mapping):
            continue

        recommendation = str(payload.get("recommendation") or "").strip()
        if recommendation != "retry_replay_lifecycle_check":
            continue

        reason = str(payload.get("reason") or "").strip()
        timeout_profile = str(payload.get("timeout_profile") or "").strip()
        command_template = str(payload.get("command_template") or "").strip()

        if not reason or not timeout_profile or not command_template:
            continue

        proposal_id = _proposal_id(
            recommendation=recommendation,
            reason=reason,
            timeout_profile=timeout_profile,
            command_template=command_template,
        )

        proposals.append(
            {
                "type": "replay_lifecycle_retry_proposal",
                "proposal_id": proposal_id,
                "status": "pending",
                "source": str(source or "overseer"),
                "recommendation": recommendation,
                "reason": reason,
                "timeout_profile": timeout_profile,
                "command_template": command_template,
                "payload": {
                    "recommendation": recommendation,
                    "reason": reason,
                    "timeout_profile": timeout_profile,
                    "suggested_wait_seconds": payload.get("suggested_wait_seconds"),
                    "suggested_poll_interval": payload.get("suggested_poll_interval"),
                    "security_replay_lifecycle_timeouts": payload.get(
                        "security_replay_lifecycle_timeouts"
                    ),
                },
                "created_at": time.time(),
            }
        )

    return proposals


def _proposal_id(
    *,
    recommendation: str,
    reason: str,
    timeout_profile: str,
    command_template: str,
) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                recommendation,
                reason,
                timeout_profile,
                command_template,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]

    return f"replay-retry-{digest}"


__all__ = ["build_replay_lifecycle_retry_proposals_from_brief"]