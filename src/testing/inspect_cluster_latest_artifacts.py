from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.testing.check_explorer_memory_replay_smoke import (
    validate_explorer_memory_replay_smoke,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS_ROOT = (
    PROJECT_ROOT / "data" / "cluster_runtime" / "latest" / "artifacts"
)

EXPLORER_MEMORY_REPLAY_SMOKE_TYPE = "explorer_memory_replay_smoke_result"
MEMORY_REPLAY_LATEST_SUMMARY_TYPE = "memory_replay_latest_summary"

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


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json_mapping(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _json_artifact_paths(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []

    return sorted(
        [
            path
            for path in root.glob("*.json")
            if path.exists() and path.is_file()
        ],
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )


def _memory_replay_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("memory_replay_summary")
    return dict(summary) if isinstance(summary, Mapping) else {}


def _memory_replay_yield(payload: Mapping[str, Any]) -> dict[str, Any]:
    yield_metrics = payload.get("memory_replay_yield")
    return dict(yield_metrics) if isinstance(yield_metrics, Mapping) else {}


def _artifact_summary(path: Path) -> dict[str, Any]:
    try:
        payload = _load_json_mapping(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "name": path.stem,
            "path": str(path),
            "type": "invalid_json",
            "status": "invalid_json",
            "artifact_mtime": path.stat().st_mtime if path.exists() else 0.0,
            "contract_checked": False,
            "contract_ok": False,
            "contract_errors": [f"failed to read artifact JSON: {exc}"],
            "memory_replay_summary": {},
            "memory_replay_yield": {},
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        }

    artifact_type = str(payload.get("type") or "").strip()
    contract_errors: list[str] = []
    contract_checked = False

    if artifact_type == EXPLORER_MEMORY_REPLAY_SMOKE_TYPE:
        contract_checked = True
        contract_errors = validate_explorer_memory_replay_smoke(payload)
    elif artifact_type == MEMORY_REPLAY_LATEST_SUMMARY_TYPE:
        contract_checked = True
        contract_errors = list(payload.get("contract_errors") or [])
        if not bool(payload.get("contract_ok")) and not contract_errors:
            contract_errors = ["latest summary contract_ok is false"]
    else:
        contract_errors = [f"unknown latest artifact type: {artifact_type!r}"]

    contract_ok = not contract_errors

    return {
        "name": path.stem,
        "path": str(path),
        "type": artifact_type or "unknown",
        "status": str(payload.get("status") or "unknown"),
        "artifact_mtime": path.stat().st_mtime,
        "contract_checked": contract_checked,
        "contract_ok": contract_ok,
        "contract_errors": contract_errors,
        "memory_replay_summary": _memory_replay_summary(payload),
        "memory_replay_yield": _memory_replay_yield(payload),
        "total_memory_records_published": _safe_int(
            payload.get("total_memory_records_published"),
            default=0,
        ),
        "memory_replay_artifact_record_count": _safe_int(
            payload.get("memory_replay_artifact_record_count"),
            default=0,
        ),
        "explorer_memory_records_seen": _safe_int(
            payload.get("explorer_memory_records_seen"),
            default=0,
        ),
        "explorer_memory_records_replayed": _safe_int(
            payload.get("explorer_memory_records_replayed"),
            default=0,
        ),
        "memory_query_result_count": _safe_int(
            payload.get("memory_query_result_count"),
            default=0,
        ),
        "retrieval_mode": str(payload.get("retrieval_mode") or ""),
        **{
            flag: bool(payload.get(flag))
            for flag in SAFETY_FLAGS
        },
    }


def inspect_cluster_latest_artifacts(
    *,
    artifacts_root: str | Path = "",
) -> dict[str, Any]:
    root = Path(artifacts_root) if str(artifacts_root or "").strip() else DEFAULT_ARTIFACTS_ROOT
    paths = _json_artifact_paths(root)

    if not paths:
        return {
            "type": "cluster_latest_artifacts_summary",
            "status": "missing",
            "artifacts_root": str(root),
            "artifact_count": 0,
            "known_artifact_count": 0,
            "contract_ok": False,
            "artifacts": [],
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        }

    artifacts = [_artifact_summary(path) for path in paths]
    known_artifact_count = sum(
        1 for artifact in artifacts if bool(artifact.get("contract_checked"))
    )
    contract_ok = bool(artifacts) and all(
        bool(artifact.get("contract_ok")) for artifact in artifacts
    )

    return {
        "type": "cluster_latest_artifacts_summary",
        "status": "indexed",
        "artifacts_root": str(root),
        "artifact_count": len(artifacts),
        "known_artifact_count": known_artifact_count,
        "contract_ok": contract_ok,
        "artifacts": artifacts,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect cluster latest runtime artifacts index.",
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
        "--json",
        action="store_true",
        default=False,
        help="Print machine-readable JSON summary.",
    )
    parser.add_argument(
        "--check-contract",
        "--require-contract",
        dest="check_contract",
        action="store_true",
        help="Exit with code 1 unless all indexed artifact contracts are valid.",
    )
    return parser


def _print_human_summary(summary: Mapping[str, Any]) -> None:
    print("Cluster latest artifacts")
    print(f"  status:          {summary.get('status', '')}")
    print(f"  artifacts_root:  {summary.get('artifacts_root', '')}")
    print(f"  artifact_count:  {summary.get('artifact_count', 0)}")
    print(f"  contract_ok:     {summary.get('contract_ok')}")

    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return

    print("\nArtifacts:")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue

        print(
            f"- {artifact.get('name')}: "
            f"status={artifact.get('status')} "
            f"contract_ok={artifact.get('contract_ok')}"
        )

        replay_summary = artifact.get("memory_replay_summary")
        if isinstance(replay_summary, Mapping) and replay_summary:
            print(
                "  memory_replay: "
                f"published={replay_summary.get('records_published', 0)} "
                f"artifact={replay_summary.get('artifact_records', 0)} "
                f"replayed={replay_summary.get('records_replayed', 0)} "
                f"results={replay_summary.get('query_results', 0)} "
                f"full_path={replay_summary.get('full_replay_path_ratio', 0.0)}"
            )

        errors = artifact.get("contract_errors")
        if isinstance(errors, list) and errors:
            for error in errors:
                print(f"  error: {error}")


def main() -> None:
    args = build_parser().parse_args()

    summary = inspect_cluster_latest_artifacts(
        artifacts_root=str(args.artifacts_root or ""),
    )

    if bool(args.json):
        print(
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=_json_default,
            )
        )
    else:
        _print_human_summary(summary)

    if bool(args.check_contract):
        if summary.get("contract_ok") is True:
            print("✅ cluster latest artifacts contract OK")
            raise SystemExit(0)

        raise SystemExit(1)


if __name__ == "__main__":
    main()