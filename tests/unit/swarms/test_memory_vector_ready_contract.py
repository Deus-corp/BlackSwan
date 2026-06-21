from __future__ import annotations

from src.swarms.memory.catalog import (
    build_memory_evidence_catalog_from_memory_records,
    query_memory_evidence_catalog,
)
from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    memory_record_from_ingest_candidate,
)
from src.swarms.memory.vector_contract import (
    memory_vector_ready_defaults,
    normalize_memory_vector_ready_fields,
)


def _explorer_evidence_record(**overrides):
    record = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": "memory-vector-ready-1",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "Python asyncio documentation evidence about event loops, tasks, "
            "concurrency, orchestration, and autonomous agent runtime systems."
        ),
        "content_hash": "hash-memory-vector-ready-1",
        "source_score": 0.86,
        "quality_score": 0.86,
        "system_relevance_score": 0.80,
        "authority_score": 0.85,
        "freshness_score": 0.60,
        "topic_tags": ["asyncio", "agents", "memory"],
        "evidence_category": "python_docs",
        "summary": "Asyncio docs evidence for autonomous agent runtime memory systems.",
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "provenance": {
            "exploration_run_id": "run-memory-vector-ready",
            "research_goal_id": "run-memory-vector-ready",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }
    record.update(overrides)
    return record


def test_memory_vector_ready_defaults_are_schema_only() -> None:
    defaults = memory_vector_ready_defaults()

    assert defaults == {
        "semantic_retrieval_enabled": False,
        "embedding_status": "not_computed",
        "embedding_model": "",
        "embedding_dim": 0,
        "embedding_hash": "",
        "embedding_vector_ref": "",
        "embedding_updated_at": 0.0,
    }


def test_normalize_memory_vector_ready_fields_disables_semantic_retrieval() -> None:
    fields = normalize_memory_vector_ready_fields(
        {
            "semantic_retrieval_enabled": True,
            "embedding_status": "computed",
            "embedding_model": "test-model",
            "embedding_dim": "384",
            "embedding_hash": "abc123",
            "embedding_vector_ref": "vector://abc123",
            "embedding_updated_at": "123.5",
        }
    )

    assert fields["semantic_retrieval_enabled"] is False
    assert fields["embedding_status"] == "computed"
    assert fields["embedding_model"] == "test-model"
    assert fields["embedding_dim"] == 384
    assert fields["embedding_hash"] == "abc123"
    assert fields["embedding_vector_ref"] == "vector://abc123"
    assert fields["embedding_updated_at"] == 123.5


def test_ingest_candidate_includes_vector_ready_defaults() -> None:
    candidate = build_memory_ingest_candidate(_explorer_evidence_record())

    assert candidate["semantic_retrieval_enabled"] is False
    assert candidate["embedding_status"] == "not_computed"
    assert candidate["embedding_model"] == ""
    assert candidate["embedding_dim"] == 0
    assert candidate["embedding_hash"] == ""
    assert candidate["embedding_vector_ref"] == ""
    assert candidate["embedding_updated_at"] == 0.0


def test_memory_record_preserves_vector_ready_fields_from_candidate() -> None:
    candidate = build_memory_ingest_candidate(
        _explorer_evidence_record(
            embedding_status="pending",
            embedding_model="future-embedder",
            embedding_dim=768,
            embedding_hash="hash-embedding",
            embedding_vector_ref="vector://future",
            embedding_updated_at=456.0,
        )
    )

    memory_record = memory_record_from_ingest_candidate(candidate)

    assert memory_record["semantic_retrieval_enabled"] is False
    assert memory_record["embedding_status"] == "pending"
    assert memory_record["embedding_model"] == "future-embedder"
    assert memory_record["embedding_dim"] == 768
    assert memory_record["embedding_hash"] == "hash-embedding"
    assert memory_record["embedding_vector_ref"] == "vector://future"
    assert memory_record["embedding_updated_at"] == 456.0


def test_catalog_item_preserves_vector_ready_fields() -> None:
    candidate = build_memory_ingest_candidate(
        _explorer_evidence_record(
            embedding_status="failed",
            embedding_model="future-embedder",
            embedding_dim=384,
            embedding_hash="embedding-hash",
            embedding_vector_ref="",
            embedding_updated_at=789.0,
        )
    )
    memory_record = memory_record_from_ingest_candidate(candidate)

    catalog = build_memory_evidence_catalog_from_memory_records([memory_record])

    assert catalog["type"] == "memory_evidence_catalog"
    assert catalog["item_count"] == 1

    item = catalog["items"][0]

    assert item["semantic_retrieval_enabled"] is False
    assert item["embedding_status"] == "failed"
    assert item["embedding_model"] == "future-embedder"
    assert item["embedding_dim"] == 384
    assert item["embedding_hash"] == "embedding-hash"
    assert item["embedding_vector_ref"] == ""
    assert item["embedding_updated_at"] == 789.0


def test_catalog_query_returns_vector_ready_fields() -> None:
    candidate = build_memory_ingest_candidate(_explorer_evidence_record())
    memory_record = memory_record_from_ingest_candidate(candidate)
    catalog = build_memory_evidence_catalog_from_memory_records([memory_record])

    result = query_memory_evidence_catalog(
        catalog,
        text_query="asyncio agents",
        limit=5,
    )

    assert result["type"] == "memory_evidence_query_result"
    assert result["result_count"] == 1

    item = result["results"][0]

    assert item["semantic_retrieval_enabled"] is False
    assert item["embedding_status"] == "not_computed"
    assert item["embedding_model"] == ""
    assert item["embedding_dim"] == 0
    assert item["embedding_hash"] == ""
    assert item["embedding_vector_ref"] == ""
    assert item["embedding_updated_at"] == 0.0


def test_vector_ready_contract_keeps_safety_flags_false() -> None:
    candidate = build_memory_ingest_candidate(_explorer_evidence_record())
    memory_record = memory_record_from_ingest_candidate(candidate)
    catalog = build_memory_evidence_catalog_from_memory_records([memory_record])
    result = query_memory_evidence_catalog(catalog, text_query="asyncio", limit=5)

    for payload in [candidate, memory_record, catalog, result]:
        assert payload.get("external_write_performed") is False
        assert payload.get("real_execution_enabled") is False
        assert payload.get("production_paths_mutated") is False
        assert payload.get("production_secrets_accessed") is False