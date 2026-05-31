import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.publish_replay_scenarios import publish_replay_scenarios


def _memory_record(directive_id: str = "runtime-reduce-risk-1", status: str = "passed") -> dict:
    return {
        "type": "memory_record",
        "memory_id": f"memory-evidence-{directive_id}",
        "kind": "runtime_evidence",
        "status": status,
        "subject": "runtime_directive_seed_check",
        "source": "evidence-memory-bridge",
        "payload": {
            "evidence_id": f"ev-{directive_id}",
            "directive_id": directive_id,
            "checks": [
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_result_published", "status": "passed"},
                {"name": "directive_applied", "status": "passed"},
            ],
            "evidence_payload": {
                "directive": {
                    "directive_id": directive_id,
                    "action": "REDUCE_RISK",
                    "target_type": "swarm",
                    "target": "trade",
                    "status": "issued",
                },
                "result": {
                    "directive_id": directive_id,
                    "status": "applied",
                    "source": "trade-1",
                    "swarm": "trade",
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_publish_replay_scenarios_writes_scenario_to_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_memory_record())

    args = argparse.Namespace(
        source="test-replay-builder",
        db_path=db_path,
        directive_id="",
    )

    scenarios = await publish_replay_scenarios(args)

    assert len(scenarios) == 1
    assert scenarios[0]["type"] == "simulation_replay_scenario"
    assert scenarios[0]["directive_id"] == "runtime-reduce-risk-1"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    replay_records = [
        item
        for item in state.values()
        if isinstance(item, dict) and item.get("type") == "simulation_replay_scenario"
    ]

    assert len(replay_records) == 1
    assert replay_records[0]["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert replay_records[0]["source"] == "test-replay-builder"


@pytest.mark.asyncio
async def test_publish_replay_scenarios_filters_by_directive_id(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_memory_record("dir-1"))
    await crdt.add_genome(_memory_record("dir-2"))

    args = argparse.Namespace(
        source="test-replay-builder",
        db_path=db_path,
        directive_id="dir-2",
    )

    scenarios = await publish_replay_scenarios(args)

    assert len(scenarios) == 1
    assert scenarios[0]["directive_id"] == "dir-2"


@pytest.mark.asyncio
async def test_publish_replay_scenarios_skips_failed_runtime_evidence(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_memory_record(status="failed"))

    args = argparse.Namespace(
        source="test-replay-builder",
        db_path=db_path,
        directive_id="",
    )

    scenarios = await publish_replay_scenarios(args)

    assert scenarios == []