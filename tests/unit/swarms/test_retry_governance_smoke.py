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
            result_id="result-smoke",
            timeout_profile="standard",
            decision_mode="manual",
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert _exit_code_for_result(result) == 0
    assert result["records_seeded"] == 4
    assert result["trail_summary"]["chain_complete"] is True
    assert result["observability"]["status"] == "passed"
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
            result_id="result-smoke-policy",
            timeout_profile="patient",
            decision_mode="policy",
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert result["trail_summary"]["decision_modes"]["policy"] == 2