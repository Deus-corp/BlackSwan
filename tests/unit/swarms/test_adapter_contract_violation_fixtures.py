from src.testing.check_controlled_execution_readiness import _build_checks


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


def _base_trail_summary(**overrides):
    item = {
        "chain_complete": True,
        "counts": {
            "controlled_execution_results": 1,
            "mock_execution_summaries": 1,
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


def _failed_check_names(trail_summary):
    checks = _build_checks(
        trail_summary=trail_summary,
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )
    return [item["name"] for item in checks if item["status"] != "passed"]


def test_adapter_contract_violation_fixture_subprocess_invoked_fails_readiness() -> None:
    failed = _failed_check_names(
        _base_trail_summary(
            controlled_mock_adapter_subprocess_invoked={"true": 1}
        )
    )

    assert "adapter_subprocess_not_invoked" in failed


def test_adapter_contract_violation_fixture_real_execution_enabled_fails_readiness() -> None:
    failed = _failed_check_names(
        _base_trail_summary(
            controlled_mock_adapter_real_execution_enabled={"true": 1}
        )
    )

    assert "adapter_real_execution_not_enabled" in failed


def test_adapter_contract_violation_fixture_payload_executed_fails_readiness() -> None:
    failed = _failed_check_names(
        _base_trail_summary(
            controlled_mock_adapter_payload_executed={"true": 1}
        )
    )

    assert "adapter_payload_not_executed" in failed


def test_adapter_contract_violation_fixture_real_adapter_fails_readiness() -> None:
    failed = _failed_check_names(
        _base_trail_summary(
            controlled_mock_adapter={"real": 1}
        )
    )

    assert "adapter_contract_observed" in failed
    assert "adapter_is_mock" in failed


def test_adapter_contract_violation_fixture_real_mode_fails_readiness() -> None:
    failed = _failed_check_names(
        _base_trail_summary(
            controlled_mock_adapter_mode={"real": 1}
        )
    )

    assert "adapter_contract_observed" in failed
    assert "adapter_mode_is_mock" in failed