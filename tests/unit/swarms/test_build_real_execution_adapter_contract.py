import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_adapter_contract import (
    CONTRACT_SCHEMA_VERSION,
    REAL_EXECUTION_ADAPTER_CONTRACT_TYPE,
    REQUEST_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    build_real_execution_adapter_contract_record,
    build_real_execution_adapter_contract_records,
)


def _post_repair_check(**overrides):
    item = {
        "type": "replay_lifecycle_retry_post_repair_evidence_check",
        "post_repair_evidence_check_id": "post-repair-check-1",
        "guarded_repair_execution_result_id": "guarded-repair-result-1",
        "real_execution_repair_readiness_gate_id": "repair-readiness-gate-1",
        "real_execution_repair_noop_feedback_id": "repair-feedback-1",
        "real_execution_repair_noop_result_id": "repair-noop-1",
        "real_execution_repair_dry_run_envelope_id": "repair-envelope-1",
        "real_execution_repair_final_gate_id": "repair-final-gate-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "decision_mode": "manual",
        "timeout_profile": "standard",
        "post_repair_status": "passed",
        "post_repair_evidence_check_allowed": True,
        "post_repair_evidence_check_enabled": True,
        "post_repair_evidence_marker_observed": True,
        "post_repair_evidence_exit_code": 0,
        "repair_outcome_verified": True,
        "repair_targets_expected_count": 9,
        "repair_targets_verified_count": 9,
        "repair_targets_missing": [],
        "repair_targets_unexpected": [],
        "recommended_next_action": "close_repair_loop",
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
    }
    item.update(overrides)
    return item


def test_build_real_execution_adapter_contract_record_is_not_runnable() -> None:
    record = build_real_execution_adapter_contract_record(_post_repair_check())

    assert record["type"] == REAL_EXECUTION_ADAPTER_CONTRACT_TYPE
    assert record["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert record["adapter_request_schema_version"] == REQUEST_SCHEMA_VERSION
    assert record["adapter_result_schema_version"] == RESULT_SCHEMA_VERSION
    assert record["contract_status"] == "defined"
    assert record["adapter_contract_exists"] is True
    assert record["adapter_request_schema_exists"] is True
    assert record["adapter_result_schema_exists"] is True
    assert record["fail_closed_default"] is True
    assert record["sandbox_first"] is True
    assert record["capability_scoped"] is True
    assert record["policy_gated"] is True
    assert record["approval_gated"] is True
    assert record["rollback_required"] is True
    assert record["post_execution_evidence_required"] is True
    assert record["audit_record_required"] is True
    assert record["unknown_capability_rejected"] is True
    assert record["unknown_policy_rejected"] is True
    assert record["direct_rendered_command_execution_allowed"] is False
    assert record["arbitrary_shell_execution_allowed"] is False
    assert record["adapter_implementation_enabled"] is False
    assert record["adapter_request_generation_enabled"] is False
    assert record["adapter_result_generation_enabled"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["policy_gated_real_execution_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False


def test_build_real_execution_adapter_contract_records_required_schemas() -> None:
    record = build_real_execution_adapter_contract_record(_post_repair_check())

    assert "adapter_request_id" in record["adapter_request_required_fields"]
    assert "capability_id" in record["adapter_request_required_fields"]
    assert "policy_id" in record["adapter_request_required_fields"]
    assert "rollback_required" in record["adapter_request_required_fields"]
    assert "post_execution_evidence_required" in record["adapter_request_required_fields"]

    assert "adapter_result_id" in record["adapter_result_required_fields"]
    assert "adapter_request_id" in record["adapter_result_required_fields"]
    assert "real_execution_enabled" in record["adapter_result_required_fields"]
    assert "external_side_effects_performed" in record["adapter_result_required_fields"]
    assert "rollback_plan_id" in record["adapter_result_required_fields"]
    assert "post_execution_evidence_id" in record["adapter_result_required_fields"]


def test_build_real_execution_adapter_contract_records_execution_levels() -> None:
    record = build_real_execution_adapter_contract_record(_post_repair_check())

    assert "guarded-repair" in record["enabled_execution_levels"]
    assert "sandbox-real" in record["supported_execution_levels"]
    assert "policy-gated-real" in record["supported_execution_levels"]
    assert "sandbox-real" in record["disabled_execution_levels"]
    assert "policy-gated-real" in record["disabled_execution_levels"]


def test_build_real_execution_adapter_contract_requires_verified_post_repair() -> None:
    with pytest.raises(
        ValueError,
        match="adapter contract requires verified repair outcome",
    ):
        build_real_execution_adapter_contract_record(
            _post_repair_check(repair_outcome_verified=False)
        )


def test_build_real_execution_adapter_contract_rejects_post_check_real_execution() -> None:
    with pytest.raises(
        ValueError,
        match="adapter contract rejects post-check real execution enabled",
    ):
        build_real_execution_adapter_contract_record(
            _post_repair_check(real_execution_enabled=True)
        )


def test_build_real_execution_adapter_contract_rejects_missing_targets() -> None:
    with pytest.raises(
        ValueError,
        match="adapter contract rejects missing repair targets",
    ):
        build_real_execution_adapter_contract_record(
            _post_repair_check(repair_targets_missing=["evidence_published"])
        )


@pytest.mark.asyncio
async def test_build_real_execution_adapter_contract_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_post_repair_check())

    args = argparse.Namespace(
        db_path=db_path,
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
        post_repair_evidence_check_id="",
        source="real-execution-adapter-contract-test",
        json=False,
    )

    first = await build_real_execution_adapter_contract_records(args)
    second = await build_real_execution_adapter_contract_records(args)

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["contract_status"] == "defined"
    assert first[0]["adapter_contract_exists"] is True
    assert first[0]["adapter_request_schema_exists"] is True
    assert first[0]["adapter_result_schema_exists"] is True
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False
    assert first[0]["real_execution_enabled"] is False