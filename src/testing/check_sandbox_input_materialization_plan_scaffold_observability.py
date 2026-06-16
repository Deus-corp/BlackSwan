"""Check fail-closed sandbox input materialization plan scaffold observability.

This helper is read-only. It verifies that sandbox input materialization plan
scaffold records are visible through Security validation, Inspector trail
summaries, Readiness-style fail-closed gates, and Overseer global brief metrics.

It does not generate input materialization plans, materialize plans, materialize
inputs, render commands, execute sandbox commands, invoke subprocesses, or enable
real execution.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.overseer.overseer_core.brief_builder import build_global_swarm_brief
from src.swarms.security.runtime_validation import (
    build_security_validation_heartbeat_metrics,
)
from src.testing.inspect_retry_governance_trail import (
    inspect_retry_governance_trail_from_records,
)
from swarm_config import config

logger = logging.getLogger(__name__)

SANDBOX_INPUT_MATERIALIZATION_PLAN_SCAFFOLD_RECORD_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_input_materialization_plan_scaffold"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check sandbox input materialization plan scaffold observability.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def check_sandbox_input_materialization_plan_scaffold_observability_from_records(
    records: list[Any],
    *,
    proposal_id: str = "",
    rendered_command_id: str = "",
) -> dict[str, Any]:
    """Check sandbox input materialization plan scaffold observability."""
    clean_proposal_id = str(proposal_id or "").strip()
    clean_rendered_command_id = str(rendered_command_id or "").strip()

    filtered_records = [
        item
        for item in records or []
        if isinstance(item, Mapping)
        and _matches_filters(
            item,
            proposal_id=clean_proposal_id,
            rendered_command_id=clean_rendered_command_id,
        )
    ]

    trail_summary = inspect_retry_governance_trail_from_records(
        filtered_records,
        proposal_id=clean_proposal_id,
    )
    security_metrics = build_security_validation_heartbeat_metrics(filtered_records)

    security_metrics = {
        **security_metrics,
        "real_execution_sandbox_input_materialization_plan_scaffold_statuses": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_statuses",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_fail_closed": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_fail_closed",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_deny_by_default": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_deny_by_default",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_plan_generation_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_generation_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_plan_materialized": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_materialized",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_plan_executable": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_executable",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_input_materialization_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_input_materialization_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_inputs_materialized": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_inputs_materialized",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_passed": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_passed",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_directory_creation_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_directory_creation_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_workspace_created": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_workspace_created",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_cleanup_registered": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_cleanup_registered",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_workspace_creation_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_workspace_creation_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_command_rendering_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_command_rendering_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_sandbox_execution_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_sandbox_execution_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_result_generation_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_result_generation_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_execution_performed": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_execution_performed",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_subprocess_invoked": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_subprocess_invoked",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_real_execution_enabled": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_real_execution_enabled",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_external_side_effects_performed": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_external_side_effects_performed",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_production_paths_mutated": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_production_paths_mutated",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_production_secrets_accessed": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_production_secrets_accessed",
            {},
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_orphans": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_orphans",
            0,
        ),
        "real_execution_sandbox_input_materialization_plan_scaffold_linkage_complete": trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_linkage_complete",
            False,
        ),
    }

    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation=security_metrics,
    )

    record_type_counts = _safe_mapping(
        security_metrics.get("security_validation_record_type_counts")
    )
    brief_key_metrics = dict(getattr(brief, "key_metrics", {}) or {})

    checks = _build_checks(
        record_type_counts=record_type_counts,
        trail_summary=trail_summary,
        key_metrics=brief_key_metrics,
    )
    failed_checks = [
        str(item.get("name") or "unknown")
        for item in checks
        if item.get("status") != "passed"
    ]

    statuses = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_statuses"
        )
    )
    fail_closed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_fail_closed"
        )
    )
    deny_by_default = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_deny_by_default"
        )
    )
    plan_generation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_generation_enabled"
        )
    )
    plan_materialized = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_materialized"
        )
    )
    plan_executable = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_executable"
        )
    )
    input_materialization_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_input_materialization_enabled"
        )
    )
    inputs_materialized = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_inputs_materialized"
        )
    )
    preparation_preflight_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_enabled"
        )
    )
    preparation_preflight_passed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_passed"
        )
    )
    directory_creation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_directory_creation_enabled"
        )
    )
    workspace_created = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_workspace_created"
        )
    )
    cleanup_registered = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_cleanup_registered"
        )
    )
    workspace_creation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_workspace_creation_enabled"
        )
    )
    command_rendering_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_command_rendering_enabled"
        )
    )
    sandbox_execution_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_sandbox_execution_enabled"
        )
    )
    result_generation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_result_generation_enabled"
        )
    )
    execution_performed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_execution_performed"
        )
    )
    subprocess_invoked = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_subprocess_invoked"
        )
    )
    real_execution_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_real_execution_enabled"
        )
    )
    external_side_effects = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_external_side_effects_performed"
        )
    )
    production_paths_mutated = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_production_paths_mutated"
        )
    )
    production_secrets_accessed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_production_secrets_accessed"
        )
    )

    return {
        "type": "sandbox_input_materialization_plan_scaffold_observability_check",
        "status": "passed" if not failed_checks else "failed",
        "proposal_id": clean_proposal_id or None,
        "rendered_command_id": clean_rendered_command_id or None,
        "checks": checks,
        "failed_checks": failed_checks,
        "security_record_type_counts": dict(record_type_counts),
        "brief_key_metrics": brief_key_metrics,
        "brief_summary": brief.summary,
        "sandbox_input_materialization_plan_scaffold_observed": _safe_int(
            statuses.get("blocked"), 0
        )
        > 0,
        "sandbox_input_materialization_plan_scaffold_records": _safe_int(
            statuses.get("blocked"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_linkage_complete": bool(
            trail_summary.get(
                "real_execution_sandbox_input_materialization_plan_scaffold_linkage_complete"
            )
        ),
        "sandbox_input_materialization_plan_scaffold_orphans": _safe_int(
            trail_summary.get(
                "real_execution_sandbox_input_materialization_plan_scaffold_orphans"
            ),
            0,
        ),
        "sandbox_input_materialization_plan_scaffold_blocked": _safe_int(
            statuses.get("blocked"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_fail_closed": _safe_int(
            fail_closed.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_deny_by_default": _safe_int(
            deny_by_default.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_plan_generation_enabled": _safe_int(
            plan_generation_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_plan_materialized": _safe_int(
            plan_materialized.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_plan_executable": _safe_int(
            plan_executable.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_input_materialization_enabled": _safe_int(
            input_materialization_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_inputs_materialized": _safe_int(
            inputs_materialized.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_preparation_preflight_enabled": _safe_int(
            preparation_preflight_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_preparation_preflight_passed": _safe_int(
            preparation_preflight_passed.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_directory_creation_enabled": _safe_int(
            directory_creation_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_workspace_created": _safe_int(
            workspace_created.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_cleanup_registered": _safe_int(
            cleanup_registered.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_workspace_creation_enabled": _safe_int(
            workspace_creation_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_command_rendering_enabled": _safe_int(
            command_rendering_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_sandbox_execution_enabled": _safe_int(
            sandbox_execution_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_result_generation_enabled": _safe_int(
            result_generation_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_execution_performed": _safe_int(
            execution_performed.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_subprocess_invoked": _safe_int(
            subprocess_invoked.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_real_execution_enabled": _safe_int(
            real_execution_enabled.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_external_side_effects_performed": _safe_int(
            external_side_effects.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_production_paths_mutated": _safe_int(
            production_paths_mutated.get("true"), 0
        ),
        "sandbox_input_materialization_plan_scaffold_production_secrets_accessed": _safe_int(
            production_secrets_accessed.get("true"), 0
        ),
    }


def check_sandbox_input_materialization_plan_scaffold_observability(
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Read CRDT and check sandbox input materialization plan observability."""
    db_path = str(args.db_path or config.crdt_db_path)

    crdt = CRDTAdapter(
        node_id="sandbox-input-materialization-plan-scaffold-observability-reader",
        db_path=db_path,
    )
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        return check_sandbox_input_materialization_plan_scaffold_observability_from_records(
            list(state.values()),
            proposal_id=str(getattr(args, "proposal_id", "") or ""),
            rendered_command_id=str(getattr(args, "rendered_command_id", "") or ""),
        )
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _build_checks(
    *,
    record_type_counts: Mapping[str, Any],
    trail_summary: Mapping[str, Any],
    key_metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    statuses = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_statuses"
        )
    )
    fail_closed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_fail_closed"
        )
    )
    deny_by_default = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_deny_by_default"
        )
    )
    plan_generation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_generation_enabled"
        )
    )
    plan_materialized = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_materialized"
        )
    )
    plan_executable = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_plan_executable"
        )
    )
    input_materialization_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_input_materialization_enabled"
        )
    )
    inputs_materialized = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_inputs_materialized"
        )
    )
    preparation_preflight_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_enabled"
        )
    )
    preparation_preflight_passed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_preparation_preflight_passed"
        )
    )
    directory_creation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_directory_creation_enabled"
        )
    )
    workspace_created = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_workspace_created"
        )
    )
    cleanup_registered = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_cleanup_registered"
        )
    )
    workspace_creation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_workspace_creation_enabled"
        )
    )
    command_rendering_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_command_rendering_enabled"
        )
    )
    sandbox_execution_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_sandbox_execution_enabled"
        )
    )
    result_generation_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_result_generation_enabled"
        )
    )
    execution_performed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_execution_performed"
        )
    )
    subprocess_invoked = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_subprocess_invoked"
        )
    )
    real_execution_enabled = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_real_execution_enabled"
        )
    )
    external_side_effects = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_external_side_effects_performed"
        )
    )
    production_paths_mutated = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_production_paths_mutated"
        )
    )
    production_secrets_accessed = _safe_mapping(
        trail_summary.get(
            "real_execution_sandbox_input_materialization_plan_scaffold_production_secrets_accessed"
        )
    )

    security_input_plan_count = _safe_int(
        record_type_counts.get(
            SANDBOX_INPUT_MATERIALIZATION_PLAN_SCAFFOLD_RECORD_TYPE
        ),
        0,
    )
    trail_input_plan_count = _safe_int(statuses.get("blocked"), 0)
    brief_input_plan_count = _safe_int(
        key_metrics.get(
            "security_real_execution_sandbox_input_materialization_plan_scaffolds"
        ),
        0,
    )

    return [
        _check(
            "security_observes_sandbox_input_materialization_plan_scaffold",
            security_input_plan_count > 0,
            security_input_plan_count,
        ),
        _check(
            "inspector_observes_sandbox_input_materialization_plan_scaffold",
            trail_input_plan_count > 0,
            trail_input_plan_count,
        ),
        _check(
            "inspector_sandbox_input_materialization_plan_scaffold_linkage_complete",
            bool(
                trail_summary.get(
                    "real_execution_sandbox_input_materialization_plan_scaffold_linkage_complete"
                )
            ),
            bool(
                trail_summary.get(
                    "real_execution_sandbox_input_materialization_plan_scaffold_linkage_complete"
                )
            ),
        ),
        _check(
            "inspector_sandbox_input_materialization_plan_scaffold_has_no_orphans",
            _safe_int(
                trail_summary.get(
                    "real_execution_sandbox_input_materialization_plan_scaffold_orphans"
                ),
                0,
            )
            == 0,
            _safe_int(
                trail_summary.get(
                    "real_execution_sandbox_input_materialization_plan_scaffold_orphans"
                ),
                0,
            ),
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_blocked",
            trail_input_plan_count > 0,
            statuses,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_fail_closed",
            _safe_int(fail_closed.get("true"), 0) > 0,
            fail_closed,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_deny_by_default",
            _safe_int(deny_by_default.get("true"), 0) > 0,
            deny_by_default,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_generate_plan",
            _safe_int(plan_generation_enabled.get("true"), 0) == 0,
            plan_generation_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_materialize_plan",
            _safe_int(plan_materialized.get("true"), 0) == 0,
            plan_materialized,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_plan_not_executable",
            _safe_int(plan_executable.get("true"), 0) == 0,
            plan_executable,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_enable_input_materialization",
            _safe_int(input_materialization_enabled.get("true"), 0) == 0,
            input_materialization_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_materialize_inputs",
            _safe_int(inputs_materialized.get("true"), 0) == 0,
            inputs_materialized,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_enable_preparation_preflight",
            _safe_int(preparation_preflight_enabled.get("true"), 0) == 0,
            preparation_preflight_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_pass_preparation_preflight",
            _safe_int(preparation_preflight_passed.get("true"), 0) == 0,
            preparation_preflight_passed,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_enable_directory_creation",
            _safe_int(directory_creation_enabled.get("true"), 0) == 0,
            directory_creation_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_create_workspace",
            _safe_int(workspace_created.get("true"), 0) == 0,
            workspace_created,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_register_cleanup",
            _safe_int(cleanup_registered.get("true"), 0) == 0,
            cleanup_registered,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_enable_workspace_creation",
            _safe_int(workspace_creation_enabled.get("true"), 0) == 0,
            workspace_creation_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_render_commands",
            _safe_int(command_rendering_enabled.get("true"), 0) == 0,
            command_rendering_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_enable_sandbox_execution",
            _safe_int(sandbox_execution_enabled.get("true"), 0) == 0,
            sandbox_execution_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_generate_results",
            _safe_int(result_generation_enabled.get("true"), 0) == 0,
            result_generation_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_execute",
            _safe_int(execution_performed.get("true"), 0) == 0,
            execution_performed,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_invoke_subprocess",
            _safe_int(subprocess_invoked.get("true"), 0) == 0,
            subprocess_invoked,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_enable_real_execution",
            _safe_int(real_execution_enabled.get("true"), 0) == 0,
            real_execution_enabled,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_perform_external_side_effects",
            _safe_int(external_side_effects.get("true"), 0) == 0,
            external_side_effects,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_mutate_production_paths",
            _safe_int(production_paths_mutated.get("true"), 0) == 0,
            production_paths_mutated,
        ),
        _check(
            "sandbox_input_materialization_plan_scaffold_does_not_access_production_secrets",
            _safe_int(production_secrets_accessed.get("true"), 0) == 0,
            production_secrets_accessed,
        ),
        _check(
            "overseer_brief_surfaces_sandbox_input_materialization_plan_scaffold",
            brief_input_plan_count > 0,
            brief_input_plan_count,
        ),
    ]


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
) -> bool:
    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if proposal_id:
        if (
            str(record.get("proposal_id") or "").strip() != proposal_id
            and str(payload_mapping.get("proposal_id") or "").strip() != proposal_id
        ):
            return False

    if rendered_command_id:
        if (
            str(record.get("rendered_command_id") or "").strip()
            != rendered_command_id
            and str(payload_mapping.get("rendered_command_id") or "").strip()
            != rendered_command_id
        ):
            return False

    return True


def _check(name: str, condition: bool, value: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if condition else "failed",
        "value": value,
    }


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_result(result: Mapping[str, Any]) -> str:
    failed = result.get("failed_checks")
    failed_checks = failed if isinstance(failed, list) and failed else ["none"]

    return (
        "Sandbox input materialization plan scaffold observability: "
        f"status={result.get('status')} "
        f"observed="
        f"{str(bool(result.get('sandbox_input_materialization_plan_scaffold_observed'))).lower()} "
        f"records={result.get('sandbox_input_materialization_plan_scaffold_records', 0)} "
        f"linkage_complete="
        f"{str(bool(result.get('sandbox_input_materialization_plan_scaffold_linkage_complete'))).lower()} "
        f"orphans={result.get('sandbox_input_materialization_plan_scaffold_orphans', 0)} "
        f"blocked={result.get('sandbox_input_materialization_plan_scaffold_blocked', 0)} "
        f"fail_closed={result.get('sandbox_input_materialization_plan_scaffold_fail_closed', 0)} "
        f"deny_by_default={result.get('sandbox_input_materialization_plan_scaffold_deny_by_default', 0)} "
        f"plan_generation_enabled="
        f"{result.get('sandbox_input_materialization_plan_scaffold_plan_generation_enabled', 0)} "
        f"plan_materialized="
        f"{result.get('sandbox_input_materialization_plan_scaffold_plan_materialized', 0)} "
        f"plan_executable="
        f"{result.get('sandbox_input_materialization_plan_scaffold_plan_executable', 0)} "
        f"input_materialization_enabled="
        f"{result.get('sandbox_input_materialization_plan_scaffold_input_materialization_enabled', 0)} "
        f"inputs_materialized="
        f"{result.get('sandbox_input_materialization_plan_scaffold_inputs_materialized', 0)} "
        f"command_rendering_enabled="
        f"{result.get('sandbox_input_materialization_plan_scaffold_command_rendering_enabled', 0)} "
        f"sandbox_execution_enabled="
        f"{result.get('sandbox_input_materialization_plan_scaffold_sandbox_execution_enabled', 0)} "
        f"execution_performed="
        f"{result.get('sandbox_input_materialization_plan_scaffold_execution_performed', 0)} "
        f"subprocess_invoked="
        f"{result.get('sandbox_input_materialization_plan_scaffold_subprocess_invoked', 0)} "
        f"real_execution_enabled="
        f"{result.get('sandbox_input_materialization_plan_scaffold_real_execution_enabled', 0)} "
        f"failed_checks={','.join(str(item) for item in failed_checks)}"
    )


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    result = check_sandbox_input_materialization_plan_scaffold_observability(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()