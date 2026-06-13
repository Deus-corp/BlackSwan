import json

from src.testing.check_controlled_execution_readiness import (
    READINESS_SCHEMA_VERSION,
    validate_controlled_execution_readiness_report_schema,
)


def _report(**overrides):
    item = {
        "type": "controlled_execution_readiness_report",
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "real_adapter_requires_explicit_pr": True,
        "real_execution_request_observed": False,
        "real_execution_request_rejected": 0,
        "real_preflight_observed": True,
        "real_preflight_blocked": 1,
        "real_approval_observed": True,
        "real_approval_records": 1,
        "real_linkage_complete": True,
        "real_preflight_orphans": 0,
        "real_approval_orphans": 0,
        "real_approval_transition_observed": True,
        "real_approval_transition_records": 1,
        "real_approval_latest_status": "approved",
        "real_approval_transition_enabled": 0,
        "real_approval_transition_subprocess_enabled": 0,
        "real_approval_transition_execution_performed": 0,
        "real_approval_transition_subprocess_invoked": 0,
        "real_final_gate_observed": True,
        "real_final_gate_blocked": 1,
        "real_dry_run_envelope_observed": True,
        "real_dry_run_envelope_records": 1,
        "real_dry_run_linkage_complete": True,
        "real_dry_run_envelope_orphans": 0,
        "real_noop_result_observed": True,
        "real_noop_result_records": 1,
        "real_noop_linkage_complete": True,
        "real_noop_result_orphans": 0,
        "real_noop_result_stdout_marker_observed": 1,
        "real_read_only_promotion_observed": True,
        "real_read_only_promotion_records": 1,
        "real_read_only_promotion_linkage_complete": True,
        "real_read_only_promotion_orphans": 0,
        "real_read_only_final_gate_observed": True,
        "real_read_only_final_gate_records": 1,
        "real_read_only_final_gate_linkage_complete": True,
        "real_read_only_final_gate_orphans": 0,
        "real_read_only_approval_observed": True,
        "real_read_only_approval_records": 1,
        "real_read_only_approval_linkage_complete": True,
        "real_read_only_approval_orphans": 0,
        "real_read_only_approval_transition_observed": True,
        "real_read_only_approval_transition_records": 1,
        "real_read_only_approval_transition_linkage_complete": True,
        "real_read_only_approval_transition_orphans": 0,
        "real_read_only_approval_latest_status": "approved",
        "real_read_only_readiness_gate_observed": True,
        "real_read_only_readiness_gate_records": 1,
        "real_read_only_readiness_gate_linkage_complete": True,
        "real_read_only_readiness_gate_orphans": 0,
        "real_read_only_execution_result_observed": True,
        "real_read_only_execution_result_records": 1,
        "real_read_only_execution_result_linkage_complete": True,
        "real_read_only_execution_result_orphans": 0,
        "real_read_only_feedback_observed": True,
        "real_read_only_feedback_records": 1,
        "real_read_only_feedback_linkage_complete": True,
        "real_read_only_feedback_orphans": 0,
        "real_read_only_repair_plan_observed": True,
        "real_read_only_repair_plan_records": 1,
        "real_read_only_repair_plan_linkage_complete": True,
        "real_read_only_repair_plan_orphans": 0,
        "real_read_only_repair_action_bundle_observed": True,
        "real_read_only_repair_action_bundle_records": 1,
        "real_read_only_repair_action_bundle_linkage_complete": True,
        "real_read_only_repair_action_bundle_orphans": 0,
        "real_read_only_repair_action_bundle_review_observed": True,
        "real_read_only_repair_action_bundle_review_records": 1,
        "real_read_only_repair_action_bundle_review_linkage_complete": True,
        "real_read_only_repair_action_bundle_review_orphans": 0,
        "real_repair_approval_observed": True,
        "real_repair_approval_records": 1,
        "real_repair_approval_linkage_complete": True,
        "real_repair_approval_orphans": 0,
        "real_repair_approval_transition_observed": True,
        "real_repair_approval_transition_records": 1,
        "real_repair_approval_transition_linkage_complete": True,
        "real_repair_approval_transition_orphans": 0,
        "adapter_contract": {
            "type": "controlled_retry_execution_adapter_contract",
            "schema_version": "controlled-retry-execution-adapter/v1",
            "supported_adapters": ["mock"],
            "unsupported_adapters": ["real"],
            "placeholder_adapters": ["real"],
            "real_execution_supported": False,
            "subprocess_supported": False,
            "real_adapter_contract": {
                "name": "real",
                "mode": "real",
                "supported": False,
                "runnable": False,
                "requires_explicit_pr": True,
                "failure_reason": "controlled_retry_real_execution_adapter_not_supported",
            },
        },
        "real_adapter_supported": False,
        "real_adapter_runnable": False,
        "status": "passed",
        "ready_for_mock_execution": True,
        "ready_for_real_execution": False,
        "blocking_reasons": ["real_execution_not_supported_yet"],
        "adapter_contract_observed": True,
        "adapter_subprocess_invoked": 0,
        "adapter_real_execution_enabled": 0,
        "adapter_payload_executed": 0,
        "checks": [],
        "exit_codes": {
            "trail": 0,
            "retry_observability": 0,
            "controlled_observability": 0,
            "real_execution": 1,
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
            "real_approval_observed",
            "real_approval_records",
            "real_linkage_complete",
            "real_preflight_orphans",
            "real_approval_orphans",
            "real_approval_transition_observed",
            "real_approval_transition_records",
            "real_approval_latest_status",
            "real_final_gate_observed",
            "real_final_gate_blocked",
            "real_dry_run_envelope_observed",
            "real_dry_run_envelope_records",
            "real_dry_run_linkage_complete",
            "real_dry_run_envelope_orphans",
            "real_noop_result_observed",
            "real_noop_result_records",
            "real_noop_linkage_complete",
            "real_noop_result_orphans",
            "real_noop_result_stdout_marker_observed",
            "real_read_only_promotion_observed",
            "real_read_only_promotion_records",
            "real_read_only_promotion_linkage_complete",
            "real_read_only_promotion_orphans",
            "real_read_only_final_gate_observed",
            "real_read_only_final_gate_records",
            "real_read_only_final_gate_linkage_complete",
            "real_read_only_final_gate_orphans",
            "real_read_only_approval_observed",
            "real_read_only_approval_records",
            "real_read_only_approval_linkage_complete",
            "real_read_only_approval_orphans",
            "real_read_only_approval_transition_observed",
            "real_read_only_approval_transition_records",
            "real_read_only_approval_transition_linkage_complete",
            "real_read_only_approval_transition_orphans",
            "real_read_only_approval_latest_status",
            "real_read_only_readiness_gate_observed",
            "real_read_only_readiness_gate_records",
            "real_read_only_readiness_gate_linkage_complete",
            "real_read_only_readiness_gate_orphans",
            "real_read_only_execution_result_observed",
            "real_read_only_execution_result_records",
            "real_read_only_execution_result_linkage_complete",
            "real_read_only_execution_result_orphans",
            "real_read_only_feedback_observed",
            "real_read_only_feedback_records",
            "real_read_only_feedback_linkage_complete",
            "real_read_only_feedback_orphans",
            "real_read_only_repair_plan_observed",
            "real_read_only_repair_plan_records",
            "real_read_only_repair_plan_linkage_complete",
            "real_read_only_repair_plan_orphans",
            "real_read_only_repair_action_bundle_observed",
            "real_read_only_repair_action_bundle_records",
            "real_read_only_repair_action_bundle_linkage_complete",
            "real_read_only_repair_action_bundle_orphans",
            "real_read_only_repair_action_bundle_review_observed",
            "real_read_only_repair_action_bundle_review_records",
            "real_read_only_repair_action_bundle_review_linkage_complete",
            "real_read_only_repair_action_bundle_review_orphans",
            "real_repair_approval_observed",
            "real_repair_approval_records",
            "real_repair_approval_linkage_complete",
            "real_repair_approval_orphans",
            "real_repair_approval_transition_observed",
            "real_repair_approval_transition_records",
            "real_repair_approval_transition_linkage_complete",
            "real_repair_approval_transition_orphans",
        ],
    }
    item.update(overrides)
    return item


def test_validate_controlled_execution_readiness_report_schema_accepts_contract() -> None:
    result = validate_controlled_execution_readiness_report_schema(_report())

    assert result["valid"] is True
    assert result["schema_version"] == READINESS_SCHEMA_VERSION
    assert result["reasons"] == []


def test_validate_controlled_execution_readiness_report_schema_rejects_missing_field() -> None:
    report = _report()
    report.pop("adapter_contract_observed")

    result = validate_controlled_execution_readiness_report_schema(report)

    assert result["valid"] is False
    assert "missing_required_field:adapter_contract_observed" in result["reasons"]
    assert "adapter_contract_observed_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_real_execution_true() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(ready_for_real_execution=True)
    )

    assert result["valid"] is False
    assert "ready_for_real_execution_must_remain_false" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_adapter_counts() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(adapter_subprocess_invoked="0")
    )

    assert result["valid"] is False
    assert "adapter_subprocess_invoked_must_be_int" in result["reasons"]


def test_controlled_execution_readiness_schema_required_fields_snapshot() -> None:
    report = _report()

    result = validate_controlled_execution_readiness_report_schema(report)

    assert result["valid"] is True
    assert sorted(report["required_fields"]) == sorted(
        [
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
            "adapter_contract",
            "real_adapter_supported",
            "real_adapter_runnable",
            "real_adapter_requires_explicit_pr",
            "real_execution_request_observed",
            "real_execution_request_rejected",
            "real_preflight_observed",
            "real_preflight_blocked",
            "real_approval_observed",
            "real_approval_records",
            "real_linkage_complete",
            "real_preflight_orphans",
            "real_approval_orphans",
            "real_approval_transition_observed",
            "real_approval_transition_records",
            "real_approval_latest_status",
            "real_final_gate_observed",
            "real_final_gate_blocked",
            "real_dry_run_envelope_observed",
            "real_dry_run_envelope_records",
            "real_dry_run_linkage_complete",
            "real_dry_run_envelope_orphans",
            "real_noop_result_observed",
            "real_noop_result_records",
            "real_noop_linkage_complete",
            "real_noop_result_orphans",
            "real_noop_result_stdout_marker_observed",
            "real_read_only_promotion_observed",
            "real_read_only_promotion_records",
            "real_read_only_promotion_linkage_complete",
            "real_read_only_promotion_orphans",
            "real_read_only_final_gate_observed",
            "real_read_only_final_gate_records",
            "real_read_only_final_gate_linkage_complete",
            "real_read_only_final_gate_orphans",
            "real_read_only_approval_observed",
            "real_read_only_approval_records",
            "real_read_only_approval_linkage_complete",
            "real_read_only_approval_orphans",
            "real_read_only_approval_transition_observed",
            "real_read_only_approval_transition_records",
            "real_read_only_approval_transition_linkage_complete",
            "real_read_only_approval_transition_orphans",
            "real_read_only_approval_latest_status",
            "real_read_only_readiness_gate_observed",
            "real_read_only_readiness_gate_records",
            "real_read_only_readiness_gate_linkage_complete",
            "real_read_only_readiness_gate_orphans",
            "real_read_only_execution_result_observed",
            "real_read_only_execution_result_records",
            "real_read_only_execution_result_linkage_complete",
            "real_read_only_execution_result_orphans",
            "real_read_only_feedback_observed",
            "real_read_only_feedback_records",
            "real_read_only_feedback_linkage_complete",
            "real_read_only_feedback_orphans",
            "real_read_only_repair_plan_observed",
            "real_read_only_repair_plan_records",
            "real_read_only_repair_plan_linkage_complete",
            "real_read_only_repair_plan_orphans",
            "real_read_only_repair_action_bundle_observed",
            "real_read_only_repair_action_bundle_records",
            "real_read_only_repair_action_bundle_linkage_complete",
            "real_read_only_repair_action_bundle_orphans",
            "real_read_only_repair_action_bundle_review_observed",
            "real_read_only_repair_action_bundle_review_records",
            "real_read_only_repair_action_bundle_review_linkage_complete",
            "real_read_only_repair_action_bundle_review_orphans",
            "real_repair_approval_observed",
            "real_repair_approval_records",
            "real_repair_approval_linkage_complete",
            "real_repair_approval_orphans",
            "real_repair_approval_transition_observed",
            "real_repair_approval_transition_records",
            "real_repair_approval_transition_linkage_complete",
            "real_repair_approval_transition_orphans",
            "checks",
            "exit_codes",
        ]
    )


def test_validate_controlled_execution_readiness_report_schema_rejects_missing_checks() -> None:
    report = _report()
    report.pop("checks")

    result = validate_controlled_execution_readiness_report_schema(report)

    assert result["valid"] is False
    assert "missing_required_field:checks" in result["reasons"]
    assert "checks_must_be_list" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_missing_exit_codes() -> None:
    report = _report()
    report.pop("exit_codes")

    result = validate_controlled_execution_readiness_report_schema(report)

    assert result["valid"] is False
    assert "missing_required_field:exit_codes" in result["reasons"]
    assert "exit_codes_must_be_mapping" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_schema_version() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(schema_version="controlled-execution-readiness/v0")
    )

    assert result["valid"] is False
    assert "invalid_schema_version" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_schema_kind() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(schema_kind="other")
    )

    assert result["valid"] is False
    assert "invalid_schema_kind" in result["reasons"]


def test_controlled_execution_readiness_report_schema_snapshot_is_json_serializable() -> None:
    report = _report()

    payload = json.loads(json.dumps(report, sort_keys=True))

    assert payload["schema_version"] == READINESS_SCHEMA_VERSION
    assert payload["ready_for_mock_execution"] is True
    assert payload["ready_for_real_execution"] is False
    assert payload["adapter_contract_observed"] is True
    assert payload["adapter_subprocess_invoked"] == 0
    assert payload["adapter_real_execution_enabled"] == 0
    assert payload["adapter_payload_executed"] == 0


def test_validate_controlled_execution_readiness_report_schema_rejects_real_adapter_supported() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_adapter_supported=True)
    )

    assert result["valid"] is False
    assert "real_adapter_supported_must_remain_false" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_real_adapter_runnable() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_adapter_runnable=True)
    )

    assert result["valid"] is False
    assert "real_adapter_runnable_must_remain_false" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_missing_adapter_contract() -> None:
    report = _report()
    report.pop("adapter_contract")

    result = validate_controlled_execution_readiness_report_schema(report)

    assert result["valid"] is False
    assert "missing_required_field:adapter_contract" in result["reasons"]
    assert "adapter_contract_must_be_mapping" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_real_adapter_without_explicit_pr_requirement() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_adapter_requires_explicit_pr=False)
    )

    assert result["valid"] is False
    assert "real_adapter_requires_explicit_pr_must_remain_true" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_request_observed_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_execution_request_observed="false")
    )

    assert result["valid"] is False
    assert "real_execution_request_observed_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_request_rejected_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_execution_request_rejected="0")
    )

    assert result["valid"] is False
    assert "real_execution_request_rejected_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_preflight_observed_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_preflight_observed="true")
    )

    assert result["valid"] is False
    assert "real_preflight_observed_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_preflight_blocked_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_preflight_blocked="1")
    )

    assert result["valid"] is False
    assert "real_preflight_blocked_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_approval_observed_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_approval_observed="true")
    )

    assert result["valid"] is False
    assert "real_approval_observed_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_approval_records_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_approval_records="1")
    )

    assert result["valid"] is False
    assert "real_approval_records_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_linkage_complete_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_linkage_complete="true")
    )

    assert result["valid"] is False
    assert "real_linkage_complete_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_preflight_orphans_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_preflight_orphans="0")
    )

    assert result["valid"] is False
    assert "real_preflight_orphans_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_approval_orphans_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_approval_orphans="0")
    )

    assert result["valid"] is False
    assert "real_approval_orphans_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_dry_run_linkage_complete_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_dry_run_linkage_complete="true")
    )

    assert result["valid"] is False
    assert "real_dry_run_linkage_complete_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_dry_run_envelope_orphans_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_dry_run_envelope_orphans="0")
    )

    assert result["valid"] is False
    assert "real_dry_run_envelope_orphans_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_noop_linkage_complete_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_noop_linkage_complete="true")
    )

    assert result["valid"] is False
    assert "real_noop_linkage_complete_must_be_bool" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_noop_result_orphans_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_noop_result_orphans="0")
    )

    assert result["valid"] is False
    assert "real_noop_result_orphans_must_be_int" in result["reasons"]


def test_validate_controlled_execution_readiness_report_schema_rejects_bad_real_noop_stdout_marker_type() -> None:
    result = validate_controlled_execution_readiness_report_schema(
        _report(real_noop_result_stdout_marker_observed="1")
    )

    assert result["valid"] is False
    assert "real_noop_result_stdout_marker_observed_must_be_int" in result["reasons"]