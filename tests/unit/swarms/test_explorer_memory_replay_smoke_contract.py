from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.testing.check_explorer_memory_replay_smoke import (
    assert_explorer_memory_replay_smoke,
    validate_explorer_memory_replay_smoke,
)
from tests.unit.swarms.fixtures_memory_replay import (
    explorer_memory_replay_smoke_result_fixture,
)


def _valid_result() -> dict:
    return explorer_memory_replay_smoke_result_fixture()


def test_explorer_memory_replay_smoke_contract_accepts_valid_result() -> None:
    assert validate_explorer_memory_replay_smoke(_valid_result()) == []
    assert_explorer_memory_replay_smoke(_valid_result())


def test_explorer_memory_replay_smoke_contract_rejects_failed_status() -> None:
    result = _valid_result()
    result["status"] = "failed"

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("status must be passed" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_missing_yield() -> None:
    result = _valid_result()
    result.pop("memory_replay_yield")

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("memory_replay_yield must be a mapping" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_counter_mismatch() -> None:
    result = _valid_result()
    result["memory_replay_yield"]["records_replayed"] = 6

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("records_replayed must match summary counter" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_ratio_mismatch() -> None:
    result = _valid_result()
    result["memory_replay_yield"]["query_result_ratio"] = 0.5

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("query_result_ratio must equal 0.7143" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_ratio_out_of_range() -> None:
    result = _valid_result()
    result["memory_replay_yield"]["artifact_capture_ratio"] = 1.5

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("artifact_capture_ratio must be between" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_unsafe_flag() -> None:
    result = _valid_result()
    result["external_write_performed"] = True

    with pytest.raises(AssertionError, match="external_write_performed"):
        assert_explorer_memory_replay_smoke(result)


def test_explorer_memory_replay_smoke_contract_rejects_semantic_candidates() -> None:
    result = _valid_result()
    result["semantic_candidates"] = [{"url": "https://example.com"}]

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("semantic_candidates must be an empty list" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_replayed_gt_seen() -> None:
    result = _valid_result()
    result["explorer_memory_records_replayed"] = 8
    result["memory_replay_yield"]["records_replayed"] = 8
    result["memory_replay_yield"]["replay_acceptance_ratio"] = 1.1429
    result["memory_replay_yield"]["query_result_ratio"] = 0.625

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("explorer_memory_records_replayed must be <=" in error for error in errors)


def test_explorer_memory_replay_smoke_checker_cli_accepts_valid_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "explorer_memory_replay_smoke.json"
    path.write_text(json.dumps(_valid_result()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.testing.check_explorer_memory_replay_smoke",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "explorer memory replay smoke contract OK" in result.stdout


def test_explorer_memory_replay_smoke_contract_rejects_missing_summary() -> None:
    result = _valid_result()
    result.pop("memory_replay_summary")

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("memory_replay_summary must be a mapping" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_summary_counter_mismatch() -> None:
    result = _valid_result()
    result["memory_replay_summary"]["query_results"] = 4

    errors = validate_explorer_memory_replay_smoke(result)

    assert any("memory_replay_summary.query_results must match" in error for error in errors)


def test_explorer_memory_replay_smoke_contract_rejects_summary_ratio_mismatch() -> None:
    result = _valid_result()
    result["memory_replay_summary"]["full_replay_path_ratio"] = 0.5

    errors = validate_explorer_memory_replay_smoke(result)

    assert any(
        "memory_replay_summary.full_replay_path_ratio must match" in error
        for error in errors
    )