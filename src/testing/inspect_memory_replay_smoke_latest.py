from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.testing.check_explorer_memory_replay_smoke import (
    validate_explorer_memory_replay_smoke,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ARTIFACT_PATTERNS = (
    "explorer_memory_replay_smoke.json",
    "explorer_memory_replay_smoke*.json",
)

DEFAULT_SEARCH_ROOTS = (
    Path(tempfile.gettempdir()),
    PROJECT_ROOT / "data" / "cluster_runtime" / "latest",
    PROJECT_ROOT / "data" / "cluster_runtime" / "latest" / "artifacts",
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


def _candidate_paths(
    *,
    json_path: str = "",
    search_roots: Iterable[str | Path] = (),
) -> list[Path]:
    explicit_path = str(json_path or "").strip()
    if explicit_path:
        path = Path(explicit_path)
        return [path] if path.exists() and path.is_file() else []

    roots = [Path(root) for root in search_roots] if search_roots else list(DEFAULT_SEARCH_ROOTS)

    candidates: dict[str, Path] = {}

    for root in roots:
        if not root.exists():
            continue

        if root.is_file():
            candidates[str(root.resolve())] = root
            continue

        for pattern in DEFAULT_ARTIFACT_PATTERNS:
            for path in root.glob(pattern):
                if path.exists() and path.is_file():
                    candidates[str(path.resolve())] = path

        # Keep this bounded to direct children only. The smoke wrapper writes
        # named output files either directly to /tmp or explicit operator paths.
        for child in root.iterdir():
            if (
                child.is_file()
                and child.name.startswith("explorer_memory_replay_smoke")
                and child.suffix == ".json"
            ):
                candidates[str(child.resolve())] = child
        
        artifacts_dir = root / "artifacts"
        if artifacts_dir.exists() and artifacts_dir.is_dir():
            for pattern in DEFAULT_ARTIFACT_PATTERNS:
                for path in artifacts_dir.glob(pattern):
                    if path.exists() and path.is_file():
                        candidates[str(path.resolve())] = path

    return sorted(
        candidates.values(),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )


def _summary_from_payload(
    *,
    path: Path,
    payload: Mapping[str, Any],
    contract_errors: list[str],
) -> dict[str, Any]:
    memory_replay_summary = payload.get("memory_replay_summary")
    if not isinstance(memory_replay_summary, Mapping):
        memory_replay_summary = {}

    memory_replay_yield = payload.get("memory_replay_yield")
    if not isinstance(memory_replay_yield, Mapping):
        memory_replay_yield = {}

    return {
        "type": "memory_replay_latest_summary",
        "status": str(payload.get("status") or "unknown"),
        "artifact_path": str(path),
        "artifact_mtime": path.stat().st_mtime,
        "contract_ok": not contract_errors,
        "contract_errors": contract_errors,
        "memory_replay_summary": dict(memory_replay_summary),
        "memory_replay_yield": dict(memory_replay_yield),
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
        "external_write_performed": bool(payload.get("external_write_performed")),
        "real_execution_enabled": bool(payload.get("real_execution_enabled")),
        "production_paths_mutated": bool(payload.get("production_paths_mutated")),
        "production_secrets_accessed": bool(
            payload.get("production_secrets_accessed")
        ),
    }


def inspect_memory_replay_smoke_latest(
    *,
    json_path: str = "",
    search_roots: Iterable[str | Path] = (),
) -> dict[str, Any]:
    candidates = _candidate_paths(
        json_path=json_path,
        search_roots=search_roots,
    )

    if not candidates:
        return {
            "type": "memory_replay_latest_summary",
            "status": "missing",
            "artifact_path": "",
            "contract_ok": False,
            "contract_errors": ["no memory replay smoke artifact found"],
            "memory_replay_summary": {},
            "memory_replay_yield": {},
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        }

    path = candidates[0]

    try:
        payload = _load_json_mapping(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "type": "memory_replay_latest_summary",
            "status": "invalid_json",
            "artifact_path": str(path),
            "contract_ok": False,
            "contract_errors": [f"failed to read memory replay smoke artifact: {exc}"],
            "memory_replay_summary": {},
            "memory_replay_yield": {},
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        }

    contract_errors = validate_explorer_memory_replay_smoke(payload)

    return _summary_from_payload(
        path=path,
        payload=payload,
        contract_errors=contract_errors,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect latest explorer memory replay smoke artifact.",
    )
    parser.add_argument(
        "--json-path",
        default="",
        help="Explicit explorer memory replay smoke JSON artifact path.",
    )
    parser.add_argument(
        "--search-root",
        action="append",
        default=[],
        help=(
            "Directory or file to search. Can be passed multiple times. "
            "Defaults to /tmp and data/cluster_runtime/latest."
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
        help="Exit with code 1 unless the latest artifact contract is valid.",
    )
    return parser


def _print_human_summary(summary: Mapping[str, Any]) -> None:
    print("Latest memory replay smoke artifact")
    print(f"  status:          {summary.get('status', '')}")
    print(f"  artifact_path:   {summary.get('artifact_path', '')}")
    print(f"  contract_ok:     {summary.get('contract_ok')}")

    replay_summary = summary.get("memory_replay_summary")
    if isinstance(replay_summary, Mapping) and replay_summary:
        print(
            "  replay_summary:  "
            f"published={replay_summary.get('records_published', 0)} "
            f"artifact={replay_summary.get('artifact_records', 0)} "
            f"replayed={replay_summary.get('records_replayed', 0)} "
            f"results={replay_summary.get('query_results', 0)}"
        )
        print(
            "  replay_ratios:   "
            f"capture={replay_summary.get('artifact_capture_ratio', 0.0)} "
            f"acceptance={replay_summary.get('replay_acceptance_ratio', 0.0)} "
            f"full_path={replay_summary.get('full_replay_path_ratio', 0.0)}"
        )

    errors = summary.get("contract_errors")
    if isinstance(errors, list) and errors:
        print("  contract_errors:")
        for error in errors:
            print(f"    - {error}")


def main() -> None:
    args = build_parser().parse_args()

    summary = inspect_memory_replay_smoke_latest(
        json_path=str(args.json_path or ""),
        search_roots=list(args.search_root or []),
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
            print("✅ latest memory replay smoke artifact contract OK")
            raise SystemExit(0)

        raise SystemExit(1)


if __name__ == "__main__":
    main()