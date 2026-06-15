"""Build fail-closed real execution capability registry and policy matrix records.

This artifact defines the capability/policy matrix required before any future
adapter request generation.

It intentionally does not:
- generate executable adapter requests,
- generate adapter results,
- run a sandbox,
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

REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE = (
    "replay_lifecycle_retry_real_execution_adapter_request_schema"
)

REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE = (
    "replay_lifecycle_retry_real_execution_capability_policy_matrix"
)

MATRIX_SCHEMA_VERSION = "real-execution-capability-policy-matrix/v1"
EXPECTED_REQUEST_SCHEMA_SCAFFOLD_VERSION = (
    "real-execution-adapter-request-schema-scaffold/v1"
)
EXPECTED_REQUEST_SCHEMA_VERSION = "real-execution-adapter-request/v1"
EXPECTED_CONTRACT_SCHEMA_VERSION = "real-execution-adapter-contract/v1"
EXPECTED_RESULT_SCHEMA_VERSION = "real-execution-adapter-result/v1"

CAPABILITY_REGISTRY_VERSION = "real-execution-capability-registry/v1"
POLICY_MATRIX_VERSION = "real-execution-policy-matrix/v1"

CAPABILITY_STATUS_VALUES = ["defined", "blocked", "disabled", "deprecated"]
POLICY_DECISION_VALUES = ["approved", "rejected", "blocked", "expired", "superseded"]

CAPABILITIES = [
    {
        "capability_id": "capability.advisory.observe",
        "capability_version": "v1",
        "execution_level": "advisory",
        "status": "defined",
        "enabled": True,
        "sandbox_required": False,
        "rollback_required": False,
        "post_execution_evidence_required": False,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
    {
        "capability_id": "capability.dry_run.validate_bundle",
        "capability_version": "v1",
        "execution_level": "dry-run",
        "status": "defined",
        "enabled": True,
        "sandbox_required": False,
        "rollback_required": False,
        "post_execution_evidence_required": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
    {
        "capability_id": "capability.noop.marker_check",
        "capability_version": "v1",
        "execution_level": "noop",
        "status": "defined",
        "enabled": True,
        "sandbox_required": False,
        "rollback_required": False,
        "post_execution_evidence_required": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
    {
        "capability_id": "capability.guarded_read_only.evidence_check",
        "capability_version": "v1",
        "execution_level": "guarded-read-only",
        "status": "defined",
        "enabled": True,
        "sandbox_required": False,
        "rollback_required": False,
        "post_execution_evidence_required": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
    {
        "capability_id": "capability.guarded_repair.harness",
        "capability_version": "v1",
        "execution_level": "guarded-repair",
        "status": "defined",
        "enabled": True,
        "sandbox_required": False,
        "rollback_required": True,
        "post_execution_evidence_required": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
    {
        "capability_id": "capability.sandbox_real.repair_workspace",
        "capability_version": "v1",
        "execution_level": "sandbox-real",
        "status": "blocked",
        "enabled": False,
        "sandbox_required": True,
        "rollback_required": True,
        "post_execution_evidence_required": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
    {
        "capability_id": "capability.policy_gated_real.production_effect",
        "capability_version": "v1",
        "execution_level": "policy-gated-real",
        "status": "blocked",
        "enabled": False,
        "sandbox_required": True,
        "rollback_required": True,
        "post_execution_evidence_required": True,
        "external_side_effects_allowed": False,
        "production_paths_allowed": False,
        "production_secrets_allowed": False,
    },
]

POLICY_RULES = [
    {
        "policy_id": "policy.advisory.allowed",
        "execution_level": "advisory",
        "decision": "approved",
        "capability_id": "capability.advisory.observe",
        "reason": "advisory_capability_allowed",
    },
    {
        "policy_id": "policy.dry_run.allowed",
        "execution_level": "dry-run",
        "decision": "approved",
        "capability_id": "capability.dry_run.validate_bundle",
        "reason": "dry_run_capability_allowed",
    },
    {
        "policy_id": "policy.noop.allowed",
        "execution_level": "noop",
        "decision": "approved",
        "capability_id": "capability.noop.marker_check",
        "reason": "noop_capability_allowed",
    },
    {
        "policy_id": "policy.guarded_read_only.allowed",
        "execution_level": "guarded-read-only",
        "decision": "approved",
        "capability_id": "capability.guarded_read_only.evidence_check",
        "reason": "guarded_read_only_capability_allowed",
    },
    {
        "policy_id": "policy.guarded_repair.allowed",
        "execution_level": "guarded-repair",
        "decision": "approved",
        "capability_id": "capability.guarded_repair.harness",
        "reason": "guarded_repair_capability_allowed",
    },
    {
        "policy_id": "policy.sandbox_real.blocked_until_adapter_pr",
        "execution_level": "sandbox-real",
        "decision": "blocked",
        "capability_id": "capability.sandbox_real.repair_workspace",
        "reason": "sandbox_real_requires_separate_adapter_pr",
    },
    {
        "policy_id": "policy.policy_gated_real.blocked_until_future_milestone",
        "execution_level": "policy-gated-real",
        "decision": "blocked",
        "capability_id": "capability.policy_gated_real.production_effect",
        "reason": "policy_gated_real_requires_future_reviewed_milestone",
    },
]

REQUIRED_REQUEST_SCHEMA_FLAGS_TRUE = [
    "adapter_request_schema_exists",
    "adapter_contract_exists",
    "adapter_result_schema_exists",
    "fail_closed_default",
    "deny_by_default",
    "unknown_capability_rejected",
    "unknown_policy_rejected",
    "sandbox_required_default",
    "rollback_required_default",
    "post_execution_evidence_required_default",
    "operator_authorized_required",
    "policy_authorized_required",
    "capability_allowed_required",
    "security_validation_required",
    "readiness_validation_required",
    "source_adapter_contract_exists",
    "source_adapter_request_schema_exists",
    "source_adapter_result_schema_exists",
    "source_fail_closed_default",
    "source_sandbox_first",
    "source_policy_gated",
    "source_capability_scoped",
    "source_unknown_capability_rejected",
    "source_unknown_policy_rejected",
    "source_repair_outcome_verified",
]

REQUIRED_REQUEST_SCHEMA_FLAGS_FALSE = [
    "direct_rendered_command_execution_allowed",
    "arbitrary_shell_execution_allowed",
    "request_generation_enabled",
    "request_execution_enabled",
    "adapter_implementation_enabled",
    "adapter_result_generation_enabled",
    "sandbox_execution_enabled",
    "policy_gated_real_execution_enabled",
    "execution_performed",
    "subprocess_invoked",
    "real_execution_enabled",
    "external_side_effects_performed",
    "production_paths_mutated",
    "production_secrets_accessed",
    "source_adapter_implementation_enabled",
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
        raise ValueError(f"source request schema requires {key}={expected_text}")


def _validate_adapter_request_schema(record: Mapping[str, Any]) -> None:
    request_schema_id = _clean(record.get("real_execution_adapter_request_schema_id"))
    contract_id = _clean(record.get("real_execution_adapter_contract_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

    if not request_schema_id:
        raise ValueError("real_execution_adapter_request_schema_id is required")
    if not contract_id:
        raise ValueError("real_execution_adapter_contract_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")
    if not proposal_id:
        raise ValueError("proposal_id is required")

    if _clean(record.get("schema_version")) != EXPECTED_REQUEST_SCHEMA_SCAFFOLD_VERSION:
        raise ValueError("source request schema scaffold version is invalid")
    if _clean(record.get("adapter_request_schema_version")) != EXPECTED_REQUEST_SCHEMA_VERSION:
        raise ValueError("source request schema version is invalid")
    if _clean(record.get("adapter_contract_schema_version")) != EXPECTED_CONTRACT_SCHEMA_VERSION:
        raise ValueError("source contract schema version is invalid")
    if _clean(record.get("adapter_result_schema_version")) != EXPECTED_RESULT_SCHEMA_VERSION:
        raise ValueError("source result schema version is invalid")
    if _clean(record.get("adapter_request_schema_status")) != "defined":
        raise ValueError("source request schema must be defined")
    if _clean(record.get("adapter_request_schema_kind")) != "policy_gated_real_execution_adapter_request":
        raise ValueError("source request schema kind is invalid")
    if _clean(record.get("recommended_next_action")) != "prepare_capability_registry_and_policy_matrix":
        raise ValueError("source request schema next action is invalid")

    for key in REQUIRED_REQUEST_SCHEMA_FLAGS_TRUE:
        _require_bool(record, key, True)

    for key in REQUIRED_REQUEST_SCHEMA_FLAGS_FALSE:
        _require_bool(record, key, False)

    if _clean(record.get("source_contract_status")) != "defined":
        raise ValueError("source contract status must be defined")
    if _clean(record.get("source_post_repair_status")) != "passed":
        raise ValueError("source post-repair status must be passed")

    expected_count = int(record.get("source_repair_targets_expected_count") or 0)
    verified_count = int(record.get("source_repair_targets_verified_count") or 0)
    if expected_count <= 0:
        raise ValueError("source expected repair target count is required")
    if verified_count != expected_count:
        raise ValueError("source repair target counts must match")

    request_fields = _safe_list(record.get("request_required_fields"))
    gate_fields = _safe_list(record.get("required_gate_fields"))
    request_levels = _safe_list(record.get("request_execution_levels"))
    request_rules = _safe_list(record.get("request_generation_rules"))
    rejection_reasons = _safe_list(record.get("default_rejection_reasons"))

    for field in (
        "adapter_request_id",
        "proposal_id",
        "rendered_command_id",
        "capability_id",
        "execution_level",
        "policy_id",
        "operator_authorized",
        "sandbox_required",
        "rollback_required",
        "post_execution_evidence_required",
    ):
        if field not in request_fields:
            raise ValueError(f"source request schema missing request field: {field}")

    for field in (
        "operator_authorized",
        "policy_authorized",
        "capability_allowed",
        "rollback_plan_present",
        "post_execution_evidence_required",
        "security_validation_passed",
        "readiness_validation_passed",
    ):
        if field not in gate_fields:
            raise ValueError(f"source request schema missing gate field: {field}")

    for level in (
        "advisory",
        "dry-run",
        "noop",
        "guarded-read-only",
        "guarded-repair",
        "sandbox-real",
        "policy-gated-real",
    ):
        if level not in request_levels:
            raise ValueError(f"source request schema missing execution level: {level}")

    for rule in (
        "contract_must_be_defined",
        "policy_must_be_known",
        "capability_must_be_known",
        "execution_level_must_be_supported",
        "sandbox_real_must_remain_disabled_until_policy_matrix",
        "policy_gated_real_must_remain_disabled_until_future_milestone",
    ):
        if rule not in request_rules:
            raise ValueError(f"source request schema missing generation rule: {rule}")

    for rejection_reason in (
        "unknown_policy",
        "unknown_capability",
        "unsupported_execution_level",
        "missing_rollback_plan",
        "missing_post_execution_evidence_requirement",
    ):
        if rejection_reason not in rejection_reasons:
            raise ValueError(
                f"source request schema missing rejection reason: {rejection_reason}"
            )


def build_real_execution_capability_policy_matrix_record(
    adapter_request_schema: Mapping[str, Any],
    *,
    source: str = "real-execution-capability-policy-matrix",
) -> dict[str, Any]:
    """Build fail-closed capability registry and policy matrix record."""
    _validate_adapter_request_schema(adapter_request_schema)

    request_schema_id = _clean(
        adapter_request_schema.get("real_execution_adapter_request_schema_id")
    )
    contract_id = _clean(adapter_request_schema.get("real_execution_adapter_contract_id"))
    post_repair_check_id = _clean(adapter_request_schema.get("post_repair_evidence_check_id"))
    rendered_command_id = _clean(adapter_request_schema.get("rendered_command_id"))
    proposal_id = _clean(adapter_request_schema.get("proposal_id"))

    matrix_id = _stable_id(
        "replay-retry-real-execution-capability-policy-matrix",
        request_schema_id,
        contract_id,
        rendered_command_id,
        proposal_id,
        MATRIX_SCHEMA_VERSION,
    )

    capabilities = [dict(item) for item in CAPABILITIES]
    policy_rules = [dict(item) for item in POLICY_RULES]

    enabled_capabilities = [
        item["capability_id"] for item in capabilities if bool(item.get("enabled"))
    ]
    blocked_capabilities = [
        item["capability_id"] for item in capabilities if not bool(item.get("enabled"))
    ]
    approved_policies = [
        item["policy_id"] for item in policy_rules if item.get("decision") == "approved"
    ]
    blocked_policies = [
        item["policy_id"] for item in policy_rules if item.get("decision") == "blocked"
    ]

    payload = {
        "real_execution_capability_policy_matrix_id": matrix_id,
        "real_execution_adapter_request_schema_id": request_schema_id,
        "real_execution_adapter_contract_id": contract_id,
        "post_repair_evidence_check_id": post_repair_check_id,
        "guarded_repair_execution_result_id": _clean(
            adapter_request_schema.get("guarded_repair_execution_result_id")
        ),
        "controlled_execution_result_id": _clean(
            adapter_request_schema.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(adapter_request_schema.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(adapter_request_schema.get("approval_id")),
        "decision_mode": _clean(adapter_request_schema.get("decision_mode")) or "manual",
        "timeout_profile": _clean(adapter_request_schema.get("timeout_profile"))
        or "standard",
        "schema_version": MATRIX_SCHEMA_VERSION,
        "capability_registry_version": CAPABILITY_REGISTRY_VERSION,
        "policy_matrix_version": POLICY_MATRIX_VERSION,
        "source_request_schema_version": _clean(adapter_request_schema.get("schema_version")),
        "source_adapter_request_schema_version": _clean(
            adapter_request_schema.get("adapter_request_schema_version")
        ),
        "matrix_status": "defined",
        "matrix_kind": "capability_registry_policy_matrix",
        "capability_registry_exists": True,
        "policy_matrix_exists": True,
        "capability_count": len(capabilities),
        "enabled_capability_count": len(enabled_capabilities),
        "blocked_capability_count": len(blocked_capabilities),
        "policy_rule_count": len(policy_rules),
        "approved_policy_count": len(approved_policies),
        "blocked_policy_count": len(blocked_policies),
        "capabilities": capabilities,
        "policy_rules": policy_rules,
        "enabled_capabilities": enabled_capabilities,
        "blocked_capabilities": blocked_capabilities,
        "approved_policies": approved_policies,
        "blocked_policies": blocked_policies,
        "capability_status_values": list(CAPABILITY_STATUS_VALUES),
        "policy_decision_values": list(POLICY_DECISION_VALUES),
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
        "source_request_schema_status": _clean(
            adapter_request_schema.get("adapter_request_schema_status")
        ),
        "source_adapter_request_schema_exists": bool(
            adapter_request_schema.get("adapter_request_schema_exists")
        ),
        "source_adapter_contract_exists": bool(
            adapter_request_schema.get("adapter_contract_exists")
        ),
        "source_adapter_result_schema_exists": bool(
            adapter_request_schema.get("adapter_result_schema_exists")
        ),
        "source_fail_closed_default": bool(
            adapter_request_schema.get("fail_closed_default")
        ),
        "source_deny_by_default": bool(adapter_request_schema.get("deny_by_default")),
        "source_unknown_capability_rejected": bool(
            adapter_request_schema.get("unknown_capability_rejected")
        ),
        "source_unknown_policy_rejected": bool(
            adapter_request_schema.get("unknown_policy_rejected")
        ),
        "source_request_generation_enabled": bool(
            adapter_request_schema.get("request_generation_enabled")
        ),
        "source_request_execution_enabled": bool(
            adapter_request_schema.get("request_execution_enabled")
        ),
        "source_sandbox_execution_enabled": bool(
            adapter_request_schema.get("sandbox_execution_enabled")
        ),
        "source_policy_gated_real_execution_enabled": bool(
            adapter_request_schema.get("policy_gated_real_execution_enabled")
        ),
        "source_execution_performed": bool(
            adapter_request_schema.get("execution_performed")
        ),
        "source_subprocess_invoked": bool(
            adapter_request_schema.get("subprocess_invoked")
        ),
        "source_real_execution_enabled": bool(
            adapter_request_schema.get("real_execution_enabled")
        ),
        "source_external_side_effects_performed": bool(
            adapter_request_schema.get("external_side_effects_performed")
        ),
        "source_post_repair_status": _clean(
            adapter_request_schema.get("source_post_repair_status")
        ),
        "source_repair_outcome_verified": bool(
            adapter_request_schema.get("source_repair_outcome_verified")
        ),
        "source_repair_targets_expected_count": int(
            adapter_request_schema.get("source_repair_targets_expected_count") or 0
        ),
        "source_repair_targets_verified_count": int(
            adapter_request_schema.get("source_repair_targets_verified_count") or 0
        ),
        "recommended_next_action": "prepare_sandbox_adapter_scaffold",
        "reason": "real_execution_capability_policy_matrix_defined_not_runnable",
    }

    return {
        "type": REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    request_schema_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if (
        request_schema_id
        and _clean(record.get("real_execution_adapter_request_schema_id"))
        != request_schema_id
    ):
        return False
    return True


def _find_existing_matrix(
    records: list[Mapping[str, Any]],
    *,
    request_schema_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_EXECUTION_CAPABILITY_POLICY_MATRIX_TYPE:
            continue
        if _clean(item.get("real_execution_adapter_request_schema_id")) == request_schema_id:
            return item
    return None


async def build_real_execution_capability_policy_matrix_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-capability-policy-matrix"
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    request_schema_id = _clean(
        getattr(args, "real_execution_adapter_request_schema_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    request_schemas = [
        item
        for item in records
        if item.get("type") == REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            request_schema_id=request_schema_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for schema in request_schemas:
        current_schema_id = _clean(schema.get("real_execution_adapter_request_schema_id"))
        if _find_existing_matrix(records, request_schema_id=current_schema_id):
            logger.info(
                "Skipping duplicate capability policy matrix: request_schema_id=%s",
                current_schema_id,
            )
            continue

        record = build_real_execution_capability_policy_matrix_record(
            schema,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published real execution capability policy matrix: matrix_id=%s "
            "status=%s capabilities=%s policies=%s execution_performed=%s",
            record.get("real_execution_capability_policy_matrix_id"),
            record.get("matrix_status"),
            record.get("capability_count"),
            record.get("policy_rule_count"),
            record.get("execution_performed"),
        )

    logger.info(
        "Real execution capability policy matrix builder completed: matrices=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed real execution capability policy matrix records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-adapter-request-schema-id", default="")
    parser.add_argument("--source", default="real-execution-capability-policy-matrix")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_capability_policy_matrix_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution capability policy matrix builder completed: "
            f"matrices={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()