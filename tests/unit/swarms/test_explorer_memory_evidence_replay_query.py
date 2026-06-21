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
        "gid": "explorer-memory-replay-1",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "Python asyncio documentation evidence about event loops, tasks, "
            "concurrency, orchestration, autonomous agents, and memory systems."
        ),
        "content_hash": "hash-explorer-memory-replay-1",
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
            "exploration_run_id": "run-explorer-memory-replay",
            "research_goal_id": "run-explorer-memory-replay",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        },
    }
    record.update(overrides)
    return record


def test_extract_explorer_memory_records_from_nested_payload() -> None:
    payload = {
        "outer": {
            "records": [
                {"type": "ignored"},
                _explorer_memory_record(),
            ]
        }
    }

    records = extract_explorer_memory_records_from_payload(payload)

    assert len(records) == 1
    assert records[0]["record_kind"] == "explorer_useful_evidence"


def test_replay_builds_contract_valid_memory_query_result() -> None:
    result = replay_explorer_memory_evidence_query(
        [_explorer_memory_record()],
        text_query="asyncio agents",
        limit=5,
    )

    assert result["type"] == "memory_evidence_query_result"
    assert result["replay_source"] == "explorer_memory_evidence"
    assert result["explorer_memory_records_seen"] == 1
    assert result["explorer_memory_records_replayed"] == 1
    assert result["result_count"] == 1

    assert validate_memory_evidence_query_contract(result) == []


def test_empty_replay_still_returns_contract_valid_query_result() -> None:
    result = replay_explorer_memory_evidence_query(
        [],
        text_query="agents memory",
        limit=5,
    )

    assert result["explorer_memory_records_seen"] == 0
    assert result["explorer_memory_records_replayed"] == 0
    assert result["result_count"] == 0
    assert result["retrieval_mode"] == "deterministic"
    assert result["semantic_candidates"] == []

    assert validate_memory_evidence_query_contract(result) == []


def test_replay_preserves_vector_ready_fields() -> None:
    result = replay_explorer_memory_evidence_query(
        [
            _explorer_memory_record(
                embedding_status="pending",
                embedding_model="future-embedder",
                embedding_dim=768,
                embedding_hash="embedding-hash",
                embedding_vector_ref="vector://future",
                embedding_updated_at=123.0,
            )
        ],
        text_query="asyncio",
        limit=5,
    )

    assert result["result_count"] == 1

    item = result["results"][0]

    assert item["semantic_retrieval_enabled"] is False
    assert item["embedding_status"] == "pending"
    assert item["embedding_model"] == "future-embedder"
    assert item["embedding_dim"] == 768
    assert item["embedding_hash"] == "embedding-hash"
    assert item["embedding_vector_ref"] == "vector://future"
    assert item["embedding_updated_at"] == 123.0


def test_replay_keeps_safety_flags_false() -> None:
    result = replay_explorer_memory_evidence_query(
        [_explorer_memory_record()],
        text_query="asyncio",
        limit=5,
    )

    assert result["external_write_performed"] is False
    assert result["real_execution_enabled"] is False
    assert result["production_paths_mutated"] is False
    assert result["production_secrets_accessed"] is False


def test_replay_cli_reads_json_and_checks_contract(tmp_path: Path) -> None:
    input_path = tmp_path / "explorer_memory_records.json"
    output_path = tmp_path / "replay_query_result.json"

    input_path.write_text(
        json.dumps({"records": [_explorer_memory_record()]}),
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
            str(input_path),
            "--text-query",
            "asyncio agents",
            "--limit",
            "5",
            "--json-output",
            str(output_path),
            "--check-contract",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "memory evidence query contract OK" in completed.stdout

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["type"] == "memory_evidence_query_result"
    assert payload["replay_source"] == "explorer_memory_evidence"
    assert payload["result_count"] == 1