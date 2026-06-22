from __future__ import annotations

from typing import Any


def memory_replay_record_fixture(
    index: int = 1,
    **overrides: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": f"fixture-memory-replay-{index}",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "Python asyncio documentation evidence about event loops, tasks, "
            "autonomous agents, and memory systems."
        ),
        "content_hash": f"hash-fixture-memory-replay-{index}",
        "source_score": 0.86,
        "quality_score": 0.86,
        "system_relevance_score": 0.82,
        "authority_score": 0.85,
        "freshness_score": 0.60,
        "topic_tags": ["asyncio", "agents", "memory"],
        "evidence_category": "python_docs",
        "semantic_retrieval_enabled": False,
        "embedding_status": "not_computed",
        "embedding_model": "",
        "embedding_dim": 0,
        "embedding_hash": "",
        "embedding_vector_ref": "",
        "embedding_updated_at": 0.0,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "provenance": {
            "memory_replay_artifact": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }

    record.update(overrides)
    return record


def memory_replay_artifact_fixture(
    records: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    clean_records = list(
        records if records is not None else [memory_replay_record_fixture()]
    )

    artifact: dict[str, Any] = {
        "type": "explorer_memory_replay_artifact",
        "artifact_status": "bounded",
        "record_count": len(clean_records),
        "available_record_count": len(clean_records),
        "truncated": False,
        "limit": 20,
        "records": clean_records,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    artifact.update(overrides)
    return artifact


def memory_evidence_query_result_fixture(
    *,
    records_seen: int = 1,
    records_replayed: int = 1,
    result_count: int = 1,
    **overrides: Any,
) -> dict[str, Any]:
    results = [
        {
            "type": "memory_evidence_catalog_item",
            "url": "https://docs.python.org/3/library/asyncio.html",
            "domain": "docs.python.org",
            "ranking_score": 0.8,
            "source_score": 0.86,
            "system_relevance_score": 0.82,
            "semantic_retrieval_enabled": False,
            "embedding_status": "not_computed",
            "embedding_model": "",
            "embedding_dim": 0,
            "embedding_hash": "",
            "embedding_vector_ref": "",
            "embedding_updated_at": 0.0,
        }
    ][:result_count]

    deterministic_candidates = [
        {
            "rank": index,
            "url": item["url"],
            "domain": item["domain"],
            "dedupe_key": f"dedupe-fixture-{index}",
            "ranking_score": item["ranking_score"],
            "source_score": item["source_score"],
            "system_relevance_score": item["system_relevance_score"],
            "retrieval_path": "deterministic_catalog_query",
        }
        for index, item in enumerate(results, start=1)
    ]

    result: dict[str, Any] = {
        "type": "memory_evidence_query_result",
        "retrieval_contract_version": "memory_retrieval_v0_1",
        "retrieval_mode": "deterministic",
        "hybrid_retrieval_enabled": False,
        "semantic_retrieval_enabled": False,
        "semantic_candidates": [],
        "deterministic_candidates": deterministic_candidates,
        "deterministic_candidate_count": len(deterministic_candidates),
        "embedding_status": "not_computed",
        "embedding_model": "",
        "embedding_dim": 0,
        "embedding_hash": "",
        "embedding_vector_ref": "",
        "embedding_updated_at": 0.0,
        "query": {
            "text_query": "agents memory",
            "limit": 5,
            "domain": "",
            "evidence_category": "",
            "topic_tags": [],
            "min_ranking_score": 0.0,
        },
        "catalog_item_count": result_count,
        "matched_count": result_count,
        "result_count": result_count,
        "results": results,
        "replay_source": "explorer_memory_evidence",
        "explorer_memory_records_seen": records_seen,
        "explorer_memory_records_replayed": records_replayed,
        "explorer_memory_records_rejected": 0,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    result.update(overrides)
    return result


def explorer_memory_replay_smoke_result_fixture(
    *,
    records_published: int = 7,
    artifact_records: int = 7,
    artifact_available_records: int = 7,
    records_seen: int = 7,
    records_replayed: int = 7,
    query_results: int = 5,
    **overrides: Any,
) -> dict[str, Any]:
    artifact_capture_ratio = (
        round(artifact_records / records_published, 4)
        if records_published > 0
        else 0.0
    )
    artifact_availability_ratio = (
        round(artifact_available_records / records_published, 4)
        if records_published > 0
        else 0.0
    )
    replay_visibility_ratio = (
        round(records_seen / artifact_records, 4)
        if artifact_records > 0
        else 0.0
    )
    replay_acceptance_ratio = (
        round(records_replayed / records_seen, 4)
        if records_seen > 0
        else 0.0
    )
    query_result_ratio = (
        round(query_results / records_replayed, 4)
        if records_replayed > 0
        else 0.0
    )
    full_replay_path_ratio = (
        round(query_results / records_published, 4)
        if records_published > 0
        else 0.0
    )

    memory_replay_yield = {
        "records_published": records_published,
        "artifact_records": artifact_records,
        "artifact_available_records": artifact_available_records,
        "records_seen": records_seen,
        "records_replayed": records_replayed,
        "query_results": query_results,
        "artifact_capture_ratio": artifact_capture_ratio,
        "artifact_availability_ratio": artifact_availability_ratio,
        "replay_visibility_ratio": replay_visibility_ratio,
        "replay_acceptance_ratio": replay_acceptance_ratio,
        "query_result_ratio": query_result_ratio,
        "full_replay_path_ratio": full_replay_path_ratio,
    }

    memory_replay_summary = {
        "status": "passed",
        "records_published": records_published,
        "artifact_records": artifact_records,
        "records_replayed": records_replayed,
        "query_results": query_results,
        "artifact_capture_ratio": artifact_capture_ratio,
        "replay_acceptance_ratio": replay_acceptance_ratio,
        "full_replay_path_ratio": full_replay_path_ratio,
    }

    result: dict[str, Any] = {
        "type": "explorer_memory_replay_smoke_result",
        "status": "passed",
        "explorer_contract_ok": True,
        "memory_query_contract_ok": True,
        "total_memory_records_published": records_published,
        "memory_replay_artifact_record_count": artifact_records,
        "memory_replay_artifact_available_record_count": (
            artifact_available_records
        ),
        "explorer_memory_records_seen": records_seen,
        "explorer_memory_records_replayed": records_replayed,
        "memory_query_result_count": query_results,
        "retrieval_mode": "deterministic",
        "hybrid_retrieval_enabled": False,
        "semantic_retrieval_enabled": False,
        "semantic_candidates": [],
        "memory_replay_yield": memory_replay_yield,
        "memory_replay_summary": memory_replay_summary,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    result.update(overrides)
    return result


def explorer_source_planned_result_fixture(
    *,
    total_memory_records_published: int = 7,
    evidence_seen: int = 20,
    evidence_selected: int = 7,
    **overrides: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": total_memory_records_published,
        "total_targets_published": 123,
        "total_findings_emitted": 10,
        "memory_replay_artifact": memory_replay_artifact_fixture(),
        "memory_replay_artifact_record_count": 1,
        "memory_replay_artifact_available_record_count": 1,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "ticks": [
            {
                "tick": 3,
                "memory_records_published": max(
                    1,
                    min(total_memory_records_published, 7),
                ),
                "targets_published": 123,
                "findings_emitted": 10,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "evidence": evidence_seen,
                        "github": 2,
                    },
                    "source_adapter_targets_selected": {
                        "evidence": evidence_selected,
                        "github": 1,
                    },
                    "source_adapter_rate_limits": {},
                    "domain_rate_limits": {},
                },
            }
        ],
    }

    result.update(overrides)
    return result