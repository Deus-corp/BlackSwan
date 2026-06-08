"""Gate evaluation for future controlled retry command execution.

This module only evaluates whether a controlled retry command would be eligible
for execution. It does not execute commands.
"""

from __future__ import annotations

from typing import Any, Mapping


def evaluate_controlled_retry_execution_gate(
    *,
    controlled_result: Mapping[str, Any],
    controlled_execution_enabled: bool = False,
    implementation_enabled: bool = False,
    min_readiness_score: int = 100,
) -> dict[str, Any]:
    """Evaluate controlled execution gates without executing anything."""
    reasons: list[str] = []

    payload = controlled_result.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    command_parse = controlled_result.get("command_parse")
    if not isinstance(command_parse, Mapping):
        command_parse = payload_mapping.get("command_parse")
    command_parse_mapping = command_parse if isinstance(command_parse, Mapping) else {}

    status = str(controlled_result.get("status") or "").strip()
    reason = str(controlled_result.get("reason") or "").strip()

    operator_authorized = bool(controlled_result.get("operator_authorized"))
    allowlist_matched = bool(controlled_result.get("allowlist_matched"))
    command_parse_valid = bool(command_parse_mapping.get("valid"))
    command_parse_allowlist_matched = bool(command_parse_mapping.get("allowlist_matched"))
    command_parse_execution_performed = bool(command_parse_mapping.get("execution_performed"))
    payload_executed = bool(payload_mapping.get("executed"))
    execution_enabled = bool(controlled_result.get("execution_enabled"))

    readiness_score = _safe_int(controlled_result.get("readiness_score"), 0)

    if status != "rejected":
        reasons.append("controlled_result_not_rejected")

    if reason != "controlled_execution_not_implemented":
        reasons.append("controlled_result_reason_not_not_implemented")

    if not operator_authorized:
        reasons.append("operator_authorization_missing")

    if not allowlist_matched:
        reasons.append("allowlist_not_matched")

    if not command_parse_mapping:
        reasons.append("missing_command_parse")

    if not command_parse_valid:
        reasons.append("command_parse_invalid")

    if not command_parse_allowlist_matched:
        reasons.append("command_parse_allowlist_not_matched")

    if command_parse_execution_performed:
        reasons.append("command_parse_already_performed_execution")

    if payload_executed:
        reasons.append("payload_already_executed")

    if execution_enabled:
        # Rendered command execution_enabled can only become meaningful after
        # controlled execution gates are intentionally opened.
        reasons.append("rendered_execution_enabled_not_supported_yet")

    if readiness_score < min_readiness_score:
        reasons.append("readiness_score_below_threshold")

    if not controlled_execution_enabled:
        reasons.append("controlled_execution_not_enabled")

    if not implementation_enabled:
        reasons.append("controlled_execution_implementation_not_enabled")

    would_execute = (
        not reasons
        and controlled_execution_enabled
        and implementation_enabled
        and operator_authorized
        and allowlist_matched
        and command_parse_valid
        and command_parse_allowlist_matched
        and not command_parse_execution_performed
        and not payload_executed
        and readiness_score >= min_readiness_score
    )

    # PR 29.4 invariant: evaluator never executes and should never authorize
    # execution while implementation_enabled defaults to false.
    return {
        "type": "controlled_retry_execution_gate_evaluation",
        "gate_status": "ready" if would_execute else "blocked",
        "would_execute": False,
        "would_execute_if_enabled": would_execute,
        "reasons": reasons,
        "controlled_execution_enabled": bool(controlled_execution_enabled),
        "implementation_enabled": bool(implementation_enabled),
        "operator_authorized": operator_authorized,
        "allowlist_matched": allowlist_matched,
        "command_parse_valid": command_parse_valid,
        "command_parse_allowlist_matched": command_parse_allowlist_matched,
        "command_parse_execution_performed": command_parse_execution_performed,
        "payload_executed": payload_executed,
        "execution_enabled": execution_enabled,
        "readiness_score": readiness_score,
        "min_readiness_score": min_readiness_score,
        "execution_performed": False,
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default