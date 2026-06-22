from __future__ import annotations

import argparse
import json
import subprocess
import sys
import os
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

    assert summary["invalid_artifact_count"] == 0
    assert summary["stale_artifact_count"] == 0
    assert summary["retention"]["mode"] == "inspect_only"
    assert summary["retention"]["would_delete_count"] == 0


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

    assert summary["invalid_artifact_count"] == 0
    assert summary["stale_artifact_count"] == 0
    assert summary["retention"]["mode"] == "inspect_only"
    assert summary["retention"]["would_delete_count"] == 0


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

    assert summary["invalid_artifact_count"] == 1


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
    assert "--retention-max-age-days" in result.stdout
    assert "--retention-max-age-seconds" in result.stdout


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
        retention_max_age_days=7.0,
        retention_max_age_seconds=0.0,
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

    assert "--retention-max-age-days" in command
    assert "7.0" in command


def test_latest_artifacts_inspector_reports_stale_artifacts(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()

    artifact_path = artifacts_root / "explorer_memory_replay_smoke.json"
    artifact_path.write_text(
        json.dumps(explorer_memory_replay_smoke_result_fixture()),
        encoding="utf-8",
    )

    old_mtime = 1_700_000_000.0
    artifact_path.touch()

    os.utime(artifact_path, (old_mtime, old_mtime))

    summary = inspect_cluster_latest_artifacts(
        artifacts_root=artifacts_root,
        retention_max_age_seconds=10.0,
        now=old_mtime + 100.0,
    )

    assert summary["artifact_count"] == 1
    assert summary["stale_artifact_count"] == 1
    assert summary["retention"]["mode"] == "inspect_only"
    assert summary["retention"]["max_age_seconds"] == 10.0
    assert summary["retention"]["would_delete_count"] == 1
    assert summary["retention"]["would_delete"][0]["name"] == (
        "explorer_memory_replay_smoke"
    )
    assert summary["artifacts"][0]["stale"] is True
    assert summary["artifacts"][0]["age_seconds"] == 100.0
    assert artifact_path.exists()


def test_cluster_cli_latest_artifacts_passes_retention_seconds(
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

    args = argparse.Namespace(
        artifacts_root=str(tmp_path / "artifacts"),
        retention_max_age_days=7.0,
        retention_max_age_seconds=30.0,
        json=True,
        check_contract=True,
    )

    exit_code = cluster_cli.run_latest_artifacts(args)

    assert exit_code == 0

    command = calls[0]

    assert "--retention-max-age-seconds" in command
    assert "30.0" in command
    assert "--retention-max-age-days" not in command