from __future__ import annotations

import pytest

from src.testing.check_memory_evidence_query_contract import (
    assert_memory_evidence_query_contract,
    validate_memory_evidence_query_contract,
)


def _valid_result() -> dict:
    return {
        "type": "memory_evidence_query_result",
        "retrieval_contract_version": "memory_retrieval_v0_1",
        "retrieval_mode": "deterministic",
        "hybrid_retrieval_enabled": False,
        "semantic_retrieval_enabled": False,
        "semantic_candidates": [],
        "deterministic_candidates": [
            {
                "rank": 1,
                "url": "https://docs.python.org/3/library/asyncio.html",
                "domain": "docs.python.org",
                "dedupe_key": "dedupe-1",
                "ranking_score": 0.85,
                "source_score": 0.86,
                "system_relevance_score": 0.80,
                "retrieval_path": "deterministic_catalog_query",
            }
        ],
        "deterministic_candidate_count": 1,
        "embedding_status": "not_computed",
        "embedding_model": "",
        "embedding_dim": 0,
        "embedding_hash": "",
        "embedding_vector_ref": "",
        "embedding_updated_at": 0.0,
        "query": {
            "text_query": "asyncio agents",
            "limit": 5,
            "domain": "",
            "evidence_category": "",
            "topic_tags": [],
            "min_ranking_score": 0.0,
        },
        "catalog_item_count": 1,
        "matched_count": 1,
        "result_count": 1,
        "results": [
            {
                "type": "memory_evidence_catalog_item",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "domain": "docs.python.org",
                "ranking_score": 0.85,
                "source_score": 0.86,
                "system_relevance_score": 0.80,
                "semantic_retrieval_enabled": False,
                "embedding_status": "not_computed",
                "embedding_model": "",
                "embedding_dim": 0,
                "embedding_hash": "",
                "embedding_vector_ref": "",
                "embedding_updated_at": 0.0,
            }
        ],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def test_memory_query_contract_accepts_valid_result() -> None:
    assert validate_memory_evidence_query_contract(_valid_result()) == []


def test_memory_query_contract_rejects_hybrid_enabled() -> None:
    result = _valid_result()
    result["hybrid_retrieval_enabled"] = True

    errors = validate_memory_evidence_query_contract(result)

    assert any("hybrid_retrieval_enabled must be false" in error for error in errors)


def test_memory_query_contract_rejects_semantic_candidates() -> None:
    result = _valid_result()
    result["semantic_candidates"] = [{"url": "https://example.com"}]

    errors = validate_memory_evidence_query_contract(result)

    assert any("semantic_candidates must be an empty list" in error for error in errors)


def test_memory_query_contract_rejects_result_count_mismatch() -> None:
    result = _valid_result()
    result["result_count"] = 2

    errors = validate_memory_evidence_query_contract(result)

    assert any("result_count must equal len(results)" in error for error in errors)


def test_memory_query_contract_rejects_deterministic_candidate_count_mismatch() -> None:
    result = _valid_result()
    result["deterministic_candidate_count"] = 2

    errors = validate_memory_evidence_query_contract(result)

    assert any(
        "deterministic_candidate_count must equal" in error
        for error in errors
    )


def test_memory_query_contract_rejects_wrong_candidate_rank() -> None:
    result = _valid_result()
    result["deterministic_candidates"][0]["rank"] = 2

    errors = validate_memory_evidence_query_contract(result)

    assert any("rank must equal 1" in error for error in errors)


def test_memory_query_contract_rejects_unsafe_flag() -> None:
    result = _valid_result()
    result["external_write_performed"] = True

    with pytest.raises(AssertionError, match="external_write_performed"):
        assert_memory_evidence_query_contract(result)