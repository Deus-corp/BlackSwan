import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.evidence_memory_bridge import (
    build_memory_record_for_directive_evidence,
    build_memory_record_from_evidence,
    find_directive_evidence,
    publish_memory_record_for_directive_evidence,
    publish_evidence_memory_records,
)


def _evidence_record(*, evidence_id: str = "ev-1", directive_id: str = "dir-1", status: str = "passed"):
    return {
        "type": "evidence_record",
        "evidence_id": evidence_id,
        "subject": "runtime_directive_seed_check",
        "source": "manual-runtime-check",
        "status": status,
        "confidence": 1.0 if status == "passed" else 0.0,
        "checks": [
            {"name": "directive_seeded", "status": "passed", "value": True},
            {"name": "directive_result_published", "status": status, "value": status == "passed"},
        ],
        "payload": {
            "directive_id": directive_id,
            "directive": {"action": "REDUCE_RISK"},
            "result": {"status": "applied"} if status == "passed" else {},
        },
        "created_at": 10.0,
    }


def test_build_memory_record_from_evidence() -> None:
    evidence = _evidence_record()

    record = build_memory_record_from_evidence(evidence, source="test-bridge")

    assert record["type"] == "memory_record"
    assert record["memory_id"] == "memory-evidence-ev-1"
    assert record["source"] == "test-bridge"
    assert record["scope"] == "global"
    assert record["kind"] == "runtime_evidence"
    assert record["status"] == "passed"
    assert record["subject"] == "runtime_directive_seed_check"
    assert record["importance"] == 0.85
    assert "runtime_evidence" in record["tags"]
    assert "directive:dir-1" in record["tags"]
    assert record["payload"]["evidence_id"] == "ev-1"
    assert record["payload"]["directive_id"] == "dir-1"


def test_find_directive_evidence_returns_latest_match() -> None:
    old = _evidence_record(evidence_id="old", directive_id="dir-1")
    old["created_at"] = 1.0

    new = _evidence_record(evidence_id="new", directive_id="dir-1")
    new["created_at"] = 2.0

    state = {"old": old, "new": new}

    assert find_directive_evidence(directive_id="dir-1", crdt_state=state)["evidence_id"] == "new"


def test_build_memory_record_for_directive_evidence() -> None:
    state = {"ev": _evidence_record(directive_id="dir-1")}

    record = build_memory_record_for_directive_evidence(
        directive_id="dir-1",
        crdt_state=state,
        source="test-bridge",
    )

    assert record["type"] == "memory_record"
    assert record["payload"]["directive_id"] == "dir-1"


def test_build_memory_record_for_directive_evidence_rejects_missing_evidence() -> None:
    with pytest.raises(ValueError, match="No evidence_record"):
        build_memory_record_for_directive_evidence(
            directive_id="missing",
            crdt_state={},
        )


def test_build_memory_record_from_evidence_rejects_wrong_type() -> None:
    with pytest.raises(ValueError, match="evidence_record"):
        build_memory_record_from_evidence({"type": "memory_record", "evidence_id": "ev"})


@pytest.mark.asyncio
async def test_publish_memory_record_for_directive_evidence(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_evidence_record(directive_id="dir-1"))

    args = argparse.Namespace(
        directive_id="dir-1",
        source="test-bridge",
        db_path=db_path,
    )

    record = await publish_memory_record_for_directive_evidence(args)

    assert record["type"] == "memory_record"
    assert record["payload"]["directive_id"] == "dir-1"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    records = [
        item for item in state.values()
        if isinstance(item, dict) and item.get("type") == "memory_record"
    ]

    assert len(records) == 1
    assert records[0]["kind"] == "runtime_evidence"
    assert records[0]["payload"]["evidence_id"] == "ev-1"

def _replay_execution_evidence() -> dict:
    return {
        "type": "evidence_record",
        "evidence_id": "evidence-exec-replay-runtime-reduce-risk-1",
        "subject": "simulation_replay_execution_check",
        "status": "passed",
        "confidence": 1.0,
        "source": "replay-evidence-publisher",
        "scenario_id": "replay-runtime-reduce-risk-1",
        "directive_id": "runtime-run-replay-evidence-1",
        "execution_id": "exec-replay-runtime-reduce-risk-1",
        "payload": {
            "scenario_id": "replay-runtime-reduce-risk-1",
            "directive_id": "runtime-run-replay-evidence-1",
            "execution_id": "exec-replay-runtime-reduce-risk-1",
            "checks": [
                {
                    "name": "replay_execution_completed",
                    "status": "passed",
                    "value": "completed",
                }
            ],
        },
    }

def test_build_memory_record_from_replay_execution_evidence_preserves_replay_fields() -> None:
    record = build_memory_record_from_evidence(
        _replay_execution_evidence(),
        source="evidence-memory-bridge",
    )

    assert record["type"] == "memory_record"
    assert record["kind"] == "runtime_evidence"
    assert record["subject"] == "simulation_replay_execution_check"
    assert record["status"] == "passed"
    assert record["source"] == "evidence-memory-bridge"

    payload = record["payload"]
    assert payload["subject"] == "simulation_replay_execution_check"
    assert payload["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert payload["directive_id"] == "runtime-run-replay-evidence-1"
    assert payload["execution_id"] == "exec-replay-runtime-reduce-risk-1"
    assert payload["checks"][0]["name"] == "replay_execution_completed"

    assert "subject:simulation_replay_execution_check" in record["tags"]
    assert "status:passed" in record["tags"]

@pytest.mark.asyncio
async def test_evidence_memory_bridge_publishes_replay_execution_memory_record(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_replay_execution_evidence())

    args = argparse.Namespace(
        source="evidence-memory-bridge",
        db_path=db_path,
        directive_id="",
        evidence_id="",
        subject="simulation_replay_execution_check",
    )

    records = await publish_evidence_memory_records(args)

    assert len(records) == 1
    assert records[0]["subject"] == "simulation_replay_execution_check"
    assert records[0]["payload"]["scenario_id"] == "replay-runtime-reduce-risk-1"