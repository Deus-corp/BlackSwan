from src.testing.directive_evidence import build_directive_runtime_evidence


def test_build_directive_runtime_evidence_passes_when_directive_applied() -> None:
    state = {
        "dir": {
            "type": "swarm_directive",
            "directive_id": "runtime-reduce-risk-1",
            "action": "REDUCE_RISK",
            "source": "overseer-seed",
            "target_type": "swarm",
            "target": "trade",
            "status": "issued",
        },
        "res": {
            "type": "swarm_directive_result",
            "directive_id": "runtime-reduce-risk-1",
            "status": "applied",
            "source": "trade-1",
            "swarm": "trade",
            "node_id": "trade-1",
            "message": "Trade risk reduced.",
        },
    }

    evidence = build_directive_runtime_evidence(
        directive_id="runtime-reduce-risk-1",
        crdt_state=state,
        source="test",
    )

    assert evidence["type"] == "evidence_record"
    assert evidence["subject"] == "runtime_directive_seed_check"
    assert evidence["source"] == "test"
    assert evidence["status"] == "passed"
    assert evidence["confidence"] == 1.0
    assert evidence["payload"]["directive"]["action"] == "REDUCE_RISK"
    assert evidence["payload"]["result"]["status"] == "applied"
    assert [check["status"] for check in evidence["checks"]] == ["passed", "passed", "passed"]


def test_build_directive_runtime_evidence_fails_without_result() -> None:
    state = {
        "dir": {
            "type": "swarm_directive",
            "directive_id": "runtime-reduce-risk-1",
            "action": "REDUCE_RISK",
            "source": "overseer-seed",
            "target_type": "swarm",
            "target": "trade",
            "status": "issued",
        }
    }

    evidence = build_directive_runtime_evidence(
        directive_id="runtime-reduce-risk-1",
        crdt_state=state,
    )

    assert evidence["status"] == "failed"
    assert evidence["confidence"] == 0.0
    assert [check["status"] for check in evidence["checks"]] == ["passed", "failed", "failed"]


def test_build_directive_runtime_evidence_fails_without_directive() -> None:
    state = {}

    evidence = build_directive_runtime_evidence(
        directive_id="runtime-reduce-risk-1",
        crdt_state=state,
    )

    assert evidence["status"] == "failed"
    assert evidence["payload"]["directive"] == {}
    assert evidence["payload"]["result"] == {}