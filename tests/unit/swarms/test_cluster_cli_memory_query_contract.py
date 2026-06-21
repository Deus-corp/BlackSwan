from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cluster_cli_memory_query_help_includes_contract_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-query",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--json-output" in result.stdout
    assert "--check-contract" in result.stdout


def test_cluster_cli_memory_query_writes_json_output_and_checks_contract(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "memory_query_result.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-query",
            "--text-query",
            "agents memory",
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
    assert payload["retrieval_mode"] == "deterministic"
    assert payload["hybrid_retrieval_enabled"] is False
    assert payload["semantic_retrieval_enabled"] is False
    assert payload["semantic_candidates"] == []
    assert payload["external_write_performed"] is False
    assert payload["real_execution_enabled"] is False