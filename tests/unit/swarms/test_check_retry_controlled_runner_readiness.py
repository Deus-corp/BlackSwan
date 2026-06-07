import argparse
import asyncio

from src.testing.check_retry_controlled_runner_readiness import (
    _exit_code_for_result,
    check_retry_controlled_runner_readiness,
    check_retry_controlled_runner_readiness_from_summaries,
)
from src.testing.retry_governance_smoke import run_retry_governance_smoke


def _complete_trail_summary():
    return {
        "type": "retry_governance_trail_summary",
        "chain_complete": True,
        "counts": {
            "proposals": 1,
            "approvals": 1,
            "plans": 1,
            "rendered_commands": 1,
            "rendered_command_results": 1,
            "eligibilities": 1,
            "results": 1,
        },
        "rendered_command_result_statuses": {"skipped": 1},
        "eligibility_statuses": {"blocked": 1},
        "result_statuses": {"skipped": 1},
    }


def _passed_observability():
    return {
        "status": "passed",
        "brief_key_metrics": {
            "security_retry_rendered_command_results": 1,
            "security_retry_execution_eligibilities": 1,
            "security_retry_execution_blocked": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
        },
    }


def test_retry_controlled_runner_readiness_passes_for_complete_safe_baseline() -> None:
    result = check_retry_controlled_runner_readiness_from_summaries(
        trail_summary=_complete_trail_summary(),
        observability=_passed_observability(),
    )

    assert result["status"] == "passed"
    assert result["readiness_score"] == 100
    assert result["failed_checks"] == []
    assert result["controlled_execution_enabled"] is False
    assert result["recommendation"] == "ready_for_controlled_runner_design"
    assert _exit_code_for_result(result) == 0


def test_retry_controlled_runner_readiness_fails_when_eligibility_missing() -> None:
    trail = _complete_trail_summary()
    trail["counts"]["eligibilities"] = 0
    trail["eligibility_statuses"] = {}

    result = check_retry_controlled_runner_readiness_from_summaries(
        trail_summary=trail,
        observability=_passed_observability(),
    )

    assert result["status"] == "failed"
    assert result["readiness_score"] < 100
    assert "trail_has_eligibilities" in result["failed_checks"]
    assert "execution_eligibility_is_blocked" in result["failed_checks"]
    assert result["recommendation"] == "complete_safe_retry_governance_baseline_first"
    assert _exit_code_for_result(result) == 1


def test_retry_controlled_runner_readiness_fails_on_security_invalid_records() -> None:
    observability = _passed_observability()
    observability["brief_key_metrics"]["security_validation_invalid_records"] = 1

    result = check_retry_controlled_runner_readiness_from_summaries(
        trail_summary=_complete_trail_summary(),
        observability=observability,
    )

    assert result["status"] == "failed"
    assert "no_security_validation_failures" in result["failed_checks"]


def test_retry_controlled_runner_readiness_reads_runtime_smoke_chain(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    asyncio.run(
        run_retry_governance_smoke(
            argparse.Namespace(
                db_path=db_path,
                source="retry-governance-smoke-test",
                proposal_id="proposal-readiness",
                approval_id="approval-readiness",
                plan_id="plan-readiness",
                rendered_command_id="rendered-readiness",
                result_id="result-readiness",
                timeout_profile="standard",
                decision_mode="manual",
                require_clean=False,
                json=False,
            )
        )
    )

    result = check_retry_controlled_runner_readiness(
        argparse.Namespace(
            db_path=db_path,
            proposal_id="proposal-readiness",
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert result["readiness_score"] == 100
    assert result["chain_complete"] is True
    assert result["observability_status"] == "passed"
    assert result["controlled_execution_enabled"] is False