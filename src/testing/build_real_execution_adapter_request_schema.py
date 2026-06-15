"""Build fail-closed real execution adapter request schema records.

This artifact defines the future adapter request schema after a valid
real-execution adapter contract exists.

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

REAL_EXECUTION_ADAPTER_CONTRACT_TYPE = (
    "replay_lifecycle_retry_real_execution_adapter_contract"
)

REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE = (
    "replay_lifecycle_retry_real_execution_adapter_request_schema"
)

REQUEST_SCHEMA_SCAFFOLD_VERSION = "real-execution-adapter-request-schema-scaffold/v1"
EXPECTED_CONTRACT_SCHEMA_VERSION = "real-execution-adapter-contract/v1"
EXPECTED_REQUEST_SCHEMA_VERSION = "real-execution-adapter-request/v1"
EXPECTED_RESULT_SCHEMA_VERSION = "real-execution-adapter-result/v1"

REQUEST_STATUSES = ["defined", "rejected", "blocked", "expired", "superseded"]
REQUEST_EXECUTION_LEVELS = [
    "advisory",
    "dry-run",
    "noop",
    "guarded-read-only",
    "guarded-repair",
    "sandbox-real",
    "policy-gated-real",
]
REQUEST_GENERATION_RULES = [
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
]
DEFAULT_REJECTION_REASONS = [
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
        raise ValueError(f"source contract requires {key}={expected_text}")


def _validate_real_execution_adapter_contract(record: Mapping[str, Any]) -> None:
    contract_id = _clean(record.get("real_execution_adapter_contract_id"))
    post_repair_check_id = _clean(record.get("post_repair_evidence_check_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

    if not contract_id:
        raise ValueError("real_execution_adapter_contract_id is required")
    if not post_repair_check_id:
        raise ValueError("post_repair_evidence_check_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")
    if not proposal_id:
        raise ValueError("proposal_id is required")

    if _clean(record.get("schema_version")) != EXPECTED_CONTRACT_SCHEMA_VERSION:
        raise ValueError("source contract schema_version is invalid")
    if (
        _clean(record.get("adapter_request_schema_version"))
        != EXPECTED_REQUEST_SCHEMA_VERSION
    ):
        raise ValueError("source request schema version is invalid")
    if (
        _clean(record.get("adapter_result_schema_version"))
        != EXPECTED_RESULT_SCHEMA_VERSION
    ):
        raise ValueError("source result schema version is invalid")
    if _clean(record.get("contract_status")) != "defined":
        raise ValueError("source contract must be defined")
    if _clean(record.get("contract_kind")) != "policy_gated_real_execution_adapter":
        raise ValueError("source contract kind is invalid")
    if (
        _clean(record.get("recommended_next_action"))
        != "prepare_real_execution_adapter_request_schema"
    ):
        raise ValueError("source contract next action is invalid")

    for key in (
        "adapter_contract_exists",
        "adapter_request_schema_exists",
        "adapter_result_schema_exists",
        "fail_closed_default",
        "sandbox_first",
        "capability_scoped",
        "policy_gated",
        "approval_gated",
        "rollback_required",
        "post_execution_evidence_required",
        "audit_record_required",
        "unknown_capability_rejected",
        "unknown_policy_rejected",
        "missing_approval_rejected",
        "missing_final_gate_rejected",
        "missing_dry_run_envelope_rejected",
        "missing_rollback_plan_rejected",
        "missing_post_execution_evidence_rejected",
        "orphaned_records_rejected",
        "stale_records_rejected",
        "source_repair_outcome_verified",
    ):
        _require_bool(record, key, True)

    for key in (
        "direct_rendered_command_execution_allowed",
        "arbitrary_shell_execution_allowed",
        "adapter_implementation_enabled",
        "adapter_request_generation_enabled",
        "adapter_result_generation_enabled",
        "sandbox_execution_enabled",
        "policy_gated_real_execution_enabled",
        "execution_performed",
        "subprocess_invoked",
        "real_execution_enabled",
        "external_side_effects_performed",
        "production_paths_mutated",
        "production_secrets_accessed",
    ):
        _require_bool(record, key, False)

    if _clean(record.get("source_post_repair_status")) != "passed":
        raise ValueError("source post-repair status must be passed")
    if _clean(record.get("source_post_repair_next_action")) != "close_repair_loop":
        raise ValueError("source post-repair next action must close loop")

    expected_count = int(record.get("source_repair_targets_expected_count") or 0)
    verified_count = int(record.get("source_repair_targets_verified_count") or 0)
    if expected_count <= 0:
        raise ValueError("source expected repair target count is required")
    if verified_count != expected_count:
        raise ValueError("source repair target counts must match")

    request_fields = _safe_list(record.get("adapter_request_required_fields"))
    result_fields = _safe_list(record.get("adapter_result_required_fields"))
    gate_fields = _safe_list(record.get("required_gate_fields"))
    supported_levels = _safe_list(record.get("supported_execution_levels"))
    enabled_levels = _safe_list(record.get("enabled_execution_levels"))
    disabled_levels = _safe_list(record.get("disabled_execution_levels"))

    for field in (
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
    ):
        if field not in request_fields:
            raise ValueError(f"source contract missing request field: {field}")

    for field in (
        "adapter_result_id",
        "adapter_request_id",
        "execution_status",
        "execution_level",
        "capability_id",
        "policy_id",
        "sandbox_id",
        "exit_code",
        "execution_performed",
        "subprocess_invoked",
        "real_execution_enabled",
        "external_side_effects_performed",
        "rollback_plan_id",
        "post_execution_evidence_id",
        "recommended_next_action",
    ):
        if field not in result_fields:
            raise ValueError(f"source contract missing result field: {field}")

    for field in (
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
    ):
        if field not in gate_fields:
            raise ValueError(f"source contract missing gate field: {field}")

    for level in REQUEST_EXECUTION_LEVELS:
        if level not in supported_levels:
            raise ValueError(f"source contract missing execution level: {level}")

    if "sandbox-real" not in disabled_levels:
        raise ValueError("source contract must disable sandbox-real")
    if "policy-gated-real" not in disabled_levels:
        raise ValueError("source contract must disable policy-gated-real")
    if "sandbox-real" in enabled_levels:
        raise ValueError("source contract must not enable sandbox-real")
    if "policy-gated-real" in enabled_levels:
        raise ValueError("source contract must not enable policy-gated-real")


def build_real_execution_adapter_request_schema_record(
    real_execution_adapter_contract: Mapping[str, Any],
    *,
    source: str = "real-execution-adapter-request-schema",
) -> dict[str, Any]:
    """Build a fail-closed real execution adapter request schema scaffold."""
    _validate_real_execution_adapter_contract(real_execution_adapter_contract)

    contract_id = _clean(
        real_execution_adapter_contract.get("real_execution_adapter_contract_id")
    )
    post_repair_check_id = _clean(
        real_execution_adapter_contract.get("post_repair_evidence_check_id")
    )
    rendered_command_id = _clean(real_execution_adapter_contract.get("rendered_command_id"))
    proposal_id = _clean(real_execution_adapter_contract.get("proposal_id"))

    schema_id = _stable_id(
        "replay-retry-real-execution-adapter-request-schema",
        contract_id,
        post_repair_check_id,
        rendered_command_id,
        proposal_id,
        REQUEST_SCHEMA_SCAFFOLD_VERSION,
    )

    request_required_fields = list(
        _safe_list(real_execution_adapter_contract.get("adapter_request_required_fields"))
    )
    gate_fields = list(_safe_list(real_execution_adapter_contract.get("required_gate_fields")))

    payload = {
        "real_execution_adapter_request_schema_id": schema_id,
        "real_execution_adapter_contract_id": contract_id,
        "post_repair_evidence_check_id": post_repair_check_id,
        "guarded_repair_execution_result_id": _clean(
            real_execution_adapter_contract.get("guarded_repair_execution_result_id")
        ),
        "controlled_execution_result_id": _clean(
            real_execution_adapter_contract.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(real_execution_adapter_contract.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(real_execution_adapter_contract.get("approval_id")),
        "decision_mode": _clean(real_execution_adapter_contract.get("decision_mode"))
        or "manual",
        "timeout_profile": _clean(real_execution_adapter_contract.get("timeout_profile"))
        or "standard",
        "schema_version": REQUEST_SCHEMA_SCAFFOLD_VERSION,
        "adapter_request_schema_version": EXPECTED_REQUEST_SCHEMA_VERSION,
        "adapter_contract_schema_version": _clean(
            real_execution_adapter_contract.get("schema_version")
        ),
        "adapter_result_schema_version": _clean(
            real_execution_adapter_contract.get("adapter_result_schema_version")
        ),
        "adapter_request_schema_status": "defined",
        "adapter_request_schema_kind": "policy_gated_real_execution_adapter_request",
        "adapter_request_schema_exists": True,
        "adapter_contract_exists": True,
        "adapter_result_schema_exists": True,
        "request_required_fields": request_required_fields,
        "required_gate_fields": gate_fields,
        "request_statuses": list(REQUEST_STATUSES),
        "request_execution_levels": list(REQUEST_EXECUTION_LEVELS),
        "request_generation_rules": list(REQUEST_GENERATION_RULES),
        "default_rejection_reasons": list(DEFAULT_REJECTION_REASONS),
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
        "source_contract_status": _clean(
            real_execution_adapter_contract.get("contract_status")
        ),
        "source_adapter_contract_exists": bool(
            real_execution_adapter_contract.get("adapter_contract_exists")
        ),
        "source_adapter_request_schema_exists": bool(
            real_execution_adapter_contract.get("adapter_request_schema_exists")
        ),
        "source_adapter_result_schema_exists": bool(
            real_execution_adapter_contract.get("adapter_result_schema_exists")
        ),
        "source_fail_closed_default": bool(
            real_execution_adapter_contract.get("fail_closed_default")
        ),
        "source_sandbox_first": bool(
            real_execution_adapter_contract.get("sandbox_first")
        ),
        "source_policy_gated": bool(
            real_execution_adapter_contract.get("policy_gated")
        ),
        "source_capability_scoped": bool(
            real_execution_adapter_contract.get("capability_scoped")
        ),
        "source_unknown_capability_rejected": bool(
            real_execution_adapter_contract.get("unknown_capability_rejected")
        ),
        "source_unknown_policy_rejected": bool(
            real_execution_adapter_contract.get("unknown_policy_rejected")
        ),
        "source_adapter_implementation_enabled": bool(
            real_execution_adapter_contract.get("adapter_implementation_enabled")
        ),
        "source_sandbox_execution_enabled": bool(
            real_execution_adapter_contract.get("sandbox_execution_enabled")
        ),
        "source_policy_gated_real_execution_enabled": bool(
            real_execution_adapter_contract.get("policy_gated_real_execution_enabled")
        ),
        "source_execution_performed": bool(
            real_execution_adapter_contract.get("execution_performed")
        ),
        "source_subprocess_invoked": bool(
            real_execution_adapter_contract.get("subprocess_invoked")
        ),
        "source_real_execution_enabled": bool(
            real_execution_adapter_contract.get("real_execution_enabled")
        ),
        "source_external_side_effects_performed": bool(
            real_execution_adapter_contract.get("external_side_effects_performed")
        ),
        "source_post_repair_status": _clean(
            real_execution_adapter_contract.get("source_post_repair_status")
        ),
        "source_repair_outcome_verified": bool(
            real_execution_adapter_contract.get("source_repair_outcome_verified")
        ),
        "source_repair_targets_expected_count": int(
            real_execution_adapter_contract.get("source_repair_targets_expected_count")
            or 0
        ),
        "source_repair_targets_verified_count": int(
            real_execution_adapter_contract.get("source_repair_targets_verified_count")
            or 0
        ),
        "recommended_next_action": "prepare_capability_registry_and_policy_matrix",
        "reason": "real_execution_adapter_request_schema_defined_not_runnable",
    }

    return {
        "type": REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    contract_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if (
        contract_id
        and _clean(record.get("real_execution_adapter_contract_id")) != contract_id
    ):
        return False
    return True


def _find_existing_request_schema(
    records: list[Mapping[str, Any]],
    *,
    contract_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_EXECUTION_ADAPTER_REQUEST_SCHEMA_TYPE:
            continue
        if _clean(item.get("real_execution_adapter_contract_id")) == contract_id:
            return item
    return None


async def build_real_execution_adapter_request_schema_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-adapter-request-schema"
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    contract_id = _clean(getattr(args, "real_execution_adapter_contract_id", ""))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    contracts = [
        item
        for item in records
        if item.get("type") == REAL_EXECUTION_ADAPTER_CONTRACT_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            contract_id=contract_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for contract in contracts:
        current_contract_id = _clean(contract.get("real_execution_adapter_contract_id"))
        if _find_existing_request_schema(records, contract_id=current_contract_id):
            logger.info(
                "Skipping duplicate real execution adapter request schema: contract_id=%s",
                current_contract_id,
            )
            continue

        record = build_real_execution_adapter_request_schema_record(
            contract,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published real execution adapter request schema: schema_id=%s "
            "status=%s generation_enabled=%s execution_performed=%s",
            record.get("real_execution_adapter_request_schema_id"),
            record.get("adapter_request_schema_status"),
            record.get("request_generation_enabled"),
            record.get("execution_performed"),
        )

    logger.info(
        "Real execution adapter request schema builder completed: schemas=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed real execution adapter request schema records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-adapter-contract-id", default="")
    parser.add_argument("--source", default="real-execution-adapter-request-schema")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_adapter_request_schema_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution adapter request schema builder completed: "
            f"schemas={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()