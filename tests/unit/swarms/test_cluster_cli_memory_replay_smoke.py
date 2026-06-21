from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cluster_cli_memory_replay_smoke_help_includes_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-replay-smoke",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--goal" in result.stdout
    assert "--ticks" in result.stdout
    assert "--source-adapter" in result.stdout
    assert "--memory-replay-artifact-limit" in result.stdout
    assert "--text-query" in result.stdout
    assert "--json-output" in result.stdout


def test_cluster_cli_memory_replay_smoke_runs_testing_wrapper(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "explorer_memory_replay_smoke.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-replay-smoke",
            "--goal",
            "autonomous agents memory systems",
            "--ticks",
            "3",
            "--json",
            "--json-output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.exists()
    assert "explorer memory replay smoke OK" in result.stdout

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["type"] == "explorer_memory_replay_smoke_result"
    assert payload["status"] == "passed"
    assert payload["explorer_contract_ok"] is True
    assert payload["memory_query_contract_ok"] is True
    assert payload["retrieval_mode"] == "deterministic"
    assert payload["hybrid_retrieval_enabled"] is False
    assert payload["semantic_retrieval_enabled"] is False
    assert payload["external_write_performed"] is False
    assert payload["real_execution_enabled"] is False