import pytest

from src.testing.build_real_execution_sandbox_adapter_request_preflight import (
    REAL_EXECUTION_SANDBOX_ADAPTER_REQUEST_PREFLIGHT_TYPE,
    SANDBOX_ADAPTER_REQUEST_PREFLIGHT_SCHEMA_VERSION,
    build_real_execution_sandbox_adapter_request_preflight_record,
)


def _scaffold_record(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold",
        "real_execution_sandbox_adapter_scaffold_id": "scaffold-1",
        "real_execution_capability_policy_matrix_id": "matrix-1",
        "real_execution_adapter_request_schema_id": "request-schema-1",
        "real_execution_adapter_contract_id": "contract-1",
        "post_repair_evidence_check_id": "post-repair-1",
        "guarded_repair_execution_result_id": "guarded-repair-1",
        "controlled_execution_result_id": "controlled-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "decision_mode": "manual",
        "timeout_profile": "standard",
        "schema_version": "real-execution-sandbox-adapter-scaffold/v1",
        "sandbox_adapter_contract_version": "real-execution-sandbox-adapter/v1",
        "sandbox_adapter_scaffold_status": "defined",
        "sandbox_adapter_scaffold_kind": "fail_closed_sandbox_adapter_scaffold",
        "sandbox_adapter_scaffold_exists": True,
        "sandbox_adapter_contract_exists": True,
        "sandbox_required_fields": [
            "sandbox_id",
            "sandbox_workspace_path",
            "sandbox_policy_id",
            "capability_id",
            "execution_level",
            "allowed_input_paths",
            "allowed_output_paths",
            "network_policy",
            "secret_policy",
            "filesystem_policy",
            "resource_limits",
            "rollback_strategy",
            "evidence_strategy",
        ],
        "sandbox_workspace_strategy": "ephemeral_temp_workspace",
        "sandbox_input_strategy": "explicit_allowlist_only",
        "sandbox_output_strategy": "explicit_allowlist_only",
        "sandbox_rollback_strategy": "workspace_destruction",
        "sandbox_evidence_strategy": "post_execution_evidence_required",
        "sandbox_network_policy": "deny",
        "sandbox_secret_policy": "deny",
        "sandbox_filesystem_policy": "no_production_writes",
        "sandbox_production_write_policy": "deny",
        "sandbox_external_side_effect_policy": "deny",
        "sandbox_adapter_fail_closed": True,
        "sandbox_adapter_deny_by_default": True,
        "sandbox_adapter_requires_policy_matrix": True,
        "sandbox_adapter_requires_known_capability": True,
        "sandbox_adapter_requires_known_policy": True,
        "sandbox_adapter_requires_operator_authorization": True,
        "sandbox_adapter_requires_approval_lineage": True,
        "sandbox_adapter_requires_final_gate": True,
        "sandbox_adapter_requires_dry_run_envelope": True,
        "sandbox_adapter_requires_rollback_plan": True,
        "sandbox_adapter_requires_post_execution_evidence": True,
        "sandbox_adapter_rejects_unknown_capability": True,
        "sandbox_adapter_rejects_unknown_policy": True,
        "sandbox_adapter_rejects_orphans": True,
        "sandbox_adapter_rejects_stale_records": True,
        "source_capability_registry_exists": True,
        "source_policy_matrix_exists": True,
        "source_unknown_capability_rejected": True,
        "source_unknown_policy_rejected": True,
        "source_deny_by_default": True,
        "source_fail_closed_default": True,
        "source_sandbox_real_blocked": True,
        "source_policy_gated_real_blocked": True,
        "source_repair_outcome_verified": True,
        "source_capability_count": 7,
        "source_enabled_capability_count": 5,
        "source_blocked_capability_count": 2,
        "source_policy_rule_count": 7,
        "source_approved_policy_count": 5,
        "source_blocked_policy_count": 2,
        "sandbox_adapter_implementation_enabled": False,
        "sandbox_workspace_creation_enabled": False,
        "sandbox_input_materialization_enabled": False,
        "sandbox_command_rendering_enabled": False,
        "sandbox_execution_enabled": False,
        "sandbox_result_generation_enabled": False,
        "adapter_request_generation_enabled": False,
        "adapter_request_execution_enabled": False,
        "adapter_result_generation_enabled": False,
        "capability_execution_enabled": False,
        "policy_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "source_capability_execution_enabled": False,
        "source_policy_execution_enabled": False,
        "source_adapter_request_generation_enabled": False,
        "source_sandbox_execution_enabled": False,
        "source_policy_gated_real_execution_enabled": False,
        "source_execution_performed": False,
        "source_subprocess_invoked": False,
        "source_real_execution_enabled": False,
        "source_external_side_effects_performed": False,
        "recommended_next_action": "surface_sandbox_adapter_scaffold_observability",
        "reason": "real_execution_sandbox_adapter_scaffold_defined_not_runnable",
    }
    item["payload"] = dict(item)
    item.update(overrides)
    return item


def test_build_sandbox_adapter_request_preflight_record_is_fail_closed() -> None:
    record = build_real_execution_sandbox_adapter_request_preflight_record(
        _scaffold_record()
    )

    assert record["type"] == REAL_EXECUTION_SANDBOX_ADAPTER_REQUEST_PREFLIGHT_TYPE
    assert record["schema_version"] == SANDBOX_ADAPTER_REQUEST_PREFLIGHT_SCHEMA_VERSION
    assert record["sandbox_adapter_request_preflight_status"] == "blocked"
    assert (
        record["sandbox_adapter_request_preflight_kind"]
        == "fail_closed_sandbox_adapter_request_preflight"
    )
    assert record["sandbox_adapter_request_preflight_exists"] is True
    assert record["sandbox_adapter_request_preflight_fail_closed"] is True
    assert record["sandbox_adapter_request_preflight_deny_by_default"] is True
    assert record["real_execution_sandbox_adapter_scaffold_id"] == "scaffold-1"
    assert record["real_execution_capability_policy_matrix_id"] == "matrix-1"
    assert record["sandbox_request_allowed_input_paths"] == []
    assert record["sandbox_request_allowed_output_paths"] == []
    assert record["sandbox_workspace_strategy"] == "ephemeral_temp_workspace"
    assert record["sandbox_network_policy"] == "deny"
    assert record["sandbox_secret_policy"] == "deny"
    assert record["sandbox_filesystem_policy"] == "no_production_writes"
    assert record["sandbox_adapter_request_generation_allowed"] is False
    assert record["sandbox_adapter_request_generation_enabled"] is False
    assert record["sandbox_workspace_creation_allowed"] is False
    assert record["sandbox_workspace_creation_enabled"] is False
    assert record["sandbox_input_materialization_allowed"] is False
    assert record["sandbox_input_materialization_enabled"] is False
    assert record["sandbox_command_rendering_allowed"] is False
    assert record["sandbox_command_rendering_enabled"] is False
    assert record["sandbox_execution_allowed"] is False
    assert record["sandbox_execution_enabled"] is False
    assert record["sandbox_result_generation_allowed"] is False
    assert record["sandbox_result_generation_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_enabled"] is False
    assert record["external_side_effects_performed"] is False
    assert record["production_paths_mutated"] is False
    assert record["production_secrets_accessed"] is False
    assert (
        record["recommended_next_action"]
        == "surface_sandbox_adapter_request_preflight_observability"
    )
    assert record["reason"] == "sandbox_adapter_request_preflight_defined_blocked_not_runnable"
    assert record["payload"]["real_execution_sandbox_adapter_request_preflight_id"] == (
        record["real_execution_sandbox_adapter_request_preflight_id"]
    )


def test_build_sandbox_adapter_request_preflight_record_is_stable() -> None:
    first = build_real_execution_sandbox_adapter_request_preflight_record(
        _scaffold_record()
    )
    second = build_real_execution_sandbox_adapter_request_preflight_record(
        _scaffold_record()
    )

    assert first["real_execution_sandbox_adapter_request_preflight_id"] == (
        second["real_execution_sandbox_adapter_request_preflight_id"]
    )


def test_build_sandbox_adapter_request_preflight_rejects_enabled_source_scaffold() -> None:
    with pytest.raises(ValueError, match="sandbox_execution_enabled=false"):
        build_real_execution_sandbox_adapter_request_preflight_record(
            _scaffold_record(sandbox_execution_enabled=True)
        )


def test_build_sandbox_adapter_request_preflight_rejects_missing_required_field() -> None:
    source = _scaffold_record(
        sandbox_required_fields=[
            "sandbox_id",
            "sandbox_workspace_path",
            "sandbox_policy_id",
        ]
    )

    with pytest.raises(ValueError, match="missing required field"):
        build_real_execution_sandbox_adapter_request_preflight_record(source)