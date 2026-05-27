import pytest

from src.memory.contracts import MemoryQuery, MemoryStats
from src.memory.local_memory import LocalMemoryAPI, MemoryRecord


@pytest.mark.asyncio
async def test_local_memory_recall_with_memory_query() -> None:
    memory = LocalMemoryAPI(node_id="node-a")

    record_id = await memory.remember(
        MemoryRecord(
            kind="fact",
            scope="own",
            topic="architecture",
            payload={
                "subject": "BlackSwan",
                "predicate": "is",
                "object": "multi-swarm platform",
                "tags": ["project", "architecture"],
            },
            source={"originNodeId": "node-a", "swarm": "memory", "parents": []},
            verified=True,
        )
    )

    results = await memory.recall(
        MemoryQuery(
            kind="fact",
            scope="own",
            owner_node_id="node-a",
            swarm="memory",
            tags=["architecture"],
            text="multi-swarm",
            limit=10,
        )
    )

    assert [item.id for item in results] == [record_id]


@pytest.mark.asyncio
async def test_local_memory_stats_returns_canonical_stats() -> None:
    memory = LocalMemoryAPI(node_id="node-a")

    await memory.remember(
        MemoryRecord(
            kind="event",
            scope="local",
            payload={"message": "started"},
            verified=True,
        )
    )
    await memory.remember(
        MemoryRecord(
            kind="policy",
            scope="shared",
            payload={"name": "safe-mode", "actions": ["PAUSE"]},
        )
    )

    stats = await memory.stats()

    assert isinstance(stats, MemoryStats)
    assert stats.total_records == 2
    assert stats.by_kind["event"] == 1
    assert stats.by_kind["policy"] == 1
    assert stats.by_scope["local"] == 1
    assert stats.by_scope["shared"] == 1
    assert stats.verified_records == 1
    assert stats.backend == "local"
    assert stats.details["node_id"] == "node-a"