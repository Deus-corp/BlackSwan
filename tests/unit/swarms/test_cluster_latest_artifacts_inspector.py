from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from src.swarms.runtime import cluster_cli
from src.testing.inspect_cluster_latest_artifacts import (
    inspect_cluster_latest_artifacts,
)
from tests.unit.swarms.fixtures_memory_replay import (
    explorer_memory_replay_smoke_result_fixture,
)


def test_latest_artifacts_inspector_indexes_memory_replay_smoke(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()

    artifact_path = artifacts_root / "explorer_memory_replay_smoke.json"
    artifact_path.write_text(
        json.dumps(explorer_memory_replay_smoke_result_fixture()),
        encoding="utf-8",
    )

    summary = inspect_cluster_latest_artifacts(
        artifacts_root=artifacts_root,
    )

    assert summary["type"] == "cluster_latest_artifacts_summary"
    assert summary["status"] == "indexed"
    assert summary["artifacts_root"] == str(artifacts_root)
    assert summary["artifact_count"] == 1
    assert summary["known_artifact_count"] == 1
    assert summary["contract_ok"] is True
    assert summary["external_write_performed"] is False
    assert summary["real_execution_enabled"] is False

    artifact = summary["artifacts"][0]

    assert artifact["name"] == "explorer_memory_replay_smoke"
    assert artifact["type"] == "explorer_memory_replay_smoke_result"
    assert artifact["status"] == "passed"
    assert artifact["contract_checked"] is True
    assert artifact["contract_ok"] is True
    assert artifact["contract_errors"] == []
    assert artifact["memory_replay_summary"]["records_published"] == 7
    assert artifact["memory_replay_summary"]["query_results"] == 5
    assert artifact["memory_replay_summary"]["full_replay_path_ratio"] == 0.7143


def test_latest_artifacts_inspector_reports_missing_root(
    tmp_path: Path,
) -> None:
    summary = inspect_cluster_latest_artifacts(
        artifacts_root=tmp_path / "missing",
    )

    assert summary["type"] == "cluster_latest_artifacts_summary"
    assert summary["status"] == "missing"
    assert summary["artifact_count"] == 0
    assert summary["known_artifact_count"] == 0
    assert summary["contract_ok"] is False
    assert summary["artifacts"] == []


def test_latest_artifacts_inspector_marks_unknown_artifact_invalid(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()

    artifact_path = artifacts_root / "unknown_artifact.json"
    artifact_path.write_text(
        json.dumps({"type": "unknown_artifact", "status": "passed"}),
        encoding="utf-8",
    )

    summary = inspect_cluster_latest_artifacts(
        artifacts_root=artifacts_root,
    )

    assert summary["artifact_count"] == 1
    assert summary["known_artifact_count"] == 0
    assert summary["contract_ok"] is False

    artifact = summary["artifacts"][0]

    assert artifact["contract_ok"] is False
    assert any("unknown latest artifact type" in error for error in artifact["contract_errors"])


def test_latest_artifacts_cli_accepts_valid_artifacts_root(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()

    artifact_path = artifacts_root / "explorer_memory_replay_smoke.json"
    artifact_path.write_text(
        json.dumps(explorer_memory_replay_smoke_result_fixture()),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.testing.inspect_cluster_latest_artifacts",
            "--artifacts-root",
            str(artifacts_root),
            "--json",
            "--check-contract",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "cluster latest artifacts contract OK" in result.stdout

    payload_text = result.stdout.split("✅", 1)[0].strip()
    payload = json.loads(payload_text)

    assert payload["type"] == "cluster_latest_artifacts_summary"
    assert payload["contract_ok"] is True
    assert payload["artifact_count"] == 1


def test_cluster_cli_latest_artifacts_help_includes_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "latest-artifacts",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--artifacts-root" in result.stdout
    assert "--json" in result.stdout
    assert "--check-contract" in result.stdout


def test_cluster_cli_latest_artifacts_passes_arguments(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cluster_cli.subprocess, "run", fake_run)

    artifacts_root = tmp_path / "artifacts"

    args = argparse.Namespace(
        artifacts_root=str(artifacts_root),
        json=True,
        check_contract=True,
    )

    exit_code = cluster_cli.run_latest_artifacts(args)

    assert exit_code == 0
    assert len(calls) == 1

    command = calls[0]

    assert "src.testing.inspect_cluster_latest_artifacts" in command
    assert "--artifacts-root" in command
    assert str(artifacts_root) in command
    assert "--json" in command
    assert "--check-contract" in command