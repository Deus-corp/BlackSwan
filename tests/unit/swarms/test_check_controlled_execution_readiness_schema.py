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