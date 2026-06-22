from __future__ import annotations

import json
import subprocess
import sys
import os
from pathlib import Path

from src.testing.inspect_memory_replay_smoke_latest import (
    inspect_memory_replay_smoke_latest,
)
from tests.unit.swarms.fixtures_memory_replay import (
    explorer_memory_replay_smoke_result_fixture,
)


def test_inspector_reads_explicit_valid_artifact(tmp_path: Path) -> None:
    path = tmp_path / "explorer_memory_replay_smoke.json"
    path.write_text(
        json.dumps(explorer_memory_replay_smoke_result_fixture()),
        encoding="utf-8",
    )

    summary = inspect_memory_replay_smoke_latest(json_path=str(path))

    assert summary["type"] == "memory_replay_latest_summary"
    assert summary["status"] == "passed"
    assert summary["artifact_path"] == str(path)
    assert summary["contract_ok"] is True
    assert summary["contract_errors"] == []
    assert summary["memory_replay_summary"]["records_published"] == 7
    assert summary["memory_replay_summary"]["artifact_records"] == 7
    assert summary["memory_replay_summary"]["records_replayed"] == 7
    assert summary["memory_replay_summary"]["query_results"] == 5
    assert summary["memory_replay_summary"]["full_replay_path_ratio"] == 0.7143


def test_inspector_finds_latest_artifact_in_search_root(tmp_path: Path) -> None:
    older = tmp_path / "explorer_memory_replay_smoke.json"
    newer = tmp_path / "explorer_memory_replay_smoke_newer.json"

    older.write_text(
        json.dumps(
            explorer_memory_replay_smoke_result_fixture(
                query_results=1,
            )
        ),
        encoding="utf-8",
    )
    newer.write_text(
        json.dumps(
            explorer_memory_replay_smoke_result_fixture(
                query_results=5,
            )
        ),
        encoding="utf-8",
    )

    # Ensure newer mtime wins even on filesystems with coarse timestamp
    # resolution.
    older_time = older.stat().st_mtime
    os.utime(newer, (older_time + 10.0, older_time + 10.0))

    summary = inspect_memory_replay_smoke_latest(
        search_roots=[tmp_path],
    )

    assert summary["artifact_path"] == str(newer)
    assert summary["contract_ok"] is True
    assert summary["memory_replay_summary"]["query_results"] == 5


def test_inspector_reports_missing_artifact(tmp_path: Path) -> None:
    summary = inspect_memory_replay_smoke_latest(
        search_roots=[tmp_path],
    )

    assert summary["type"] == "memory_replay_latest_summary"
    assert summary["status"] == "missing"
    assert summary["artifact_path"] == ""
    assert summary["contract_ok"] is False
    assert summary["memory_replay_summary"] == {}
    assert any("no memory replay smoke artifact found" in error for error in summary["contract_errors"])


def test_inspector_cli_accepts_valid_artifact(tmp_path: Path) -> None:
    path = tmp_path / "explorer_memory_replay_smoke.json"
    path.write_text(
        json.dumps(explorer_memory_replay_smoke_result_fixture()),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.testing.inspect_memory_replay_smoke_latest",
            "--json-path",
            str(path),
            "--json",
            "--check-contract",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "latest memory replay smoke artifact contract OK" in result.stdout

    payload_text = result.stdout.split("✅", 1)[0].strip()
    payload = json.loads(payload_text)

    assert payload["type"] == "memory_replay_latest_summary"
    assert payload["contract_ok"] is True