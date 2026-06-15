"""Build fail-closed real execution sandbox adapter scaffold records.

This artifact defines the future sandbox adapter scaffold after a valid
capability registry and policy matrix exists.

It intentionally does not:
- generate executable adapter requests,
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

REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE = (
    "replay_lifecycle_retry_real_execution_capability_policy_matrix"
)

REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold"
)

SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-adapter-scaffold/v1"
)
EXPECTED_MATRIX_SCHEMA_VERSION = "real-execution-capability-policy-matrix/v1"
EXPECTED_CAPABILITY_REGISTRY_VERSION = "real-execution-capability-registry/v1"
EXPECTED_POLICY_MATRIX_VERSION = "real-execution-policy-matrix/v1"

SANDBOX_ADAPTER_CONTRACT_VERSION = "real-execution-sandbox-adapter/v1"

SANDBOX_REQUIRED_FIELDS = [
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
]

SANDBOX_DENY_POLICIES = {
    "network_policy": "deny",
    "secret_policy": "deny",
    "production_write_policy": "deny",
    "external_side_effect_policy": "deny",
}

SANDBOX_RESOURCE_LIMITS = {
    "max_duration_seconds": 30,
    "max_workspace_bytes": 50_000_000,
    "max_output_bytes": 5_000_000,
    "max_processes": 1,
}


REQUIRED_MATRIX_FLAGS_TRUE = [
    "capability_registry_exists",
    "policy_matrix_exists",
    "unknown_capability_rejected",
    "unknown_policy_rejected",
    "deny_by_default",
    "fail_closed_default",
    "sandbox_real_blocked",
    "policy_gated_real_blocked",
    "sandbox_real_requires_separate_adapter_pr",
    "policy_gated_real_requires_future_reviewed_milestone",
    "source_adapter_request_schema_exists",
    "source_adapter_contract_exists",
    "source_adapter_result_schema_exists",
    "source_fail_closed_default",
    "source_deny_by_default",
    "source_unknown_capability_rejected",
    "source_unknown_policy_rejected",
    "source_repair_outcome_verified",
]

REQUIRED_MATRIX_FLAGS_FALSE = [
    "external_side_effects_allowed",
    "production_paths_allowed",
    "production_secrets_allowed",
    "capability_execution_enabled",
    "policy_execution_enabled",
    "adapter_request_generation_enabled",
    "adapter_request_execution_enabled",
    "adapter_result_generation_enabled",
    "sandbox_execution_enabled",
    "policy_gated_real_execution_enabled",
    "execution_performed",
    "subprocess_invoked",
    "real_execution_enabled",
    "external_side_effects_performed",
    "production_paths_mutated",
    "production_secrets_accessed",
    "source_request_generation_enabled",
    "source_request_execution_enabled",
    "source_sandbox_execution_enabled",
    "source_policy_gated_real_execution_enabled",
    "source_execution_performed",
    "source_subprocess_invoked",
    "source_real_execution_enabled",
    "source_external_side_effects_performed",
]


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
        raise ValueError(f"source capability policy matrix requires {key}={expected_text}")


def _validate_capability_policy_matrix(record: Mapping[str, Any]) -> None:
    matrix_id = _clean(record.get("real_execution_capability_policy_matrix_id"))
    request_schema_id = _clean(record.get("real_execution_adapter_request_schema_id"))
    contract_id = _clean(record.get("real_execution_adapter_contract_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

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

    if _clean(record.get("schema_version")) != EXPECTED_MATRIX_SCHEMA_VERSION:
        raise ValueError("source capability policy matrix schema version is invalid")
    if _clean(record.get("capability_registry_version")) != EXPECTED_CAPABILITY_REGISTRY_VERSION:
        raise ValueError("source capability registry version is invalid")
    if _clean(record.get("policy_matrix_version")) != EXPECTED_POLICY_MATRIX_VERSION:
        raise ValueError("source policy matrix version is invalid")
    if _clean(record.get("matrix_status")) != "defined":
        raise ValueError("source capability policy matrix must be defined")
    if _clean(record.get("matrix_kind")) != "capability_registry_policy_matrix":
        raise ValueError("source capability policy matrix kind is invalid")
    if _clean(record.get("recommended_next_action")) != "prepare_sandbox_adapter_scaffold":
        raise ValueError("source capability policy matrix next action is invalid")

    for key in REQUIRED_MATRIX_FLAGS_TRUE:
        _require_bool(record, key, True)

    for key in REQUIRED_MATRIX_FLAGS_FALSE:
        _require_bool(record, key, False)

    if int(record.get("capability_count") or 0) != 7:
        raise ValueError("source capability count must be 7")
    if int(record.get("enabled_capability_count") or 0) != 5:
        raise ValueError("source enabled capability count must be 5")
    if int(record.get("blocked_capability_count") or 0) != 2:
        raise ValueError("source blocked capability count must be 2")
    if int(record.get("policy_rule_count") or 0) != 7:
        raise ValueError("source policy rule count must be 7")
    if int(record.get("approved_policy_count") or 0) != 5:
        raise ValueError("source approved policy count must be 5")
    if int(record.get("blocked_policy_count") or 0) != 2:
        raise ValueError("source blocked policy count must be 2")

    blocked_capabilities = set(_safe_list(record.get("blocked_capabilities")))
    blocked_policies = set(_safe_list(record.get("blocked_policies")))

    if "capability.sandbox_real.repair_workspace" not in blocked_capabilities:
        raise ValueError("source matrix must block sandbox real capability")
    if "capability.policy_gated_real.production_effect" not in blocked_capabilities:
        raise ValueError("source matrix must block policy-gated real capability")
    if "policy.sandbox_real.blocked_until_adapter_pr" not in blocked_policies:
        raise ValueError("source matrix must block sandbox real policy")
    if "policy.policy_gated_real.blocked_until_future_milestone" not in blocked_policies:
        raise ValueError("source matrix must block policy-gated real policy")

    if _clean(record.get("source_request_schema_status")) != "defined":
        raise ValueError("source request schema status must be defined")
    if _clean(record.get("source_post_repair_status")) != "passed":
        raise ValueError("source post-repair status must be passed")

    expected_count = int(record.get("source_repair_targets_expected_count") or 0)
    verified_count = int(record.get("source_repair_targets_verified_count") or 0)
    if expected_count <= 0:
        raise ValueError("source expected repair target count is required")
    if verified_count != expected_count:
        raise ValueError("source repair target counts must match")


def build_real_execution_sandbox_adapter_scaffold_record(
    capability_policy_matrix: Mapping[str, Any],
    *,
    source: str = "real-execution-sandbox-adapter-scaffold",
) -> dict[str, Any]:
    """Build fail-closed sandbox adapter scaffold record."""
    _validate_capability_policy_matrix(capability_policy_matrix)

    matrix_id = _clean(
        capability_policy_matrix.get("real_execution_capability_policy_matrix_id")
    )
    request_schema_id = _clean(
        capability_policy_matrix.get("real_execution_adapter_request_schema_id")
    )
    contract_id = _clean(capability_policy_matrix.get("real_execution_adapter_contract_id"))
    post_repair_check_id = _clean(capability_policy_matrix.get("post_repair_evidence_check_id"))
    rendered_command_id = _clean(capability_policy_matrix.get("rendered_command_id"))
    proposal_id = _clean(capability_policy_matrix.get("proposal_id"))

    scaffold_id = _stable_id(
        "replay-retry-real-execution-sandbox-adapter-scaffold",
        matrix_id,
        request_schema_id,
        contract_id,
        rendered_command_id,
        proposal_id,
        SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION,
    )

    payload = {
        "real_execution_sandbox_adapter_scaffold_id": scaffold_id,
        "real_execution_capability_policy_matrix_id": matrix_id,
        "real_execution_adapter_request_schema_id": request_schema_id,
        "real_execution_adapter_contract_id": contract_id,
        "post_repair_evidence_check_id": post_repair_check_id,
        "guarded_repair_execution_result_id": _clean(
            capability_policy_matrix.get("guarded_repair_execution_result_id")
        ),
        "controlled_execution_result_id": _clean(
            capability_policy_matrix.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(capability_policy_matrix.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(capability_policy_matrix.get("approval_id")),
        "decision_mode": _clean(capability_policy_matrix.get("decision_mode")) or "manual",
        "timeout_profile": _clean(capability_policy_matrix.get("timeout_profile"))
        or "standard",
        "schema_version": SANDBOX_ADAPTER_SCAFFOLD_SCHEMA_VERSION,
        "sandbox_adapter_contract_version": SANDBOX_ADAPTER_CONTRACT_VERSION,
        "source_matrix_schema_version": _clean(capability_policy_matrix.get("schema_version")),
        "source_capability_registry_version": _clean(
            capability_policy_matrix.get("capability_registry_version")
        ),
        "source_policy_matrix_version": _clean(
            capability_policy_matrix.get("policy_matrix_version")
        ),
        "sandbox_adapter_scaffold_status": "defined",
        "sandbox_adapter_scaffold_kind": "fail_closed_sandbox_adapter_scaffold",
        "sandbox_adapter_scaffold_exists": True,
        "sandbox_adapter_contract_exists": True,
        "sandbox_required_fields": list(SANDBOX_REQUIRED_FIELDS),
        "sandbox_deny_policies": dict(SANDBOX_DENY_POLICIES),
        "sandbox_resource_limits": dict(SANDBOX_RESOURCE_LIMITS),
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
        "source_matrix_status": _clean(capability_policy_matrix.get("matrix_status")),
        "source_capability_registry_exists": bool(
            capability_policy_matrix.get("capability_registry_exists")
        ),
        "source_policy_matrix_exists": bool(
            capability_policy_matrix.get("policy_matrix_exists")
        ),
        "source_capability_count": int(capability_policy_matrix.get("capability_count") or 0),
        "source_enabled_capability_count": int(
            capability_policy_matrix.get("enabled_capability_count") or 0
        ),
        "source_blocked_capability_count": int(
            capability_policy_matrix.get("blocked_capability_count") or 0
        ),
        "source_policy_rule_count": int(capability_policy_matrix.get("policy_rule_count") or 0),
        "source_approved_policy_count": int(
            capability_policy_matrix.get("approved_policy_count") or 0
        ),
        "source_blocked_policy_count": int(
            capability_policy_matrix.get("blocked_policy_count") or 0
        ),
        "source_unknown_capability_rejected": bool(
            capability_policy_matrix.get("unknown_capability_rejected")
        ),
        "source_unknown_policy_rejected": bool(
            capability_policy_matrix.get("unknown_policy_rejected")
        ),
        "source_deny_by_default": bool(capability_policy_matrix.get("deny_by_default")),
        "source_fail_closed_default": bool(
            capability_policy_matrix.get("fail_closed_default")
        ),
        "source_sandbox_real_blocked": bool(
            capability_policy_matrix.get("sandbox_real_blocked")
        ),
        "source_policy_gated_real_blocked": bool(
            capability_policy_matrix.get("policy_gated_real_blocked")
        ),
        "source_capability_execution_enabled": bool(
            capability_policy_matrix.get("capability_execution_enabled")
        ),
        "source_policy_execution_enabled": bool(
            capability_policy_matrix.get("policy_execution_enabled")
        ),
        "source_adapter_request_generation_enabled": bool(
            capability_policy_matrix.get("adapter_request_generation_enabled")
        ),
        "source_sandbox_execution_enabled": bool(
            capability_policy_matrix.get("sandbox_execution_enabled")
        ),
        "source_policy_gated_real_execution_enabled": bool(
            capability_policy_matrix.get("policy_gated_real_execution_enabled")
        ),
        "source_execution_performed": bool(
            capability_policy_matrix.get("execution_performed")
        ),
        "source_subprocess_invoked": bool(
            capability_policy_matrix.get("subprocess_invoked")
        ),
        "source_real_execution_enabled": bool(
            capability_policy_matrix.get("real_execution_enabled")
        ),
        "source_external_side_effects_performed": bool(
            capability_policy_matrix.get("external_side_effects_performed")
        ),
        "source_post_repair_status": _clean(
            capability_policy_matrix.get("source_post_repair_status")
        ),
        "source_repair_outcome_verified": bool(
            capability_policy_matrix.get("source_repair_outcome_verified")
        ),
        "source_repair_targets_expected_count": int(
            capability_policy_matrix.get("source_repair_targets_expected_count") or 0
        ),
        "source_repair_targets_verified_count": int(
            capability_policy_matrix.get("source_repair_targets_verified_count") or 0
        ),
        "recommended_next_action": "surface_sandbox_adapter_scaffold_observability",
        "reason": "real_execution_sandbox_adapter_scaffold_defined_not_runnable",
    }

    return {
        "type": REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    matrix_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if (
        matrix_id
        and _clean(record.get("real_execution_capability_policy_matrix_id"))
        != matrix_id
    ):
        return False
    return True


def _find_existing_scaffold(
    records: list[Mapping[str, Any]],
    *,
    matrix_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_EXECUTION_SANDBOX_ADAPTER_SCAFFOLD_TYPE:
            continue
        if _clean(item.get("real_execution_capability_policy_matrix_id")) == matrix_id:
            return item
    return None


async def build_real_execution_sandbox_adapter_scaffold_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-sandbox-adapter-scaffold"
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    matrix_id = _clean(
        getattr(args, "real_execution_capability_policy_matrix_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    matrices = [
        item
        for item in records
        if item.get("type") == REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            matrix_id=matrix_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for matrix in matrices:
        current_matrix_id = _clean(
            matrix.get("real_execution_capability_policy_matrix_id")
        )
        if _find_existing_scaffold(records, matrix_id=current_matrix_id):
            logger.info(
                "Skipping duplicate sandbox adapter scaffold: matrix_id=%s",
                current_matrix_id,
            )
            continue

        record = build_real_execution_sandbox_adapter_scaffold_record(
            matrix,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published real execution sandbox adapter scaffold: scaffold_id=%s "
            "status=%s sandbox_enabled=%s execution_performed=%s",
            record.get("real_execution_sandbox_adapter_scaffold_id"),
            record.get("sandbox_adapter_scaffold_status"),
            record.get("sandbox_execution_enabled"),
            record.get("execution_performed"),
        )

    logger.info(
        "Real execution sandbox adapter scaffold builder completed: scaffolds=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed real execution sandbox adapter scaffold records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-capability-policy-matrix-id", default="")
    parser.add_argument("--source", default="real-execution-sandbox-adapter-scaffold")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_sandbox_adapter_scaffold_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution sandbox adapter scaffold builder completed: "
            f"scaffolds={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()