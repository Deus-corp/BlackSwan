import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_sandbox_adapter_scaffold import (
    REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE,
    SANDBOX_ADAPTER_CONTRACT_VERSION,
    SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION,
    build_real_execution_sandbox_adapter_scaffold_record,
    build_real_execution_sandbox_adapter_scaffold_records,
)


def _matrix(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_capability_policy_matrix",
        "real_execution_capability_policy_matrix_id": "matrix-1",
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
        "schema_version": "real-execution-capability-policy-matrix/v1",
        "capability_registry_version": "real-execution-capability-registry/v1",
        "policy_matrix_version": "real-execution-policy-matrix/v1",
        "matrix_status": "defined",
        "matrix_kind": "capability_registry_policy_matrix",
        "capability_registry_exists": True,
        "policy_matrix_exists": True,
        "capability_count": 7,
        "enabled_capability_count": 5,
        "blocked_capability_count": 2,
        "policy_rule_count": 7,
        "approved_policy_count": 5,
        "blocked_policy_count": 2,
        "blocked_capabilities": [
            "capability.sandbox_real.repair_workspace",
            "capability.policy_gated_real.production_effect",
        ],
        "blocked_policies": [
            "policy.sandbox_real.blocked_until_adapter_pr",
            "policy.policy_gated_real.blocked_until_future_milestone",
        ],
        "unknown_capability_rejected": True,
        "unknown_policy_rejected": True,
        "deny_by_default": True,
        "fail_closed_default": True,
        "sandbox_real_blocked": True,
        "policy_gated_real_blocked": True,
        "sandbox_real_requires_separate_adapter_pr": True,
        "policy_gated_real_requires_future_reviewed_milestone": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
        "capability_execution_enabled": False,
        "policy_execution_enabled": False,
        "adapter_request_generation_enabled": False,
        "adapter_request_execution_enabled": False,
        "adapter_result_generation_enabled": False,
        "sandbox_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "source_adapter_request_schema_exists": True,
        "source_adapter_contract_exists": True,
        "source_adapter_result_schema_exists": True,
        "source_fail_closed_default": True,
        "source_deny_by_default": True,
        "source_unknown_capability_rejected": True,
        "source_unknown_policy_rejected": True,
        "source_request_generation_enabled": False,
        "source_request_execution_enabled": False,
        "source_sandbox_execution_enabled": False,
        "source_policy_gated_real_execution_enabled": False,
        "source_execution_performed": False,
        "source_subprocess_invoked": False,
        "source_real_execution_enabled": False,
        "source_external_side_effects_performed": False,
        "source_request_schema_status": "defined",
        "source_post_repair_status": "passed",
        "source_repair_outcome_verified": True,
        "source_repair_targets_expected_count": 9,
        "source_repair_targets_verified_count": 9,
        "recommended_next_action": "prepare_sandbox_adapter_scaffold",
    }
    item.update(overrides)
    return item


def test_sandbox_adapter_scaffold_record_is_fail_closed() -> None:
    record = build_real_execution_sandbox_adapter_scaffold_record(_matrix())

    assert record["type"] == REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE
    assert record["schema_version"] == SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION
    assert record["sandbox_adapter_contract_version"] == SANDBOX_ADAPTER_CONTRACT_VERSION
    assert record["sandbox_adapter_scaffold_status"] == "defined"
    assert record["sandbox_adapter_scaffold_exists"] is True
    assert record["sandbox_adapter_contract_exists"] is True
    assert record["sandbox_adapter_fail_closed"] is True
    assert record["sandbox_adapter_deny_by_default"] is True
    assert record["sandbox_adapter_requires_policy_matrix"] is True
    assert record["sandbox_adapter_requires_known_capability"] is True
    assert record["sandbox_adapter_requires_known_policy"] is True
    assert record["sandbox_adapter_requires_operator_authorization"] is True
    assert record["sandbox_adapter_requires_approval_lineage"] is True
    assert record["sandbox_adapter_requires_final_gate"] is True
    assert record["sandbox_adapter_requires_dry_run_envelope"] is True
    assert record["sandbox_adapter_requires_rollback_plan"] is True
    assert record["sandbox_adapter_requires_post_execution_evidence"] is True
    assert record["sandbox_adapter_rejects_unknown_capability"] is True
    assert record["sandbox_adapter_rejects_unknown_policy"] is True
    assert record["sandbox_adapter_implementation_enabled"] is False
    assert record["sandbox_workspace_creation_enabled"] is False
    assert record["sandbox_input_materialization_enabled"] is False
    assert record["sandbox_command_rendering_enabled"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["sandbox_result_generation_enabled"] is False
    assert record["adapter_request_generation_enabled"] is False
    assert record["adapter_request_execution_enabled"] is False
    assert record["adapter_result_generation_enabled"] is False
    assert record["capability_execution_enabled"] is False
    assert record["policy_execution_enabled"] is False
    assert record["policy_gated_real_execution_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False


def test_sandbox_adapter_scaffold_defines_sandbox_boundaries() -> None:
    record = build_real_execution_sandbox_adapter_scaffold_record(_matrix())

    assert "sandbox_id" in record["sandbox_required_fields"]
    assert "sandbox_workspace_path" in record["sandbox_required_fields"]
    assert "network_policy" in record["sandbox_required_fields"]
    assert "secret_policy" in record["sandbox_required_fields"]
    assert "rollback_strategy" in record["sandbox_required_fields"]
    assert "evidence_strategy" in record["sandbox_required_fields"]

    assert record["sandbox_workspace_strategy"] == "ephemeral_temp_workspace"
    assert record["sandbox_input_strategy"] == "explicit_allowlist_only"
    assert record["sandbox_output_strategy"] == "explicit_allowlist_only"
    assert record["sandbox_rollback_strategy"] == "workspace_destruction"
    assert record["sandbox_evidence_strategy"] == "post_execution_evidence_required"
    assert record["sandbox_network_policy"] == "deny"
    assert record["sandbox_secret_policy"] == "deny"
    assert record["sandbox_filesystem_policy"] == "no_production_writes"
    assert record["sandbox_production_write_policy"] == "deny"
    assert record["sandbox_external_side_effect_policy"] == "deny"


def test_sandbox_adapter_scaffold_carries_source_matrix_state() -> None:
    record = build_real_execution_sandbox_adapter_scaffold_record(_matrix())

    assert record["source_matrix_status"] == "defined"
    assert record["source_capability_registry_exists"] is True
    assert record["source_policy_matrix_exists"] is True
    assert record["source_capability_count"] == 7
    assert record["source_enabled_capability_count"] == 5
    assert record["source_blocked_capability_count"] == 2
    assert record["source_policy_rule_count"] == 7
    assert record["source_approved_policy_count"] == 5
    assert record["source_blocked_policy_count"] == 2
    assert record["source_unknown_capability_rejected"] is True
    assert record["source_unknown_policy_rejected"] is True
    assert record["source_deny_by_default"] is True
    assert record["source_fail_closed_default"] is True
    assert record["source_sandbox_real_blocked"] is True
    assert record["source_policy_gated_real_blocked"] is True
    assert record["source_capability_execution_enabled"] is False
    assert record["source_policy_execution_enabled"] is False
    assert record["source_adapter_request_generation_enabled"] is False
    assert record["source_sandbox_execution_enabled"] is False
    assert record["source_policy_gated_real_execution_enabled"] is False
    assert record["source_execution_performed"] is False
    assert record["source_subprocess_invoked"] is False
    assert record["source_real_execution_enabled"] is False
    assert record["source_external_side_effects_performed"] is False
    assert record["recommended_next_action"] == "surface_sandbox_adapter_scaffold_observability"


def test_sandbox_adapter_scaffold_rejects_enabled_sandbox_execution() -> None:
    with pytest.raises(
        ValueError,
        match="source capability policy matrix requires sandbox_execution_enabled=false",
    ):
        build_real_execution_sandbox_adapter_scaffold_record(
            _matrix(sandbox_execution_enabled=True)
        )


def test_sandbox_adapter_scaffold_rejects_real_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="source capability policy matrix requires real_execution_enabled=false",
    ):
        build_real_execution_sandbox_adapter_scaffold_record(
            _matrix(real_execution_enabled=True)
        )


def test_sandbox_adapter_scaffold_rejects_missing_sandbox_block() -> None:
    with pytest.raises(
        ValueError,
        match="source matrix must block sandbox real capability",
    ):
        build_real_execution_sandbox_adapter_scaffold_record(
            _matrix(blocked_capabilities=["capability.policy_gated_real.production_effect"])
        )


@pytest.mark.asyncio
async def test_sandbox_adapter_scaffold_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_matrix())

    args = argparse.Namespace(
        db_path=db_path,
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
        real_execution_capability_policy_matrix_id="",
        source="sandbox-adapter-scaffold-test",
        json=False,
    )

    first = await build_real_execution_sandbox_adapter_scaffold_records(args)
    second = await build_real_execution_sandbox_adapter_scaffold_records(args)

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["sandbox_adapter_scaffold_status"] == "defined"
    assert first[0]["sandbox_adapter_implementation_enabled"] is False
    assert first[0]["sandbox_workspace_creation_enabled"] is False
    assert first[0]["sandbox_execution_enabled"] is False
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False
    assert first[0]["real_execution_enabled"] is False