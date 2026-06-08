from src.testing.controlled_retry_execution_gate import (
    evaluate_controlled_retry_execution_gate,
)


def _controlled_result(**overrides):
    item = {
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "execution_enabled": False,
        "operator_authorized": True,
        "allowlist_matched": True,
        "readiness_score": 100,
        "command_parse": {
            "valid": True,
            "allowlist_matched": True,
            "execution_performed": False,
        },
        "payload": {
            "executed": False,
            "command_parse": {
                "valid": True,
                "allowlist_matched": True,
                "execution_performed": False,
            },
        },
    }
    item.update(overrides)
    return item


def test_controlled_retry_execution_gate_blocks_when_global_gate_disabled() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(),
        controlled_execution_enabled=False,
        implementation_enabled=False,
    )

    assert result["gate_status"] == "blocked"
    assert result["would_execute"] is False
    assert result["would_execute_if_enabled"] is False
    assert "controlled_execution_not_enabled" in result["reasons"]
    assert "controlled_execution_implementation_not_enabled" in result["reasons"]
    assert result["execution_performed"] is False


def test_controlled_retry_execution_gate_reports_ready_if_all_gates_enabled() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(),
        controlled_execution_enabled=True,
        implementation_enabled=True,
    )

    assert result["gate_status"] == "ready"
    assert result["would_execute"] is False
    assert result["would_execute_if_enabled"] is True
    assert result["reasons"] == []
    assert result["execution_performed"] is False


def test_controlled_retry_execution_gate_blocks_without_operator_authorization() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(operator_authorized=False),
        controlled_execution_enabled=True,
        implementation_enabled=True,
    )

    assert result["gate_status"] == "blocked"
    assert result["would_execute"] is False
    assert "operator_authorization_missing" in result["reasons"]


def test_controlled_retry_execution_gate_blocks_when_command_parse_invalid() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(
            command_parse={
                "valid": False,
                "allowlist_matched": False,
                "execution_performed": False,
            },
            payload={
                "executed": False,
                "command_parse": {
                    "valid": False,
                    "allowlist_matched": False,
                    "execution_performed": False,
                },
            },
        ),
        controlled_execution_enabled=True,
        implementation_enabled=True,
    )

    assert result["gate_status"] == "blocked"
    assert "command_parse_invalid" in result["reasons"]
    assert "command_parse_allowlist_not_matched" in result["reasons"]


def test_controlled_retry_execution_gate_blocks_when_parse_performed_execution() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(
            command_parse={
                "valid": True,
                "allowlist_matched": True,
                "execution_performed": True,
            },
            payload={
                "executed": False,
                "command_parse": {
                    "valid": True,
                    "allowlist_matched": True,
                    "execution_performed": True,
                },
            },
        ),
        controlled_execution_enabled=True,
        implementation_enabled=True,
    )

    assert result["gate_status"] == "blocked"
    assert "command_parse_already_performed_execution" in result["reasons"]


def test_controlled_retry_execution_gate_blocks_when_payload_executed() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(payload={"executed": True}),
        controlled_execution_enabled=True,
        implementation_enabled=True,
    )

    assert result["gate_status"] == "blocked"
    assert "payload_already_executed" in result["reasons"]


def test_controlled_retry_execution_gate_blocks_below_readiness_threshold() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(readiness_score=99),
        controlled_execution_enabled=True,
        implementation_enabled=True,
        min_readiness_score=100,
    )

    assert result["gate_status"] == "blocked"
    assert "readiness_score_below_threshold" in result["reasons"]


def test_controlled_retry_execution_gate_blocks_unexpected_result_status() -> None:
    result = evaluate_controlled_retry_execution_gate(
        controlled_result=_controlled_result(status="executed"),
        controlled_execution_enabled=True,
        implementation_enabled=True,
    )

    assert result["gate_status"] == "blocked"
    assert "controlled_result_not_rejected" in result["reasons"]