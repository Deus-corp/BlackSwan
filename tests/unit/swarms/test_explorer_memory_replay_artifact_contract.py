from __future__ import annotations

from src.testing.check_explorer_source_planned_evidence_loop import (
    _validate_memory_replay_artifact_contract,
)

from tests.unit.swarms.fixtures_memory_replay import (
    memory_replay_artifact_fixture,
    memory_replay_record_fixture,
)


def _record(**overrides):
    return memory_replay_record_fixture(**overrides)


def _artifact(records=None, **overrides):
    return memory_replay_artifact_fixture(records=records, **overrides)


def _validate(result: dict) -> list[str]:
    errors: list[str] = []
    _validate_memory_replay_artifact_contract(result, errors)
    return errors


def test_memory_replay_artifact_contract_accepts_valid_artifact() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(),
    }

    assert _validate(result) == []


def test_memory_replay_artifact_required_when_memory_records_published() -> None:
    result = {
        "total_memory_records_published": 1,
    }

    errors = _validate(result)

    assert any("memory replay artifact is required" in error for error in errors)


def test_memory_replay_artifact_rejects_empty_records_when_memory_published() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(records=[]),
    }

    errors = _validate(result)

    assert any("must include replayable records" in error for error in errors)


def test_memory_replay_artifact_accepts_empty_when_no_memory_published() -> None:
    result = {
        "total_memory_records_published": 0,
        "memory_replay_artifact": _artifact(records=[]),
    }

    assert _validate(result) == []


def test_memory_replay_artifact_rejects_record_count_mismatch() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(record_count=2),
    }

    errors = _validate(result)

    assert any("record_count must equal len(records)" in error for error in errors)


def test_memory_replay_artifact_rejects_unsafe_artifact_flag() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(external_write_performed=True),
    }

    errors = _validate(result)

    assert any("unsafe flag is true" in error for error in errors)


def test_memory_replay_artifact_rejects_invalid_record_kind() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(
            records=[_record(record_kind="other")]
        ),
    }

    errors = _validate(result)

    assert any("record_kind must be explorer_useful_evidence" in error for error in errors)


def test_memory_replay_artifact_rejects_semantic_retrieval_enabled() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(
            records=[_record(semantic_retrieval_enabled=True)]
        ),
    }

    errors = _validate(result)

    assert any("semantic_retrieval_enabled must be false" in error for error in errors)


def test_memory_replay_artifact_rejects_bad_embedding_status() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(
            records=[_record(embedding_status="enabled")]
        ),
    }

    errors = _validate(result)

    assert any("invalid embedding_status" in error for error in errors)


def test_memory_replay_artifact_rejects_truncated_inconsistency() -> None:
    result = {
        "total_memory_records_published": 1,
        "memory_replay_artifact": _artifact(truncated=True),
    }

    errors = _validate(result)

    assert any("truncated=true requires" in error for error in errors)