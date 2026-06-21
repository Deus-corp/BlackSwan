from __future__ import annotations

from src.swarms.memory.catalog import (
    build_memory_evidence_catalog_from_memory_records,
    query_memory_evidence_catalog,
)
from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    memory_record_from_ingest_candidate,
)
from src.swarms.memory.retrieval_contract import (
    MEMORY_RETRIEVAL_CONTRACT_VERSION,
    deterministic_candidate_summary,
    memory_retrieval_contract_defaults,
)


def _explorer_evidence_record(**overrides):
    record = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": "memory-retrieval-contract-1",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "Python asyncio documentation evidence about event loops, tasks, "
            "concurrency, orchestration, and autonomous agent runtime systems."
        ),
        "content_hash": "hash-memory-retrieval-contract-1",
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
            "exploration_run_id": "run-memory-retrieval-contract",
            "research_goal_id": "run-memory-retrieval-contract",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }
    record.update(overrides)
    return record


def _query_result():
    candidate = build_memory_ingest_candidate(_explorer_evidence_record())
    memory_record = memory_record_from_ingest_candidate(candidate)
    catalog = build_memory_evidence_catalog_from_memory_records([memory_record])

    return query_memory_evidence_catalog(
        catalog,
        text_query="asyncio agents",
        limit=5,
    )


def test_memory_retrieval_contract_defaults_are_deterministic_only() -> None:
    defaults = memory_retrieval_contract_defaults()

    assert defaults == {
        "retrieval_contract_version": MEMORY_RETRIEVAL_CONTRACT_VERSION,
        "retrieval_mode": "deterministic",
        "hybrid_retrieval_enabled": False,
        "semantic_retrieval_enabled": False,
        "semantic_candidates": [],
    }


def test_query_result_declares_deterministic_retrieval_mode() -> None:
    result = _query_result()

    assert result["type"] == "memory_evidence_query_result"
    assert result["retrieval_contract_version"] == MEMORY_RETRIEVAL_CONTRACT_VERSION
    assert result["retrieval_mode"] == "deterministic"
    assert result["hybrid_retrieval_enabled"] is False
    assert result["semantic_retrieval_enabled"] is False
    assert result["semantic_candidates"] == []


def test_query_result_includes_deterministic_candidate_summary() -> None:
    result = _query_result()

    assert result["result_count"] == 1
    assert result["deterministic_candidate_count"] == 1

    candidate = result["deterministic_candidates"][0]

    assert candidate["rank"] == 1
    assert candidate["url"] == "https://docs.python.org/3/library/asyncio.html"
    assert candidate["domain"] == "docs.python.org"
    assert candidate["retrieval_path"] == "deterministic_catalog_query"
    assert candidate["ranking_score"] > 0.0
    assert candidate["source_score"] > 0.0
    assert candidate["system_relevance_score"] > 0.0


def test_deterministic_candidate_summary_is_compact() -> None:
    summary = deterministic_candidate_summary(
        [
            {
                "url": "https://example.com/a",
                "domain": "example.com",
                "dedupe_key": "dedupe-a",
                "ranking_score": 0.9,
                "source_score": 0.8,
                "system_relevance_score": 0.7,
                "content_preview": "should not be copied into compact telemetry",
            }
        ]
    )

    assert summary == [
        {
            "rank": 1,
            "url": "https://example.com/a",
            "domain": "example.com",
            "dedupe_key": "dedupe-a",
            "ranking_score": 0.9,
            "source_score": 0.8,
            "system_relevance_score": 0.7,
            "retrieval_path": "deterministic_catalog_query",
        }
    ]


def test_empty_query_result_still_declares_retrieval_contract() -> None:
    catalog = {
        "type": "memory_evidence_catalog",
        "catalog_status": "indexed",
        "item_count": 0,
        "items": [],
        "top_items": [],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    result = query_memory_evidence_catalog(
        catalog,
        text_query="missing",
        limit=5,
    )

    assert result["result_count"] == 0
    assert result["retrieval_mode"] == "deterministic"
    assert result["hybrid_retrieval_enabled"] is False
    assert result["semantic_candidates"] == []
    assert result["deterministic_candidates"] == []
    assert result["deterministic_candidate_count"] == 0


def test_retrieval_contract_keeps_safety_flags_false() -> None:
    result = _query_result()

    assert result["external_write_performed"] is False
    assert result["real_execution_enabled"] is False
    assert result["production_paths_mutated"] is False
    assert result["production_secrets_accessed"] is False