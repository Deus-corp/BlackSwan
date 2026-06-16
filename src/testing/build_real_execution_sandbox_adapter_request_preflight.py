"""Build fail-closed sandbox adapter request preflight scaffold records.

This artifact prepares the next read-only step after the sandbox adapter
scaffold is visible through Security, Inspector, Readiness, and Overseer.

It intentionally does not:
- generate executable sandbox adapter requests,
- create sandbox workspaces,
- materialize sandbox inputs,
- render sandbox commands,
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

REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold"
)

REAL_EXECUTION_SANDBOX_ADAPTER_REQUEST_PREFLIGHT_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight"
)

SANDBOX_ADAPTER_REQUEST_PREFLIGHT_SCHEMA_VERSION = (
    "real-execution-sandbox-adapter-request-preflight/v1"
)
EXPECTED_SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-adapter-scaffold/v1"
)
EXPECTED_SANDBOX_ADAPTER_CONTRACT_VERSION = "real-execution-sandbox-adapter/v1"

REQUIRED_SOURCE_FLAGS_TRUE = [
    "sandbox_adapter_scaffold_exists",
    "sandbox_adapter_contract_exists",
    "sandbox_adapter_fail_closed",
    "sandbox_adapter_deny_by_default",
    "sandbox_adapter_requires_policy_matrix",
    "sandbox_adapter_requires_known_capability",
    "sandbox_adapter_requires_known_policy",
    "sandbox_adapter_requires_operator_authorization",
    "sandbox_adapter_requires_approval_lineage",
    "sandbox_adapter_requires_final_gate",
    "sandbox_adapter_requires_dry_run_envelope",
    "sandbox_adapter_requires_rollback_plan",
    "sandbox_adapter_requires_post_execution_evidence",
    "sandbox_adapter_rejects_unknown_capability",
    "sandbox_adapter_rejects_unknown_policy",
    "sandbox_adapter_rejects_orphans",
    "sandbox_adapter_rejects_stale_records",
    "source_capability_registry_exists",
    "source_policy_matrix_exists",
    "source_unknown_capability_rejected",
    "source_unknown_policy_rejected",
    "source_deny_by_default",
    "source_fail_closed_default",
    "source_sandbox_real_blocked",
    "source_policy_gated_real_blocked",
    "source_repair_outcome_verified",
]

REQUIRED_SOURCE_FLAGS_FALSE = [
    "sandbox_adapter_implementation_enabled",
    "sandbox_workspace_creation_enabled",
    "sandbox_input_materialization_enabled",
    "sandbox_command_rendering_enabled",
    "sandbox_execution_enabled",
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
    "source_capability_execution_enabled",
    "source_policy_execution_enabled",
    "source_adapter_request_generation_enabled",
    "source_sandbox_execution_enabled",
    "source_policy_gated_real_execution_enabled",
    "source_execution_performed",
    "source_subprocess_invoked",
    "source_real_execution_enabled",
    "source_external_side_effects_performed",
]

EXPECTED_SOURCE_STRINGS = {
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
    "recommended_next_action": "surface_sandbox_adapter_scaffold_observability",
    "reason": "real_execution_sandbox_adapter_scaffold_defined_not_runnable",
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
        raise ValueError(f"source sandbox adapter scaffold requires {key}={expected_text}")


def _validate_sandbox_adapter_scaffold(record: Mapping[str, Any]) -> None:
    scaffold_id = _clean(record.get("real_execution_sandbox_adapter_scaffold_id"))
    matrix_id = _clean(record.get("real_execution_capability_policy_matrix_id"))
    request_schema_id = _clean(record.get("real_execution_adapter_request_schema_id"))
    contract_id = _clean(record.get("real_execution_adapter_contract_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

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

    if _clean(record.get("schema_version")) != EXPECTED_SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION:
        raise ValueError("source sandbox adapter scaffold schema version is invalid")
    if _clean(record.get("sandbox_adapter_contract_version")) != EXPECTED_SANDBOX_ADAPTER_CONTRACT_VERSION:
        raise ValueError("source sandbox adapter contract version is invalid")

    for key, expected in EXPECTED_SOURCE_STRINGS.items():
        if _clean(record.get(key)) != expected:
            raise ValueError(f"source sandbox adapter scaffold requires {key}={expected}")

    for key in REQUIRED_SOURCE_FLAGS_TRUE:
        _require_bool(record, key, True)

    for key in REQUIRED_SOURCE_FLAGS_FALSE:
        _require_bool(record, key, False)

    if int(record.get("source_capability_count") or 0) != 7:
        raise ValueError("source capability count must be 7")
    if int(record.get("source_enabled_capability_count") or 0) != 5:
        raise ValueError("source enabled capability count must be 5")
    if int(record.get("source_blocked_capability_count") or 0) != 2:
        raise ValueError("source blocked capability count must be 2")
    if int(record.get("source_policy_rule_count") or 0) != 7:
        raise ValueError("source policy rule count must be 7")
    if int(record.get("source_approved_policy_count") or 0) != 5:
        raise ValueError("source approved policy count must be 5")
    if int(record.get("source_blocked_policy_count") or 0) != 2:
        raise ValueError("source blocked policy count must be 2")

    required_fields = set(_safe_list(record.get("sandbox_required_fields")))
    expected_required = {
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
    missing = sorted(expected_required - required_fields)
    if missing:
        raise ValueError(
            "source sandbox adapter scaffold missing required field(s): "
            + ",".join(missing)
        )


def build_real_execution_sandbox_adapter_request_preflight_record(
    sandbox_adapter_scaffold: Mapping[str, Any],
    *,
    source: str = "real-execution-sandbox-adapter-request-preflight",
) -> dict[str, Any]:
    """Build fail-closed sandbox adapter request preflight scaffold record."""
    _validate_sandbox_adapter_scaffold(sandbox_adapter_scaffold)

    scaffold_id = _clean(
        sandbox_adapter_scaffold.get("real_execution_sandbox_adapter_scaffold_id")
    )
    matrix_id = _clean(
        sandbox_adapter_scaffold.get("real_execution_capability_policy_matrix_id")
    )
    request_schema_id = _clean(
        sandbox_adapter_scaffold.get("real_execution_adapter_request_schema_id")
    )
    contract_id = _clean(
        sandbox_adapter_scaffold.get("real_execution_adapter_contract_id")
    )
    rendered_command_id = _clean(sandbox_adapter_scaffold.get("rendered_command_id"))
    proposal_id = _clean(sandbox_adapter_scaffold.get("proposal_id"))

    preflight_id = _stable_id(
        "replay-retry-real-execution-sandbox-adapter-request-preflight",
        scaffold_id,
        matrix_id,
        request_schema_id,
        contract_id,
        rendered_command_id,
        proposal_id,
        SANDBOX_ADAPTER_REQUEST_PREFLIGHT_SCHEMA_VERSION,
    )

    payload = {
        "real_execution_sandbox_adapter_request_preflight_id": preflight_id,
        "real_execution_sandbox_adapter_scaffold_id": scaffold_id,
        "real_execution_capability_policy_matrix_id": matrix_id,
        "real_execution_adapter_request_schema_id": request_schema_id,
        "real_execution_adapter_contract_id": contract_id,
        "post_repair_evidence_check_id": _clean(
            sandbox_adapter_scaffold.get("post_repair_evidence_check_id")
        ),
        "guarded_repair_execution_result_id": _clean(
            sandbox_adapter_scaffold.get("guarded_repair_execution_result_id")
        ),
        "controlled_execution_result_id": _clean(
            sandbox_adapter_scaffold.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(sandbox_adapter_scaffold.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(sandbox_adapter_scaffold.get("approval_id")),
        "decision_mode": _clean(sandbox_adapter_scaffold.get("decision_mode")) or "manual",
        "timeout_profile": _clean(sandbox_adapter_scaffold.get("timeout_profile"))
        or "standard",
        "schema_version": SANDBOX_ADAPTER_REQUEST_PREFLIGHT_SCHEMA_VERSION,
        "source_scaffold_schema_version": _clean(
            sandbox_adapter_scaffold.get("schema_version")
        ),
        "source_sandbox_adapter_contract_version": _clean(
            sandbox_adapter_scaffold.get("sandbox_adapter_contract_version")
        ),
        "sandbox_adapter_request_preflight_status": "blocked",
        "sandbox_adapter_request_preflight_kind": (
            "fail_closed_sandbox_adapter_request_preflight"
        ),
        "sandbox_adapter_request_preflight_exists": True,
        "sandbox_adapter_request_preflight_fail_closed": True,
        "sandbox_adapter_request_preflight_deny_by_default": True,
        "sandbox_adapter_request_preflight_requires_policy_matrix": True,
        "sandbox_adapter_request_preflight_requires_known_capability": True,
        "sandbox_adapter_request_preflight_requires_known_policy": True,
        "sandbox_adapter_request_preflight_requires_operator_authorization": True,
        "sandbox_adapter_request_preflight_requires_approval_lineage": True,
        "sandbox_adapter_request_preflight_requires_final_gate": True,
        "sandbox_adapter_request_preflight_requires_dry_run_envelope": True,
        "sandbox_adapter_request_preflight_requires_rollback_plan": True,
        "sandbox_adapter_request_preflight_requires_post_execution_evidence": True,
        "sandbox_adapter_request_preflight_rejects_unknown_capability": True,
        "sandbox_adapter_request_preflight_rejects_unknown_policy": True,
        "sandbox_adapter_request_preflight_rejects_orphans": True,
        "sandbox_adapter_request_preflight_rejects_stale_records": True,
        "sandbox_request_required_fields": list(
            _safe_list(sandbox_adapter_scaffold.get("sandbox_required_fields"))
        ),
        "sandbox_request_allowed_input_paths": [],
        "sandbox_request_allowed_output_paths": [],
        "sandbox_workspace_strategy": "ephemeral_temp_workspace",
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
        "sandbox_adapter_request_generation_allowed": False,
        "sandbox_adapter_request_generation_enabled": False,
        "sandbox_workspace_creation_allowed": False,
        "sandbox_workspace_creation_enabled": False,
        "sandbox_input_materialization_allowed": False,
        "sandbox_input_materialization_enabled": False,
        "sandbox_command_rendering_allowed": False,
        "sandbox_command_rendering_enabled": False,
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
        "source_scaffold_status": _clean(
            sandbox_adapter_scaffold.get("sandbox_adapter_scaffold_status")
        ),
        "source_scaffold_exists": bool(
            sandbox_adapter_scaffold.get("sandbox_adapter_scaffold_exists")
        ),
        "source_scaffold_fail_closed": bool(
            sandbox_adapter_scaffold.get("sandbox_adapter_fail_closed")
        ),
        "source_scaffold_deny_by_default": bool(
            sandbox_adapter_scaffold.get("sandbox_adapter_deny_by_default")
        ),
        "source_scaffold_sandbox_execution_enabled": bool(
            sandbox_adapter_scaffold.get("sandbox_execution_enabled")
        ),
        "source_scaffold_execution_performed": bool(
            sandbox_adapter_scaffold.get("execution_performed")
        ),
        "source_scaffold_subprocess_invoked": bool(
            sandbox_adapter_scaffold.get("subprocess_invoked")
        ),
        "source_scaffold_real_execution_enabled": bool(
            sandbox_adapter_scaffold.get("real_execution_enabled")
        ),
        "source_scaffold_external_side_effects_performed": bool(
            sandbox_adapter_scaffold.get("external_side_effects_performed")
        ),
        "source_scaffold_production_paths_mutated": bool(
            sandbox_adapter_scaffold.get("production_paths_mutated")
        ),
        "source_scaffold_production_secrets_accessed": bool(
            sandbox_adapter_scaffold.get("production_secrets_accessed")
        ),
        "recommended_next_action": (
            "surface_sandbox_adapter_request_preflight_observability"
        ),
        "reason": "sandbox_adapter_request_preflight_defined_blocked_not_runnable",
    }

    return {
        "type": REAL_EXECUTION_SANDBOX_ADAPTER_REQUEST_PREFLIGHT_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    scaffold_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if scaffold_id and _clean(record.get("real_execution_sandbox_adapter_scaffold_id")) != scaffold_id:
        return False
    return True


def _find_existing_preflight(
    records: list[Mapping[str, Any]],
    *,
    scaffold_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_EXECUTION_SANDBOX_ADAPTER_REQUEST_PREFLIGHT_TYPE:
            continue
        if _clean(item.get("real_execution_sandbox_adapter_scaffold_id")) == scaffold_id:
            return item
    return None


async def build_real_execution_sandbox_adapter_request_preflight_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-sandbox-adapter-request-preflight"
    )
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    scaffold_id = _clean(
        getattr(args, "real_execution_sandbox_adapter_scaffold_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    scaffolds = [
        item
        for item in records
        if item.get("type") == REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            scaffold_id=scaffold_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for scaffold in scaffolds:
        current_scaffold_id = _clean(
            scaffold.get("real_execution_sandbox_adapter_scaffold_id")
        )
        if _find_existing_preflight(records, scaffold_id=current_scaffold_id):
            logger.info(
                "Skipping duplicate sandbox adapter request preflight: scaffold_id=%s",
                current_scaffold_id,
            )
            continue

        record = build_real_execution_sandbox_adapter_request_preflight_record(
            scaffold,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published real execution sandbox adapter request preflight: "
            "preflight_id=%s status=%s sandbox_enabled=%s execution_performed=%s",
            record.get("real_execution_sandbox_adapter_request_preflight_id"),
            record.get("sandbox_adapter_request_preflight_status"),
            record.get("sandbox_execution_enabled"),
            record.get("execution_performed"),
        )

    logger.info(
        "Real execution sandbox adapter request preflight builder completed: "
        "preflights=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed sandbox adapter request preflight records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-sandbox-adapter-scaffold-id", default="")
    parser.add_argument(
        "--source",
        default="real-execution-sandbox-adapter-request-preflight",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_sandbox_adapter_request_preflight_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution sandbox adapter request preflight builder completed: "
            f"preflights={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()