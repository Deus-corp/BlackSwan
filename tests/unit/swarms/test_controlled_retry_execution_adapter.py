import pytest

from src.testing.controlled_retry_execution_adapter import (
    MockControlledRetryExecutionAdapter,
    UnsupportedControlledRetryExecutionAdapter,
    UnsupportedRealControlledRetryExecutionAdapter,
    describe_controlled_retry_execution_adapter_contract,
    get_controlled_retry_execution_adapter,
)


def _controlled_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "timeout_profile": "standard",
        "payload": {
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def test_mock_controlled_retry_execution_adapter_never_invokes_subprocess() -> None:
    adapter = MockControlledRetryExecutionAdapter()

    result = adapter.run(_controlled_result())

    assert result["adapter"] == "mock"
    assert result["mode"] == "mock"
    assert result["status"] == "mock_executed"
    assert result["reason"] == "mock_execution_completed"
    assert result["subprocess_invoked"] is False
    assert result["real_execution_enabled"] is False
    assert result["payload"]["executed"] is False
    assert result["payload"]["mock_executed"] is True
    assert result["payload"]["subprocess_invoked"] is False


def test_get_controlled_retry_execution_adapter_returns_mock_adapter() -> None:
    adapter = get_controlled_retry_execution_adapter("mock")

    assert adapter.name == "mock"
    assert adapter.mode == "mock"


def test_get_controlled_retry_execution_adapter_rejects_real_adapter() -> None:
    with pytest.raises(
        UnsupportedControlledRetryExecutionAdapter,
        match="real execution adapter is not supported",
    ):
        get_controlled_retry_execution_adapter("real")


def test_get_controlled_retry_execution_adapter_rejects_unknown_adapter() -> None:
    with pytest.raises(
        UnsupportedControlledRetryExecutionAdapter,
        match="unsupported controlled retry execution adapter",
    ):
        get_controlled_retry_execution_adapter("subprocess")


def test_controlled_retry_execution_adapter_contract_documents_invariants() -> None:
    contract = describe_controlled_retry_execution_adapter_contract()

    assert contract["supported_adapters"] == ["mock"]
    assert contract["real_execution_supported"] is False
    assert contract["subprocess_supported"] is False
    assert contract["required_invariants"]["payload_executed"] is False
    assert contract["required_invariants"]["subprocess_invoked"] is False
    assert contract["required_invariants"]["real_execution_enabled"] is False
    assert contract["schema_version"] == "controlled-retry-execution-adapter/v1"
    assert contract["unsupported_adapters"] == ["real"]
    assert contract["placeholder_adapters"] == ["real"]
    assert contract["real_adapter_contract"]["supported"] is False
    assert contract["real_adapter_contract"]["runnable"] is False
    assert contract["real_adapter_contract"]["requires_explicit_pr"] is True
    assert (
        contract["real_adapter_contract"]["failure_reason"]
        == "controlled_retry_real_execution_adapter_not_supported"
    )


def test_unsupported_real_controlled_retry_execution_adapter_is_not_runnable() -> None:
    adapter = UnsupportedRealControlledRetryExecutionAdapter()

    assert adapter.name == "real"
    assert adapter.mode == "real"
    assert adapter.supported is False
    assert adapter.real_execution_supported is False
    assert adapter.subprocess_supported is False

    with pytest.raises(
        UnsupportedControlledRetryExecutionAdapter,
        match="real execution adapter is not supported",
    ):
        adapter.run(_controlled_result())