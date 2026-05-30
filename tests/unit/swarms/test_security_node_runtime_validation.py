from src.swarms.security.node import SecurityNode


class DummyCRDT:
    def __init__(self) -> None:
        self.state = {
            "dir-good": {
                "type": "swarm_directive",
                "directive_id": "dir-good",
                "action": "OBSERVE",
                "source": "overseer",
                "target_type": "swarm",
                "target": "memory",
                "payload": {},
            },
            "dir-bad": {
                "type": "swarm_directive",
                "directive_id": "dir-bad",
                "action": "ENABLE_LIVE_TRADING",
                "source": "overseer",
                "target_type": "swarm",
                "target": "trade",
                "payload": {},
            },
        }


def test_security_node_heartbeat_reports_runtime_validation_metrics() -> None:
    node = make_security_node()
    node.crdt = DummyCRDT()

    heartbeat = node.build_heartbeat()
    metrics = heartbeat["metrics"]

    assert metrics["security_validation_enabled"] is True
    assert metrics["security_validation_records"] == 2
    assert metrics["security_validation_valid_records"] == 1
    assert metrics["security_validation_invalid_records"] == 1
    assert metrics["security_validation_critical_records"] == 1
    assert metrics["security_validation_invalid_reasons"]["unsafe_or_unknown_action"] == 1

def make_security_node() -> SecurityNode:
    try:
        return SecurityNode(node_id="security-test")
    except TypeError:
        node = SecurityNode()
        node.node_id = "security-test"
        return node