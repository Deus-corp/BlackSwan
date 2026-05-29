from src.swarms.trade.node_core.commands import (
    command_action,
    command_applies_to_node,
    command_has_explicit_approval,
    command_value,
)


def test_trade_command_value_prefers_payload() -> None:
    command = {
        "action": "PAUSE",
        "payload": {
            "action": "RESUME",
            "approved": True,
        },
    }

    assert command_value(command, "action") == "RESUME"
    assert command_value(command, "missing", "fallback") == "fallback"


def test_trade_command_action_normalizes_payload_action() -> None:
    command = {
        "payload": {
            "action": " pause ",
        },
    }

    assert command_action(command) == "PAUSE"


def test_trade_command_has_explicit_approval() -> None:
    assert command_has_explicit_approval({"payload": {"explicit_approval": True}}) is True
    assert command_has_explicit_approval({"payload": {"approved": True}}) is True
    assert command_has_explicit_approval({"payload": {"approval": "approved"}}) is True
    assert command_has_explicit_approval({"payload": {"authorized": "yes"}}) is True
    assert command_has_explicit_approval({"payload": {"safety_gate": "approved"}}) is True
    assert command_has_explicit_approval({"payload": {"approved": False}}) is False
    assert command_has_explicit_approval({}) is False


def test_trade_command_applies_to_node_or_swarm() -> None:
    assert command_applies_to_node({"target": "trade"}, node_id="trade-1") is True
    assert command_applies_to_node({"target_swarm": "trade"}, node_id="trade-1") is True
    assert command_applies_to_node({"target": "trade-1"}, node_id="trade-1") is True
    assert command_applies_to_node({"targets": ["memory", "trade"]}, node_id="trade-1") is True
    assert command_applies_to_node({"target": "memory"}, node_id="trade-1") is False