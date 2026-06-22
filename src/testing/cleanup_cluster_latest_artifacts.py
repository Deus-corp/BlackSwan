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

MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS = "execute_delete_local_artifacts"

ALLOWED_MODES = {
    MODE_DRY_RUN,
    MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS,
}

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


def _compact_post_cleanup_summary(
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Build compact post-cleanup verification summary.

    For dry-run this reflects the same read-only index. For execute mode this
    should be built from a fresh post-delete index.
    """
    retention = summary.get("retention")
    if not isinstance(retention, Mapping):
        retention = {}

    artifact_count = _safe_int(summary.get("artifact_count"), default=0)
    known_artifact_count = _safe_int(summary.get("known_artifact_count"), default=0)
    invalid_artifact_count = _safe_int(
        summary.get("invalid_artifact_count"),
        default=0,
    )
    stale_artifact_count = _safe_int(
        summary.get("stale_artifact_count"),
        default=0,
    )
    would_delete_count = _safe_int(
        retention.get("would_delete_count"),
        default=0,
    )

    return {
        "checked": True,
        "source_summary_type": summary.get("type"),
        "status": str(summary.get("status") or "unknown"),
        "artifacts_root": str(summary.get("artifacts_root") or ""),
        "artifact_count": artifact_count,
        "known_artifact_count": known_artifact_count,
        "invalid_artifact_count": invalid_artifact_count,
        "stale_artifact_count": stale_artifact_count,
        "contract_ok": bool(summary.get("contract_ok")),
        "cleanup_ok": (
            invalid_artifact_count == 0
            and stale_artifact_count == 0
            and would_delete_count == 0
        ),
        "retention": {
            "mode": retention.get("mode", ""),
            "max_age_seconds": _safe_float(
                retention.get("max_age_seconds"),
                default=0.0,
            ),
            "max_age_days": _safe_float(
                retention.get("max_age_days"),
                default=0.0,
            ),
            "would_delete_count": would_delete_count,
            "oldest_artifact_mtime": _safe_float(
                retention.get("oldest_artifact_mtime"),
                default=0.0,
            ),
            "newest_artifact_mtime": _safe_float(
                retention.get("newest_artifact_mtime"),
                default=0.0,
            ),
        },
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolved_default_artifacts_root() -> Path:
    return DEFAULT_ARTIFACTS_ROOT.resolve()


def _cleanup_root_allowed(root: Path) -> bool:
    """Return true only for the allowlisted local latest artifacts root."""
    return root.resolve() == _resolved_default_artifacts_root()


def _safe_unlink_artifact(path: Path) -> tuple[bool, str]:
    try:
        if not path.exists():
            return False, "artifact does not exist"

        if not path.is_file():
            return False, "artifact path is not a file"

        path.unlink()
        return True, ""
    except OSError as exc:
        return False, str(exc)


def build_cluster_latest_artifacts_cleanup_result(
    *,
    artifacts_root: str | Path = "",
    retention_max_age_seconds: float = 0.0,
    now: float | None = None,
    execute_delete_local_artifacts: bool = False,
) -> dict[str, Any]:
    """Build dry-run cleanup summary for latest artifacts.

    This function never deletes files. It only reuses the inspect-only retention
    policy from inspect_cluster_latest_artifacts and exposes would-delete data
    in a cleanup-shaped result.
    """
    root = (
        Path(artifacts_root)
        if str(artifacts_root or "").strip()
        else DEFAULT_ARTIFACTS_ROOT
    )

    summary = inspect_cluster_latest_artifacts(
        artifacts_root=root,
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

    mode = (
        MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS
        if execute_delete_local_artifacts
        else MODE_DRY_RUN
    )

    root_resolved = root.resolve()
    cleanup_root_allowed = _cleanup_root_allowed(root)
    source_contract_ok = bool(summary.get("contract_ok"))

    deleted: list[dict[str, Any]] = []
    deletion_errors: list[dict[str, Any]] = []
    local_artifact_deletion_performed = False
    status = "completed"

    if execute_delete_local_artifacts:
        if not cleanup_root_allowed:
            status = "blocked"
            deletion_errors.append(
                {
                    "reason": "artifacts_root_not_allowlisted",
                    "artifacts_root": str(root),
                    "allowlisted_root": str(_resolved_default_artifacts_root()),
                }
            )
        elif not source_contract_ok:
            status = "blocked"
            deletion_errors.append(
                {
                    "reason": "source_contract_not_ok",
                    "source_status": summary.get("status"),
                }
            )
        else:
            would_delete_paths = {
                str(Path(str(item.get("path") or "")).resolve())
                for item in would_delete
                if isinstance(item, Mapping)
            }

            for item in would_delete:
                if not isinstance(item, Mapping):
                    continue

                candidate_path = Path(str(item.get("path") or "")).resolve()

                if str(candidate_path) not in would_delete_paths:
                    deletion_errors.append(
                        {
                            "path": str(candidate_path),
                            "reason": "path_not_in_retention_would_delete",
                        }
                    )
                    continue

                if not _is_relative_to(candidate_path, root_resolved):
                    deletion_errors.append(
                        {
                            "path": str(candidate_path),
                            "reason": "path_outside_artifacts_root",
                        }
                    )
                    continue

                deleted_ok, error = _safe_unlink_artifact(candidate_path)
                if deleted_ok:
                    deleted_item = dict(item)
                    deleted_item["deleted"] = True
                    deleted.append(deleted_item)
                    local_artifact_deletion_performed = True
                else:
                    deletion_errors.append(
                        {
                            "path": str(candidate_path),
                            "reason": error or "delete_failed",
                        }
                    )

            if deletion_errors:
                status = "partial" if deleted else "failed"
    
    if mode == MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS and cleanup_root_allowed:
        post_cleanup_source = inspect_cluster_latest_artifacts(
            artifacts_root=root,
            retention_max_age_seconds=retention_max_age_seconds,
            now=now,
        )
    else:
        post_cleanup_source = summary

    post_cleanup = _compact_post_cleanup_summary(post_cleanup_source)

    contract_ok = (
        source_contract_ok
        and not deletion_errors
        and (
            mode == MODE_DRY_RUN
            or cleanup_root_allowed
        )
    )

    return {
        "type": RESULT_TYPE,
        "mode": mode,
        "status": status,
        "artifacts_root": str(root),
        "allowlisted_artifacts_root": str(_resolved_default_artifacts_root()),
        "artifacts_root_allowed": cleanup_root_allowed,
        "execute_delete_local_artifacts": bool(execute_delete_local_artifacts),
        "local_artifact_deletion_performed": local_artifact_deletion_performed,
        "source_summary_type": summary.get("type"),
        "source_status": summary.get("status"),
        "source_contract_ok": source_contract_ok,
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
        "deleted_count": len(deleted),
        "deleted": deleted,
        "deletion_errors": deletion_errors,
        "post_cleanup": post_cleanup,
        "contract_ok": contract_ok,
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

    mode = str(result.get("mode") or "")
    if mode not in ALLOWED_MODES:
        errors.append(
            f"mode must be one of {sorted(ALLOWED_MODES)}"
        )

    status = str(result.get("status") or "")
    if status not in {"completed", "blocked", "partial", "failed"}:
        errors.append("status must be completed, blocked, partial, or failed")

    for flag in SAFETY_FLAGS:
        if bool(result.get(flag)):
            errors.append(f"{flag} must be false")

    deleted = result.get("deleted")
    if not isinstance(deleted, list):
        errors.append("deleted must be a list")
        deleted = []

    deleted_count = _safe_int(result.get("deleted_count"), default=-1)
    if deleted_count != len(deleted):
        errors.append(
            "deleted_count must equal len(deleted): "
            f"deleted_count={deleted_count}, len={len(deleted)}"
        )

    local_delete_performed = bool(
        result.get("local_artifact_deletion_performed")
    )

    if mode == MODE_DRY_RUN:
        if deleted_count != 0:
            errors.append("deleted_count must be 0 for dry-run cleanup")

        if deleted:
            errors.append("deleted must be an empty list for dry-run cleanup")

        if local_delete_performed:
            errors.append(
                "local_artifact_deletion_performed must be false for dry-run"
            )

    if mode == MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS:
        if result.get("execute_delete_local_artifacts") is not True:
            errors.append(
                "execute_delete_local_artifacts must be true in execute mode"
            )

        if result.get("artifacts_root_allowed") is not True:
            errors.append(
                "artifacts_root_allowed must be true in execute mode"
            )

        if deleted_count > 0 and not local_delete_performed:
            errors.append(
                "local_artifact_deletion_performed must be true when "
                "deleted_count > 0"
            )

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
    
    deletion_errors = result.get("deletion_errors")
    if not isinstance(deletion_errors, list):
        errors.append("deletion_errors must be a list")
        deletion_errors = []

    if bool(result.get("contract_ok")) and deletion_errors:
        errors.append("deletion_errors must be empty when contract_ok is true")

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
    
    would_delete_paths = {
        str(item.get("path") or "")
        for item in would_delete
        if isinstance(item, Mapping)
    }

    for index, item in enumerate(deleted, start=1):
        if not isinstance(item, Mapping):
            errors.append(f"deleted item #{index} must be a mapping")
            continue

        path = str(item.get("path") or "").strip()
        if not path:
            errors.append(f"deleted item #{index} path is required")

        if path and path not in would_delete_paths:
            errors.append(
                f"deleted item #{index} path must be present in would_delete"
            )
    
    post_cleanup = result.get("post_cleanup")
    if not isinstance(post_cleanup, Mapping):
        errors.append("post_cleanup must be a mapping")
        post_cleanup = {}

    if post_cleanup.get("checked") is not True:
        errors.append("post_cleanup.checked must be true")

    for field in (
        "artifact_count",
        "known_artifact_count",
        "invalid_artifact_count",
        "stale_artifact_count",
    ):
        if _safe_int(post_cleanup.get(field), default=-1) < 0:
            errors.append(f"post_cleanup.{field} must be >= 0")

    post_retention = post_cleanup.get("retention")
    if not isinstance(post_retention, Mapping):
        errors.append("post_cleanup.retention must be a mapping")
        post_retention = {}

    if _safe_int(post_retention.get("would_delete_count"), default=-1) < 0:
        errors.append("post_cleanup.retention.would_delete_count must be >= 0")

    if _safe_float(post_retention.get("max_age_seconds"), default=-1.0) < 0.0:
        errors.append("post_cleanup.retention.max_age_seconds must be >= 0")

    if mode == MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS and not deletion_errors:
        if _safe_int(post_cleanup.get("stale_artifact_count"), default=0) > 0:
            errors.append(
                "post_cleanup.stale_artifact_count must be 0 after successful execute cleanup"
            )

        if _safe_int(post_retention.get("would_delete_count"), default=0) > 0:
            errors.append(
                "post_cleanup.retention.would_delete_count must be 0 after successful execute cleanup"
            )

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
        "--execute-delete-local-artifacts",
        action="store_true",
        default=False,
        help=(
            "Execute deletion of stale local latest artifacts. This only "
            "deletes files from the allowlisted "
            "data/cluster_runtime/latest/artifacts root and only for paths "
            "reported by retention.would_delete."
        ),
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

    print(
        "  local_delete:     "
        f"{result.get('local_artifact_deletion_performed')}"
    )

    retention = result.get("retention")
    if isinstance(retention, Mapping):
        print(
            "  retention:        "
            f"mode={retention.get('mode', '')} "
            f"max_age_seconds={retention.get('max_age_seconds', 0.0)} "
            f"max_age_days={retention.get('max_age_days', 0.0)}"
        )
    
    post_cleanup = result.get("post_cleanup")
    if isinstance(post_cleanup, Mapping):
        print(
            "  post_cleanup:    "
            f"checked={post_cleanup.get('checked')} "
            f"status={post_cleanup.get('status', '')} "
            f"artifacts={post_cleanup.get('artifact_count', 0)} "
            f"stale={post_cleanup.get('stale_artifact_count', 0)} "
            f"invalid={post_cleanup.get('invalid_artifact_count', 0)} "
            f"cleanup_ok={post_cleanup.get('cleanup_ok')}"
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
    
    deleted = result.get("deleted")
    if isinstance(deleted, list) and deleted:
        print("\nDeleted:")
        for item in deleted:
            if not isinstance(item, Mapping):
                continue
            print(
                f"- {item.get('name', '')}: "
                f"path={item.get('path', '')}"
            )

    deletion_errors = result.get("deletion_errors")
    if isinstance(deletion_errors, list) and deletion_errors:
        print("\nDeletion errors:")
        for item in deletion_errors:
            if not isinstance(item, Mapping):
                continue
            print(
                f"- reason={item.get('reason', '')} "
                f"path={item.get('path', '')}"
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
        execute_delete_local_artifacts=bool(
            getattr(args, "execute_delete_local_artifacts", False)
        ),
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
            if result.get("mode") == MODE_EXECUTE_DELETE_LOCAL_ARTIFACTS:
                print("✅ cluster latest artifacts cleanup execute-local-artifacts contract OK")
            else:
                print("✅ cluster latest artifacts cleanup dry-run contract OK")
            raise SystemExit(0)

        raise SystemExit(1)


if __name__ == "__main__":
    main()