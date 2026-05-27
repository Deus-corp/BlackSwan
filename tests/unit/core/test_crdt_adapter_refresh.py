import pytest

from src.core.crdt_adapter import CRDTAdapter


@pytest.mark.asyncio
async def test_crdt_adapter_refresh_from_shared_storage(tmp_path) -> None:
    db_path = tmp_path / "shared_crdt.sqlite3"

    writer = CRDTAdapter(node_id="writer", db_path=str(db_path))
    reader = CRDTAdapter(node_id="reader", db_path=str(db_path))

    assert reader.state == {}

    await writer.add_genome(
        {
            "type": "memory_record",
            "id": "mem-1",
            "kind": "event",
            "scope": "shared",
            "payload": {"message": "hello"},
            "source": {
                "originNodeId": "writer",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
        }
    )

    assert reader.state == {}

    refreshed = reader.refresh_from_storage()

    assert refreshed >= 1
    assert any(payload.get("type") == "memory_record" for payload in reader.state.values())