import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.publish_replay_execution_evidence import publish_replay_execution_evidence


def _execution(status: str = "completed") -> dict:
    return {
        "type": "simulation_replay_execution",
        "execution_id": "exec-replay-runtime-reduce-risk-1",
        "scenario_id": "replay-runtime-reduce-risk-1",
        "directive_id": "runtime-run-replay-exec-1",
        "source": "simulation-1",
        "status": status,
        "dry_run": True,
        "action": "REDUCE_RISK",
        "expected_result_status": "applied",
    }


@pytest.mark.asyncio
async def test_publish_replay_execution_evidence_writes_passed_evidence_to_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_execution())

    args = argparse.Namespace(
        source="replay-evidence-test",
        db_path=db_path,
        scenario_id="",
        directive_id="",
    )

    records = await publish_replay_execution_evidence(args)

    assert len(records) == 1
    evidence = records[0]
    assert evidence["type"] == "evidence_record"
    assert evidence["subject"] == "simulation_replay_execution_check"
    assert evidence["status"] == "passed"
    assert evidence["confidence"] == 1.0
    assert evidence["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert evidence["directive_id"] == "runtime-run-replay-exec-1"
    assert evidence["payload"]["checks"][1]["name"] == "replay_execution_completed"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    evidence_records = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "evidence_record"
        and item.get("subject") == "simulation_replay_execution_check"
    ]

    assert len(evidence_records) == 1
    assert evidence_records[0]["source"] == "replay-evidence-test"


@pytest.mark.asyncio
async def test_publish_replay_execution_evidence_filters_by_scenario_id(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_execution())
    other = _execution()
    other["execution_id"] = "exec-other"
    other["scenario_id"] = "replay-other"
    await crdt.add_genome(other)

    args = argparse.Namespace(
        source="replay-evidence-test",
        db_path=db_path,
        scenario_id="replay-runtime-reduce-risk-1",
        directive_id="",
    )

    records = await publish_replay_execution_evidence(args)

    assert len(records) == 1
    assert records[0]["scenario_id"] == "replay-runtime-reduce-risk-1"


@pytest.mark.asyncio
async def test_publish_replay_execution_evidence_marks_failed_execution_as_failed(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_execution(status="failed"))

    args = argparse.Namespace(
        source="replay-evidence-test",
        db_path=db_path,
        scenario_id="",
        directive_id="",
    )

    records = await publish_replay_execution_evidence(args)

    assert len(records) == 1
    assert records[0]["status"] == "failed"
    assert records[0]["confidence"] == 0.0
    assert records[0]["payload"]["checks"][1]["status"] == "failed"