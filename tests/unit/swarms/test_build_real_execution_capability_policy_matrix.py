import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_capability_policy_matrix import (
    CAPABILITY_REGISTRY_VERSION,
    MATRIX_SCHEMA_VERSION,
    POLICY_MATRIX_VERSION,
    REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE,
    build_real_execution_capability_policy_matrix_record,
    build_real_execution_capability_policy_matrix_records,
)


def _request_schema(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_adapter_request_schema",
        "real_execution_adapter_request_schema_id": "request-schema-1",
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
        "schema_version": "real-execution-adapter-request-schema-scaffold/v1",
        "adapter_request_schema_version": "real-execution-adapter-request/v1",
        "adapter_contract_schema_version": "real-execution-adapter-contract/v1",
        "adapter_result_schema_version": "real-execution-adapter-result/v1",
        "adapter_request_schema_status": "defined",
        "adapter_request_schema_kind": "policy_gated_real_execution_adapter_request",
        "adapter_request_schema_exists": True,
        "adapter_contract_exists": True,
        "adapter_result_schema_exists": True,
        "fail_closed_default": True,
        "deny_by_default": True,
        "unknown_capability_rejected": True,
        "unknown_policy_rejected": True,
        "unsupported_execution_level_rejected": True,
        "missing_operator_authorization_rejected": True,
        "missing_approval_lineage_rejected": True,
        "missing_final_gate_rejected": True,
        "missing_dry_run_envelope_rejected": True,
        "missing_rollback_plan_rejected": True,
        "missing_post_execution_evidence_rejected": True,
        "orphaned_contract_rejected": True,
        "stale_contract_rejected": True,
        "sandbox_required_default": True,
        "rollback_required_default": True,
        "post_execution_evidence_required_default": True,
        "operator_authorized_required": True,
        "policy_authorized_required": True,
        "capability_allowed_required": True,
        "security_validation_required": True,
        "readiness_validation_required": True,
        "direct_rendered_command_execution_allowed": False,
        "arbitrary_shell_execution_allowed": False,
        "request_generation_enabled": False,
        "request_execution_enabled": False,
        "adapter_implementation_enabled": False,
        "adapter_result_generation_enabled": False,
        "sandbox_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "source_adapter_contract_exists": True,
        "source_adapter_request_schema_exists": True,
        "source_adapter_result_schema_exists": True,
        "source_fail_closed_default": True,
        "source_sandbox_first": True,
        "source_policy_gated": True,
        "source_capability_scoped": True,
        "source_unknown_capability_rejected": True,
        "source_unknown_policy_rejected": True,
        "source_adapter_implementation_enabled": False,
        "source_sandbox_execution_enabled": False,
        "source_policy_gated_real_execution_enabled": False,
        "source_execution_performed": False,
        "source_subprocess_invoked": False,
        "source_real_execution_enabled": False,
        "source_external_side_effects_performed": False,
        "source_contract_status": "defined",
        "source_post_repair_status": "passed",
        "source_repair_outcome_verified": True,
        "source_repair_targets_expected_count": 9,
        "source_repair_targets_verified_count": 9,
        "request_required_fields": [
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
        "request_execution_levels": [
            "advisory",
            "dry-run",
            "noop",
            "guarded-read-only",
            "guarded-repair",
            "sandbox-real",
            "policy-gated-real",
        ],
        "request_generation_rules": [
            "contract_must_be_defined",
            "policy_must_be_known",
            "capability_must_be_known",
            "execution_level_must_be_supported",
            "sandbox_real_must_remain_disabled_until_policy_matrix",
            "policy_gated_real_must_remain_disabled_until_future_milestone",
            "rollback_must_be_required",
            "post_execution_evidence_must_be_required",
            "operator_authorization_must_be_required",
            "approval_lineage_must_be_required",
            "dry_run_envelope_must_be_required",
            "final_gate_must_be_required",
        ],
        "default_rejection_reasons": [
            "unknown_policy",
            "unknown_capability",
            "unsupported_execution_level",
            "missing_operator_authorization",
            "missing_approval_lineage",
            "missing_final_gate",
            "missing_dry_run_envelope",
            "missing_rollback_plan",
            "missing_post_execution_evidence_requirement",
            "stale_contract",
            "orphaned_contract",
        ],
        "recommended_next_action": "prepare_capability_registry_and_policy_matrix",
    }
    item.update(overrides)
    return item


def test_capability_policy_matrix_record_is_fail_closed() -> None:
    record = build_real_execution_capability_policy_matrix_record(_request_schema())

    assert record["type"] == REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE
    assert record["schema_version"] == MATRIX_SCHEMA_VERSION
    assert record["capability_registry_version"] == CAPABILITY_REGISTRY_VERSION
    assert record["policy_matrix_version"] == POLICY_MATRIX_VERSION
    assert record["matrix_status"] == "defined"
    assert record["capability_registry_exists"] is True
    assert record["policy_matrix_exists"] is True
    assert record["capability_count"] == 7
    assert record["enabled_capability_count"] == 5
    assert record["blocked_capability_count"] == 2
    assert record["policy_rule_count"] == 7
    assert record["approved_policy_count"] == 5
    assert record["blocked_policy_count"] == 2
    assert record["unknown_capability_rejected"] is True
    assert record["unknown_policy_rejected"] is True
    assert record["deny_by_default"] is True
    assert record["fail_closed_default"] is True
    assert record["sandbox_real_blocked"] is True
    assert record["policy_gated_real_blocked"] is True
    assert record["external_side_effects_allowed"] is False
    assert record["production_paths_allowed"] is False
    assert record["production_secrets_allowed"] is False
    assert record["capability_execution_enabled"] is False
    assert record["policy_execution_enabled"] is False
    assert record["adapter_request_generation_enabled"] is False
    assert record["adapter_request_execution_enabled"] is False
    assert record["adapter_result_generation_enabled"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["policy_gated_real_execution_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False


def test_capability_policy_matrix_carries_blocked_real_capabilities() -> None:
    record = build_real_execution_capability_policy_matrix_record(_request_schema())

    assert "capability.sandbox_real.repair_workspace" in record["blocked_capabilities"]
    assert (
        "capability.policy_gated_real.production_effect"
        in record["blocked_capabilities"]
    )
    assert "policy.sandbox_real.blocked_until_adapter_pr" in record["blocked_policies"]
    assert (
        "policy.policy_gated_real.blocked_until_future_milestone"
        in record["blocked_policies"]
    )


def test_capability_policy_matrix_carries_source_request_schema_state() -> None:
    record = build_real_execution_capability_policy_matrix_record(_request_schema())

    assert record["source_request_schema_status"] == "defined"
    assert record["source_adapter_request_schema_exists"] is True
    assert record["source_adapter_contract_exists"] is True
    assert record["source_adapter_result_schema_exists"] is True
    assert record["source_fail_closed_default"] is True
    assert record["source_deny_by_default"] is True
    assert record["source_unknown_capability_rejected"] is True
    assert record["source_unknown_policy_rejected"] is True
    assert record["source_request_generation_enabled"] is False
    assert record["source_request_execution_enabled"] is False
    assert record["source_sandbox_execution_enabled"] is False
    assert record["source_policy_gated_real_execution_enabled"] is False
    assert record["source_execution_performed"] is False
    assert record["source_subprocess_invoked"] is False
    assert record["source_real_execution_enabled"] is False
    assert record["source_external_side_effects_performed"] is False
    assert record["recommended_next_action"] == "prepare_sandbox_adapter_scaffold"


def test_capability_policy_matrix_rejects_request_generation_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="source request schema requires request_generation_enabled=false",
    ):
        build_real_execution_capability_policy_matrix_record(
            _request_schema(request_generation_enabled=True)
        )


def test_capability_policy_matrix_rejects_real_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="source request schema requires real_execution_enabled=false",
    ):
        build_real_execution_capability_policy_matrix_record(
            _request_schema(real_execution_enabled=True)
        )


def test_capability_policy_matrix_rejects_missing_policy_rule_source() -> None:
    schema = _request_schema()
    schema["request_generation_rules"] = [
        item
        for item in schema["request_generation_rules"]
        if item != "policy_must_be_known"
    ]

    with pytest.raises(
        ValueError,
        match="source request schema missing generation rule: policy_must_be_known",
    ):
        build_real_execution_capability_policy_matrix_record(schema)


@pytest.mark.asyncio
async def test_capability_policy_matrix_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_request_schema())

    args = argparse.Namespace(
        db_path=db_path,
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
        real_execution_adapter_request_schema_id="",
        source="capability-policy-matrix-test",
        json=False,
    )

    first = await build_real_execution_capability_policy_matrix_records(args)
    second = await build_real_execution_capability_policy_matrix_records(args)

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["matrix_status"] == "defined"
    assert first[0]["capability_registry_exists"] is True
    assert first[0]["policy_matrix_exists"] is True
    assert first[0]["sandbox_real_blocked"] is True
    assert first[0]["policy_gated_real_blocked"] is True
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False
    assert first[0]["real_execution_enabled"] is False