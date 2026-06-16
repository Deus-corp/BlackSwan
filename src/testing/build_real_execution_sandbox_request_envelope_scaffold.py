"""Build fail-closed sandbox request envelope scaffold records.

This artifact prepares a blocked sandbox request envelope scaffold from a valid
sandbox adapter request preflight.

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

SANDBOX_REQUEST_PREFLIGHT_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight"
)
SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_TYPE = (
    "replay_lifecycle_retry_real_execution_sandbox_request_envelope_scaffold"
)

SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION = (
    "real-execution-sandbox-request-envelope-scaffold/v1"
)
EXPECTED_SANDBOX_REQUEST_PREFLIGHT_SCHEMA_VERSION = (
    "real-execution-sandbox-adapter-request-preflight/v1"
)

REQUIRED_PREFLIGHT_TRUE_FLAGS = [
    "sandbox_adapter_request_preflight_exists",
    "sandbox_adapter_request_preflight_fail_closed",
    "sandbox_adapter_request_preflight_deny_by_default",
    "sandbox_adapter_request_preflight_requires_policy_matrix",
    "sandbox_adapter_request_preflight_requires_known_capability",
    "sandbox_adapter_request_preflight_requires_known_policy",
    "sandbox_adapter_request_preflight_requires_operator_authorization",
    "sandbox_adapter_request_preflight_requires_approval_lineage",
    "sandbox_adapter_request_preflight_requires_final_gate",
    "sandbox_adapter_request_preflight_requires_dry_run_envelope",
    "sandbox_adapter_request_preflight_requires_rollback_plan",
    "sandbox_adapter_request_preflight_requires_post_execution_evidence",
    "sandbox_adapter_request_preflight_rejects_unknown_capability",
    "sandbox_adapter_request_preflight_rejects_unknown_policy",
    "sandbox_adapter_request_preflight_rejects_orphans",
    "sandbox_adapter_request_preflight_rejects_stale_records",
    "source_scaffold_exists",
    "source_scaffold_fail_closed",
    "source_scaffold_deny_by_default",
]

REQUIRED_PREFLIGHT_FALSE_FLAGS = [
    "sandbox_adapter_request_generation_allowed",
    "sandbox_adapter_request_generation_enabled",
    "sandbox_workspace_creation_allowed",
    "sandbox_workspace_creation_enabled",
    "sandbox_input_materialization_allowed",
    "sandbox_input_materialization_enabled",
    "sandbox_command_rendering_allowed",
    "sandbox_command_rendering_enabled",
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
    "source_scaffold_sandbox_execution_enabled",
    "source_scaffold_execution_performed",
    "source_scaffold_subprocess_invoked",
    "source_scaffold_real_execution_enabled",
    "source_scaffold_external_side_effects_performed",
    "source_scaffold_production_paths_mutated",
    "source_scaffold_production_secrets_accessed",
]

EXPECTED_PREFLIGHT_STRINGS = {
    "schema_version": EXPECTED_SANDBOX_REQUEST_PREFLIGHT_SCHEMA_VERSION,
    "sandbox_adapter_request_preflight_status": "blocked",
    "sandbox_adapter_request_preflight_kind": (
        "fail_closed_sandbox_adapter_request_preflight"
    ),
    "source_scaffold_schema_version": "real-execution-sandbox-adapter-scaffold/v1",
    "source_sandbox_adapter_contract_version": "real-execution-sandbox-adapter/v1",
    "source_scaffold_status": "defined",
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
    "recommended_next_action": (
        "surface_sandbox_adapter_request_preflight_observability"
    ),
    "reason": "sandbox_adapter_request_preflight_defined_blocked_not_runnable",
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
            f"source sandbox adapter request preflight requires {key}={expected_text}"
        )


def _validate_sandbox_adapter_request_preflight(record: Mapping[str, Any]) -> None:
    preflight_id = _clean(
        record.get("real_execution_sandbox_adapter_request_preflight_id")
    )
    scaffold_id = _clean(record.get("real_execution_sandbox_adapter_scaffold_id"))
    matrix_id = _clean(record.get("real_execution_capability_policy_matrix_id"))
    request_schema_id = _clean(record.get("real_execution_adapter_request_schema_id"))
    contract_id = _clean(record.get("real_execution_adapter_contract_id"))
    rendered_command_id = _clean(record.get("rendered_command_id"))
    proposal_id = _clean(record.get("proposal_id"))

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

    for key, expected in EXPECTED_PREFLIGHT_STRINGS.items():
        if _clean(record.get(key)) != expected:
            raise ValueError(
                f"source sandbox adapter request preflight requires {key}={expected}"
            )

    for key in REQUIRED_PREFLIGHT_TRUE_FLAGS:
        _require_bool(record, key, True)

    for key in REQUIRED_PREFLIGHT_FALSE_FLAGS:
        _require_bool(record, key, False)

    required_fields = set(_safe_list(record.get("sandbox_request_required_fields")))
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
            "source sandbox adapter request preflight missing required field(s): "
            + ",".join(missing)
        )

    if _safe_list(record.get("sandbox_request_allowed_input_paths")):
        raise ValueError(
            "source sandbox adapter request preflight must not allow input paths"
        )
    if _safe_list(record.get("sandbox_request_allowed_output_paths")):
        raise ValueError(
            "source sandbox adapter request preflight must not allow output paths"
        )


def build_real_execution_sandbox_request_envelope_scaffold_record(
    sandbox_adapter_request_preflight: Mapping[str, Any],
    *,
    source: str = "real-execution-sandbox-request-envelope-scaffold",
) -> dict[str, Any]:
    """Build blocked sandbox request envelope scaffold record."""
    _validate_sandbox_adapter_request_preflight(sandbox_adapter_request_preflight)

    preflight_id = _clean(
        sandbox_adapter_request_preflight.get(
            "real_execution_sandbox_adapter_request_preflight_id"
        )
    )
    scaffold_id = _clean(
        sandbox_adapter_request_preflight.get(
            "real_execution_sandbox_adapter_scaffold_id"
        )
    )
    matrix_id = _clean(
        sandbox_adapter_request_preflight.get(
            "real_execution_capability_policy_matrix_id"
        )
    )
    request_schema_id = _clean(
        sandbox_adapter_request_preflight.get(
            "real_execution_adapter_request_schema_id"
        )
    )
    contract_id = _clean(
        sandbox_adapter_request_preflight.get("real_execution_adapter_contract_id")
    )
    rendered_command_id = _clean(
        sandbox_adapter_request_preflight.get("rendered_command_id")
    )
    proposal_id = _clean(sandbox_adapter_request_preflight.get("proposal_id"))

    envelope_id = _stable_id(
        "replay-retry-real-execution-sandbox-request-envelope-scaffold",
        preflight_id,
        scaffold_id,
        matrix_id,
        request_schema_id,
        contract_id,
        rendered_command_id,
        proposal_id,
        SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION,
    )

    payload = {
        "real_execution_sandbox_request_envelope_scaffold_id": envelope_id,
        "real_execution_sandbox_adapter_request_preflight_id": preflight_id,
        "real_execution_sandbox_adapter_scaffold_id": scaffold_id,
        "real_execution_capability_policy_matrix_id": matrix_id,
        "real_execution_adapter_request_schema_id": request_schema_id,
        "real_execution_adapter_contract_id": contract_id,
        "post_repair_evidence_check_id": _clean(
            sandbox_adapter_request_preflight.get("post_repair_evidence_check_id")
        ),
        "guarded_repair_execution_result_id": _clean(
            sandbox_adapter_request_preflight.get("guarded_repair_execution_result_id")
        ),
        "controlled_execution_result_id": _clean(
            sandbox_adapter_request_preflight.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(sandbox_adapter_request_preflight.get("plan_id")),
        "proposal_id": proposal_id,
        "approval_id": _clean(sandbox_adapter_request_preflight.get("approval_id")),
        "decision_mode": _clean(sandbox_adapter_request_preflight.get("decision_mode"))
        or "manual",
        "timeout_profile": _clean(
            sandbox_adapter_request_preflight.get("timeout_profile")
        )
        or "standard",
        "schema_version": SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_SCHEMA_VERSION,
        "source_request_preflight_schema_version": _clean(
            sandbox_adapter_request_preflight.get("schema_version")
        ),
        "sandbox_request_envelope_scaffold_status": "blocked",
        "sandbox_request_envelope_scaffold_kind": (
            "fail_closed_sandbox_request_envelope_scaffold"
        ),
        "sandbox_request_envelope_scaffold_exists": True,
        "sandbox_request_envelope_scaffold_fail_closed": True,
        "sandbox_request_envelope_scaffold_deny_by_default": True,
        "sandbox_request_envelope_requires_preflight": True,
        "sandbox_request_envelope_requires_policy_matrix": True,
        "sandbox_request_envelope_requires_known_capability": True,
        "sandbox_request_envelope_requires_known_policy": True,
        "sandbox_request_envelope_requires_operator_authorization": True,
        "sandbox_request_envelope_requires_approval_lineage": True,
        "sandbox_request_envelope_requires_final_gate": True,
        "sandbox_request_envelope_requires_dry_run_envelope": True,
        "sandbox_request_envelope_requires_rollback_plan": True,
        "sandbox_request_envelope_requires_post_execution_evidence": True,
        "sandbox_request_envelope_rejects_unknown_capability": True,
        "sandbox_request_envelope_rejects_unknown_policy": True,
        "sandbox_request_envelope_rejects_orphans": True,
        "sandbox_request_envelope_rejects_stale_records": True,
        "sandbox_request_required_fields": list(
            _safe_list(
                sandbox_adapter_request_preflight.get(
                    "sandbox_request_required_fields"
                )
            )
        ),
        "sandbox_request_allowed_input_paths": [],
        "sandbox_request_allowed_output_paths": [],
        "sandbox_request_envelope_generation_allowed": False,
        "sandbox_request_envelope_generation_enabled": False,
        "sandbox_request_envelope_materialized": False,
        "sandbox_request_envelope_executable": False,
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
        "source_preflight_status": _clean(
            sandbox_adapter_request_preflight.get(
                "sandbox_adapter_request_preflight_status"
            )
        ),
        "source_preflight_exists": bool(
            sandbox_adapter_request_preflight.get(
                "sandbox_adapter_request_preflight_exists"
            )
        ),
        "source_preflight_fail_closed": bool(
            sandbox_adapter_request_preflight.get(
                "sandbox_adapter_request_preflight_fail_closed"
            )
        ),
        "source_preflight_deny_by_default": bool(
            sandbox_adapter_request_preflight.get(
                "sandbox_adapter_request_preflight_deny_by_default"
            )
        ),
        "source_preflight_request_generation_enabled": bool(
            sandbox_adapter_request_preflight.get(
                "sandbox_adapter_request_generation_enabled"
            )
        ),
        "source_preflight_workspace_creation_enabled": bool(
            sandbox_adapter_request_preflight.get("sandbox_workspace_creation_enabled")
        ),
        "source_preflight_input_materialization_enabled": bool(
            sandbox_adapter_request_preflight.get(
                "sandbox_input_materialization_enabled"
            )
        ),
        "source_preflight_command_rendering_enabled": bool(
            sandbox_adapter_request_preflight.get("sandbox_command_rendering_enabled")
        ),
        "source_preflight_sandbox_execution_enabled": bool(
            sandbox_adapter_request_preflight.get("sandbox_execution_enabled")
        ),
        "source_preflight_result_generation_enabled": bool(
            sandbox_adapter_request_preflight.get("sandbox_result_generation_enabled")
        ),
        "source_preflight_execution_performed": bool(
            sandbox_adapter_request_preflight.get("execution_performed")
        ),
        "source_preflight_subprocess_invoked": bool(
            sandbox_adapter_request_preflight.get("subprocess_invoked")
        ),
        "source_preflight_real_execution_enabled": bool(
            sandbox_adapter_request_preflight.get("real_execution_enabled")
        ),
        "source_preflight_external_side_effects_performed": bool(
            sandbox_adapter_request_preflight.get("external_side_effects_performed")
        ),
        "source_preflight_production_paths_mutated": bool(
            sandbox_adapter_request_preflight.get("production_paths_mutated")
        ),
        "source_preflight_production_secrets_accessed": bool(
            sandbox_adapter_request_preflight.get("production_secrets_accessed")
        ),
        "recommended_next_action": (
            "surface_sandbox_request_envelope_scaffold_observability"
        ),
        "reason": "sandbox_request_envelope_scaffold_defined_blocked_not_runnable",
    }

    return {
        "type": SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    rendered_command_id: str,
    preflight_id: str,
) -> bool:
    if proposal_id and _clean(record.get("proposal_id")) != proposal_id:
        return False
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        preflight_id
        and _clean(record.get("real_execution_sandbox_adapter_request_preflight_id"))
        != preflight_id
    ):
        return False
    return True


def _find_existing_envelope_scaffold(
    records: list[Mapping[str, Any]],
    *,
    preflight_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != SANDBOX_REQUEST_ENVELOPE_SCAFFOLD_TYPE:
            continue
        if (
            _clean(item.get("real_execution_sandbox_adapter_request_preflight_id"))
            == preflight_id
        ):
            return item
    return None


async def build_real_execution_sandbox_request_envelope_scaffold_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-sandbox-request-envelope-scaffold"
    )
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    preflight_id = _clean(
        getattr(args, "real_execution_sandbox_adapter_request_preflight_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    preflights = [
        item
        for item in records
        if item.get("type") == SANDBOX_REQUEST_PREFLIGHT_TYPE
        and _matches_filters(
            item,
            proposal_id=proposal_id,
            rendered_command_id=rendered_command_id,
            preflight_id=preflight_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for preflight in preflights:
        current_preflight_id = _clean(
            preflight.get("real_execution_sandbox_adapter_request_preflight_id")
        )
        if _find_existing_envelope_scaffold(
            records,
            preflight_id=current_preflight_id,
        ):
            logger.info(
                "Skipping duplicate sandbox request envelope scaffold: "
                "preflight_id=%s",
                current_preflight_id,
            )
            continue

        record = build_real_execution_sandbox_request_envelope_scaffold_record(
            preflight,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published sandbox request envelope scaffold: envelope_id=%s "
            "status=%s request_generation_enabled=%s sandbox_execution_enabled=%s",
            record.get("real_execution_sandbox_request_envelope_scaffold_id"),
            record.get("sandbox_request_envelope_scaffold_status"),
            record.get("sandbox_request_envelope_generation_enabled"),
            record.get("sandbox_execution_enabled"),
        )

    logger.info(
        "Sandbox request envelope scaffold builder completed: envelopes=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build blocked sandbox request envelope scaffold records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument(
        "--real-execution-sandbox-adapter-request-preflight-id",
        default="",
    )
    parser.add_argument(
        "--source",
        default="real-execution-sandbox-request-envelope-scaffold",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_sandbox_request_envelope_scaffold_records(
        args
    )

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Sandbox request envelope scaffold builder completed: "
            f"envelopes={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()