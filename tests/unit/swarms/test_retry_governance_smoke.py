import argparse

import pytest

from src.testing.retry_governance_smoke import (
    _exit_code_for_result,
    run_retry_governance_smoke,
)


@pytest.mark.asyncio
async def test_retry_governance_smoke_passes_for_synthetic_trail(tmp_path) -> None:
    result = await run_retry_governance_smoke(
        argparse.Namespace(
            db_path=str(tmp_path / "crdt.db"),
            source="retry-governance-smoke-test",
            proposal_id="proposal-smoke",
            approval_id="approval-smoke",
            plan_id="plan-smoke",
            rendered_command_id="rendered-smoke",
            result_id="result-smoke",
            timeout_profile="standard",
            decision_mode="manual",
            require_clean=False,
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert _exit_code_for_result(result) == 0
    assert result["records_seeded"] == 5
    assert result["rendered_command_results"] == 1
    assert result["trail_summary"]["chain_complete"] is True
    assert result["trail_summary"]["counts"]["rendered_commands"] == 1
    assert result["trail_summary"]["chain_ids"]["rendered_command_ids"] == ["rendered-smoke"]
    assert result["observability"]["status"] == "passed"
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_commands"] == 1
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_command_results"] == 1
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_command_skipped"] == 1
    assert result["exit_codes"]["trail"] == 0
    assert result["exit_codes"]["observability"] == 0


@pytest.mark.asyncio
async def test_retry_governance_smoke_accepts_policy_patient_profile(tmp_path) -> None:
    result = await run_retry_governance_smoke(
        argparse.Namespace(
            db_path=str(tmp_path / "crdt.db"),
            source="retry-governance-smoke-test",
            proposal_id="proposal-smoke-policy",
            approval_id="approval-smoke-policy",
            plan_id="plan-smoke-policy",
            rendered_command_id="rendered-smoke-policy",
            result_id="result-smoke-policy",
            timeout_profile="patient",
            decision_mode="policy",
            require_clean=False,
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert result["records_seeded"] == 5
    assert result["rendered_command_results"] == 1
    assert result["trail_summary"]["counts"]["rendered_commands"] == 1
    assert result["trail_summary"]["decision_modes"]["policy"] == 3
    assert result["trail_summary"]["chain_ids"]["rendered_command_ids"] == ["rendered-smoke-policy"]
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_commands"] == 1
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_command_results"] == 1
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_command_skipped"] == 1


@pytest.mark.asyncio
async def test_retry_governance_smoke_require_clean_fails_when_records_exist(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    first = await run_retry_governance_smoke(
        argparse.Namespace(
            db_path=db_path,
            source="retry-governance-smoke-test",
            proposal_id="proposal-smoke-clean",
            approval_id="approval-smoke-clean",
            plan_id="plan-smoke-clean",
            rendered_command_id="rendered-smoke-clean",
            result_id="result-smoke-clean",
            timeout_profile="standard",
            decision_mode="manual",
            require_clean=False,
            json=False,
        )
    )

    assert first["status"] == "passed"
    assert first["records_seeded"] == 5
    assert first["rendered_command_results"] == 1

    second = await run_retry_governance_smoke(
        argparse.Namespace(
            db_path=db_path,
            source="retry-governance-smoke-test",
            proposal_id="proposal-smoke-clean",
            approval_id="approval-smoke-clean-2",
            plan_id="plan-smoke-clean-2",
            rendered_command_id="rendered-smoke-clean-2",
            result_id="result-smoke-clean-2",
            timeout_profile="standard",
            decision_mode="manual",
            require_clean=True,
            json=False,
        )
    )

    assert second["status"] == "failed"
    assert second["reason"] == "existing_retry_governance_records"
    assert second["records_seeded"] == 0
    assert second["rendered_command_results"] == 0
    assert second["existing_records"] >= 1
    assert _exit_code_for_result(second) == 1


@pytest.mark.asyncio
async def test_retry_governance_smoke_require_clean_passes_on_clean_db(tmp_path) -> None:
    result = await run_retry_governance_smoke(
        argparse.Namespace(
            db_path=str(tmp_path / "crdt.db"),
            source="retry-governance-smoke-test",
            proposal_id="proposal-smoke-clean-first",
            approval_id="approval-smoke-clean-first",
            plan_id="plan-smoke-clean-first",
            rendered_command_id="rendered-smoke-clean-first",
            result_id="result-smoke-clean-first",
            timeout_profile="standard",
            decision_mode="manual",
            require_clean=True,
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert result["reason"] == "ok"
    assert result["records_seeded"] == 5
    assert result["rendered_command_results"] == 1
    assert result["trail_summary"]["counts"]["rendered_commands"] == 1
    assert result["trail_summary"]["chain_ids"]["rendered_command_ids"] == [
        "rendered-smoke-clean-first"
    ]
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_commands"] == 1
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_command_results"] == 1
    assert result["observability"]["brief_key_metrics"]["security_retry_rendered_command_skipped"] == 1
    assert result["existing_records"] == 0
    assert result["exit_codes"]["preflight"] == 0