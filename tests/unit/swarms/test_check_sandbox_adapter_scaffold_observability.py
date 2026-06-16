from src.testing.check_sandbox_adapter_scaffold_observability import (
    _exit_code_for_result,
    _format_result,
    check_sandbox_adapter_scaffold_observability_from_records,
)


def _matrix_record():
    return {
        "type": "replay_lifecycle_retry_real_execution_capability_policy_matrix",
        "real_execution_capability_policy_matrix_id": "matrix-1",
        "real_execution_adapter_request_schema_id": "request-schema-1",
        "real_execution_adapter_contract_id": "contract-1",
        "rendered_command_id": "rendered-1",
        "proposal_id": "proposal-1",
    }


def _scaffold_record(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold",
        "real_execution_sandbox_adapter_scaffold_id": "scaffold-1",
        "real_execution_capability_policy_matrix_id": "matrix-1",
        "real_execution_adapter_request_schema_id": "request-schema-1",
        "real_execution_adapter_contract_id": "contract-1",
        "proposal_id": "proposal-1",
        "rendered_command_id": "rendered-1",
        "schema_version": "real-execution-sandbox-adapter-scaffold/v1",
        "sandbox_adapter_contract_version": "real-execution-sandbox-adapter/v1",
        "sandbox_adapter_scaffold_status": "defined",
        "sandbox_adapter_scaffold_kind": "fail_closed_sandbox_adapter_scaffold",
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
        "sandbox_adapter_scaffold_exists": True,
        "sandbox_adapter_contract_exists": True,
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


def test_check_sandbox_adapter_scaffold_observability_passes_for_fail_closed_scaffold() -> None:
    result = check_sandbox_adapter_scaffold_observability_from_records(
        [_matrix_record(), _scaffold_record()],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "passed"
    assert result["failed_checks"] == []
    assert result["sandbox_adapter_scaffold_observed"] is True
    assert result["sandbox_adapter_scaffold_records"] == 1
    assert result["sandbox_adapter_scaffold_linkage_complete"] is True
    assert result["sandbox_adapter_scaffold_orphans"] == 0
    assert result["sandbox_adapter_scaffold_fail_closed"] == 1
    assert result["sandbox_adapter_scaffold_deny_by_default"] == 1
    assert result["sandbox_adapter_scaffold_sandbox_execution_enabled"] == 0
    assert result["sandbox_adapter_scaffold_execution_performed"] == 0
    assert result["sandbox_adapter_scaffold_subprocess_invoked"] == 0
    assert result["sandbox_adapter_scaffold_real_execution_enabled"] == 0
    assert result["sandbox_adapter_scaffold_external_side_effects_performed"] == 0
    assert result["sandbox_adapter_scaffold_production_paths_mutated"] == 0
    assert result["sandbox_adapter_scaffold_production_secrets_accessed"] == 0
    assert (
        result["brief_key_metrics"][
            "security_real_execution_sandbox_adapter_scaffolds"
        ]
        == 1
    )
    assert "Sandbox adapter scaffold observed" in result["brief_summary"]


def test_check_sandbox_adapter_scaffold_observability_fails_when_scaffold_executes() -> None:
    result = check_sandbox_adapter_scaffold_observability_from_records(
        [
            _matrix_record(),
            _scaffold_record(
                sandbox_execution_enabled=True,
                execution_performed=True,
                subprocess_invoked=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_adapter_scaffold_does_not_enable_sandbox_execution" in result[
        "failed_checks"
    ]
    assert "sandbox_adapter_scaffold_does_not_execute" in result["failed_checks"]
    assert "sandbox_adapter_scaffold_does_not_invoke_subprocess" in result[
        "failed_checks"
    ]


def test_check_sandbox_adapter_scaffold_observability_format_and_exit_code() -> None:
    result = check_sandbox_adapter_scaffold_observability_from_records(
        [_matrix_record(), _scaffold_record()],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    text = _format_result(result)

    assert _exit_code_for_result(result) == 0
    assert "Sandbox adapter scaffold observability: status=passed" in text
    assert "observed=true" in text
    assert "sandbox_execution_enabled=0" in text
    assert "real_execution_enabled=0" in text