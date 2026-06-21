from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

from src.testing.check_explorer_source_planned_evidence_loop import (
    assert_explorer_source_planned_evidence_loop,
)
from src.testing.check_memory_evidence_query_contract import (
    assert_memory_evidence_query_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_ADAPTERS = ("github", "arxiv", "search", "sitemap")
DEFAULT_GOAL = "autonomous agents memory systems"
DEFAULT_TEXT_QUERY = "agents memory"


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


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


def _safe_ratio(
    numerator: int,
    denominator: int,
    *,
    precision: int = 4,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(float(numerator) / float(denominator), precision)


def _build_memory_replay_yield_metrics(
    *,
    records_published: int,
    artifact_records: int,
    artifact_available_records: int,
    records_seen: int,
    records_replayed: int,
    query_results: int,
) -> dict[str, Any]:
    """Build compact explorer→memory replay yield metrics."""
    return {
        "records_published": records_published,
        "artifact_records": artifact_records,
        "artifact_available_records": artifact_available_records,
        "records_seen": records_seen,
        "records_replayed": records_replayed,
        "query_results": query_results,
        "artifact_capture_ratio": _safe_ratio(
            artifact_records,
            records_published,
        ),
        "artifact_availability_ratio": _safe_ratio(
            artifact_available_records,
            records_published,
        ),
        "replay_visibility_ratio": _safe_ratio(
            records_seen,
            artifact_records,
        ),
        "replay_acceptance_ratio": _safe_ratio(
            records_replayed,
            records_seen,
        ),
        "query_result_ratio": _safe_ratio(
            query_results,
            records_replayed,
        ),
        "full_replay_path_ratio": _safe_ratio(
            query_results,
            records_published,
        ),
    }


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _default_command_runner(
    command: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )


def _command_text(command: Sequence[str]) -> str:
    return " ".join(str(part) for part in command)


def _build_explorer_command(
    args: argparse.Namespace,
    *,
    explorer_result_path: Path,
    crdt_db_path: Path,
    node_memory_db_path: Path,
    meta_memory_db_path: Path,
) -> list[str]:
    source_adapters = list(
        getattr(args, "source_adapter", None) or DEFAULT_SOURCE_ADAPTERS
    )

    command = [
        sys.executable,
        "-m",
        "src.testing.run_explorer_network_read_loop",
        "--exploration-run-id",
        str(getattr(args, "exploration_run_id", "") or "exp-run-memory-replay-smoke"),
        "--goal",
        str(getattr(args, "goal", "") or DEFAULT_GOAL),
        "--ticks",
        str(max(0, int(getattr(args, "ticks", 3) or 3))),
        "--json",
        "--json-output",
        str(explorer_result_path),
        "--db-path",
        str(crdt_db_path),
        "--node-memory-db",
        str(node_memory_db_path),
        "--meta-memory-db",
        str(meta_memory_db_path),
        "--memory-replay-artifact-limit",
        str(
            max(
                0,
                int(getattr(args, "memory_replay_artifact_limit", 20) or 20),
            )
        ),
    ]

    if bool(getattr(args, "source_plan", True)):
        command.append("--source-plan")

    for adapter in source_adapters:
        command.extend(["--source-adapter", str(adapter)])

    return command


def _build_replay_command(
    args: argparse.Namespace,
    *,
    explorer_result_path: Path,
    memory_replay_result_path: Path,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "src.testing.replay_explorer_memory_evidence_query",
        "--db-path",
        "",
        "--json-input",
        str(explorer_result_path),
        "--text-query",
        str(getattr(args, "text_query", "") or DEFAULT_TEXT_QUERY),
        "--limit",
        str(max(0, int(getattr(args, "limit", 5) or 5))),
        "--json-output",
        str(memory_replay_result_path),
        "--check-contract",
        "--json",
    ]


def _summary_from_results(
    *,
    explorer_result: dict[str, Any],
    memory_replay_result: dict[str, Any],
    explorer_result_path: Path,
    memory_replay_result_path: Path,
    explorer_command: Sequence[str],
    replay_command: Sequence[str],
) -> dict[str, Any]:
    memory_replay_artifact = explorer_result.get("memory_replay_artifact")
    if not isinstance(memory_replay_artifact, dict):
        memory_replay_artifact = {}
    
    records_published = _safe_int(
        explorer_result.get("total_memory_records_published"),
        default=0,
    )
    artifact_records = _safe_int(
        explorer_result.get("memory_replay_artifact_record_count")
        or memory_replay_artifact.get("record_count"),
        default=0,
    )
    artifact_available_records = _safe_int(
        explorer_result.get("memory_replay_artifact_available_record_count")
        or memory_replay_artifact.get("available_record_count"),
        default=0,
    )
    records_seen = _safe_int(
        memory_replay_result.get("explorer_memory_records_seen"),
        default=0,
    )
    records_replayed = _safe_int(
        memory_replay_result.get("explorer_memory_records_replayed"),
        default=0,
    )
    query_results = _safe_int(
        memory_replay_result.get("result_count"),
        default=0,
    )

    memory_replay_yield = _build_memory_replay_yield_metrics(
        records_published=records_published,
        artifact_records=artifact_records,
        artifact_available_records=artifact_available_records,
        records_seen=records_seen,
        records_replayed=records_replayed,
        query_results=query_results,
    )

    return {
        "type": "explorer_memory_replay_smoke_result",
        "status": "passed",
        "explorer_contract_ok": True,
        "memory_query_contract_ok": True,
        "explorer_result_path": str(explorer_result_path),
        "memory_replay_result_path": str(memory_replay_result_path),
        "explorer_command": list(explorer_command),
        "memory_replay_command": list(replay_command),
        "total_memory_records_published": records_published,
        "memory_replay_artifact_record_count": artifact_records,
        "memory_replay_artifact_available_record_count": (
            artifact_available_records
        ),
        "explorer_memory_records_seen": records_seen,
        "explorer_memory_records_replayed": records_replayed,
        "memory_query_result_count": query_results,
        "memory_replay_yield": memory_replay_yield,
        "retrieval_mode": str(memory_replay_result.get("retrieval_mode") or ""),
        "hybrid_retrieval_enabled": _safe_bool(
            memory_replay_result.get("hybrid_retrieval_enabled")
        ),
        "semantic_retrieval_enabled": _safe_bool(
            memory_replay_result.get("semantic_retrieval_enabled")
        ),
        "semantic_candidates": list(
            memory_replay_result.get("semantic_candidates") or []
        ),
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def run_explorer_memory_replay_smoke(
    args: argparse.Namespace,
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Run explorer runtime artifact + memory replay query contract smoke."""
    runner = command_runner or _default_command_runner

    keep_artifacts = bool(getattr(args, "keep_artifacts", False))
    clean_work_dir = str(getattr(args, "work_dir", "") or "").strip()

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if clean_work_dir:
        work_dir = Path(clean_work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="explorer_memory_replay_smoke_")
        work_dir = Path(temp_dir.name)

    explorer_result_path = work_dir / "explorer_plan_result.json"
    memory_replay_result_path = work_dir / "explorer_memory_replay_query.json"
    crdt_db_path = work_dir / "explorer_plan_crdt.sqlite3"
    node_memory_db_path = work_dir / "explorer_plan_node.sqlite3"
    meta_memory_db_path = work_dir / "explorer_plan_meta.sqlite3"

    try:
        explorer_command = _build_explorer_command(
            args,
            explorer_result_path=explorer_result_path,
            crdt_db_path=crdt_db_path,
            node_memory_db_path=node_memory_db_path,
            meta_memory_db_path=meta_memory_db_path,
        )

        explorer_completed = runner(explorer_command)
        if explorer_completed.returncode != 0:
            return {
                "type": "explorer_memory_replay_smoke_result",
                "status": "failed",
                "failure_stage": "explorer_runtime",
                "returncode": explorer_completed.returncode,
                "command": list(explorer_command),
                "stdout": explorer_completed.stdout,
                "stderr": explorer_completed.stderr,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
            }

        explorer_result = _load_json(explorer_result_path)
        assert_explorer_source_planned_evidence_loop(explorer_result)

        replay_command = _build_replay_command(
            args,
            explorer_result_path=explorer_result_path,
            memory_replay_result_path=memory_replay_result_path,
        )

        replay_completed = runner(replay_command)
        if replay_completed.returncode != 0:
            return {
                "type": "explorer_memory_replay_smoke_result",
                "status": "failed",
                "failure_stage": "memory_replay_query",
                "returncode": replay_completed.returncode,
                "command": list(replay_command),
                "stdout": replay_completed.stdout,
                "stderr": replay_completed.stderr,
                "external_write_performed": False,
                "real_execution_enabled": False,
                "production_paths_mutated": False,
                "production_secrets_accessed": False,
            }

        memory_replay_result = _load_json(memory_replay_result_path)
        assert_memory_evidence_query_contract(memory_replay_result)

        summary = _summary_from_results(
            explorer_result=explorer_result,
            memory_replay_result=memory_replay_result,
            explorer_result_path=explorer_result_path,
            memory_replay_result_path=memory_replay_result_path,
            explorer_command=explorer_command,
            replay_command=replay_command,
        )

        output_path = str(getattr(args, "json_output", "") or "").strip()
        if output_path:
            _write_json(Path(output_path), summary)

        return summary

    finally:
        if temp_dir is not None and not keep_artifacts:
            temp_dir.cleanup()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one-command explorer runtime + memory replay contract smoke. "
            "Testing-only, local-only, no external writes."
        )
    )
    parser.add_argument(
        "--goal",
        default=DEFAULT_GOAL,
        help="Explorer research goal.",
    )
    parser.add_argument(
        "--exploration-run-id",
        default="exp-run-memory-replay-smoke",
    )
    parser.add_argument("--ticks", type=int, default=3)
    parser.add_argument(
        "--source-adapter",
        action="append",
        default=None,
        help=(
            "Source adapter to seed. Can be passed multiple times. "
            f"Default: {', '.join(DEFAULT_SOURCE_ADAPTERS)}."
        ),
    )
    parser.add_argument(
        "--no-source-plan",
        action="store_false",
        dest="source_plan",
        default=True,
        help="Disable source-plan seeding.",
    )
    parser.add_argument(
        "--memory-replay-artifact-limit",
        type=int,
        default=20,
        help="Maximum replayable memory records embedded by explorer runtime.",
    )
    parser.add_argument(
        "--text-query",
        default=DEFAULT_TEXT_QUERY,
        help="Memory replay query text.",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--work-dir",
        default="",
        help="Optional directory for intermediate explorer/replay artifacts.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep temporary artifacts when --work-dir is not provided.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print full JSON smoke summary.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write smoke summary JSON.",
    )
    return parser


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = summary.get("status", "unknown")
    print("Explorer memory replay smoke")
    print(f"  status:                         {status}")

    if status != "passed":
        print(f"  failure_stage:                  {summary.get('failure_stage', '')}")
        print(f"  returncode:                     {summary.get('returncode', '')}")
        print(f"  command:                        {_command_text(summary.get('command', []))}")
        return

    print(f"  explorer_contract_ok:           {summary.get('explorer_contract_ok')}")
    print(f"  memory_query_contract_ok:       {summary.get('memory_query_contract_ok')}")
    print(
        "  total_memory_records_published: "
        f"{summary.get('total_memory_records_published', 0)}"
    )
    print(
        "  memory_replay_artifact_records: "
        f"{summary.get('memory_replay_artifact_record_count', 0)}"
    )
    print(
        "  explorer_memory_records_seen:   "
        f"{summary.get('explorer_memory_records_seen', 0)}"
    )
    print(
        "  explorer_memory_records_replayed: "
        f"{summary.get('explorer_memory_records_replayed', 0)}"
    )
    print(
        "  memory_query_result_count:      "
        f"{summary.get('memory_query_result_count', 0)}"
    )

    memory_replay_yield = summary.get("memory_replay_yield")
    if isinstance(memory_replay_yield, dict):
        print(
            "  artifact_capture_ratio:        "
            f"{memory_replay_yield.get('artifact_capture_ratio', 0.0)}"
        )
        print(
            "  replay_acceptance_ratio:       "
            f"{memory_replay_yield.get('replay_acceptance_ratio', 0.0)}"
        )
        print(
            "  query_result_ratio:            "
            f"{memory_replay_yield.get('query_result_ratio', 0.0)}"
        )
        print(
            "  full_replay_path_ratio:        "
            f"{memory_replay_yield.get('full_replay_path_ratio', 0.0)}"
        )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    summary = run_explorer_memory_replay_smoke(args)

    if bool(getattr(args, "json", False)):
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

    if summary.get("status") == "passed":
        print("✅ explorer source-planned evidence loop contract OK")
        print("✅ memory evidence query contract OK")
        print("✅ explorer memory replay smoke OK")
        raise SystemExit(0)

    raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])