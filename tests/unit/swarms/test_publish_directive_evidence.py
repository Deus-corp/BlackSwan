import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.publish_directive_evidence import publish_directive_evidence


@pytest.mark.asyncio
async def test_publish_directive_evidence_writes_evidence_record(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(
        {
            "type": "swarm_directive",
            "directive_id": "dir-1",
            "action": "REDUCE_RISK",
            "source": "overseer-seed",
            "target_type": "swarm",
            "target": "trade",
            "status": "issued",
        }
    )
    await crdt.add_genome(
        {
            "type": "swarm_directive_result",
            "directive_id": "dir-1",
            "status": "applied",
            "source": "trade-1",
            "swarm": "trade",
            "node_id": "trade-1",
            "message": "Trade risk reduced.",
        }
    )

    args = argparse.Namespace(
        directive_id="dir-1",
        source="test-evidence",
        db_path=db_path,
    )

    evidence = await publish_directive_evidence(args)

    assert evidence["type"] == "evidence_record"
    assert evidence["subject"] == "runtime_directive_seed_check"
    assert evidence["status"] == "passed"
    assert evidence["confidence"] == 1.0

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    evidence_records = [
        item for item in state.values()
        if isinstance(item, dict) and item.get("type") == "evidence_record"
    ]

    assert len(evidence_records) == 1
    assert evidence_records[0]["status"] == "passed"
    assert evidence_records[0]["payload"]["directive_id"] == "dir-1"


@pytest.mark.asyncio
async def test_publish_directive_evidence_fails_without_result_but_still_publishes(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(
        {
            "type": "swarm_directive",
            "directive_id": "dir-missing-result",
            "action": "REDUCE_RISK",
            "source": "overseer-seed",
            "target_type": "swarm",
            "target": "trade",
            "status": "issued",
        }
    )

    args = argparse.Namespace(
        directive_id="dir-missing-result",
        source="test-evidence",
        db_path=db_path,
    )

    evidence = await publish_directive_evidence(args)

    assert evidence["type"] == "evidence_record"
    assert evidence["status"] == "failed"
    assert evidence["confidence"] == 0.0
    assert [check["status"] for check in evidence["checks"]] == ["passed", "failed", "failed"]


@pytest.mark.asyncio
async def test_publish_directive_evidence_rejects_empty_directive_id(tmp_path) -> None:
    args = argparse.Namespace(
        directive_id="",
        source="test-evidence",
        db_path=str(tmp_path / "crdt.db"),
    )

    with pytest.raises(ValueError, match="directive_id"):
        await publish_directive_evidence(args)