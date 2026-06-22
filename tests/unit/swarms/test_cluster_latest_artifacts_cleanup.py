from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from src.swarms.runtime import cluster_cli
from src.testing.cleanup_cluster_latest_artifacts import (
    assert_cluster_latest_artifacts_cleanup_result,
    build_cluster_latest_artifacts_cleanup_result,
    validate_cluster_latest_artifacts_cleanup_result,
)
from tests.unit.swarms.fixtures_memory_replay import (
    explorer_memory_replay_smoke_result_fixture,
)


def test_cleanup_dry_run_reports_would_delete_without_deleting(
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
    os.utime(artifact_path, (old_mtime, old_mtime))

    result = build_cluster_latest_artifacts_cleanup_result(
        artifacts_root=artifacts_root,
        retention_max_age_seconds=10.0,
        now=old_mtime + 100.0,
    )

    assert result["type"] == "cluster_latest_artifacts_cleanup_result"
    assert result["mode"] == "dry_run"
    assert result["status"] == "completed"
    assert result["source_contract_ok"] is True
    assert result["contract_ok"] is True
    assert result["artifact_count"] == 1
    assert result["stale_artifact_count"] == 1
    assert result["would_delete_count"] == 1
    assert result["would_delete"][0]["name"] == "explorer_memory_replay_smoke"
    assert result["would_delete"][0]["reason"] == "older_than_retention_max_age"
    assert result["deleted_count"] == 0
    assert result["deleted"] == []
    assert result["external_write_performed"] is False
    assert result["real_execution_enabled"] is False
    assert artifact_path.exists()

    assert validate_cluster_latest_artifacts_cleanup_result(result) == []
    assert_cluster_latest_artifacts_cleanup_result(result)


def test_cleanup_dry_run_reports_noop_for_fresh_artifact(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()

    artifact_path = artifacts_root / "explorer_memory_replay_smoke.json"
    artifact_path.write_text(
        json.dumps(explorer_memory_replay_smoke_result_fixture()),
        encoding="utf-8",
    )

    result = build_cluster_latest_artifacts_cleanup_result(
        artifacts_root=artifacts_root,
        retention_max_age_seconds=10.0,
        now=artifact_path.stat().st_mtime + 1.0,
    )

    assert result["artifact_count"] == 1
    assert result["stale_artifact_count"] == 0
    assert result["would_delete_count"] == 0
    assert result["would_delete"] == []
    assert result["deleted_count"] == 0
    assert artifact_path.exists()
    assert validate_cluster_latest_artifacts_cleanup_result(result) == []


def test_cleanup_contract_rejects_deleted_count() -> None:
    result = {
        "type": "cluster_latest_artifacts_cleanup_result",
        "mode": "dry_run",
        "status": "completed",
        "source_contract_ok": True,
        "contract_ok": True,
        "artifact_count": 0,
        "known_artifact_count": 0,
        "invalid_artifact_count": 0,
        "stale_artifact_count": 0,
        "retention": {
            "mode": "inspect_only",
            "max_age_seconds": 0.0,
            "would_delete_count": 0,
            "would_delete": [],
        },
        "would_delete_count": 0,
        "would_delete": [],
        "deleted_count": 1,
        "deleted": ["artifact.json"],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    errors = validate_cluster_latest_artifacts_cleanup_result(result)

    assert any("deleted_count must be 0" in error for error in errors)
    assert any("deleted must be an empty list" in error for error in errors)


def test_cleanup_cli_accepts_valid_dry_run(
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
            "src.testing.cleanup_cluster_latest_artifacts",
            "--artifacts-root",
            str(artifacts_root),
            "--retention-max-age-days",
            "7",
            "--dry-run",
            "--json",
            "--check-contract",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "cluster latest artifacts cleanup dry-run contract OK" in result.stdout

    payload_text = result.stdout.split("✅", 1)[0].strip()
    payload = json.loads(payload_text)

    assert payload["type"] == "cluster_latest_artifacts_cleanup_result"
    assert payload["mode"] == "dry_run"
    assert payload["deleted_count"] == 0


def test_cluster_cli_latest_artifacts_cleanup_help_includes_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "latest-artifacts-cleanup",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--artifacts-root" in result.stdout
    assert "--retention-max-age-days" in result.stdout
    assert "--retention-max-age-seconds" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--json" in result.stdout
    assert "--check-contract" in result.stdout


def test_cluster_cli_latest_artifacts_cleanup_passes_arguments(
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
        retention_max_age_days=7.0,
        retention_max_age_seconds=0.0,
        dry_run=True,
        json=True,
        check_contract=True,
    )

    exit_code = cluster_cli.run_latest_artifacts_cleanup(args)

    assert exit_code == 0
    assert len(calls) == 1

    command = calls[0]

    assert "src.testing.cleanup_cluster_latest_artifacts" in command
    assert "--artifacts-root" in command
    assert str(artifacts_root) in command
    assert "--retention-max-age-days" in command
    assert "7.0" in command
    assert "--dry-run" in command
    assert "--json" in command
    assert "--check-contract" in command


def test_cluster_cli_latest_artifacts_cleanup_seconds_override(
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
        dry_run=True,
        json=True,
        check_contract=True,
    )

    exit_code = cluster_cli.run_latest_artifacts_cleanup(args)

    assert exit_code == 0

    command = calls[0]

    assert "--retention-max-age-seconds" in command
    assert "30.0" in command
    assert "--retention-max-age-days" not in command