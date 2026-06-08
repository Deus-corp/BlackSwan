from src.testing.controlled_retry_mock_execution import (
    build_controlled_retry_mock_execution,
)


def _controlled_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-controlled-1",
        "plan_id": "plan-controlled-1",
        "proposal_id": "proposal-controlled-1",
        "approval_id": "approval-controlled-1",
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "operator_authorized": True,
        "allowlist_matched": True,
        "command_parse": {
            "valid": True,
            "allowlist_matched": True,
            "execution_performed": False,
        },
        "gate_evaluation": {
            "gate_status": "blocked",
            "would_execute": False,
            "execution_performed": False,
        },
        "payload": {
            "executed": False,
            "command_parse": {
                "valid": True,
                "allowlist_matched": True,
                "execution_performed": False,
            },
            "gate_evaluation": {
                "gate_status": "blocked",
                "would_execute": False,
                "execution_performed": False,
            },
        },
    }
    item.update(overrides)
    return item


def test_controlled_retry_mock_execution_performs_when_enabled_and_safe() -> None:
    result = build_controlled_retry_mock_execution(
        _controlled_result(),
        mock_execution_enabled=True,
        real_execution_enabled=False,
    )

    assert result["status"] == "mock_executed"
    assert result["reason"] == "mock_execution_completed"
    assert result["mock_execution"]["performed"] is True
    assert result["mock_execution"]["adapter"] == "mock"
    assert result["mock_execution"]["subprocess_invoked"] is False
    assert result["mock_execution"]["exit_code"] == 0
    assert result["payload"]["executed"] is False
    assert result["payload"]["mock_executed"] is True
    assert result["payload"]["subprocess_invoked"] is False


def test_controlled_retry_mock_execution_blocks_when_not_enabled() -> None:
    result = build_controlled_retry_mock_execution(
        _controlled_result(),
        mock_execution_enabled=False,
        real_execution_enabled=False,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "mock_execution_blocked"
    assert result["mock_execution"]["performed"] is False
    assert "mock_execution_not_enabled" in result["mock_execution"]["reasons"]
    assert result["payload"]["executed"] is False


def test_controlled_retry_mock_execution_blocks_when_real_execution_enabled() -> None:
    result = build_controlled_retry_mock_execution(
        _controlled_result(),
        mock_execution_enabled=True,
        real_execution_enabled=True,
    )

    assert result["status"] == "blocked"
    assert "real_execution_must_remain_disabled" in result["mock_execution"]["reasons"]
    assert result["mock_execution"]["subprocess_invoked"] is False


def test_controlled_retry_mock_execution_blocks_without_operator_authorization() -> None:
    result = build_controlled_retry_mock_execution(
        _controlled_result(operator_authorized=False),
        mock_execution_enabled=True,
        real_execution_enabled=False,
    )

    assert result["status"] == "blocked"
    assert "operator_authorization_missing" in result["mock_execution"]["reasons"]


def test_controlled_retry_mock_execution_blocks_if_payload_executed() -> None:
    result = build_controlled_retry_mock_execution(
        _controlled_result(payload={"executed": True}),
        mock_execution_enabled=True,
        real_execution_enabled=False,
    )

    assert result["status"] == "blocked"
    assert "payload_already_executed" in result["mock_execution"]["reasons"]
    assert result["payload"]["executed"] is False