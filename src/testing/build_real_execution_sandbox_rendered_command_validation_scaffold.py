"""Build fail-closed sandbox rendered command validation scaffold records.

This artifact prepares a blocked rendered command validation scaffold from a
valid sandbox rendered command scaffold.

It intentionally does not:
- generate rendered commands,
- materialize rendered commands,
- validate rendered commands,
- mark rendered commands executable,
- render sandbox commands,
- create sandbox workspaces,
- run sandbox execution,
- generate adapter results,
- invoke subprocesses,
- enable real execution,
- perform external side effects.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

SANDBOX_RENDERED_COMMAND_SCAFFOLD_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_rendered_command_scaffold"
)
SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_rendered_command_validation_scaffold"
)

SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-rendered-command-validation-scaffold/v1"
)
EXPECTED_SANDBOX_RENDERED_COMMAND_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-rendered-command-scaffold/v1"
)
EXPECTED_SANDBOX_COMMAND_RENDER_PLAN_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-command-render-plan-scaffold/v1"
)
EXPECTED_SANDBOX_INPUT_MATERIALIZATION_PLAN_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-input-materialization-plan-scaffold/v1"
)
EXPECTED_SANDBOX_WORKSPACE_PREPARATION_PREFLIGHT_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-workspace-preparation-preflight-scaffold/v1"
)
EXPECTED_SANDBOX_WORKSPACE_PLAN_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-workspace-plan-scaffold/v1"
)
EXPECTED_SANDBOX_MATERIALIZATION_PREFLIGHT_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-materialization-preflight-scaffold/v1"
)
EXPECTED_SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-request-envelope-scaffold/v1"
)
EXPECTED_SANDBOX_REQUEST_PREFLIGHT_SCHEMA_VERSION = (
    "real-execution-sandbox-adapter-request-preflight/v1"
)

REQUIRED_RENDERED_COMMAND_TRUE_FLAGS = [
    "sandbox_rendered_command_scaffold_exists",
    "sandbox_rendered_command_scaffold_fail_closed",
    "sandbox_rendered_command_scaffold_deny_by_default",
    "sandbox_rendered_command_requires_command_render_plan",
    "sandbox_rendered_command_requires_input_materialization_plan",
    "sandbox_rendered_command_requires_workspace_preparation_preflight",
    "sandbox_rendered_command_requires_workspace_plan",
    "sandbox_rendered_command_requires_materialization_preflight",
    "sandbox_rendered_command_requires_envelope_scaffold",
    "sandbox_rendered_command_requires_request_preflight",
    "sandbox_rendered_command_requires_policy_matrix",
    "sandbox_rendered_command_requires_known_capability",
    "sandbox_rendered_command_requires_known_policy",
    "sandbox_rendered_command_requires_operator_authorization",
    "sandbox_rendered_command_requires_approval_lineage",
    "sandbox_rendered_command_requires_final_gate",
    "sandbox_rendered_command_requires_dry_run_envelope",
    "sandbox_rendered_command_requires_rollback_plan",
    "sandbox_rendered_command_requires_post_execution_evidence",
    "sandbox_rendered_command_rejects_unknown_capability",
    "sandbox_rendered_command_rejects_unknown_policy",
    "sandbox_rendered_command_rejects_orphans",
    "sandbox_rendered_command_rejects_stale_records",
    "source_command_render_plan_scaffold_exists",
    "source_command_render_plan_scaffold_fail_closed",
    "source_command_render_plan_scaffold_deny_by_default",
]

REQUIRED_RENDERED_COMMAND_FALSE_FLAGS = [
    "sandbox_rendered_command_generation_allowed",
    "sandbox_rendered_command_generation_enabled",
    "sandbox_rendered_command_materialized",
    "sandbox_rendered_command_executable",
    "sandbox_rendered_command_validated",
    "sandbox_command_render_plan_generation_allowed",
    "sandbox_command_render_plan_generation_enabled",
    "sandbox_command_render_plan_materialized",
    "sandbox_command_render_plan_executable",
    "sandbox_command_rendering_allowed",
    "sandbox_command_rendering_enabled",
    "sandbox_command_rendered",
    "sandbox_input_materialization_plan_generation_allowed",
    "sandbox_input_materialization_plan_generation_enabled",
    "sandbox_input_materialization_plan_materialized",
    "sandbox_input_materialization_plan_executable",
    "sandbox_input_materialization_allowed",
    "sandbox_input_materialization_enabled",
    "sandbox_inputs_materialized",
    "sandbox_workspace_preparation_preflight_allowed",
    "sandbox_workspace_preparation_preflight_enabled",
    "sandbox_workspace_preparation_preflight_passed",
    "sandbox_workspace_plan_generation_allowed",
    "sandbox_workspace_plan_generation_enabled",
    "sandbox_workspace_plan_materialized",
    "sandbox_workspace_plan_executable",
    "sandbox_workspace_directory_creation_allowed",
    "sandbox_workspace_directory_creation_enabled",
    "sandbox_workspace_created",
    "sandbox_workspace_cleanup_registered",
    "sandbox_materialization_preflight_allowed",
    "sandbox_materialization_preflight_enabled",
    "sandbox_materialization_preflight_passed",
    "sandbox_request_envelope_generation_allowed",
    "sandbox_request_envelope_generation_enabled",
    "sandbox_request_envelope_materialized",
    "sandbox_request_envelope_executable",
    "sandbox_adapter_request_generation_allowed",
    "sandbox_adapter_request_generation_enabled",
    "sandbox_workspace_creation_allowed",
    "sandbox_workspace_creation_enabled",
    "sandbox_execution_allowed",
    "sandbox_execution_enabled",
    "sandbox_result_generation_allowed",
    "sandbox_result_generation_enabled",
    "adapter_request_generation_enabled",
    "adapter_request_execution_enabled",
    "adapter_result_generation_enabled",
    "capability_execution_enabled",
    "policy_execution_enabled",
    "policy_gated_real_execution_enabled",
    "execution_performed",
    "subprocess_invoked",
    "real_execution_enabled",
    "external_side_effects_performed",
    "production_paths_mutated",
    "production_secrets_accessed",
    "source_command_render_plan_generation_enabled",
    "source_command_render_plan_materialized",
    "source_command_render_plan_executable",
    "source_command_rendering_enabled",
    "source_command_rendered",
    "source_rendered_command_validated",
    "source_sandbox_execution_enabled",
    "source_result_generation_enabled",
    "source_execution_performed",
    "source_subprocess_invoked",
    "source_real_execution_enabled",
    "source_external_side_effects_performed",
    "source_production_paths_mutated",
    "source_production_secrets_accessed",
]

EXPECTED_RENDERED_COMMAND_STRINGS = {
    "schema_version": EXPECTED_SANDBOX_RENDERED_COMMAND_SCAFFOLD_SCHEMA_VERSION,
    "source_command_render_plan_scaffold_schema_version": (
        EXPECTED_SANDBOX_COMMAND_RENDER_PLAN_SCAFFOLD_SCHEMA_VERSION
    ),
    "source_input_materialization_plan_scaffold_schema_version": (
        EXPECTED_SANDBOX_INPUT_MATERIALIZATION_PLAN_SCAFFOLD_SCHEMA_VERSION
    ),
    "source_workspace_preparation_preflight_scaffold_schema_version": (
        EXPECTED_SANDBOX_WORKSPACE_PREPARATION_PREFLIGHT_SCAFFOLD_SCHEMA_VERSION
    ),
    "source_workspace_plan_scaffold_schema_version": (
        EXPECTED_SANDBOX_WORKSPACE_PLAN_SCAFFOLD_SCHEMA_VERSION
    ),
    "source_materialization_preflight_scaffold_schema_version": (
        EXPECTED_SANDBOX_MATERIALIZATION_PREFLIGHT_SCAFFOLD_SCHEMA_VERSION
    ),
    "source_envelope_scaffold_schema_version": (
        EXPECTED_SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION
    ),
    "source_request_preflight_schema_version": (
        EXPECTED_SANDBOX_REQUEST_PREFLIGHT_SCHEMA_VERSION
    ),
    "source_command_render_plan_scaffold_status": "blocked",
    "sandbox_rendered_command_scaffold_status": "blocked",
    "sandbox_rendered_command_scaffold_kind": (
        "fail_closed_sandbox_rendered_command_scaffold"
    ),
    "sandbox_workspace_strategy": "ephemeral_temp_workspace",
    "sandbox_workspace_plan_strategy": "explicit_plan_only",
    "sandbox_workspace_preparation_strategy": "preflight_only_no_directory_creation",
    "sandbox_input_materialization_strategy": "plan_only_no_file_copy",
    "sandbox_command_render_strategy": "plan_only_no_command_render",
    "sandbox_rendered_command_strategy": "scaffold_only_no_rendered_command",
    "sandbox_input_strategy": "explicit_allowlist_only",
    "sandbox_output_strategy": "explicit_allowlist_only",
    "sandbox_rollback_strategy": "workspace_destruction",
    "sandbox_evidence_strategy": "post_execution_evidence_required",
    "sandbox_network_policy": "deny",
    "sandbox_secret_policy": "deny",
    "sandbox_filesystem_policy": "no_production_writes",
    "sandbox_production_write_policy": "deny",
    "sandbox_external_side_effect_policy": "deny",
    "recommended_next_action": (
        "surface_sandbox_rendered_command_scaffold_observability"
    ),
    "reason": "sandbox_rendered_command_scaffold_defined_blocked_not_runnable",
}

EXPECTED_SANDBOX_REQUIRED_FIELDS = {
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
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _require_bool(record: Mapping[str, Any], key: str, expected: bool) -> None:
    value = bool(record.get(key))
    if value is not expected:
        expected_text = str(expected).lower()
        raise ValueError(
            "source sandbox rendered command scaffold requires "
            f"{key}={expected_text}"
        )


def _validate_sandbox_rendered_command_scaffold(
    record: Mapping[str, Any],
) -> None:
    rendered_scaffold_id = _clean(
        record.get("real_execution_sandbox_rendered_command_scaffold_id")
    )
    command_render_plan_id = _clean(
        record.get("real_execution_sandbox_command_render_plan_scaffold_id")
    )
    input_plan_id = _clean(
        record.get("real_execution_sandbox_input_materialization_plan_scaffold_id")
    )
    preparation_id = _clean(
        record.get(
            "real_execution_sandbox_workspace_preparation_preflight_scaffold_id"
        )
    )
    workspace_plan_id = _clean(
        record.get("real_execution_sandbox_workspace_plan_scaffold_id")
    )
    materialization_id = _clean(
        record.get("real_execution_sandbox_materialization_preflight_scaffold_id")
    )
    envelope_id = _clean(
        record.get("real_execution_sandbox_request_envelope_scaffold_id")
    )
    preflight_id = _clean(
        record.get("real_execution_sandbox_adapter_request_preflight_id")
    )
    scaffold_id = _clean(record.get("real_execution_sandbox_adapter_scaffold_id"))
    matrix_id = _clean(record.get("real_execution_capability_policy_matrix_id"))
    request_schema_id = _clean(record.get("real_execution_adapter_request_schema_id"))
    contract_id = _clean(record.get("real_execution_adapter_contract_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

    if not rendered_scaffold_id:
        raise ValueError("real_execution_sandbox_rendered_command_scaffold_id is required")
    if not command_render_plan_id:
        raise ValueError(
            "real_execution_sandbox_command_render_plan_scaffold_id is required"
        )
    if not input_plan_id:
        raise ValueError(
            "real_execution_sandbox_input_materialization_plan_scaffold_id is required"
        )
    if not preparation_id:
        raise ValueError(
            "real_execution_sandbox_workspace_preparation_preflight_scaffold_id "
            "is required"
        )
    if not workspace_plan_id:
        raise ValueError("real_execution_sandbox_workspace_plan_scaffold_id is required")
    if not materialization_id:
        raise ValueError(
            "real_execution_sandbox_materialization_preflight_scaffold_id is required"
        )
    if not envelope_id:
        raise ValueError(
            "real_execution_sandbox_request_envelope_scaffold_id is required"
        )
    if not preflight_id:
        raise ValueError(
            "real_execution_sandbox_adapter_request_preflight_id is required"
        )
    if not scaffold_id:
        raise ValueError("real_execution_sandbox_adapter_scaffold_id is required")
    if not matrix_id:
        raise ValueError("real_execution_capability_policy_matrix_id is required")
    if not request_schema_id:
        raise ValueError("real_execution_adapter_request_schema_id is required")
    if not contract_id:
        raise ValueError("real_execution_adapter_contract_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")
    if not proposal_id:
        raise ValueError("proposal_id is required")

    for key, expected in EXPECTED_RENDERED_COMMAND_STRINGS.items():
        if _clean(record.get(key)) != expected:
            raise ValueError(
                "source sandbox rendered command scaffold requires "
                f"{key}={expected}"
            )

    for key in REQUIRED_RENDERED_COMMAND_TRUE_FLAGS:
        _require_bool(record, key, True)

    for key in REQUIRED_RENDERED_COMMAND_FALSE_FLAGS:
        _require_bool(record, key, False)

    required_fields = set(_safe_list(record.get("sandbox_request_required_fields")))
    missing = sorted(EXPECTED_SANDBOX_REQUIRED_FIELDS - required_fields)
    if missing:
        raise ValueError(
            "source sandbox rendered command scaffold missing required field(s): "
            + ",".join(missing)
        )

    if _safe_list(record.get("sandbox_request_allowed_input_paths")):
        raise ValueError(
            "source sandbox rendered command scaffold must not allow input paths"
        )
    if _safe_list(record.get("sandbox_request_allowed_output_paths")):
        raise ValueError(
            "source sandbox rendered command scaffold must not allow output paths"
        )


def build_real_execution_sandbox_rendered_command_validation_scaffold_record(
    sandbox_rendered_command_scaffold: Mapping[str, Any],
    *,
    source: str = "real-execution-sandbox-rendered-command-validation-scaffold",
) -> dict[str, Any]:
    """Build blocked sandbox rendered command validation scaffold record."""
    _validate_sandbox_rendered_command_scaffold(sandbox_rendered_command_scaffold)

    rendered_scaffold_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_rendered_command_scaffold_id"
        )
    )
    command_render_plan_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_command_render_plan_scaffold_id"
        )
    )
    input_plan_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_id"
        )
    )
    preparation_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_workspace_preparation_preflight_scaffold_id"
        )
    )
    workspace_plan_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_workspace_plan_scaffold_id"
        )
    )
    materialization_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_materialization_preflight_scaffold_id"
        )
    )
    envelope_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_request_envelope_scaffold_id"
        )
    )
    preflight_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_adapter_request_preflight_id"
        )
    )
    scaffold_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_sandbox_adapter_scaffold_id"
        )
    )
    matrix_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_capability_policy_matrix_id"
        )
    )
    request_schema_id = _clean(
        sandbox_rendered_command_scaffold.get(
            "real_execution_adapter_request_schema_id"
        )
    )
    contract_id = _clean(
        sandbox_rendered_command_scaffold.get("real_execution_adapter_contract_id")
    )
    rendered_command_id = _clean(
        sandbox_rendered_command_scaffold.get("rendered_command_id")
    )
    proposal_id = _clean(sandbox_rendered_command_scaffold.get("proposal_id"))

    validation_scaffold_id = _stable_id(
        "replay-retry-real-execution-sandbox-rendered-command-validation-scaffold",
        rendered_scaffold_id,
        command_render_plan_id,
        input_plan_id,
        preparation_id,
        workspace_plan_id,
        materialization_id,
        envelope_id,
        preflight_id,
        scaffold_id,
        matrix_id,
        request_schema_id,
        contract_id,
        rendered_command_id,
        proposal_id,
        SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_SCHEMA_VERSION,
    )

    payload = {
        "real_execution_sandbox_rendered_command_validation_scaffold_id": (
            validation_scaffold_id
        ),
        "real_execution_sandbox_rendered_command_scaffold_id": rendered_scaffold_id,
        "real_execution_sandbox_command_render_plan_scaffold_id": (
            command_render_plan_id
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_id": (
            input_plan_id
        ),
        "real_execution_sandbox_workspace_preparation_preflight_scaffold_id": (
            preparation_id
        ),
        "real_execution_sandbox_workspace_plan_scaffold_id": workspace_plan_id,
        "real_execution_sandbox_materialization_preflight_scaffold_id": (
            materialization_id
        ),
        "real_execution_sandbox_request_envelope_scaffold_id": envelope_id,
        "real_execution_sandbox_adapter_request_preflight_id": preflight_id,
        "real_execution_sandbox_adapter_scaffold_id": scaffold_id,
        "real_execution_capability_policy_matrix_id": matrix_id,
        "real_execution_adapter_request_schema_id": request_schema_id,
        "real_execution_adapter_contract_id": contract_id,
        "post_repair_evidence_check_id": _clean(
            sandbox_rendered_command_scaffold.get("post_repair_evidence_check_id")
        ),
        "guarded_repair_execution_result_id": _clean(
            sandbox_rendered_command_scaffold.get(
                "guarded_repair_execution_result_id"
            )
        ),
        "controlled_execution_result_id": _clean(
            sandbox_rendered_command_scaffold.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(sandbox_rendered_command_scaffold.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(sandbox_rendered_command_scaffold.get("approval_id")),
        "decision_mode": _clean(
            sandbox_rendered_command_scaffold.get("decision_mode")
        )
        or "manual",
        "timeout_profile": _clean(
            sandbox_rendered_command_scaffold.get("timeout_profile")
        )
        or "standard",
        "schema_version": (
            SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_SCHEMA_VERSION
        ),
        "source_rendered_command_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get("schema_version")
        ),
        "source_command_render_plan_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_command_render_plan_scaffold_schema_version"
            )
        ),
        "source_input_materialization_plan_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_input_materialization_plan_scaffold_schema_version"
            )
        ),
        "source_workspace_preparation_preflight_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_workspace_preparation_preflight_scaffold_schema_version"
            )
        ),
        "source_workspace_plan_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_workspace_plan_scaffold_schema_version"
            )
        ),
        "source_materialization_preflight_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_materialization_preflight_scaffold_schema_version"
            )
        ),
        "source_envelope_scaffold_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_envelope_scaffold_schema_version"
            )
        ),
        "source_request_preflight_schema_version": _clean(
            sandbox_rendered_command_scaffold.get(
                "source_request_preflight_schema_version"
            )
        ),
        "sandbox_rendered_command_validation_scaffold_status": "blocked",
        "sandbox_rendered_command_validation_scaffold_kind": (
            "fail_closed_sandbox_rendered_command_validation_scaffold"
        ),
        "sandbox_rendered_command_validation_scaffold_exists": True,
        "sandbox_rendered_command_validation_scaffold_fail_closed": True,
        "sandbox_rendered_command_validation_scaffold_deny_by_default": True,
        "sandbox_rendered_command_validation_requires_rendered_command_scaffold": True,
        "sandbox_rendered_command_validation_requires_command_render_plan": True,
        "sandbox_rendered_command_validation_requires_input_materialization_plan": True,
        "sandbox_rendered_command_validation_requires_workspace_preparation_preflight": True,
        "sandbox_rendered_command_validation_requires_workspace_plan": True,
        "sandbox_rendered_command_validation_requires_materialization_preflight": True,
        "sandbox_rendered_command_validation_requires_envelope_scaffold": True,
        "sandbox_rendered_command_validation_requires_request_preflight": True,
        "sandbox_rendered_command_validation_requires_policy_matrix": True,
        "sandbox_rendered_command_validation_requires_known_capability": True,
        "sandbox_rendered_command_validation_requires_known_policy": True,
        "sandbox_rendered_command_validation_requires_operator_authorization": True,
        "sandbox_rendered_command_validation_requires_approval_lineage": True,
        "sandbox_rendered_command_validation_requires_final_gate": True,
        "sandbox_rendered_command_validation_requires_dry_run_envelope": True,
        "sandbox_rendered_command_validation_requires_rollback_plan": True,
        "sandbox_rendered_command_validation_requires_post_execution_evidence": True,
        "sandbox_rendered_command_validation_rejects_unknown_capability": True,
        "sandbox_rendered_command_validation_rejects_unknown_policy": True,
        "sandbox_rendered_command_validation_rejects_orphans": True,
        "sandbox_rendered_command_validation_rejects_stale_records": True,
        "sandbox_request_required_fields": list(
            _safe_list(
                sandbox_rendered_command_scaffold.get(
                    "sandbox_request_required_fields"
                )
            )
        ),
        "sandbox_request_allowed_input_paths": [],
        "sandbox_request_allowed_output_paths": [],
        "sandbox_rendered_command_validation_allowed": False,
        "sandbox_rendered_command_validation_enabled": False,
        "sandbox_rendered_command_validation_performed": False,
        "sandbox_rendered_command_validation_passed": False,
        "sandbox_rendered_command_validation_failed": False,
        "sandbox_rendered_command_generation_allowed": False,
        "sandbox_rendered_command_generation_enabled": False,
        "sandbox_rendered_command_materialized": False,
        "sandbox_rendered_command_executable": False,
        "sandbox_rendered_command_validated": False,
        "sandbox_command_render_plan_generation_allowed": False,
        "sandbox_command_render_plan_generation_enabled": False,
        "sandbox_command_render_plan_materialized": False,
        "sandbox_command_render_plan_executable": False,
        "sandbox_command_rendering_allowed": False,
        "sandbox_command_rendering_enabled": False,
        "sandbox_command_rendered": False,
        "sandbox_input_materialization_plan_generation_allowed": False,
        "sandbox_input_materialization_plan_generation_enabled": False,
        "sandbox_input_materialization_plan_materialized": False,
        "sandbox_input_materialization_plan_executable": False,
        "sandbox_input_materialization_allowed": False,
        "sandbox_input_materialization_enabled": False,
        "sandbox_inputs_materialized": False,
        "sandbox_workspace_preparation_preflight_allowed": False,
        "sandbox_workspace_preparation_preflight_enabled": False,
        "sandbox_workspace_preparation_preflight_passed": False,
        "sandbox_workspace_plan_generation_allowed": False,
        "sandbox_workspace_plan_generation_enabled": False,
        "sandbox_workspace_plan_materialized": False,
        "sandbox_workspace_plan_executable": False,
        "sandbox_workspace_directory_creation_allowed": False,
        "sandbox_workspace_directory_creation_enabled": False,
        "sandbox_workspace_created": False,
        "sandbox_workspace_cleanup_registered": False,
        "sandbox_materialization_preflight_allowed": False,
        "sandbox_materialization_preflight_enabled": False,
        "sandbox_materialization_preflight_passed": False,
        "sandbox_request_envelope_generation_allowed": False,
        "sandbox_request_envelope_generation_enabled": False,
        "sandbox_request_envelope_materialized": False,
        "sandbox_request_envelope_executable": False,
        "sandbox_adapter_request_generation_allowed": False,
        "sandbox_adapter_request_generation_enabled": False,
        "sandbox_workspace_creation_allowed": False,
        "sandbox_workspace_creation_enabled": False,
        "sandbox_execution_allowed": False,
        "sandbox_execution_enabled": False,
        "sandbox_result_generation_allowed": False,
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
        "sandbox_workspace_strategy": "ephemeral_temp_workspace",
        "sandbox_workspace_plan_strategy": "explicit_plan_only",
        "sandbox_workspace_preparation_strategy": (
            "preflight_only_no_directory_creation"
        ),
        "sandbox_input_materialization_strategy": "plan_only_no_file_copy",
        "sandbox_command_render_strategy": "plan_only_no_command_render",
        "sandbox_rendered_command_strategy": "scaffold_only_no_rendered_command",
        "sandbox_rendered_command_validation_strategy": (
            "scaffold_only_no_validation"
        ),
        "sandbox_input_strategy": "explicit_allowlist_only",
        "sandbox_output_strategy": "explicit_allowlist_only",
        "sandbox_cleanup_strategy": "destroy_or_archive_by_policy",
        "sandbox_rollback_strategy": "workspace_destruction",
        "sandbox_evidence_strategy": "post_execution_evidence_required",
        "sandbox_network_policy": "deny",
        "sandbox_secret_policy": "deny",
        "sandbox_filesystem_policy": "no_production_writes",
        "sandbox_production_write_policy": "deny",
        "sandbox_external_side_effect_policy": "deny",
        "source_rendered_command_scaffold_status": _clean(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_scaffold_status"
            )
        ),
        "source_rendered_command_scaffold_exists": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_scaffold_exists"
            )
        ),
        "source_rendered_command_scaffold_fail_closed": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_scaffold_fail_closed"
            )
        ),
        "source_rendered_command_scaffold_deny_by_default": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_scaffold_deny_by_default"
            )
        ),
        "source_rendered_command_generation_enabled": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_generation_enabled"
            )
        ),
        "source_rendered_command_materialized": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_materialized"
            )
        ),
        "source_rendered_command_executable": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_executable"
            )
        ),
        "source_rendered_command_validated": bool(
            sandbox_rendered_command_scaffold.get(
                "sandbox_rendered_command_validated"
            )
        ),
        "source_sandbox_execution_enabled": bool(
            sandbox_rendered_command_scaffold.get("sandbox_execution_enabled")
        ),
        "source_result_generation_enabled": bool(
            sandbox_rendered_command_scaffold.get("sandbox_result_generation_enabled")
        ),
        "source_execution_performed": bool(
            sandbox_rendered_command_scaffold.get("execution_performed")
        ),
        "source_subprocess_invoked": bool(
            sandbox_rendered_command_scaffold.get("subprocess_invoked")
        ),
        "source_real_execution_enabled": bool(
            sandbox_rendered_command_scaffold.get("real_execution_enabled")
        ),
        "source_external_side_effects_performed": bool(
            sandbox_rendered_command_scaffold.get("external_side_effects_performed")
        ),
        "source_production_paths_mutated": bool(
            sandbox_rendered_command_scaffold.get("production_paths_mutated")
        ),
        "source_production_secrets_accessed": bool(
            sandbox_rendered_command_scaffold.get("production_secrets_accessed")
        ),
        "recommended_next_action": (
            "surface_sandbox_rendered_command_validation_scaffold_observability"
        ),
        "reason": (
            "sandbox_rendered_command_validation_scaffold_defined_blocked_not_runnable"
        ),
    }

    return {
        "type": SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    rendered_command_scaffold_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        rendered_command_scaffold_id
        and _clean(record.get("real_execution_sandbox_rendered_command_scaffold_id"))
        != rendered_command_scaffold_id
    ):
        return False
    return True


def _find_existing_validation_scaffold(
    records: list[Mapping[str, Any]],
    *,
    rendered_command_scaffold_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != SANDBOX_RENDERED_COMMAND_VALIDATION_SCAFFOLD_TYPE:
            continue
        if (
            _clean(item.get("real_execution_sandbox_rendered_command_scaffold_id"))
            == rendered_command_scaffold_id
        ):
            return item
    return None


async def build_real_execution_sandbox_rendered_command_validation_scaffold_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-sandbox-rendered-command-validation-scaffold"
    )
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    rendered_command_scaffold_id = _clean(
        getattr(args, "real_execution_sandbox_rendered_command_scaffold_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    rendered_command_scaffolds = [
        item
        for item in records
        if item.get("type") == SANDBOX_RENDERED_COMMAND_SCAFFOLD_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            rendered_command_scaffold_id=rendered_command_scaffold_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for rendered_command_scaffold in rendered_command_scaffolds:
        current_rendered_scaffold_id = _clean(
            rendered_command_scaffold.get(
                "real_execution_sandbox_rendered_command_scaffold_id"
            )
        )
        if _find_existing_validation_scaffold(
            records,
            rendered_command_scaffold_id=current_rendered_scaffold_id,
        ):
            logger.info(
                "Skipping duplicate sandbox rendered command validation scaffold: "
                "rendered_command_scaffold_id=%s",
                current_rendered_scaffold_id,
            )
            continue

        record = build_real_execution_sandbox_rendered_command_validation_scaffold_record(
            rendered_command_scaffold,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published sandbox rendered command validation scaffold: "
            "validation_scaffold_id=%s status=%s validation_enabled=%s "
            "validation_passed=%s sandbox_execution_enabled=%s",
            record.get(
                "real_execution_sandbox_rendered_command_validation_scaffold_id"
            ),
            record.get("sandbox_rendered_command_validation_scaffold_status"),
            record.get("sandbox_rendered_command_validation_enabled"),
            record.get("sandbox_rendered_command_validation_passed"),
            record.get("sandbox_execution_enabled"),
        )

    logger.info(
        "Sandbox rendered command validation scaffold builder completed: "
        "validation_scaffolds=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build blocked sandbox rendered command validation scaffold records."
        ),
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument(
        "--real-execution-sandbox-rendered-command-scaffold-id",
        default="",
    )
    parser.add_argument(
        "--source",
        default="real-execution-sandbox-rendered-command-validation-scaffold",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = (
        await build_real_execution_sandbox_rendered_command_validation_scaffold_records(
            args
        )
    )

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Sandbox rendered command validation scaffold builder completed: "
            f"validation_scaffolds={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()