from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import argparse

from src.swarms.runtime import cluster_cli


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
    assert "--check-contract" in result.stdout


def test_cluster_cli_memory_replay_smoke_passes_check_contract_flag(
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

    output_path = tmp_path / "explorer_memory_replay_smoke.json"

    args = argparse.Namespace(
        goal="autonomous agents memory systems",
        exploration_run_id="exp-run-memory-replay-smoke",
        ticks=3,
        source_adapter=None,
        no_source_plan=False,
        memory_replay_artifact_limit=20,
        text_query="agents memory",
        limit=5,
        work_dir="",
        keep_artifacts=False,
        json=True,
        json_output=str(output_path),
        check_contract=True,
    )

    exit_code = cluster_cli.run_memory_replay_smoke(args)

    assert exit_code == 0
    assert len(calls) == 1

    command = calls[0]

    assert "src.testing.run_explorer_memory_replay_smoke" in command
    assert "--json" in command
    assert "--json-output" in command
    assert str(output_path) in command
    assert "--check-contract" in command


def test_cluster_cli_memory_replay_smoke_omits_check_contract_by_default(
    monkeypatch,
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
        goal="autonomous agents memory systems",
        exploration_run_id="exp-run-memory-replay-smoke",
        ticks=3,
        source_adapter=None,
        no_source_plan=False,
        memory_replay_artifact_limit=20,
        text_query="agents memory",
        limit=5,
        work_dir="",
        keep_artifacts=False,
        json=False,
        json_output="",
        check_contract=False,
    )

    exit_code = cluster_cli.run_memory_replay_smoke(args)

    assert exit_code == 0
    assert len(calls) == 1
    assert "--check-contract" not in calls[0]


def test_cluster_cli_memory_replay_latest_help_includes_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.swarms.runtime.cluster_cli",
            "memory-replay-latest",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--json-path" in result.stdout
    assert "--search-root" in result.stdout
    assert "--json" in result.stdout
    assert "--check-contract" in result.stdout


def test_cluster_cli_memory_replay_latest_passes_arguments(
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

    artifact_path = tmp_path / "explorer_memory_replay_smoke.json"

    args = argparse.Namespace(
        json_path=str(artifact_path),
        search_root=[str(tmp_path)],
        json=True,
        check_contract=True,
    )

    exit_code = cluster_cli.run_memory_replay_latest(args)

    assert exit_code == 0
    assert len(calls) == 1

    command = calls[0]

    assert "src.testing.inspect_memory_replay_smoke_latest" in command
    assert "--json-path" in command
    assert str(artifact_path) in command
    assert "--search-root" in command
    assert str(tmp_path) in command
    assert "--json" in command
    assert "--check-contract" in command