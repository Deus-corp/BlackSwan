from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.testing.inspect_cluster_latest_artifacts import (
    DEFAULT_ARTIFACTS_ROOT,
    SECONDS_PER_DAY,
    inspect_cluster_latest_artifacts,
)


RESULT_TYPE = "cluster_latest_artifacts_cleanup_result"
MODE_DRY_RUN = "dry_run"

SAFETY_FLAGS = (
    "external_write_performed",
    "real_execution_enabled",
    "production_paths_mutated",
    "production_secrets_accessed",
)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    return str(value)


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_cluster_latest_artifacts_cleanup_result(
    *,
    artifacts_root: str | Path = "",
    retention_max_age_seconds: float = 0.0,
    now: float | None = None,
) -> dict[str, Any]:
    """Build dry-run cleanup summary for latest artifacts.

    This function never deletes files. It only reuses the inspect-only retention
    policy from inspect_cluster_latest_artifacts and exposes would-delete data
    in a cleanup-shaped result.
    """
    summary = inspect_cluster_latest_artifacts(
        artifacts_root=artifacts_root,
        retention_max_age_seconds=retention_max_age_seconds,
        now=now,
    )

    retention = summary.get("retention")
    if not isinstance(retention, Mapping):
        retention = {}

    would_delete = list(retention.get("would_delete") or [])
    would_delete_count = _safe_int(
        retention.get("would_delete_count"),
        default=len(would_delete),
    )

    return {
        "type": RESULT_TYPE,
        "mode": MODE_DRY_RUN,
        "status": "completed",
        "artifacts_root": str(
            artifacts_root or summary.get("artifacts_root") or DEFAULT_ARTIFACTS_ROOT
        ),
        "source_summary_type": summary.get("type"),
        "source_status": summary.get("status"),
        "source_contract_ok": bool(summary.get("contract_ok")),
        "artifact_count": _safe_int(summary.get("artifact_count"), default=0),
        "known_artifact_count": _safe_int(
            summary.get("known_artifact_count"),
            default=0,
        ),
        "invalid_artifact_count": _safe_int(
            summary.get("invalid_artifact_count"),
            default=0,
        ),
        "stale_artifact_count": _safe_int(
            summary.get("stale_artifact_count"),
            default=0,
        ),
        "retention": dict(retention),
        "would_delete_count": would_delete_count,
        "would_delete": would_delete,
        "deleted_count": 0,
        "deleted": [],
        "contract_ok": bool(summary.get("contract_ok")),
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def validate_cluster_latest_artifacts_cleanup_result(
    result: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []

    if result.get("type") != RESULT_TYPE:
        errors.append(f"type must be {RESULT_TYPE}")

    if result.get("mode") != MODE_DRY_RUN:
        errors.append(f"mode must be {MODE_DRY_RUN}")

    if result.get("status") != "completed":
        errors.append("status must be completed")

    for flag in SAFETY_FLAGS:
        if bool(result.get(flag)):
            errors.append(f"{flag} must be false")

    if _safe_int(result.get("deleted_count"), default=-1) != 0:
        errors.append("deleted_count must be 0 for dry-run cleanup")

    deleted = result.get("deleted")
    if deleted != []:
        errors.append("deleted must be an empty list for dry-run cleanup")

    would_delete = result.get("would_delete")
    if not isinstance(would_delete, list):
        errors.append("would_delete must be a list")
        would_delete = []

    would_delete_count = _safe_int(result.get("would_delete_count"), default=-1)
    if would_delete_count != len(would_delete):
        errors.append(
            "would_delete_count must equal len(would_delete): "
            f"would_delete_count={would_delete_count}, len={len(would_delete)}"
        )

    retention = result.get("retention")
    if not isinstance(retention, Mapping):
        errors.append("retention must be a mapping")
        retention = {}

    if retention.get("mode") != "inspect_only":
        errors.append("retention.mode must be inspect_only")

    retention_would_delete_count = _safe_int(
        retention.get("would_delete_count"),
        default=-1,
    )
    if retention_would_delete_count != would_delete_count:
        errors.append(
            "retention.would_delete_count must match would_delete_count: "
            f"retention={retention_would_delete_count}, "
            f"cleanup={would_delete_count}"
        )

    if _safe_float(retention.get("max_age_seconds"), default=-1.0) < 0.0:
        errors.append("retention.max_age_seconds must be >= 0")

    if _safe_int(result.get("artifact_count"), default=-1) < 0:
        errors.append("artifact_count must be >= 0")

    if _safe_int(result.get("known_artifact_count"), default=-1) < 0:
        errors.append("known_artifact_count must be >= 0")

    if _safe_int(result.get("invalid_artifact_count"), default=-1) < 0:
        errors.append("invalid_artifact_count must be >= 0")

    if _safe_int(result.get("stale_artifact_count"), default=-1) < 0:
        errors.append("stale_artifact_count must be >= 0")

    if bool(result.get("source_contract_ok")) is not bool(result.get("contract_ok")):
        errors.append("source_contract_ok must match contract_ok")

    for index, item in enumerate(would_delete, start=1):
        if not isinstance(item, Mapping):
            errors.append(f"would_delete item #{index} must be a mapping")
            continue

        if not str(item.get("path") or "").strip():
            errors.append(f"would_delete item #{index} path is required")

        if not str(item.get("reason") or "").strip():
            errors.append(f"would_delete item #{index} reason is required")

        if _safe_float(item.get("age_seconds"), default=-1.0) < 0.0:
            errors.append(f"would_delete item #{index} age_seconds must be >= 0")

    return errors


def assert_cluster_latest_artifacts_cleanup_result(
    result: Mapping[str, Any],
) -> None:
    errors = validate_cluster_latest_artifacts_cleanup_result(result)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise AssertionError(
            "cluster latest artifacts cleanup contract failed:\n"
            f"{details}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run cleanup inspector for cluster latest artifacts. "
            "No files are deleted."
        ),
    )
    parser.add_argument(
        "--artifacts-root",
        default="",
        help=(
            "Directory containing latest artifact JSON files. Defaults to "
            "data/cluster_runtime/latest/artifacts."
        ),
    )
    parser.add_argument(
        "--retention-max-age-days",
        type=float,
        default=0.0,
        help=(
            "Dry-run retention threshold in days. Artifacts older than this "
            "threshold are reported in would_delete. No files are deleted."
        ),
    )
    parser.add_argument(
        "--retention-max-age-seconds",
        type=float,
        default=0.0,
        help=(
            "Dry-run retention threshold in seconds. Overrides days when "
            "provided. No files are deleted."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Explicitly run in dry-run mode. This command never deletes files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print machine-readable JSON summary.",
    )
    parser.add_argument(
        "--check-contract",
        action="store_true",
        default=False,
        help="Exit with code 1 unless the dry-run cleanup contract is valid.",
    )
    return parser


def _print_human_summary(result: Mapping[str, Any]) -> None:
    print("Cluster latest artifacts cleanup")
    print(f"  mode:             {result.get('mode', '')}")
    print(f"  status:           {result.get('status', '')}")
    print(f"  artifacts_root:   {result.get('artifacts_root', '')}")
    print(f"  source_contract:  {result.get('source_contract_ok')}")
    print(f"  artifact_count:   {result.get('artifact_count', 0)}")
    print(f"  stale_count:      {result.get('stale_artifact_count', 0)}")
    print(f"  invalid_count:    {result.get('invalid_artifact_count', 0)}")
    print(f"  would_delete:     {result.get('would_delete_count', 0)}")
    print(f"  deleted_count:    {result.get('deleted_count', 0)}")

    retention = result.get("retention")
    if isinstance(retention, Mapping):
        print(
            "  retention:        "
            f"mode={retention.get('mode', '')} "
            f"max_age_seconds={retention.get('max_age_seconds', 0.0)} "
            f"max_age_days={retention.get('max_age_days', 0.0)}"
        )

    would_delete = result.get("would_delete")
    if isinstance(would_delete, list) and would_delete:
        print("\nWould delete:")
        for item in would_delete:
            if not isinstance(item, Mapping):
                continue
            print(
                f"- {item.get('name', '')}: "
                f"path={item.get('path', '')} "
                f"age_seconds={item.get('age_seconds', 0.0)} "
                f"reason={item.get('reason', '')}"
            )


def _retention_seconds_from_args(args: argparse.Namespace) -> float:
    retention_max_age_seconds = _safe_float(
        getattr(args, "retention_max_age_seconds", 0.0),
        default=0.0,
    )
    if retention_max_age_seconds > 0.0:
        return retention_max_age_seconds

    retention_max_age_days = _safe_float(
        getattr(args, "retention_max_age_days", 0.0),
        default=0.0,
    )
    return max(0.0, retention_max_age_days * SECONDS_PER_DAY)


def main() -> None:
    args = build_parser().parse_args()

    result = build_cluster_latest_artifacts_cleanup_result(
        artifacts_root=str(args.artifacts_root or ""),
        retention_max_age_seconds=_retention_seconds_from_args(args),
    )

    assert_cluster_latest_artifacts_cleanup_result(result)

    if bool(args.json):
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=_json_default,
            )
        )
    else:
        _print_human_summary(result)

    if bool(args.check_contract):
        if result.get("contract_ok") is True:
            print("✅ cluster latest artifacts cleanup dry-run contract OK")
            raise SystemExit(0)

        raise SystemExit(1)


if __name__ == "__main__":
    main()