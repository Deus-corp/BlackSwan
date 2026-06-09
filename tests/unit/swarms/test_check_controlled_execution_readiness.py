import argparse

from src.testing.check_controlled_execution_readiness import (
    _build_checks,
    _exit_code_for_result,
    _format_result,
)


def _trail_summary(**overrides):
    item = {
        "chain_complete": True,
        "counts": {
            "controlled_execution_results": 1,
        },
        "controlled_execution_result_statuses": {
            "rejected": 1,
        },
        "controlled_execution_result_reasons": {
            "controlled_execution_not_implemented": 1,
        },
        "controlled_command_parse_valid": {
            "true": 1,
        },
        "controlled_command_parse_allowlist_matched": {
            "true": 1,
        },
        "controlled_command_parse_execution_performed": {
            "false": 1,
        },
        "controlled_execution_operator_authorized": {
            "true": 1,
        },
        "controlled_gate_statuses": {
            "blocked": 1,
        },
        "controlled_gate_would_execute": {
            "false": 1,
        },
        "controlled_gate_execution_performed": {
            "false": 1,
        },
        "controlled_gate_reasons": {
            "controlled_execution_not_enabled": 1,
            "controlled_execution_implementation_not_enabled": 1,
        },
        "controlled_mock_statuses": {
            "mock_executed": 1,
        },
        "controlled_mock_performed": {
            "true": 1,
        },
        "controlled_mock_subprocess_invoked": {
            "false": 1,
        },
        "mock_summary_statuses": {
            "mock_executed": 1,
        },
        "mock_summary_performed": {
            "true": 1,
        },
        "mock_summary_subprocess_invoked": {
            "false": 1,
        },
        "controlled_mock_adapter": {
            "mock": 1,
        },
        "controlled_mock_adapter_mode": {
            "mock": 1,
        },
        "controlled_mock_adapter_result_statuses": {
            "mock_executed": 1,
        },
        "controlled_mock_adapter_subprocess_invoked": {
            "false": 1,
        },
        "controlled_mock_adapter_real_execution_enabled": {
            "false": 1,
        },
        "controlled_mock_adapter_payload_executed": {
            "false": 1,
        },
    }
    item.update(overrides)
    return item


def _retry_observability(**overrides):
    item = {
        "status": "passed",
    }
    item.update(overrides)
    return item


def _controlled_observability(**overrides):
    item = {
        "status": "passed",
        "controlled_execution_executed": 0,
        "controlled_execution_gate_execution_performed": 0,
    }
    item.update(overrides)
    return item


def test_controlled_execution_readiness_checks_pass_for_safe_pre_execution_stack() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    assert [item for item in checks if item["status"] != "passed"] == []


def test_controlled_execution_readiness_checks_fail_without_operator_when_required() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_execution_operator_authorized={"false": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert failed == ["operator_authorized"]


def test_controlled_execution_readiness_checks_allow_missing_operator_when_optional() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_execution_operator_authorized={"false": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=False,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert failed == []


def test_controlled_execution_readiness_checks_fail_when_gate_would_execute() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_gate_would_execute={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=False,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "controlled_gate_would_not_execute" in failed


def test_controlled_execution_readiness_checks_fail_when_observability_failed() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(),
        retry_observability=_retry_observability(status="failed"),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=False,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "retry_observability_passed" in failed


def test_controlled_execution_readiness_format_reports_mock_and_real_readiness() -> None:
    text = _format_result(
        {
            "status": "passed",
            "ready_for_mock_execution": True,
            "ready_for_real_execution": False,
            "require_operator_authorized": True,
            "blocking_reasons": ["real_execution_not_supported_yet"],
            "mock_execution_observed": True,
            "mock_execution_performed": 1,
            "mock_subprocess_invoked": 0,
            "adapter_contract_observed": True,
            "adapter_mock": 1,
            "adapter_mode_mock": 1,
            "adapter_result_mock_executed": 1,
            "adapter_subprocess_invoked": 0,
            "adapter_real_execution_enabled": 0,
            "adapter_payload_executed": 0,
        }
    )

    assert "status=passed" in text
    assert "ready_for_mock_execution=true" in text
    assert "ready_for_real_execution=false" in text
    assert "require_operator_authorized=true" in text
    assert "blocking_reasons=real_execution_not_supported_yet" in text
    assert "mock_execution_observed=true" in text
    assert "mock_execution_performed=1" in text
    assert "mock_subprocess_invoked=0" in text
    assert "adapter_contract_observed=true" in text
    assert "adapter_mock=1" in text
    assert "adapter_mode_mock=1" in text
    assert "adapter_result_mock_executed=1" in text
    assert "adapter_subprocess_invoked=0" in text
    assert "adapter_real_execution_enabled=0" in text
    assert "adapter_payload_executed=0" in text


def test_controlled_execution_readiness_exit_code() -> None:
    assert _exit_code_for_result({"status": "passed"}) == 0
    assert _exit_code_for_result({"status": "failed"}) == 1


def test_controlled_execution_readiness_checks_fail_when_mock_missing() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_statuses={},
            controlled_mock_performed={},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "mock_execution_observed" in failed
    assert "mock_execution_performed" in failed


def test_controlled_execution_readiness_checks_fail_when_mock_summary_missing() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            mock_summary_statuses={},
            mock_summary_performed={},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "mock_execution_summary_observed" in failed
    assert "mock_execution_summary_performed" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_contract_missing() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter={},
            controlled_mock_adapter_mode={},
            controlled_mock_adapter_result_statuses={},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_contract_observed" in failed
    assert "adapter_is_mock" in failed
    assert "adapter_mode_is_mock" in failed
    assert "adapter_result_mock_executed" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_subprocess_invoked={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_subprocess_not_invoked" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_payload_executed() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_payload_executed={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_payload_not_executed" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_real_execution_enabled() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_real_execution_enabled={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_real_execution_not_enabled" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_is_not_mock() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter={"real": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_contract_observed" in failed
    assert "adapter_is_mock" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_mode_is_not_mock() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_mode={"real": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_contract_observed" in failed
    assert "adapter_mode_is_mock" in failed