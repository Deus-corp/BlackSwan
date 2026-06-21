from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cluster_cli_memory_replay_query_help_includes_contract_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-replay-query",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--db-path" in result.stdout
    assert "--json-input" in result.stdout
    assert "--json-output" in result.stdout
    assert "--check-contract" in result.stdout


def test_cluster_cli_memory_replay_query_writes_json_and_checks_contract(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "explorer_memory_records.json"
    output_path = tmp_path / "explorer_memory_replay_query.json"

    input_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "type": "memory_record",
                        "record_kind": "explorer_useful_evidence",
                        "gid": "cluster-cli-replay-1",
                        "url": "https://docs.python.org/3/library/asyncio.html",
                        "domain": "docs.python.org",
                        "content_preview": (
                            "Python asyncio documentation evidence about event "
                            "loops, tasks, concurrency, autonomous agents, and "
                            "memory systems."
                        ),
                        "content_hash": "hash-cluster-cli-replay-1",
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
                        "provenance": {
                            "external_write_performed": False,
                            "real_execution_enabled": False,
                            "production_paths_mutated": False,
                            "production_secrets_accessed": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-replay-query",
            "--db-path",
            "",
            "--json-input",
            str(input_path),
            "--text-query",
            "asyncio agents",
            "--limit",
            "5",
            "--json",
            "--json-output",
            str(output_path),
            "--check-contract",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.exists()
    assert "memory evidence query contract OK" in result.stdout

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["type"] == "memory_evidence_query_result"
    assert payload["replay_source"] == "explorer_memory_evidence"
    assert payload["retrieval_mode"] == "deterministic"
    assert payload["hybrid_retrieval_enabled"] is False
    assert payload["semantic_retrieval_enabled"] is False
    assert payload["result_count"] == 1
    assert payload["external_write_performed"] is False
    assert payload["real_execution_enabled"] is False