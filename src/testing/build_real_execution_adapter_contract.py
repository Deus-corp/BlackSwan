"""Build policy-gated real execution adapter contract records.

This is a contract/schema artifact only. It intentionally does not run a real
execution adapter, does not create executable adapter requests, and does not
invoke subprocesses.

The contract is allowed only after the verified guarded repair loop exists:
guarded repair execution succeeded and post-repair evidence passed.
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

POST_REPAIR_EVIDENCE_CHECK_TYPE = (
    "replay_lifecycle_retry_post_repair_evidence_check"
)

REAL_EXECUTION_ADAPTER_CONTRACT_TYPE = (
    "replay_lifecycle_retry_real_execution_adapter_contract"
)

CONTRACT_SCHEMA_VERSION = "real-execution-adapter-contract/v1"
REQUEST_SCHEMA_VERSION = "real-execution-adapter-request/v1"
RESULT_SCHEMA_VERSION = "real-execution-adapter-result/v1"

SUPPORTED_EXECUTION_LEVELS = [
    "advisory",
    "dry-run",
    "noop",
    "guarded-read-only",
    "guarded-repair",
    "sandbox-real",
    "policy-gated-real",
]

ENABLED_EXECUTION_LEVELS = [
    "advisory",
    "dry-run",
    "noop",
    "guarded-read-only",
    "guarded-repair",
]

DISABLED_EXECUTION_LEVELS = [
    "sandbox-real",
    "policy-gated-real",
]

ADAPTER_REQUEST_REQUIRED_FIELDS = [
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
]

ADAPTER_RESULT_REQUIRED_FIELDS = [
    "adapter_result_id",
    "adapter_request_id",
    "execution_status",
    "execution_level",
    "capability_id",
    "policy_id",
    "sandbox_id",
    "exit_code",
    "stdout_digest",
    "stderr_digest",
    "duration_seconds",
    "execution_performed",
    "subprocess_invoked",
    "real_execution_enabled",
    "external_side_effects_performed",
    "rollback_plan_id",
    "rollback_performed",
    "post_execution_evidence_id",
    "recommended_next_action",
]

REQUIRED_GATE_FIELDS = [
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
]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _validate_post_repair_evidence_check(record: Mapping[str, Any]) -> None:
    check_id = _clean(record.get("post_repair_evidence_check_id"))
    guarded_result_id = _clean(record.get("guarded_repair_execution_result_id"))
    readiness_gate_id = _clean(record.get("real_execution_repair_readiness_gate_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

    if not check_id:
        raise ValueError("post_repair_evidence_check_id is required")
    if not guarded_result_id:
        raise ValueError("guarded_repair_execution_result_id is required")
    if not readiness_gate_id:
        raise ValueError("real_execution_repair_readiness_gate_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")
    if not proposal_id:
        raise ValueError("proposal_id is required")

    if _clean(record.get("post_repair_status")) != "passed":
        raise ValueError("adapter contract requires passed post-repair evidence")
    if not bool(record.get("post_repair_evidence_check_allowed")):
        raise ValueError("adapter contract requires allowed post-repair evidence")
    if not bool(record.get("post_repair_evidence_check_enabled")):
        raise ValueError("adapter contract requires enabled post-repair evidence")
    if not bool(record.get("post_repair_evidence_marker_observed")):
        raise ValueError("adapter contract requires post-repair evidence marker")
    if int(record.get("post_repair_evidence_exit_code") or 0) != 0:
        raise ValueError("adapter contract requires zero post-repair evidence exit code")
    if not bool(record.get("repair_outcome_verified")):
        raise ValueError("adapter contract requires verified repair outcome")
    if _clean(record.get("recommended_next_action")) != "close_repair_loop":
        raise ValueError("adapter contract requires close_repair_loop next action")

    expected_count = int(record.get("repair_targets_expected_count") or 0)
    verified_count = int(record.get("repair_targets_verified_count") or 0)
    missing_targets = _safe_list(record.get("repair_targets_missing"))
    unexpected_targets = _safe_list(record.get("repair_targets_unexpected"))

    if expected_count <= 0:
        raise ValueError("adapter contract requires expected repair targets")
    if verified_count != expected_count:
        raise ValueError("adapter contract requires verified target count match")
    if missing_targets:
        raise ValueError("adapter contract rejects missing repair targets")
    if unexpected_targets:
        raise ValueError("adapter contract rejects unexpected repair targets")

    if bool(record.get("repair_execution_enabled")):
        raise ValueError("adapter contract rejects post-check repair execution enabled")
    if bool(record.get("real_execution_enabled")):
        raise ValueError("adapter contract rejects post-check real execution enabled")
    if bool(record.get("repair_execution_performed")):
        raise ValueError("adapter contract rejects post-check repair execution performed")
    if bool(record.get("repair_subprocess_invoked")):
        raise ValueError("adapter contract rejects post-check repair subprocess invoked")


def build_real_execution_adapter_contract_record(
    post_repair_evidence_check: Mapping[str, Any],
    *,
    source: str = "real-execution-adapter-contract",
) -> dict[str, Any]:
    """Build a fail-closed real execution adapter contract record."""
    _validate_post_repair_evidence_check(post_repair_evidence_check)

    check_id = _clean(post_repair_evidence_check.get("post_repair_evidence_check_id"))
    guarded_result_id = _clean(
        post_repair_evidence_check.get("guarded_repair_execution_result_id")
    )
    rendered_command_id = _clean(post_repair_evidence_check.get("rendered_command_id"))
    proposal_id = _clean(post_repair_evidence_check.get("proposal_id"))

    contract_id = _stable_id(
        "replay-retry-real-execution-adapter-contract",
        check_id,
        guarded_result_id,
        rendered_command_id,
        proposal_id,
        CONTRACT_SCHEMA_VERSION,
    )

    payload = {
        "real_execution_adapter_contract_id": contract_id,
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "adapter_request_schema_version": REQUEST_SCHEMA_VERSION,
        "adapter_result_schema_version": RESULT_SCHEMA_VERSION,
        "post_repair_evidence_check_id": check_id,
        "guarded_repair_execution_result_id": guarded_result_id,
        "real_execution_repair_readiness_gate_id": _clean(
            post_repair_evidence_check.get("real_execution_repair_readiness_gate_id")
        ),
        "real_execution_repair_noop_feedback_id": _clean(
            post_repair_evidence_check.get("real_execution_repair_noop_feedback_id")
        ),
        "real_execution_repair_noop_result_id": _clean(
            post_repair_evidence_check.get("real_execution_repair_noop_result_id")
        ),
        "real_execution_repair_dry_run_envelope_id": _clean(
            post_repair_evidence_check.get("real_execution_repair_dry_run_envelope_id")
        ),
        "real_execution_repair_final_gate_id": _clean(
            post_repair_evidence_check.get("real_execution_repair_final_gate_id")
        ),
        "controlled_execution_result_id": _clean(
            post_repair_evidence_check.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(post_repair_evidence_check.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(post_repair_evidence_check.get("approval_id")),
        "decision_mode": _clean(post_repair_evidence_check.get("decision_mode"))
        or "manual",
        "timeout_profile": _clean(post_repair_evidence_check.get("timeout_profile"))
        or "standard",
        "contract_status": "defined",
        "contract_kind": "policy_gated_real_execution_adapter",
        "adapter_contract_exists": True,
        "adapter_request_schema_exists": True,
        "adapter_result_schema_exists": True,
        "fail_closed_default": True,
        "sandbox_first": True,
        "capability_scoped": True,
        "policy_gated": True,
        "approval_gated": True,
        "rollback_required": True,
        "post_execution_evidence_required": True,
        "audit_record_required": True,
        "direct_rendered_command_execution_allowed": False,
        "arbitrary_shell_execution_allowed": False,
        "unknown_capability_rejected": True,
        "unknown_policy_rejected": True,
        "missing_approval_rejected": True,
        "missing_final_gate_rejected": True,
        "missing_dry_run_envelope_rejected": True,
        "missing_rollback_plan_rejected": True,
        "missing_post_execution_evidence_rejected": True,
        "orphaned_records_rejected": True,
        "stale_records_rejected": True,
        "supported_execution_levels": list(SUPPORTED_EXECUTION_LEVELS),
        "enabled_execution_levels": list(ENABLED_EXECUTION_LEVELS),
        "disabled_execution_levels": list(DISABLED_EXECUTION_LEVELS),
        "adapter_request_required_fields": list(ADAPTER_REQUEST_REQUIRED_FIELDS),
        "adapter_result_required_fields": list(ADAPTER_RESULT_REQUIRED_FIELDS),
        "required_gate_fields": list(REQUIRED_GATE_FIELDS),
        "next_implementation_step": "build_fail_closed_adapter_request_schema",
        "recommended_next_action": "prepare_real_execution_adapter_request_schema",
        "source_post_repair_status": _clean(
            post_repair_evidence_check.get("post_repair_status")
        ),
        "source_repair_outcome_verified": bool(
            post_repair_evidence_check.get("repair_outcome_verified")
        ),
        "source_post_repair_next_action": _clean(
            post_repair_evidence_check.get("recommended_next_action")
        ),
        "source_repair_targets_expected_count": int(
            post_repair_evidence_check.get("repair_targets_expected_count") or 0
        ),
        "source_repair_targets_verified_count": int(
            post_repair_evidence_check.get("repair_targets_verified_count") or 0
        ),
        "adapter_implementation_enabled": False,
        "adapter_request_generation_enabled": False,
        "adapter_result_generation_enabled": False,
        "sandbox_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "reason": "real_execution_adapter_contract_defined_not_runnable",
    }

    return {
        "type": REAL_EXECUTION_ADAPTER_CONTRACT_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    post_repair_evidence_check_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if (
        post_repair_evidence_check_id
        and _clean(record.get("post_repair_evidence_check_id"))
        != post_repair_evidence_check_id
    ):
        return False
    return True


def _find_existing_contract(
    records: list[Mapping[str, Any]],
    *,
    post_repair_evidence_check_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_EXECUTION_ADAPTER_CONTRACT_TYPE:
            continue
        if (
            _clean(item.get("post_repair_evidence_check_id"))
            == post_repair_evidence_check_id
        ):
            return item
    return None


async def build_real_execution_adapter_contract_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-adapter-contract"
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    post_repair_evidence_check_id = _clean(
        getattr(args, "post_repair_evidence_check_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    post_repair_checks = [
        item
        for item in records
        if item.get("type") == POST_REPAIR_EVIDENCE_CHECK_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            post_repair_evidence_check_id=post_repair_evidence_check_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for check in post_repair_checks:
        check_id = _clean(check.get("post_repair_evidence_check_id"))
        if _find_existing_contract(records, post_repair_evidence_check_id=check_id):
            logger.info(
                "Skipping duplicate real execution adapter contract: post_repair_evidence_check_id=%s",
                check_id,
            )
            continue

        record = build_real_execution_adapter_contract_record(check, source=source)
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published real execution adapter contract: contract_id=%s "
            "contract_status=%s runnable=%s real_execution_enabled=%s",
            record.get("real_execution_adapter_contract_id"),
            record.get("contract_status"),
            record.get("adapter_implementation_enabled"),
            record.get("real_execution_enabled"),
        )

    logger.info("Real execution adapter contract builder completed: contracts=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build policy-gated real execution adapter contract records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--post-repair-evidence-check-id", default="")
    parser.add_argument("--source", default="real-execution-adapter-contract")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_adapter_contract_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Real execution adapter contract builder completed: contracts={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()