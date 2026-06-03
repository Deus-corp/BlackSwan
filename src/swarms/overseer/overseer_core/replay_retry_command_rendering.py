"""Render non-executing retry commands from replay retry execution plans."""

from __future__ import annotations

import hashlib
import shlex
import time
from typing import Any, Mapping


SAFE_TIMEOUT_PROFILES = {"standard", "patient"}


def build_replay_lifecycle_retry_rendered_command(
    plan: Mapping[str, Any],
    *,
    scenario_id: str,
    new_directive_id: str,
    source: str = "overseer",
) -> dict[str, Any]:
    """Build an auditable non-executing rendered retry command record."""
    if not isinstance(plan, Mapping):
        raise TypeError("plan must be a mapping")

    if plan.get("type") != "replay_lifecycle_retry_execution_plan":
        raise ValueError("plan must have type='replay_lifecycle_retry_execution_plan'")

    plan_id = str(plan.get("plan_id") or "").strip()
    proposal_id = str(plan.get("proposal_id") or "").strip()
    approval_id = str(plan.get("approval_id") or "").strip()
    status = str(plan.get("status") or "").strip().lower()
    timeout_profile = str(plan.get("timeout_profile") or "").strip()
    decision_mode = str(plan.get("decision_mode") or "").strip().lower()
    command_template = str(plan.get("command_template") or "").strip()
    execution_enabled = bool(plan.get("execution_enabled"))

    clean_scenario_id = _clean_token(scenario_id, field_name="scenario_id")
    clean_new_directive_id = _clean_token(new_directive_id, field_name="new_directive_id")

    if not plan_id:
        raise ValueError("plan_id must be present")
    if not proposal_id:
        raise ValueError("proposal_id must be present")
    if not approval_id:
        raise ValueError("approval_id must be present")
    if status != "planned":
        raise ValueError("plan status must be planned")
    if execution_enabled:
        raise ValueError("execution_enabled must be false for rendering")
    if timeout_profile not in SAFE_TIMEOUT_PROFILES:
        raise ValueError("timeout_profile must be standard or patient")
    if decision_mode not in {"manual", "policy"}:
        raise ValueError("decision_mode must be manual or policy")
    if not command_template:
        raise ValueError("command_template must be present")
    if "<scenario_id>" not in command_template:
        raise ValueError("command_template must include <scenario_id>")
    if "<new_directive_id>" not in command_template:
        raise ValueError("command_template must include <new_directive_id>")

    command = command_template.replace("<scenario_id>", clean_scenario_id).replace(
        "<new_directive_id>",
        clean_new_directive_id,
    )

    _validate_rendered_command(command, timeout_profile=timeout_profile)

    rendered_id = _rendered_command_id(
        plan_id=plan_id,
        scenario_id=clean_scenario_id,
        new_directive_id=clean_new_directive_id,
        command=command,
    )

    return {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": rendered_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": "rendered",
        "source": str(source or "overseer"),
        "execution_enabled": False,
        "scenario_id": clean_scenario_id,
        "new_directive_id": clean_new_directive_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "payload": {
            "plan_id": plan_id,
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "scenario_id": clean_scenario_id,
            "new_directive_id": clean_new_directive_id,
            "timeout_profile": timeout_profile,
            "decision_mode": decision_mode,
            "command_template": command_template,
            "command": command,
            "execution_enabled": False,
            "executed": False,
        },
        "created_at": time.time(),
    }


def _clean_token(value: str, *, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be present")

    forbidden = {";", "&&", "|", ">", "<", "`", "$", "\n", "\r", "\t"}
    if any(token in clean for token in forbidden):
        raise ValueError(f"{field_name} contains unsafe characters")

    return clean


def _validate_rendered_command(command: str, *, timeout_profile: str) -> None:
    if not command:
        raise ValueError("rendered command must be present")

    forbidden = [";", "&&", "|", ">", "<", "`", "$("]
    if any(token in command for token in forbidden):
        raise ValueError("rendered command contains unsafe shell syntax")

    parts = shlex.split(command)
    expected_prefix = ["python", "-m", "src.testing.run_replay_evidence_check"]
    if parts[:3] != expected_prefix:
        raise ValueError("rendered command must call src.testing.run_replay_evidence_check")

    if "--timeout-profile" not in parts:
        raise ValueError("rendered command must include --timeout-profile")

    profile_index = parts.index("--timeout-profile")
    if profile_index + 1 >= len(parts):
        raise ValueError("rendered command missing timeout profile value")

    if parts[profile_index + 1] != timeout_profile:
        raise ValueError("rendered command timeout profile mismatch")

    if timeout_profile not in SAFE_TIMEOUT_PROFILES:
        raise ValueError("timeout_profile must be standard or patient")


def _rendered_command_id(
    *,
    plan_id: str,
    scenario_id: str,
    new_directive_id: str,
    command: str,
) -> str:
    digest = hashlib.sha256(
        "|".join([plan_id, scenario_id, new_directive_id, command]).encode("utf-8")
    ).hexdigest()[:16]

    return f"replay-retry-rendered-{digest}"


__all__ = ["build_replay_lifecycle_retry_rendered_command"]