from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from src.testing.run_explorer_memory_replay_smoke import (
    _build_memory_replay_yield_metrics,
    build_parser,
    run_explorer_memory_replay_smoke,
)
from src.testing.check_explorer_memory_replay_smoke import (
    validate_explorer_memory_replay_smoke,
)

from tests.unit.swarms.fixtures_memory_replay import (
    memory_evidence_query_result_fixture,
    memory_replay_artifact_fixture,
    memory_replay_record_fixture,
)


def _explorer_result() -> dict:
    record = memory_replay_record_fixture(index=1, gid="smoke-memory-record-1")

    return {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": 5,
        "total_targets_published": 20,
        "total_findings_emitted": 5,
        "memory_replay_artifact": memory_replay_artifact_fixture(
            records=[record],
        ),
        "memory_replay_artifact_record_count": 1,
        "memory_replay_artifact_available_record_count": 1,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "ticks": [
            {
                "tick": 1,
                "memory_records_published": 5,
                "targets_published": 20,
                "findings_emitted": 5,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "evidence": 5,
                        "github": 2,
                    },
                    "source_adapter_targets_selected": {
                        "evidence": 5,
                        "github": 1,
                    },
                    "source_adapter_rate_limits": {},
                    "domain_rate_limits": {},
                },
            }
        ],
    }


def _memory_replay_result() -> dict:
    return memory_evidence_query_result_fixture(
        records_seen=1,
        records_replayed=1,
        result_count=1,
    )


def _completed() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="",
    )


def test_parser_includes_expected_flags() -> None:
    parser = build_parser()
    help_text = parser.format_help()

    assert "--goal" in help_text
    assert "--ticks" in help_text
    assert "--source-adapter" in help_text
    assert "--memory-replay-artifact-limit" in help_text
    assert "--text-query" in help_text
    assert "--json-output" in help_text
    assert "--check-contract" in help_text


def test_memory_replay_yield_metrics_are_computed() -> None:
    metrics = _build_memory_replay_yield_metrics(
        records_published=7,
        artifact_records=7,
        artifact_available_records=7,
        records_seen=7,
        records_replayed=7,
        query_results=5,
    )

    assert metrics == {
        "records_published": 7,
        "artifact_records": 7,
        "artifact_available_records": 7,
        "records_seen": 7,
        "records_replayed": 7,
        "query_results": 5,
        "artifact_capture_ratio": 1.0,
        "artifact_availability_ratio": 1.0,
        "replay_visibility_ratio": 1.0,
        "replay_acceptance_ratio": 1.0,
        "query_result_ratio": 0.7143,
        "full_replay_path_ratio": 0.7143,
    }


def test_memory_replay_yield_metrics_handle_zero_denominators() -> None:
    metrics = _build_memory_replay_yield_metrics(
        records_published=0,
        artifact_records=0,
        artifact_available_records=0,
        records_seen=0,
        records_replayed=0,
        query_results=0,
    )

    assert metrics["artifact_capture_ratio"] == 0.0
    assert metrics["artifact_availability_ratio"] == 0.0
    assert metrics["replay_visibility_ratio"] == 0.0
    assert metrics["replay_acceptance_ratio"] == 0.0
    assert metrics["query_result_ratio"] == 0.0
    assert metrics["full_replay_path_ratio"] == 0.0


def test_one_command_smoke_runs_explorer_and_replay_contracts(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_runner(command):
        calls.append(list(command))

        if "src.testing.run_explorer_network_read_loop" in command:
            output_path = Path(command[command.index("--json-output") + 1])
            output_path.write_text(
                json.dumps(_explorer_result()),
                encoding="utf-8",
            )
            return _completed()

        if "src.testing.replay_explorer_memory_evidence_query" in command:
            output_path = Path(command[command.index("--json-output") + 1])
            output_path.write_text(
                json.dumps(_memory_replay_result()),
                encoding="utf-8",
            )
            return _completed()

        raise AssertionError(f"unexpected command: {command}")

    args = argparse.Namespace(
        goal="autonomous agents memory systems",
        exploration_run_id="exp-run-smoke-test",
        ticks=3,
        source_adapter=["github", "arxiv", "search", "sitemap"],
        source_plan=True,
        memory_replay_artifact_limit=20,
        text_query="agents memory",
        limit=5,
        work_dir=str(tmp_path),
        keep_artifacts=True,
        json=False,
        json_output="",
    )

    summary = run_explorer_memory_replay_smoke(
        args,
        command_runner=fake_runner,
    )

    assert summary["type"] == "explorer_memory_replay_smoke_result"
    assert summary["status"] == "passed"
    assert summary["explorer_contract_ok"] is True
    assert summary["memory_query_contract_ok"] is True
    assert summary["total_memory_records_published"] == 5
    assert summary["memory_replay_artifact_record_count"] == 1
    assert summary["explorer_memory_records_seen"] == 1
    assert summary["explorer_memory_records_replayed"] == 1
    assert summary["memory_query_result_count"] == 1
    assert summary["retrieval_mode"] == "deterministic"
    assert summary["hybrid_retrieval_enabled"] is False
    assert summary["semantic_retrieval_enabled"] is False
    assert summary["semantic_candidates"] == []
    assert summary["external_write_performed"] is False
    assert summary["real_execution_enabled"] is False

    assert summary["memory_replay_yield"] == {
        "records_published": 5,
        "artifact_records": 1,
        "artifact_available_records": 1,
        "records_seen": 1,
        "records_replayed": 1,
        "query_results": 1,
        "artifact_capture_ratio": 0.2,
        "artifact_availability_ratio": 0.2,
        "replay_visibility_ratio": 1.0,
        "replay_acceptance_ratio": 1.0,
        "query_result_ratio": 1.0,
        "full_replay_path_ratio": 0.2,
    }

    assert len(calls) == 2
    assert "src.testing.run_explorer_network_read_loop" in calls[0]
    assert "src.testing.replay_explorer_memory_evidence_query" in calls[1]


def test_one_command_smoke_writes_json_summary(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"

    def fake_runner(command):
        if "src.testing.run_explorer_network_read_loop" in command:
            output_path = Path(command[command.index("--json-output") + 1])
            output_path.write_text(json.dumps(_explorer_result()), encoding="utf-8")
            return _completed()

        if "src.testing.replay_explorer_memory_evidence_query" in command:
            output_path = Path(command[command.index("--json-output") + 1])
            output_path.write_text(
                json.dumps(_memory_replay_result()),
                encoding="utf-8",
            )
            return _completed()

        raise AssertionError(f"unexpected command: {command}")

    args = argparse.Namespace(
        goal="autonomous agents memory systems",
        exploration_run_id="exp-run-smoke-test",
        ticks=3,
        source_adapter=None,
        source_plan=True,
        memory_replay_artifact_limit=20,
        text_query="agents memory",
        limit=5,
        work_dir=str(tmp_path),
        keep_artifacts=True,
        json=False,
        json_output=str(summary_path),
    )

    summary = run_explorer_memory_replay_smoke(
        args,
        command_runner=fake_runner,
    )

    assert summary["status"] == "passed"
    assert summary_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["type"] == "explorer_memory_replay_smoke_result"
    assert payload["status"] == "passed"
    assert payload["explorer_contract_ok"] is True
    assert payload["memory_query_contract_ok"] is True

    assert payload["memory_replay_yield"]["records_published"] == 5
    assert payload["memory_replay_yield"]["artifact_records"] == 1
    assert payload["memory_replay_yield"]["records_seen"] == 1
    assert payload["memory_replay_yield"]["records_replayed"] == 1
    assert payload["memory_replay_yield"]["query_results"] == 1
    assert payload["memory_replay_yield"]["artifact_capture_ratio"] == 0.2


def test_one_command_smoke_returns_failed_summary_on_explorer_failure(
    tmp_path: Path,
) -> None:
    def fake_runner(command):
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=2,
            stdout="explorer stdout",
            stderr="explorer stderr",
        )

    args = argparse.Namespace(
        goal="autonomous agents memory systems",
        exploration_run_id="exp-run-smoke-test",
        ticks=3,
        source_adapter=None,
        source_plan=True,
        memory_replay_artifact_limit=20,
        text_query="agents memory",
        limit=5,
        work_dir=str(tmp_path),
        keep_artifacts=True,
        json=False,
        json_output="",
    )

    summary = run_explorer_memory_replay_smoke(
        args,
        command_runner=fake_runner,
    )

    assert summary["status"] == "failed"
    assert summary["failure_stage"] == "explorer_runtime"
    assert summary["returncode"] == 2
    assert summary["external_write_performed"] is False
    assert summary["real_execution_enabled"] is False