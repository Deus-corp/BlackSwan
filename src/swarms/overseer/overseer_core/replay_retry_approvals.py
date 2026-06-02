"""Build approval records for replay lifecycle retry proposals."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping


def build_replay_lifecycle_retry_approval(
    proposal: Mapping[str, Any],
    *,
    approved_by: str,
    status: str = "approved",
    reason: str = "operator_approved_retry",
    execution_enabled: bool = False,
    source: str = "overseer",
    decision_mode: str = "manual",
) -> dict[str, Any]:
    """Build an auditable approval/rejection record for a retry proposal."""
    if not isinstance(proposal, Mapping):
        raise TypeError("proposal must be a mapping")

    if proposal.get("type") != "replay_lifecycle_retry_proposal":
        raise ValueError("proposal must have type='replay_lifecycle_retry_proposal'")

    proposal_id = str(proposal.get("proposal_id") or "").strip()
    if not proposal_id:
        raise ValueError("proposal_id must be present")

    clean_status = str(status or "").strip().lower()
    if clean_status not in {"approved", "rejected"}:
        raise ValueError("status must be approved or rejected")

    clean_approved_by = str(approved_by or "").strip()
    if not clean_approved_by:
        raise ValueError("approved_by must be present")
    
    clean_decision_mode = str(decision_mode or "").strip().lower()
    if clean_decision_mode not in {"manual", "policy"}:
        raise ValueError("decision_mode must be manual or policy")

    clean_reason = str(reason or "").strip() or "operator_approved_retry"

    approval_id = _approval_id(
        proposal_id=proposal_id,
        status=clean_status,
        approved_by=clean_approved_by,
        reason=clean_reason,
        decision_mode=clean_decision_mode,
    )

    return {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": approval_id,
        "proposal_id": proposal_id,
        "status": clean_status,
        "approved_by": clean_approved_by,
        "source": str(source or "overseer"),
        "reason": clean_reason,
        "execution_enabled": bool(execution_enabled),
        "decision_mode": clean_decision_mode,
        "payload": {
            "proposal_id": proposal_id,
            "proposal_type": proposal.get("type"),
            "proposal_status": proposal.get("status"),
            "proposal_reason": proposal.get("reason"),
            "timeout_profile": proposal.get("timeout_profile"),
            "command_template": proposal.get("command_template"),
            "approval_status": clean_status,
            "approved_by": clean_approved_by,
            "reason": clean_reason,
            "execution_enabled": bool(execution_enabled),
            "decision_mode": clean_decision_mode,
        },
        "created_at": time.time(),
    }


def _approval_id(
    *,
    proposal_id: str,
    status: str,
    approved_by: str,
    decision_mode: str,
    reason: str,
) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                proposal_id,
                status,
                approved_by,
                decision_mode,
                reason,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]

    return f"replay-retry-approval-{digest}"


__all__ = ["build_replay_lifecycle_retry_approval"]