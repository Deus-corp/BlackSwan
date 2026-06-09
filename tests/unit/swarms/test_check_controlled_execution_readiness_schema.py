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