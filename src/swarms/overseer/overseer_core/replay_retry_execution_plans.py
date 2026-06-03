"""Build non-executing retry execution plans from approved replay retry proposals."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping


def build_replay_lifecycle_retry_execution_plan(
    proposal: Mapping[str, Any],
    approval: Mapping[str, Any],
    *,
    source: str = "overseer",
) -> dict[str, Any]:
    """Build a non-executing execution plan from a proposal and approval."""
    if not isinstance(proposal, Mapping):
        raise TypeError("proposal must be a mapping")
    if not isinstance(approval, Mapping):
        raise TypeError("approval must be a mapping")

    if proposal.get("type") != "replay_lifecycle_retry_proposal":
        raise ValueError("proposal must have type='replay_lifecycle_retry_proposal'")
    if approval.get("type") != "replay_lifecycle_retry_approval":
        raise ValueError("approval must have type='replay_lifecycle_retry_approval'")

    proposal_id = str(proposal.get("proposal_id") or "").strip()
    approval_id = str(approval.get("approval_id") or "").strip()

    if not proposal_id:
        raise ValueError("proposal_id must be present")
    if not approval_id:
        raise ValueError("approval_id must be present")

    if str(proposal.get("status") or "").strip().lower() != "pending":
        raise ValueError("proposal status must be pending")

    if str(approval.get("status") or "").strip().lower() != "approved":
        raise ValueError("approval status must be approved")

    if str(approval.get("proposal_id") or "").strip() != proposal_id:
        raise ValueError("approval proposal_id must match proposal_id")

    if bool(approval.get("execution_enabled")):
        raise ValueError("approval execution_enabled must be false before runner support")

    timeout_profile = str(proposal.get("timeout_profile") or "").strip()
    command_template = str(proposal.get("command_template") or "").strip()
    decision_mode = str(approval.get("decision_mode") or "").strip().lower()

    if timeout_profile not in {"standard", "patient"}:
        raise ValueError("timeout_profile must be standard or patient")

    if not command_template:
        raise ValueError("command_template must be present")

    if decision_mode not in {"manual", "policy"}:
        raise ValueError("decision_mode must be manual or policy")

    plan_id = _plan_id(
        proposal_id=proposal_id,
        approval_id=approval_id,
        timeout_profile=timeout_profile,
        decision_mode=decision_mode,
    )

    return {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": "planned",
        "source": str(source or "overseer"),
        "execution_enabled": False,
        "timeout_profile": timeout_profile,
        "command_template": command_template,
        "decision_mode": decision_mode,
        "payload": {
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "proposal_reason": proposal.get("reason"),
            "approval_reason": approval.get("reason"),
            "timeout_profile": timeout_profile,
            "command_template": command_template,
            "decision_mode": decision_mode,
            "execution_enabled": False,
        },
        "created_at": time.time(),
    }


def _plan_id(
    *,
    proposal_id: str,
    approval_id: str,
    timeout_profile: str,
    decision_mode: str,
) -> str:
    digest = hashlib.sha256(
        "|".join([proposal_id, approval_id, timeout_profile, decision_mode]).encode("utf-8")
    ).hexdigest()[:16]

    return f"replay-retry-plan-{digest}"


__all__ = ["build_replay_lifecycle_retry_execution_plan"]