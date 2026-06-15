import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_adapter_request_schema import (
    EXPECTED_REQUEST_SCHEMA_VERSION,
    REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE,
    REQUEST_SCHEMA_SCAFFOLD_VERSION,
    build_real_execution_adapter_request_schema_record,
    build_real_execution_adapter_request_schema_records,
)


def _contract(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_adapter_contract",
        "real_execution_adapter_contract_id": "adapter-contract-1",
        "post_repair_evidence_check_id": "post-repair-check-1",
        "guarded_repair_execution_result_id": "guarded-repair-result-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "decision_mode": "manual",
        "timeout_profile": "standard",
        "schema_version": "real-execution-adapter-contract/v1",
        "adapter_request_schema_version": "real-execution-adapter-request/v1",
        "adapter_result_schema_version": "real-execution-adapter-result/v1",
        "contract_status": "defined",
        "contract_kind": "policy_gated_real_execution_adapter",
        "adapter_contract_exists": True,
        "adapter_request_schema_exists": True,
        "adapter_result_schema_exists": True,
        "fail_closed_default": True,
        "sandbox_first": True,
        "capability_scoped": True,
        "policy_gated": True,
        "approval_gated": True,
        "rollback_required": True,
        "post_execution_evidence_required": True,
        "audit_record_required": True,
        "direct_rendered_command_execution_allowed": False,
        "arbitrary_shell_execution_allowed": False,
        "unknown_capability_rejected": True,
        "unknown_policy_rejected": True,
        "missing_approval_rejected": True,
        "missing_final_gate_rejected": True,
        "missing_dry_run_envelope_rejected": True,
        "missing_rollback_plan_rejected": True,
        "missing_post_execution_evidence_rejected": True,
        "orphaned_records_rejected": True,
        "stale_records_rejected": True,
        "supported_execution_levels": [
            "advisory",
            "dry-run",
            "noop",
            "guarded-read-only",
            "guarded-repair",
            "sandbox-real",
            "policy-gated-real",
        ],
        "enabled_execution_levels": [
            "advisory",
            "dry-run",
            "noop",
            "guarded-read-only",
            "guarded-repair",
        ],
        "disabled_execution_levels": [
            "sandbox-real",
            "policy-gated-real",
        ],
        "adapter_request_required_fields": [
            "adapter_request_id",
            "proposal_id",
            "rendered_command_id",
            "capability_id",
            "execution_level",
            "policy_id",
            "approval_id",
            "approval_transition_id",
            "final_gate_id",
            "dry_run_envelope_id",
            "operator_authorized",
            "sandbox_required",
            "rollback_required",
            "post_execution_evidence_required",
        ],
        "adapter_result_required_fields": [
            "adapter_result_id",
            "adapter_request_id",
            "execution_status",
            "execution_level",
            "capability_id",
            "policy_id",
            "sandbox_id",
            "exit_code",
            "stdout_digest",
            "stderr_digest",
            "duration_seconds",
            "execution_performed",
            "subprocess_invoked",
            "real_execution_enabled",
            "external_side_effects_performed",
            "rollback_plan_id",
            "rollback_performed",
            "post_execution_evidence_id",
            "recommended_next_action",
        ],
        "required_gate_fields": [
            "operator_authorized",
            "policy_authorized",
            "capability_allowed",
            "approval_transition_status",
            "final_gate_status",
            "dry_run_envelope_ready",
            "rollback_plan_present",
            "post_execution_evidence_required",
            "security_validation_passed",
            "readiness_validation_passed",
        ],
        "recommended_next_action": "prepare_real_execution_adapter_request_schema",
        "source_post_repair_status": "passed",
        "source_repair_outcome_verified": True,
        "source_post_repair_next_action": "close_repair_loop",
        "source_repair_targets_expected_count": 9,
        "source_repair_targets_verified_count": 9,
        "adapter_implementation_enabled": False,
        "adapter_request_generation_enabled": False,
        "adapter_result_generation_enabled": False,
        "sandbox_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "reason": "real_execution_adapter_contract_defined_not_runnable",
    }
    item.update(overrides)
    return item


def test_build_request_schema_record_is_fail_closed_and_not_runnable() -> None:
    record = build_real_execution_adapter_request_schema_record(_contract())

    assert record["type"] == REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE
    assert record["schema_version"] == REQUEST_SCHEMA_SCAFFOLD_VERSION
    assert record["adapter_request_schema_version"] == EXPECTED_REQUEST_SCHEMA_VERSION
    assert record["adapter_request_schema_status"] == "defined"
    assert record["adapter_request_schema_exists"] is True
    assert record["adapter_contract_exists"] is True
    assert record["adapter_result_schema_exists"] is True
    assert record["fail_closed_default"] is True
    assert record["deny_by_default"] is True
    assert record["unknown_capability_rejected"] is True
    assert record["unknown_policy_rejected"] is True
    assert record["unsupported_execution_level_rejected"] is True
    assert record["sandbox_required_default"] is True
    assert record["rollback_required_default"] is True
    assert record["post_execution_evidence_required_default"] is True
    assert record["operator_authorized_required"] is True
    assert record["policy_authorized_required"] is True
    assert record["capability_allowed_required"] is True
    assert record["security_validation_required"] is True
    assert record["readiness_validation_required"] is True
    assert record["direct_rendered_command_execution_allowed"] is False
    assert record["arbitrary_shell_execution_allowed"] is False
    assert record["request_generation_enabled"] is False
    assert record["request_execution_enabled"] is False
    assert record["adapter_implementation_enabled"] is False
    assert record["adapter_result_generation_enabled"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["policy_gated_real_execution_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False


def test_build_request_schema_record_carries_required_fields_and_rules() -> None:
    record = build_real_execution_adapter_request_schema_record(_contract())

    assert "adapter_request_id" in record["request_required_fields"]
    assert "capability_id" in record["request_required_fields"]
    assert "policy_id" in record["request_required_fields"]
    assert "rollback_required" in record["request_required_fields"]
    assert "post_execution_evidence_required" in record["request_required_fields"]

    assert "operator_authorized" in record["required_gate_fields"]
    assert "policy_authorized" in record["required_gate_fields"]
    assert "capability_allowed" in record["required_gate_fields"]
    assert "rollback_plan_present" in record["required_gate_fields"]
    assert "post_execution_evidence_required" in record["required_gate_fields"]

    assert "sandbox-real" in record["request_execution_levels"]
    assert "policy-gated-real" in record["request_execution_levels"]
    assert "contract_must_be_defined" in record["request_generation_rules"]
    assert "unknown_policy" in record["default_rejection_reasons"]
    assert "unknown_capability" in record["default_rejection_reasons"]


def test_build_request_schema_record_carries_source_contract_state() -> None:
    record = build_real_execution_adapter_request_schema_record(_contract())

    assert record["source_contract_status"] == "defined"
    assert record["source_adapter_contract_exists"] is True
    assert record["source_adapter_request_schema_exists"] is True
    assert record["source_adapter_result_schema_exists"] is True
    assert record["source_fail_closed_default"] is True
    assert record["source_sandbox_first"] is True
    assert record["source_policy_gated"] is True
    assert record["source_capability_scoped"] is True
    assert record["source_unknown_capability_rejected"] is True
    assert record["source_unknown_policy_rejected"] is True
    assert record["source_adapter_implementation_enabled"] is False
    assert record["source_sandbox_execution_enabled"] is False
    assert record["source_policy_gated_real_execution_enabled"] is False
    assert record["source_execution_performed"] is False
    assert record["source_subprocess_invoked"] is False
    assert record["source_real_execution_enabled"] is False
    assert record["source_external_side_effects_performed"] is False
    assert record["source_post_repair_status"] == "passed"
    assert record["source_repair_outcome_verified"] is True
    assert record["source_repair_targets_expected_count"] == 9
    assert record["source_repair_targets_verified_count"] == 9
    assert (
        record["recommended_next_action"]
        == "prepare_capability_registry_and_policy_matrix"
    )


def test_build_request_schema_rejects_enabled_contract_adapter() -> None:
    with pytest.raises(
        ValueError,
        match="source contract requires adapter_implementation_enabled=false",
    ):
        build_real_execution_adapter_request_schema_record(
            _contract(adapter_implementation_enabled=True)
        )


def test_build_request_schema_rejects_contract_real_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="source contract requires real_execution_enabled=false",
    ):
        build_real_execution_adapter_request_schema_record(
            _contract(real_execution_enabled=True)
        )


def test_build_request_schema_rejects_missing_capability_field() -> None:
    contract = _contract()
    contract["adapter_request_required_fields"] = [
        item
        for item in contract["adapter_request_required_fields"]
        if item != "capability_id"
    ]

    with pytest.raises(
        ValueError,
        match="source contract missing request field: capability_id",
    ):
        build_real_execution_adapter_request_schema_record(contract)


def test_build_request_schema_rejects_enabled_sandbox_real_level() -> None:
    with pytest.raises(
        ValueError,
        match="source contract must not enable sandbox-real",
    ):
        build_real_execution_adapter_request_schema_record(
            _contract(
                enabled_execution_levels=[
                    "advisory",
                    "dry-run",
                    "noop",
                    "guarded-read-only",
                    "guarded-repair",
                    "sandbox-real",
                ]
            )
        )


@pytest.mark.asyncio
async def test_build_request_schema_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_contract())

    args = argparse.Namespace(
        db_path=db_path,
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
        real_execution_adapter_contract_id="",
        source="real-execution-adapter-request-schema-test",
        json=False,
    )

    first = await build_real_execution_adapter_request_schema_records(args)
    second = await build_real_execution_adapter_request_schema_records(args)

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["adapter_request_schema_status"] == "defined"
    assert first[0]["request_generation_enabled"] is False
    assert first[0]["request_execution_enabled"] is False
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False
    assert first[0]["real_execution_enabled"] is False