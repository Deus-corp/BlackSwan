import pytest
import sqlite3
from src.core.crdt_layer import CRDTStorage
from src.core.crdt_layer import CRDTRecord

class FakeOp:
    op_id = "bad-op"
    node_id = '{"payload": "wrong"}'
    clock = 1
    kind = "memory-1"
    gid = "0"
    payload = {"bad": True}
    ts = 1.0


def test_crdt_storage_rejects_invalid_operation_kind(tmp_path) -> None:
    storage = CRDTStorage(tmp_path / "crdt.db")

    with pytest.raises((TypeError, ValueError), match="CRDTOperation|operation kind"):
        storage.save_op(FakeOp())  # type: ignore[arg-type]

class FakeRecord:
    gid = "bad-record"
    payload = "not-a-dict"
    clock = 1
    node_id = "node-1"
    deleted = False
    ts = 1.0


def test_crdt_storage_rejects_invalid_record_type(tmp_path) -> None:
    storage = CRDTStorage(tmp_path / "crdt.db")

    with pytest.raises(TypeError, match="CRDTRecord"):
        storage.save_record(FakeRecord())  # type: ignore[arg-type]

def test_crdt_storage_saves_valid_record(tmp_path) -> None:
    storage = CRDTStorage(tmp_path / "crdt.db")
    record = CRDTRecord(
        gid="record-1",
        payload={"type": "test"},
        clock=1,
        node_id="node-1",
        deleted=False,
        ts=1.0,
    )

    storage.save_record(record)
    records = storage.load_records()

    assert "record-1" in records
    assert records["record-1"].payload["type"] == "test"

def test_crdt_storage_rejects_non_sqlite_file(tmp_path) -> None:
    db_path = tmp_path / "crdt.db"
    db_path.write_text("not a sqlite database", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError, match="not a SQLite database"):
        CRDTStorage(db_path)

def test_crdt_storage_has_process_lock_path(tmp_path) -> None:
    storage = CRDTStorage(tmp_path / "crdt.db")

    assert storage.process_lock_path.name == "crdt.db.lock"

def test_crdt_storage_uses_delete_journal_mode(tmp_path) -> None:
    storage = CRDTStorage(tmp_path / "crdt.db")

    with storage._connect() as conn:  # noqa: SLF001
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]

    assert str(journal_mode).lower() == "delete"
    assert int(synchronous) == 2  # FULL