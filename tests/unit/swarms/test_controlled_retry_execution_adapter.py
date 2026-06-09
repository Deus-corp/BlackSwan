import pytest

from src.testing.controlled_retry_execution_adapter import (
    MockControlledRetryExecutionAdapter,
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
    with pytest.raises(ValueError, match="unsupported controlled retry execution adapter"):
        get_controlled_retry_execution_adapter("real")


def test_get_controlled_retry_execution_adapter_rejects_unknown_adapter() -> None:
    with pytest.raises(ValueError, match="unsupported controlled retry execution adapter"):
        get_controlled_retry_execution_adapter("subprocess")


def test_controlled_retry_execution_adapter_contract_documents_invariants() -> None:
    contract = describe_controlled_retry_execution_adapter_contract()

    assert contract["supported_adapters"] == ["mock"]
    assert contract["real_execution_supported"] is False
    assert contract["subprocess_supported"] is False
    assert contract["required_invariants"]["payload_executed"] is False
    assert contract["required_invariants"]["subprocess_invoked"] is False
    assert contract["required_invariants"]["real_execution_enabled"] is False