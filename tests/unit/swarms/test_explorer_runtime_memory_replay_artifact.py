from __future__ import annotations

from src.testing.check_memory_evidence_query_contract import (
    validate_memory_evidence_query_contract,
)
from src.testing.replay_explorer_memory_evidence_query import (
    extract_explorer_memory_records_from_payload,
    replay_explorer_memory_evidence_query,
)
from src.testing.run_explorer_network_read_loop import (
    _build_memory_replay_artifact,
)


def _memory_record(index: int = 1, **overrides):
    record = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": f"runtime-replay-artifact-{index}",
        "url": f"https://docs.python.org/3/library/asyncio-{index}.html",
        "domain": "docs.python.org",
        "content_preview": (
            "Python asyncio documentation evidence about event loops, tasks, "
            "concurrency, autonomous agents, and memory systems."
        ),
        "content_hash": f"hash-runtime-replay-artifact-{index}",
        "source_score": 0.86,
        "quality_score": 0.86,
        "system_relevance_score": 0.82,
        "authority_score": 0.85,
        "freshness_score": 0.60,
        "topic_tags": ["asyncio", "agents", "memory"],
        "evidence_category": "python_docs",
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "semantic_retrieval_enabled": False,
        "embedding_status": "not_computed",
        "embedding_model": "",
        "embedding_dim": 0,
        "embedding_hash": "",
        "embedding_vector_ref": "",
        "embedding_updated_at": 0.0,
        "provenance": {
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }
    record.update(overrides)
    return record


def test_build_memory_replay_artifact_extracts_meta_agent_records() -> None:
    tick_results = [
        {
            "tick": 1,
            "meta_agent": {
                "memory_records_published": 1,
                "memory_records": [_memory_record()],
            },
        }
    ]

    artifact = _build_memory_replay_artifact(tick_results, limit=20)

    assert artifact["type"] == "explorer_memory_replay_artifact"
    assert artifact["record_count"] == 1
    assert artifact["available_record_count"] == 1
    assert artifact["truncated"] is False
    assert artifact["external_write_performed"] is False
    assert artifact["real_execution_enabled"] is False

    record = artifact["records"][0]

    assert record["record_kind"] == "explorer_useful_evidence"
    assert record["semantic_retrieval_enabled"] is False
    assert record["embedding_status"] == "not_computed"


def test_memory_replay_artifact_is_bounded() -> None:
    tick_results = [
        {
            "meta_agent": {
                "memory_records": [
                    _memory_record(1),
                    _memory_record(2),
                    _memory_record(3),
                ]
            }
        }
    ]

    artifact = _build_memory_replay_artifact(tick_results, limit=2)

    assert artifact["record_count"] == 2
    assert artifact["available_record_count"] == 3
    assert artifact["truncated"] is True
    assert len(artifact["records"]) == 2


def test_memory_replay_artifact_can_be_replayed_into_query_contract() -> None:
    runtime_result = {
        "type": "explorer_network_read_loop_result",
        "memory_replay_artifact": _build_memory_replay_artifact(
            [
                {
                    "meta_agent": {
                        "memory_records": [_memory_record()],
                    }
                }
            ],
            limit=20,
        ),
    }

    records = extract_explorer_memory_records_from_payload(runtime_result)

    assert len(records) == 1

    replay_result = replay_explorer_memory_evidence_query(
        records,
        text_query="asyncio agents",
        limit=5,
    )

    assert replay_result["explorer_memory_records_seen"] == 1
    assert replay_result["explorer_memory_records_replayed"] == 1
    assert replay_result["result_count"] == 1
    assert validate_memory_evidence_query_contract(replay_result) == []


def test_empty_memory_replay_artifact_is_contract_safe() -> None:
    artifact = _build_memory_replay_artifact([], limit=20)

    assert artifact["record_count"] == 0
    assert artifact["available_record_count"] == 0
    assert artifact["truncated"] is False
    assert artifact["records"] == []
    assert artifact["external_write_performed"] is False
    assert artifact["real_execution_enabled"] is False
    assert artifact["production_paths_mutated"] is False
    assert artifact["production_secrets_accessed"] is False


def test_memory_replay_artifact_flattens_wrapped_memory_record() -> None:
    wrapped_record = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "id": "wrapped-memory-record-1",
        "kind": "evidence",
        "payload": {
            "candidate_kind": "explorer_useful_evidence",
            "source_record_gid": "wrapped-memory-record-1",
            "url": "https://docs.github.com/en/search-github/searching-on-github/searching-code",
            "domain": "docs.github.com",
            "content_preview": (
                "Searching Code Explorer useful evidence candidate. URL: "
                "https://docs.github.com/en/search-github/searching-on-github/searching-code"
            ),
            "content_hash": "hash-wrapped-memory-record-1",
            "source_score": 1.0,
            "quality_score": 1.0,
            "system_relevance_score": 0.8,
            "authority_score": 0.79,
            "freshness_score": 0.5,
            "topic_tags": ["github", "search"],
            "evidence_category": "explorer_useful_evidence",
            "provenance": {
                "record_kind": "explorer_useful_evidence",
                "url": "https://docs.github.com/en/search-github/searching-on-github/searching-code",
                "content_hash": "hash-wrapped-memory-record-1",
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
            },
        },
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    artifact = _build_memory_replay_artifact(
        [
            {
                "meta_agent": {
                    "memory_records": [wrapped_record],
                }
            }
        ],
        limit=20,
    )

    assert artifact["record_count"] == 1

    record = artifact["records"][0]

    assert record["type"] == "memory_record"
    assert record["record_kind"] == "explorer_useful_evidence"
    assert (
        record["url"]
        == "https://docs.github.com/en/search-github/searching-on-github/searching-code"
    )
    assert record["content_hash"] == "hash-wrapped-memory-record-1"
    assert record["content_preview"]
    assert record["semantic_retrieval_enabled"] is False
    assert record["embedding_status"] == "not_computed"
    assert record["external_write_performed"] is False
    assert record["real_execution_enabled"] is False