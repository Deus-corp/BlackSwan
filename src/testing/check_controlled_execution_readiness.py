"""Final pre-execution readiness report for controlled retry execution.

This helper is read-only. It aggregates the safe retry governance trail,
controlled execution observability, and controlled gate state before any
execution adapter is introduced.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.testing.check_controlled_retry_execution_observability import (
    _exit_code_for_result as controlled_observability_exit_code,
    check_controlled_retry_execution_observability,
)
from src.testing.check_retry_governance_observability import (
    _exit_code_for_result as retry_observability_exit_code,
    check_retry_governance_observability,
)
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary as trail_exit_code,
    inspect_retry_governance_trail,
)
from src.testing.controlled_retry_execution_adapter import (
    describe_controlled_retry_execution_adapter_contract,
)
from swarm_config import config

logger = logging.getLogger(__name__)


READINESS_SCHEMA_VERSION = "controlled-execution-readiness/v1"


def check_controlled_execution_readiness(args: argparse.Namespace) -> dict[str, Any]:
    """Build a read-only final pre-execution readiness report."""
    db_path = str(args.db_path or config.crdt_db_path)
    proposal_id = str(getattr(args, "proposal_id", "") or "").strip()
    rendered_command_id = str(getattr(args, "rendered_command_id", "") or "").strip()
    require_operator_authorized = bool(
        getattr(args, "require_operator_authorized", False)
    )

    trail_summary = inspect_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            approval_id="",
            plan_id="",
        )
    )
    retry_observability = check_retry_governance_observability(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            json=False,
        )
    )
    controlled_observability = check_controlled_retry_execution_observability(
        argparse.Namespace(
            db_path=db_path,
            rendered_command_id=rendered_command_id,
            plan_id="",
            proposal_id=proposal_id,
            json=False,
        )
    )

    checks = _build_checks(
        trail_summary=trail_summary,
        retry_observability=retry_observability,
        controlled_observability=controlled_observability,
        require_operator_authorized=require_operator_authorized,
    )
    failed_checks = [item for item in checks if item.get("status") != "passed"]

    ready_for_mock_execution = not failed_checks
    ready_for_real_execution = False

    blocking_reasons = [str(item.get("name")) for item in failed_checks]
    if ready_for_mock_execution:
        blocking_reasons.append("real_execution_not_supported_yet")

    controlled_mock_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_statuses")
    )
    controlled_mock_performed = _safe_mapping(
        trail_summary.get("controlled_mock_performed")
    )
    controlled_mock_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_subprocess_invoked")
    )
    mock_summary_statuses = _safe_mapping(
        trail_summary.get("mock_summary_statuses")
    )
    mock_summary_performed = _safe_mapping(
        trail_summary.get("mock_summary_performed")
    )
    mock_summary_subprocess_invoked = _safe_mapping(
        trail_summary.get("mock_summary_subprocess_invoked")
    )
    controlled_mock_adapter = _safe_mapping(
        trail_summary.get("controlled_mock_adapter")
    )
    controlled_mock_adapter_mode = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_mode")
    )
    controlled_mock_adapter_result_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_result_statuses")
    )
    controlled_mock_adapter_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_subprocess_invoked")
    )
    controlled_mock_adapter_real_execution_enabled = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_real_execution_enabled")
    )
    controlled_mock_adapter_payload_executed = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_payload_executed")
    )
    controlled_real_execution_requested = _safe_mapping(
        trail_summary.get("controlled_real_execution_requested")
    )
    controlled_real_execution_performed = _safe_mapping(
        trail_summary.get("controlled_real_execution_performed")
    )
    controlled_real_execution_supported = _safe_mapping(
        trail_summary.get("controlled_real_execution_supported")
    )
    controlled_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_subprocess_invoked")
    )
    controlled_reasons = _safe_mapping(
        trail_summary.get("controlled_execution_result_reasons")
    )
    real_preflight_statuses = _safe_mapping(trail_summary.get("real_preflight_statuses"))
    real_preflight_reasons = _safe_mapping(trail_summary.get("real_preflight_reasons"))
    real_preflight_would_execute = _safe_mapping(trail_summary.get("real_preflight_would_execute"))
    real_preflight_execution_performed = _safe_mapping(trail_summary.get("real_preflight_execution_performed"))
    real_preflight_subprocess_invoked = _safe_mapping(trail_summary.get("real_preflight_subprocess_invoked"))
    real_preflight_requires_explicit_pr = _safe_mapping(trail_summary.get("real_preflight_requires_explicit_pr"))

    adapter_contract = describe_controlled_retry_execution_adapter_contract()

    return {
        "type": "controlled_execution_readiness_report",
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "adapter_contract": adapter_contract,
        "real_adapter_supported": bool(
            adapter_contract.get("real_execution_supported")
        ),
        "real_adapter_runnable": bool(
            (
                adapter_contract.get("real_adapter_contract")
                if isinstance(adapter_contract.get("real_adapter_contract"), Mapping)
                else {}
            ).get("runnable")
        ),
        "real_adapter_requires_explicit_pr": bool(
            (
                (
                    adapter_contract.get("real_adapter_contract")
                    if isinstance(
                        adapter_contract.get("real_adapter_contract"), Mapping
                    )
                    else {}
                )
            ).get("requires_explicit_pr")
        ),
        "real_preflight_observed": _safe_int(real_preflight_statuses.get("blocked")) > 0,
        "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
        "real_preflight_would_execute": _safe_int(real_preflight_would_execute.get("true")),
        "real_preflight_execution_performed": _safe_int(real_preflight_execution_performed.get("true")),
        "real_preflight_subprocess_invoked": _safe_int(real_preflight_subprocess_invoked.get("true")),
        "real_preflight_requires_explicit_pr": _safe_int(real_preflight_requires_explicit_pr.get("true")),
        "status": "passed" if ready_for_mock_execution else "failed",
        "ready_for_mock_execution": ready_for_mock_execution,
        "ready_for_real_execution": ready_for_real_execution,
        "blocking_reasons": blocking_reasons,
        "require_operator_authorized": require_operator_authorized,
        "proposal_id": proposal_id or None,
        "rendered_command_id": rendered_command_id or None,
        "summary": {
            "status": "passed" if ready_for_mock_execution else "failed",
            "ready_for_mock_execution": ready_for_mock_execution,
            "ready_for_real_execution": ready_for_real_execution,
            "blocking_reasons": blocking_reasons,
            "mock_execution_observed": _safe_int(
                controlled_mock_statuses.get("mock_executed")
            )
            > 0,
            "mock_execution_summary_observed": _safe_int(
                mock_summary_statuses.get("mock_executed")
            )
            > 0,
            "adapter_contract_observed": (
                _safe_int(controlled_mock_adapter.get("mock")) > 0
                and _safe_int(controlled_mock_adapter_mode.get("mock")) > 0
                and _safe_int(
                    controlled_mock_adapter_result_statuses.get("mock_executed")
                )
                > 0
            ),
            "adapter_subprocess_invoked": _safe_int(
                controlled_mock_adapter_subprocess_invoked.get("true")
            ),
            "adapter_real_execution_enabled": _safe_int(
                controlled_mock_adapter_real_execution_enabled.get("true")
            ),
            "adapter_payload_executed": _safe_int(
                controlled_mock_adapter_payload_executed.get("true")
            ),
            "real_adapter_supported": bool(
                adapter_contract.get("real_execution_supported")
            ),
            "real_adapter_runnable": bool(
                (
                    adapter_contract.get("real_adapter_contract")
                    if isinstance(
                        adapter_contract.get("real_adapter_contract"), Mapping
                    )
                    else {}
                ).get("runnable")
            ),
            "real_adapter_requires_explicit_pr": bool(
                (
                    (
                        adapter_contract.get("real_adapter_contract")
                        if isinstance(
                            adapter_contract.get("real_adapter_contract"), Mapping
                        )
                        else {}
                    )
                ).get("requires_explicit_pr")
            ),
            "real_execution_request_observed": _safe_int(
                controlled_real_execution_requested.get("true")
            )
            > 0,
            "real_execution_request_rejected": _safe_int(
                controlled_reasons.get("real_execution_not_supported")
            ),
            "real_preflight_observed": _safe_int(real_preflight_statuses.get("blocked")) > 0,
            "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
            "real_preflight_would_execute": _safe_int(
                real_preflight_would_execute.get("true")
            ),
            "real_preflight_execution_performed": _safe_int(
                real_preflight_execution_performed.get("true")
            ),
            "real_preflight_subprocess_invoked": _safe_int(
                real_preflight_subprocess_invoked.get("true")
            ),
            "real_preflight_requires_explicit_pr": _safe_int(
                real_preflight_requires_explicit_pr.get("true")
            ),
        },
        "required_fields": [
            "schema_version",
            "schema_kind",
            "type",
            "status",
            "ready_for_mock_execution",
            "ready_for_real_execution",
            "blocking_reasons",
            "adapter_contract_observed",
            "adapter_subprocess_invoked",
            "adapter_real_execution_enabled",
            "adapter_payload_executed",
            "checks",
            "exit_codes",
            "adapter_contract",
            "real_adapter_supported",
            "real_adapter_runnable",
            "real_adapter_requires_explicit_pr",
            "real_execution_request_observed",
            "real_execution_request_rejected",
            "real_preflight_observed",
            "real_preflight_blocked",
        ],
        "trail_summary": trail_summary,
        "retry_observability": retry_observability,
        "controlled_observability": controlled_observability,
        "checks": checks,
        "exit_codes": {
            "trail": trail_exit_code(trail_summary, require_complete=True),
            "retry_observability": retry_observability_exit_code(retry_observability),
            "controlled_observability": controlled_observability_exit_code(
                controlled_observability
            ),
            "real_execution": 1,
        },
        "mock_execution_observed": _safe_int(
            controlled_mock_statuses.get("mock_executed")
        )
        > 0,
        "mock_execution_performed": _safe_int(
            controlled_mock_performed.get("true")
        ),
        "mock_subprocess_invoked": _safe_int(
            controlled_mock_subprocess_invoked.get("true")
        ),
        "mock_execution_summary_observed": _safe_int(
            mock_summary_statuses.get("mock_executed")
        )
        > 0,
        "mock_execution_summary_performed": _safe_int(
            mock_summary_performed.get("true")
        ),
        "mock_summary_subprocess_invoked": _safe_int(
            mock_summary_subprocess_invoked.get("true")
        ),
        "adapter_contract_observed": (
            _safe_int(controlled_mock_adapter.get("mock")) > 0
            and _safe_int(controlled_mock_adapter_mode.get("mock")) > 0
            and _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            )
            > 0
        ),
        "adapter_mock": _safe_int(controlled_mock_adapter.get("mock")),
        "adapter_mode_mock": _safe_int(controlled_mock_adapter_mode.get("mock")),
        "adapter_result_mock_executed": _safe_int(
            controlled_mock_adapter_result_statuses.get("mock_executed")
        ),
        "adapter_subprocess_invoked": _safe_int(
            controlled_mock_adapter_subprocess_invoked.get("true")
        ),
        "adapter_real_execution_enabled": _safe_int(
            controlled_mock_adapter_real_execution_enabled.get("true")
        ),
        "adapter_payload_executed": _safe_int(
            controlled_mock_adapter_payload_executed.get("true")
        ),
        "real_execution_request_observed": _safe_int(
            controlled_real_execution_requested.get("true")
        )
        > 0,
        "real_execution_request_rejected": _safe_int(
            controlled_reasons.get("real_execution_not_supported")
        ),
        "real_execution_requested": _safe_int(
            controlled_real_execution_requested.get("true")
        ),
        "real_execution_performed": _safe_int(
            controlled_real_execution_performed.get("true")
        ),
        "real_execution_supported_count": _safe_int(
            controlled_real_execution_supported.get("true")
        ),
        "subprocess_invoked_count": _safe_int(
            controlled_subprocess_invoked.get("true")
        ),
    }


def _build_checks(
    *,
    trail_summary: Mapping[str, Any],
    retry_observability: Mapping[str, Any],
    controlled_observability: Mapping[str, Any],
    require_operator_authorized: bool,
) -> list[dict[str, Any]]:
    counts = _safe_mapping(trail_summary.get("counts"))
    controlled_statuses = _safe_mapping(
        trail_summary.get("controlled_execution_result_statuses")
    )
    controlled_reasons = _safe_mapping(
        trail_summary.get("controlled_execution_result_reasons")
    )
    command_parse_valid = _safe_mapping(
        trail_summary.get("controlled_command_parse_valid")
    )
    command_parse_allowlisted = _safe_mapping(
        trail_summary.get("controlled_command_parse_allowlist_matched")
    )
    command_parse_execution_performed = _safe_mapping(
        trail_summary.get("controlled_command_parse_execution_performed")
    )
    operator_authorized = _safe_mapping(
        trail_summary.get("controlled_execution_operator_authorized")
    )
    gate_statuses = _safe_mapping(trail_summary.get("controlled_gate_statuses"))
    gate_would_execute = _safe_mapping(
        trail_summary.get("controlled_gate_would_execute")
    )
    gate_execution_performed = _safe_mapping(
        trail_summary.get("controlled_gate_execution_performed")
    )
    gate_reasons = _safe_mapping(trail_summary.get("controlled_gate_reasons"))
    controlled_mock_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_statuses")
    )
    controlled_mock_performed = _safe_mapping(
        trail_summary.get("controlled_mock_performed")
    )
    controlled_mock_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_subprocess_invoked")
    )
    mock_summary_statuses = _safe_mapping(trail_summary.get("mock_summary_statuses"))
    mock_summary_performed = _safe_mapping(trail_summary.get("mock_summary_performed"))
    mock_summary_subprocess_invoked = _safe_mapping(
        trail_summary.get("mock_summary_subprocess_invoked")
    )
    controlled_mock_adapter = _safe_mapping(
        trail_summary.get("controlled_mock_adapter")
    )
    controlled_mock_adapter_mode = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_mode")
    )
    controlled_mock_adapter_result_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_result_statuses")
    )
    controlled_mock_adapter_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_subprocess_invoked")
    )
    controlled_mock_adapter_real_execution_enabled = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_real_execution_enabled")
    )
    controlled_mock_adapter_payload_executed = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_payload_executed")
    )
    controlled_real_execution_requested = _safe_mapping(
        trail_summary.get("controlled_real_execution_requested")
    )
    controlled_real_execution_performed = _safe_mapping(
        trail_summary.get("controlled_real_execution_performed")
    )
    controlled_real_execution_supported = _safe_mapping(
        trail_summary.get("controlled_real_execution_supported")
    )
    controlled_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_subprocess_invoked")
    )
    real_preflight_statuses = _safe_mapping(trail_summary.get("real_preflight_statuses"))
    real_preflight_reasons = _safe_mapping(trail_summary.get("real_preflight_reasons"))
    real_preflight_would_execute = _safe_mapping(trail_summary.get("real_preflight_would_execute"))
    real_preflight_execution_performed = _safe_mapping(trail_summary.get("real_preflight_execution_performed"))
    real_preflight_subprocess_invoked = _safe_mapping(trail_summary.get("real_preflight_subprocess_invoked"))
    real_preflight_requires_explicit_pr = _safe_mapping(trail_summary.get("real_preflight_requires_explicit_pr"))

    checks = [
        _check(
            "trail_chain_complete",
            bool(trail_summary.get("chain_complete")),
            bool(trail_summary.get("chain_complete")),
        ),
        _check(
            "trail_has_controlled_execution_result",
            _safe_int(counts.get("controlled_execution_results")) > 0,
            _safe_int(counts.get("controlled_execution_results")),
        ),
        _check(
            "controlled_result_rejected",
            _safe_int(controlled_statuses.get("rejected")) > 0,
            _safe_int(controlled_statuses.get("rejected")),
        ),
        _check(
            "controlled_result_not_implemented",
            _safe_int(controlled_reasons.get("controlled_execution_not_implemented"))
            > 0,
            _safe_int(controlled_reasons.get("controlled_execution_not_implemented")),
        ),
        _check(
            "command_parse_valid",
            _safe_int(command_parse_valid.get("true")) > 0,
            _safe_int(command_parse_valid.get("true")),
        ),
        _check(
            "command_parse_allowlisted",
            _safe_int(command_parse_allowlisted.get("true")) > 0,
            _safe_int(command_parse_allowlisted.get("true")),
        ),
        _check(
            "command_parse_did_not_execute",
            _safe_int(command_parse_execution_performed.get("true")) == 0,
            _safe_int(command_parse_execution_performed.get("true")),
        ),
        _check(
            "controlled_gate_blocked",
            _safe_int(gate_statuses.get("blocked")) > 0,
            _safe_int(gate_statuses.get("blocked")),
        ),
        _check(
            "controlled_gate_would_not_execute",
            _safe_int(gate_would_execute.get("true")) == 0,
            _safe_int(gate_would_execute.get("true")),
        ),
        _check(
            "controlled_gate_did_not_execute",
            _safe_int(gate_execution_performed.get("true")) == 0,
            _safe_int(gate_execution_performed.get("true")),
        ),
        _check(
            "controlled_gate_not_enabled_reason_observed",
            _safe_int(gate_reasons.get("controlled_execution_not_enabled")) > 0,
            _safe_int(gate_reasons.get("controlled_execution_not_enabled")),
        ),
        _check(
            "retry_observability_passed",
            retry_observability.get("status") == "passed",
            retry_observability.get("status"),
        ),
        _check(
            "controlled_observability_passed",
            controlled_observability.get("status") == "passed",
            controlled_observability.get("status"),
        ),
        _check(
            "controlled_observability_reports_no_execution",
            _safe_int(
                controlled_observability.get(
                    "controlled_execution_gate_execution_performed"
                )
            )
            == 0
            and _safe_int(controlled_observability.get("controlled_execution_executed"))
            == 0,
            {
                "gate_execution_performed": controlled_observability.get(
                    "controlled_execution_gate_execution_performed"
                ),
                "controlled_execution_executed": controlled_observability.get(
                    "controlled_execution_executed"
                ),
            },
        ),
        _check(
            "mock_execution_observed",
            _safe_int(controlled_mock_statuses.get("mock_executed")) > 0,
            _safe_int(controlled_mock_statuses.get("mock_executed")),
        ),
        _check(
            "mock_execution_performed",
            _safe_int(controlled_mock_performed.get("true")) > 0,
            _safe_int(controlled_mock_performed.get("true")),
        ),
        _check(
            "mock_execution_did_not_invoke_subprocess",
            _safe_int(controlled_mock_subprocess_invoked.get("true")) == 0,
            _safe_int(controlled_mock_subprocess_invoked.get("true")),
        ),
        _check(
            "mock_execution_summary_observed",
            _safe_int(mock_summary_statuses.get("mock_executed")) > 0,
            _safe_int(mock_summary_statuses.get("mock_executed")),
        ),
        _check(
            "mock_execution_summary_performed",
            _safe_int(mock_summary_performed.get("true")) > 0,
            _safe_int(mock_summary_performed.get("true")),
        ),
        _check(
            "mock_execution_summary_did_not_invoke_subprocess",
            _safe_int(mock_summary_subprocess_invoked.get("true")) == 0,
            _safe_int(mock_summary_subprocess_invoked.get("true")),
        ),
        _check(
            "adapter_contract_observed",
            _safe_int(controlled_mock_adapter.get("mock")) > 0
            and _safe_int(controlled_mock_adapter_mode.get("mock")) > 0
            and _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            )
            > 0,
            {
                "adapter_mock": _safe_int(controlled_mock_adapter.get("mock")),
                "adapter_mode_mock": _safe_int(
                    controlled_mock_adapter_mode.get("mock")
                ),
                "adapter_result_mock_executed": _safe_int(
                    controlled_mock_adapter_result_statuses.get("mock_executed")
                ),
            },
        ),
        _check(
            "adapter_is_mock",
            _safe_int(controlled_mock_adapter.get("mock")) > 0,
            _safe_int(controlled_mock_adapter.get("mock")),
        ),
        _check(
            "adapter_mode_is_mock",
            _safe_int(controlled_mock_adapter_mode.get("mock")) > 0,
            _safe_int(controlled_mock_adapter_mode.get("mock")),
        ),
        _check(
            "adapter_result_mock_executed",
            _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            )
            > 0,
            _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            ),
        ),
        _check(
            "adapter_subprocess_not_invoked",
            _safe_int(controlled_mock_adapter_subprocess_invoked.get("true")) == 0,
            _safe_int(controlled_mock_adapter_subprocess_invoked.get("true")),
        ),
        _check(
            "adapter_real_execution_not_enabled",
            _safe_int(
                controlled_mock_adapter_real_execution_enabled.get("true")
            )
            == 0,
            _safe_int(
                controlled_mock_adapter_real_execution_enabled.get("true")
            ),
        ),
        _check(
            "adapter_payload_not_executed",
            _safe_int(controlled_mock_adapter_payload_executed.get("true")) == 0,
            _safe_int(controlled_mock_adapter_payload_executed.get("true")),
        ),
        _check(
            "real_execution_request_rejected_if_observed",
            _safe_int(controlled_real_execution_requested.get("true")) == 0
            or _safe_int(controlled_reasons.get("real_execution_not_supported")) > 0,
            {
                "requested": _safe_int(
                    controlled_real_execution_requested.get("true")
                ),
                "rejected": _safe_int(
                    controlled_reasons.get("real_execution_not_supported")
                ),
            },
        ),
        _check(
            "real_execution_request_did_not_execute",
            _safe_int(controlled_real_execution_performed.get("true")) == 0,
            _safe_int(controlled_real_execution_performed.get("true")),
        ),
        _check(
            "real_execution_request_did_not_enable_support",
            _safe_int(controlled_real_execution_supported.get("true")) == 0,
            _safe_int(controlled_real_execution_supported.get("true")),
        ),
        _check(
            "real_execution_request_did_not_invoke_subprocess",
            _safe_int(controlled_subprocess_invoked.get("true")) == 0,
            _safe_int(controlled_subprocess_invoked.get("true")),
        ),
        _check(
            "real_preflight_observed_if_real_request_observed",
            _safe_int(controlled_real_execution_requested.get("true")) == 0
            or _safe_int(real_preflight_statuses.get("blocked")) > 0,
            {
                "real_execution_requested": _safe_int(controlled_real_execution_requested.get("true")),
                "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
            },
        ),
        _check(
            "real_preflight_remains_blocked",
            _safe_int(real_preflight_statuses.get("blocked")) >= _safe_int(real_preflight_statuses.get("allowed")),
            dict(real_preflight_statuses),
        ),
        _check(
            "real_preflight_does_not_would_execute",
            _safe_int(real_preflight_would_execute.get("true")) == 0,
            _safe_int(real_preflight_would_execute.get("true")),
        ),
        _check(
            "real_preflight_does_not_execute",
            _safe_int(real_preflight_execution_performed.get("true")) == 0,
            _safe_int(real_preflight_execution_performed.get("true")),
        ),
        _check(
            "real_preflight_does_not_invoke_subprocess",
            _safe_int(real_preflight_subprocess_invoked.get("true")) == 0,
            _safe_int(real_preflight_subprocess_invoked.get("true")),
        ),
        _check(
            "real_preflight_requires_explicit_pr",
            _safe_int(real_preflight_requires_explicit_pr.get("true")) > 0
            or _safe_int(controlled_real_execution_requested.get("true")) == 0,
            _safe_int(real_preflight_requires_explicit_pr.get("true")),
        ),
    ]

    operator_authorized_count = _safe_int(operator_authorized.get("true"))
    if require_operator_authorized:
        checks.append(
            _check(
                "operator_authorized",
                operator_authorized_count > 0,
                operator_authorized_count,
            )
        )
    else:
        checks.append(
            _check(
                "operator_authorization_optional",
                True,
                operator_authorized_count,
            )
        )

    return checks


def _check(name: str, passed: bool, value: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "value": value,
    }


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_controlled_execution_readiness_report_schema(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the machine-readable readiness report contract."""
    required_fields = [
        "schema_version",
        "schema_kind",
        "type",
        "status",
        "ready_for_mock_execution",
        "ready_for_real_execution",
        "blocking_reasons",
        "adapter_contract_observed",
        "adapter_subprocess_invoked",
        "adapter_real_execution_enabled",
        "adapter_payload_executed",
        "checks",
        "exit_codes",
        "adapter_contract",
        "real_adapter_supported",
        "real_adapter_runnable",
        "real_adapter_requires_explicit_pr",
        "real_execution_request_observed",
        "real_execution_request_rejected",
    ]

    reasons: list[str] = []

    if report.get("schema_version") != READINESS_SCHEMA_VERSION:
        reasons.append("invalid_schema_version")
    if report.get("schema_kind") != "controlled_execution_readiness":
        reasons.append("invalid_schema_kind")
    if report.get("type") != "controlled_execution_readiness_report":
        reasons.append("invalid_report_type")
    if report.get("status") not in {"passed", "failed"}:
        reasons.append("invalid_status")

    for field in required_fields:
        if field not in report:
            reasons.append(f"missing_required_field:{field}")

    if not isinstance(report.get("ready_for_mock_execution"), bool):
        reasons.append("ready_for_mock_execution_must_be_bool")
    if not isinstance(report.get("ready_for_real_execution"), bool):
        reasons.append("ready_for_real_execution_must_be_bool")
    if report.get("ready_for_real_execution") is not False:
        reasons.append("ready_for_real_execution_must_remain_false")
    if not isinstance(report.get("blocking_reasons"), list):
        reasons.append("blocking_reasons_must_be_list")
    if not isinstance(report.get("checks"), list):
        reasons.append("checks_must_be_list")
    if not isinstance(report.get("exit_codes"), Mapping):
        reasons.append("exit_codes_must_be_mapping")

    for bool_field in (
        "adapter_contract_observed",
    ):
        if not isinstance(report.get(bool_field), bool):
            reasons.append(f"{bool_field}_must_be_bool")

    for int_field in (
        "adapter_subprocess_invoked",
        "adapter_real_execution_enabled",
        "adapter_payload_executed",
    ):
        if not isinstance(report.get(int_field), int):
            reasons.append(f"{int_field}_must_be_int")

    if report.get("real_adapter_requires_explicit_pr") is not True:
        reasons.append("real_adapter_requires_explicit_pr_must_remain_true")

    if not isinstance(report.get("adapter_contract"), Mapping):
        reasons.append("adapter_contract_must_be_mapping")
    if report.get("real_adapter_supported") is not False:
        reasons.append("real_adapter_supported_must_remain_false")
    if report.get("real_adapter_runnable") is not False:
        reasons.append("real_adapter_runnable_must_remain_false")

    if not isinstance(report.get("real_execution_request_observed"), bool):
        reasons.append("real_execution_request_observed_must_be_bool")
    if not isinstance(report.get("real_execution_request_rejected"), int):
        reasons.append("real_execution_request_rejected_must_be_int")

    if not isinstance(report.get("real_preflight_observed"), bool):
        reasons.append("real_preflight_observed_must_be_bool")
    if not isinstance(report.get("real_preflight_blocked"), int):
        reasons.append("real_preflight_blocked_must_be_int")

    return {
        "type": "controlled_execution_readiness_schema_validation",
        "valid": not reasons,
        "schema_version": report.get("schema_version"),
        "schema_kind": report.get("schema_kind"),
        "reasons": reasons,
    }


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def _format_result(result: Mapping[str, Any]) -> str:
    failed = result.get("blocking_reasons")
    blocking_reasons = failed if isinstance(failed, list) and failed else ["none"]

    return (
        "Controlled execution readiness: "
        f"status={result.get('status')} "
        f"schema_version={result.get('schema_version')} "
        f"ready_for_mock_execution="
        f"{str(bool(result.get('ready_for_mock_execution'))).lower()} "
        f"ready_for_real_execution="
        f"{str(bool(result.get('ready_for_real_execution'))).lower()} "
        f"require_operator_authorized="
        f"{str(bool(result.get('require_operator_authorized'))).lower()} "
        f"blocking_reasons={','.join(str(item) for item in blocking_reasons)} "
        f"mock_execution_observed="
        f"{str(bool(result.get('mock_execution_observed'))).lower()} "
        f"mock_execution_performed={result.get('mock_execution_performed', 0)} "
        f"mock_subprocess_invoked={result.get('mock_subprocess_invoked', 0)} "
        f"mock_execution_summary_observed={str(bool(result.get('mock_execution_summary_observed'))).lower()} "
        f"mock_execution_summary_performed={result.get('mock_execution_summary_performed', 0)} "
        f"mock_summary_subprocess_invoked={result.get('mock_summary_subprocess_invoked', 0)} "
        f"adapter_contract_observed="
        f"{str(bool(result.get('adapter_contract_observed'))).lower()} "
        f"adapter_mock={result.get('adapter_mock', 0)} "
        f"adapter_mode_mock={result.get('adapter_mode_mock', 0)} "
        f"adapter_result_mock_executed={result.get('adapter_result_mock_executed', 0)} "
        f"adapter_subprocess_invoked={result.get('adapter_subprocess_invoked', 0)} "
        f"adapter_real_execution_enabled={result.get('adapter_real_execution_enabled', 0)} "
        f"adapter_payload_executed={result.get('adapter_payload_executed', 0)} "
        f"real_adapter_supported="
        f"{str(bool(result.get('real_adapter_supported'))).lower()} "
        f"real_adapter_runnable="
        f"{str(bool(result.get('real_adapter_runnable'))).lower()} "
        f"real_adapter_requires_explicit_pr="
        f"{str(bool(result.get('real_adapter_requires_explicit_pr'))).lower()} "
        f"real_execution_request_observed="
        f"{str(bool(result.get('real_execution_request_observed'))).lower()} "
        f"real_execution_request_rejected={result.get('real_execution_request_rejected', 0)} "
        f"real_execution_requested={result.get('real_execution_requested', 0)} "
        f"real_execution_performed={result.get('real_execution_performed', 0)} "
        f"real_execution_supported_count={result.get('real_execution_supported_count', 0)} "
        f"subprocess_invoked_count={result.get('subprocess_invoked_count', 0)} "
        f"real_preflight_observed={str(bool(result.get('real_preflight_observed'))).lower()} "
        f"real_preflight_blocked={result.get('real_preflight_blocked', 0)} "
        f"real_preflight_would_execute={result.get('real_preflight_would_execute', 0)} "
        f"real_preflight_execution_performed={result.get('real_preflight_execution_performed', 0)} "
        f"real_preflight_subprocess_invoked={result.get('real_preflight_subprocess_invoked', 0)} "
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check controlled execution readiness before any execution adapter.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Retry governance proposal id filter.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Controlled rendered command id filter.",
    )
    parser.add_argument(
        "--require-operator-authorized",
        action="store_true",
        help="Require operator_authorized=true for mock execution readiness.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result.",
    )
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    result = check_controlled_execution_readiness(args)
    schema_validation = validate_controlled_execution_readiness_report_schema(result)
    result["schema_validation"] = schema_validation

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()