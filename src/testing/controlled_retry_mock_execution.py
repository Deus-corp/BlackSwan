"""Mock adapter for controlled retry execution.

This module never invokes subprocesses. It produces an execution-shaped mock
result only after the controlled gate report is ready enough for mock execution.
"""

from __future__ import annotations

from typing import Any, Mapping


def build_controlled_retry_mock_execution(
    controlled_result: Mapping[str, Any],
    *,
    mock_execution_enabled: bool = False,
    real_execution_enabled: bool = False,
) -> dict[str, Any]:
    """Build a mock execution envelope without invoking subprocesses."""
    reasons: list[str] = []

    if not mock_execution_enabled:
        reasons.append("mock_execution_not_enabled")

    if real_execution_enabled:
        reasons.append("real_execution_must_remain_disabled")

    status = str(controlled_result.get("status") or "").strip()
    reason = str(controlled_result.get("reason") or "").strip()

    if status != "rejected":
        reasons.append("controlled_result_not_rejected")
    if reason != "controlled_execution_not_implemented":
        reasons.append("controlled_result_reason_not_not_implemented")

    operator_authorized = bool(controlled_result.get("operator_authorized"))
    allowlist_matched = bool(controlled_result.get("allowlist_matched"))

    payload = controlled_result.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if bool(payload_mapping.get("executed")):
        reasons.append("payload_already_executed")

    command_parse = controlled_result.get("command_parse")
    if not isinstance(command_parse, Mapping):
        command_parse = payload_mapping.get("command_parse")
    command_parse_mapping = command_parse if isinstance(command_parse, Mapping) else {}

    if not bool(command_parse_mapping.get("valid")):
        reasons.append("command_parse_invalid")
    if not bool(command_parse_mapping.get("allowlist_matched")):
        reasons.append("command_parse_allowlist_not_matched")
    if bool(command_parse_mapping.get("execution_performed")):
        reasons.append("command_parse_already_performed_execution")

    gate_evaluation = controlled_result.get("gate_evaluation")
    if not isinstance(gate_evaluation, Mapping):
        gate_evaluation = payload_mapping.get("gate_evaluation")
    gate_mapping = gate_evaluation if isinstance(gate_evaluation, Mapping) else {}

    if not gate_mapping:
        reasons.append("missing_gate_evaluation")
    if bool(gate_mapping.get("would_execute")):
        reasons.append("gate_would_execute_must_remain_false")
    if bool(gate_mapping.get("execution_performed")):
        reasons.append("gate_already_performed_execution")

    if not operator_authorized:
        reasons.append("operator_authorization_missing")
    if not allowlist_matched:
        reasons.append("allowlist_not_matched")

    mock_performed = not reasons

    return {
        "type": "controlled_retry_mock_execution",
        "status": "mock_executed" if mock_performed else "blocked",
        "reason": "mock_execution_completed" if mock_performed else "mock_execution_blocked",
        "mock_execution_enabled": bool(mock_execution_enabled),
        "real_execution_enabled": bool(real_execution_enabled),
        "operator_authorized": operator_authorized,
        "allowlist_matched": allowlist_matched,
        "rendered_command_id": str(controlled_result.get("rendered_command_id") or ""),
        "plan_id": str(controlled_result.get("plan_id") or ""),
        "proposal_id": str(controlled_result.get("proposal_id") or ""),
        "approval_id": str(controlled_result.get("approval_id") or ""),
        "controlled_execution_result_id": str(
            controlled_result.get("controlled_execution_result_id") or ""
        ),
        "mock_execution": {
            "performed": mock_performed,
            "adapter": "mock",
            "subprocess_invoked": False,
            "exit_code": 0 if mock_performed else None,
            "stdout": (
                "mock controlled retry execution"
                if mock_performed
                else ""
            ),
            "stderr": "",
            "reasons": reasons,
        },
        "payload": {
            "executed": False,
            "mock_executed": mock_performed,
            "subprocess_invoked": False,
            "mock_execution_enabled": bool(mock_execution_enabled),
            "real_execution_enabled": bool(real_execution_enabled),
            "controlled_execution_result_id": str(
                controlled_result.get("controlled_execution_result_id") or ""
            ),
            "rendered_command_id": str(controlled_result.get("rendered_command_id") or ""),
            "plan_id": str(controlled_result.get("plan_id") or ""),
            "proposal_id": str(controlled_result.get("proposal_id") or ""),
            "approval_id": str(controlled_result.get("approval_id") or ""),
            "reasons": reasons,
        },
    }