from src.memory import MemoryEnvelope, MemoryIdentity, MemoryQuery, MemoryStats


def test_memory_envelope_to_dict_and_expiration() -> None:
    owner = MemoryIdentity(node_id="node-a", swarm="memory", role="node")
    envelope = MemoryEnvelope(
        id="mem-1",
        kind="event",
        scope="own",
        owner=owner,
        payload={"x": 1},
        tags=["test"],
        ttl_seconds=10.0,
    )

    data = envelope.to_dict()

    assert data["id"] == "mem-1"
    assert data["kind"] == "event"
    assert data["scope"] == "own"
    assert data["owner"]["node_id"] == "node-a"
    assert data["payload"]["x"] == 1
    assert envelope.is_expired(now=envelope.created_at + 11.0)


def test_memory_query_defaults() -> None:
    query = MemoryQuery()

    assert query.scope is None
    assert query.kind is None
    assert query.limit == 50
    assert query.tags == []
    assert not query.include_expired


def test_memory_stats_to_dict() -> None:
    stats = MemoryStats(
        total_records=3,
        by_scope={"own": 2, "shared": 1},
        by_kind={"event": 1, "fact": 2},
        verified_records=1,
        backend="local",
    )

    data = stats.to_dict()

    assert data["total_records"] == 3
    assert data["by_scope"]["own"] == 2
    assert data["backend"] == "local"