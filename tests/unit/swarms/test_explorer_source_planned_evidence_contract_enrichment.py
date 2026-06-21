from __future__ import annotations

from copy import deepcopy

from src.testing.check_explorer_source_planned_evidence_loop import (
    assert_explorer_source_planned_evidence_loop,
    validate_explorer_source_planned_evidence_loop,
)

from tests.unit.swarms.fixtures_memory_replay import (
    memory_replay_artifact_fixture,
)


def _healthy_result() -> dict:
    return {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": 7,
        "total_targets_published": 123,
        "total_findings_emitted": 10,
        "memory_replay_artifact": memory_replay_artifact_fixture(),
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
                "targets_published": 101,
                "findings_emitted": 7,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "arxiv": 2,
                        "evidence": 8,
                        "github": 2,
                    },
                    "source_adapter_targets_selected": {
                        "arxiv": 2,
                        "evidence": 5,
                        "github": 2,
                    },
                    "source_adapter_rate_limits": {
                        "arxiv:arxiv.org:robots_disallowed": 1,
                        "search:duckduckgo.com:robots_disallowed": 1,
                    },
                    "domain_rate_limits": {
                        "arxiv.org": 1,
                        "duckduckgo.com": 1,
                    },
                },
            },
            {
                "tick": 2,
                "memory_records_published": 1,
                "targets_published": 22,
                "findings_emitted": 2,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "evidence": 20,
                        "github": 2,
                    },
                    "source_adapter_targets_selected": {
                        "evidence": 7,
                        "github": 2,
                    },
                    "source_adapter_rate_limits": {
                        "github:github.com:http_429": 1,
                    },
                    "domain_rate_limits": {
                        "github.com": 1,
                    },
                },
            },
            {
                "tick": 3,
                "memory_records_published": 1,
                "targets_published": 0,
                "findings_emitted": 1,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "evidence": 20,
                    },
                    "source_adapter_targets_selected": {
                        "evidence": 7,
                    },
                    "source_adapter_rate_limits": {
                        "github:github.com:domain_window_rate_limited": 1,
                    },
                    "domain_rate_limits": {
                        "github.com": 1,
                    },
                },
            },
        ],
    }


def test_source_planned_evidence_contract_accepts_healthy_result() -> None:
    result = _healthy_result()

    assert validate_explorer_source_planned_evidence_loop(result) == []
    assert_explorer_source_planned_evidence_loop(result)


def test_source_planned_evidence_contract_rejects_low_memory_yield() -> None:
    result = _healthy_result()
    result["total_memory_records_published"] = 2

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("insufficient memory evidence yield" in error for error in errors)


def test_source_planned_evidence_contract_rejects_unsafe_external_write() -> None:
    result = _healthy_result()
    result["external_write_performed"] = True

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("external_write_performed" in error for error in errors)


def test_source_planned_evidence_contract_accepts_safe_rate_limit_telemetry() -> None:
    result = _healthy_result()

    result["ticks"][0]["node"]["source_adapter_rate_limits"] = {
        "arxiv:arxiv.org:robots_disallowed": 1,
        "github:github.com:http_429": 1,
        "github:github.com:domain_window_rate_limited": 1,
    }

    assert validate_explorer_source_planned_evidence_loop(result) == []


def test_source_planned_evidence_contract_rejects_unknown_rate_limit_reason() -> None:
    result = _healthy_result()

    result["ticks"][0]["node"]["source_adapter_rate_limits"] = {
        "github:github.com:unknown_error": 1,
    }

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("unknown source adapter rate-limit reason" in error for error in errors)


def test_source_planned_evidence_contract_rejects_missing_evidence_counters() -> None:
    result = _healthy_result()
    last_node = result["ticks"][-1]["node"]
    last_node["source_adapter_targets_seen"] = {"github": 2}
    last_node["source_adapter_targets_selected"] = {"github": 2}

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("missing node.source_adapter_targets_seen.evidence" in error for error in errors)
    assert any(
        "missing node.source_adapter_targets_selected.evidence" in error
        for error in errors
    )


def test_source_planned_evidence_contract_rejects_incomplete_ticks() -> None:
    result = _healthy_result()
    result["ticks_completed"] = 2

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("ticks_completed must equal ticks_requested" in error for error in errors)


def test_source_planned_evidence_contract_rejects_seen_less_than_selected() -> None:
    result = deepcopy(_healthy_result())
    last_node = result["ticks"][-1]["node"]
    last_node["source_adapter_targets_seen"]["evidence"] = 4
    last_node["source_adapter_targets_selected"]["evidence"] = 7

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("seen must be >= selected" in error for error in errors)