from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.testing.check_memory_evidence_query_contract import (
    validate_memory_evidence_query_contract,
)
from src.testing.replay_explorer_memory_evidence_query import (
    extract_explorer_memory_records_from_payload,
    replay_explorer_memory_evidence_query,
)


def _explorer_memory_record(**overrides):
    record = {
        "type": "memory_record",
        "record_kind": "explorer_useful_evidence",
        "gid": "runtime-memory-replay-1",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "Python asyncio documentation evidence about event loops, tasks, "
            "concurrency, orchestration, autonomous agents, and memory systems."
        ),
        "content_hash": "hash-runtime-memory-replay-1",
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
            "exploration_run_id": "runtime-memory-replay-run",
            "research_goal_id": "runtime-memory-replay-run",
            "source": "explorer_meta_agent",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }
    record.update(overrides)
    return record


def _runtime_like_result_with_memory_records() -> dict:
    return {
        "type": "explorer_network_read_loop_result",
        "exploration_run_id": "runtime-memory-replay-run",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": 1,
        "total_targets_published": 5,
        "total_findings_emitted": 3,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "tick_results": [
            {
                "tick": 1,
                "memory_records_published": 1,
                "meta_agent": {
                    "decision_action": "CLASSIFY_FINDINGS",
                    "memory_records_published": 1,
                    "memory_records": [
                        _explorer_memory_record(),
                    ],
                },
            }
        ],
    }


def test_extracts_memory_records_from_runtime_like_result() -> None:
    runtime_result = _runtime_like_result_with_memory_records()

    records = extract_explorer_memory_records_from_payload(runtime_result)

    assert len(records) == 1
    assert records[0]["record_kind"] == "explorer_useful_evidence"
    assert records[0]["url"] == "https://docs.python.org/3/library/asyncio.html"


def test_runtime_result_replay_passes_memory_query_contract() -> None:
    runtime_result = _runtime_like_result_with_memory_records()
    records = extract_explorer_memory_records_from_payload(runtime_result)

    replay_result = replay_explorer_memory_evidence_query(
        records,
        text_query="asyncio agents",
        limit=5,
    )

    assert replay_result["type"] == "memory_evidence_query_result"
    assert replay_result["replay_source"] == "explorer_memory_evidence"
    assert replay_result["explorer_memory_records_seen"] == 1
    assert replay_result["explorer_memory_records_replayed"] == 1
    assert replay_result["result_count"] == 1
    assert replay_result["retrieval_mode"] == "deterministic"
    assert replay_result["hybrid_retrieval_enabled"] is False
    assert replay_result["semantic_retrieval_enabled"] is False
    assert replay_result["semantic_candidates"] == []

    assert validate_memory_evidence_query_contract(replay_result) == []


def test_runtime_result_replay_preserves_vector_ready_fields() -> None:
    runtime_result = _runtime_like_result_with_memory_records()
    runtime_result["tick_results"][0]["meta_agent"]["memory_records"][0].update(
        {
            "embedding_status": "pending",
            "embedding_model": "future-embedder",
            "embedding_dim": 768,
            "embedding_hash": "embedding-hash-runtime",
            "embedding_vector_ref": "vector://runtime",
            "embedding_updated_at": 123.0,
        }
    )

    records = extract_explorer_memory_records_from_payload(runtime_result)
    replay_result = replay_explorer_memory_evidence_query(
        records,
        text_query="asyncio",
        limit=5,
    )

    assert replay_result["result_count"] == 1

    item = replay_result["results"][0]

    assert item["semantic_retrieval_enabled"] is False
    assert item["embedding_status"] == "pending"
    assert item["embedding_model"] == "future-embedder"
    assert item["embedding_dim"] == 768
    assert item["embedding_hash"] == "embedding-hash-runtime"
    assert item["embedding_vector_ref"] == "vector://runtime"
    assert item["embedding_updated_at"] == 123.0

    assert validate_memory_evidence_query_contract(replay_result) == []


def test_empty_runtime_result_replay_is_contract_valid() -> None:
    runtime_result = {
        "type": "explorer_network_read_loop_result",
        "exploration_run_id": "empty-runtime-memory-replay-run",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": 0,
        "tick_results": [],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    records = extract_explorer_memory_records_from_payload(runtime_result)
    replay_result = replay_explorer_memory_evidence_query(
        records,
        text_query="agents memory",
        limit=5,
    )

    assert records == []
    assert replay_result["explorer_memory_records_seen"] == 0
    assert replay_result["explorer_memory_records_replayed"] == 0
    assert replay_result["result_count"] == 0
    assert replay_result["retrieval_mode"] == "deterministic"
    assert replay_result["semantic_candidates"] == []

    assert validate_memory_evidence_query_contract(replay_result) == []


def test_replay_cli_accepts_explorer_runtime_json_artifact(
    tmp_path: Path,
) -> None:
    runtime_result_path = tmp_path / "explorer_plan_result.json"
    replay_result_path = tmp_path / "explorer_memory_replay_query.json"

    runtime_result_path.write_text(
        json.dumps(_runtime_like_result_with_memory_records()),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.testing.replay_explorer_memory_evidence_query",
            "--db-path",
            "",
            "--json-input",
            str(runtime_result_path),
            "--text-query",
            "asyncio agents",
            "--limit",
            "5",
            "--json-output",
            str(replay_result_path),
            "--check-contract",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "memory evidence query contract OK" in completed.stdout
    assert replay_result_path.exists()

    payload = json.loads(replay_result_path.read_text(encoding="utf-8"))

    assert payload["type"] == "memory_evidence_query_result"
    assert payload["replay_source"] == "explorer_memory_evidence"
    assert payload["explorer_memory_records_seen"] == 1
    assert payload["explorer_memory_records_replayed"] == 1
    assert payload["result_count"] == 1
    assert payload["retrieval_mode"] == "deterministic"
    assert payload["external_write_performed"] is False
    assert payload["real_execution_enabled"] is False