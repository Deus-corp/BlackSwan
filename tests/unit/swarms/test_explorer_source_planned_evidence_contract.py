import pytest

from src.testing.check_explorer_source_planned_evidence_loop import (
    assert_source_planned_evidence_loop,
)


def _valid_result() -> dict:
    return {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "source_plan_enabled": True,
        "source_plan": {
            "type": "explorer_research_source_plan",
            "execution_risk_tier": "network_read",
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
        "source_plan_targets": [
            {
                "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
                "source_adapter": "evidence",
                "source_kind": "curated_evidence_url",
                "preferred_evidence_target": True,
                "network_read_candidate": True,
                "external_write_performed": False,
                "real_execution_enabled": False,
            }
        ],
        "tick_results": [
            {
                "node": {
                    "source_adapter_targets_seen": {"evidence": 1},
                    "source_adapter_targets_selected": {"evidence": 1},
                }
            }
        ],
        "total_findings_emitted": 1,
        "total_memory_records_published": 1,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def test_source_planned_evidence_contract_accepts_successful_loop() -> None:
    assert_source_planned_evidence_loop(_valid_result())


def test_source_planned_evidence_contract_rejects_missing_memory_record() -> None:
    result = _valid_result()
    result["total_memory_records_published"] = 0

    with pytest.raises(AssertionError, match="memory_record"):
        assert_source_planned_evidence_loop(result)


def test_source_planned_evidence_contract_rejects_external_write() -> None:
    result = _valid_result()
    result["external_write_performed"] = True

    with pytest.raises(AssertionError, match="external writes"):
        assert_source_planned_evidence_loop(result)


def test_source_planned_evidence_contract_rejects_unselected_evidence_target() -> None:
    result = _valid_result()
    result["tick_results"][0]["node"]["source_adapter_targets_selected"] = {
        "evidence": 0
    }

    with pytest.raises(AssertionError, match="select"):
        assert_source_planned_evidence_loop(result)