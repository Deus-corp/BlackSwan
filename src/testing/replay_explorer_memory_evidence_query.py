from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.swarms.memory.catalog import (
    build_memory_evidence_catalog_from_memory_records,
    query_memory_evidence_catalog,
)
from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    is_explorer_useful_evidence_record,
    memory_record_from_ingest_candidate,
)
from src.testing.check_memory_evidence_query_contract import (
    assert_memory_evidence_query_contract,
)


DEFAULT_CRDT_DB_PATH = (
    Path("data")
    / "cluster_runtime"
    / "latest"
    / "ledgers"
    / "swarm_crdt.local.db"
)


def _json_default(value: Any) -> Any:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    if isinstance(value, Path):
        return str(value)

    return str(value)


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_json_text(value: Any) -> Any | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if not (
        text.startswith("{")
        or text.startswith("[")
        or text.startswith('"')
    ):
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _iter_json_values(value: Any) -> Iterable[Any]:
    """Recursively walk mappings/lists and JSON-encoded string payloads."""
    yield value

    parsed = _parse_json_text(value)
    if parsed is not None:
        yield from _iter_json_values(parsed)
        return

    if isinstance(value, Mapping):
        for child in value.values():
            yield from _iter_json_values(child)
        return

    if isinstance(value, list):
        for child in value:
            yield from _iter_json_values(child)
        return


def _dedupe_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}

    for record in records:
        key = str(
            record.get("gid")
            or record.get("id")
            or record.get("content_hash")
            or record.get("url")
            or len(deduped)
        )
        if key not in deduped:
            deduped[key] = dict(record)

    return list(deduped.values())


def extract_explorer_memory_records_from_payload(
    payload: Any,
) -> list[dict[str, Any]]:
    """Extract explorer useful evidence memory records from nested payloads."""
    records: list[Mapping[str, Any]] = []

    for value in _iter_json_values(payload):
        if isinstance(value, Mapping) and is_explorer_useful_evidence_record(value):
            records.append(value)

    return _dedupe_records(records)


def _load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sqlite_table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    return [
        str(row[0])
        for row in rows
        if row and not str(row[0]).startswith("sqlite_")
    ]


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [str(row[1]) for row in rows]


def _load_sqlite_payloads(path: Path, *, max_rows_per_table: int = 5000) -> list[Any]:
    """Best-effort scan of CRDT sqlite payloads.

    The project has evolved CRDT storage shapes over time, so this reader avoids
    depending on one table/column name. It scans all tables and recursively parses
    JSON-like text fields.
    """
    if not path.exists():
        return []

    payloads: list[Any] = []

    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row

        for table in _sqlite_table_names(conn):
            columns = _sqlite_columns(conn, table)
            if not columns:
                continue

            selected_columns = ", ".join(f'"{column}"' for column in columns)
            query = (
                f'SELECT {selected_columns} FROM "{table}" '
                f"LIMIT {int(max_rows_per_table)}"
            )

            try:
                rows = conn.execute(query).fetchall()
            except sqlite3.DatabaseError:
                continue

            for row in rows:
                row_mapping = dict(row)
                payloads.append(row_mapping)

                for value in row_mapping.values():
                    parsed = _parse_json_text(value)
                    if parsed is not None:
                        payloads.append(parsed)

    return payloads


def load_explorer_memory_records(
    *,
    db_path: str = "",
    json_path: str = "",
    max_rows_per_table: int = 5000,
) -> list[dict[str, Any]]:
    """Load explorer useful evidence records from JSON and/or CRDT sqlite."""
    records: list[dict[str, Any]] = []

    clean_json_path = str(json_path or "").strip()
    if clean_json_path:
        payload = _load_json_file(Path(clean_json_path))
        records.extend(extract_explorer_memory_records_from_payload(payload))

    clean_db_path = str(db_path or "").strip()
    if clean_db_path:
        for payload in _load_sqlite_payloads(
            Path(clean_db_path),
            max_rows_per_table=max_rows_per_table,
        ):
            records.extend(extract_explorer_memory_records_from_payload(payload))

    return _dedupe_records(records)


def replay_explorer_memory_evidence_query(
    records: Iterable[Mapping[str, Any]],
    *,
    text_query: str = "",
    domain: str = "",
    evidence_category: str = "",
    topic_tags: list[str] | None = None,
    min_ranking_score: float = 0.0,
    limit: int = 10,
    top_items_limit: int = 100,
) -> dict[str, Any]:
    """Replay explorer useful evidence records through memory catalog query."""
    source_records = _dedupe_records(
        record
        for record in records
        if isinstance(record, Mapping)
    )

    local_memory_records: list[dict[str, Any]] = []
    rejected_count = 0

    for record in source_records:
        try:
            candidate = build_memory_ingest_candidate(record)
            local_memory_records.append(memory_record_from_ingest_candidate(candidate))
        except (TypeError, ValueError):
            rejected_count += 1

    catalog = build_memory_evidence_catalog_from_memory_records(
        local_memory_records,
        top_items_limit=top_items_limit,
    )

    result = query_memory_evidence_catalog(
        catalog,
        domain=domain,
        evidence_category=evidence_category,
        topic_tags=topic_tags or [],
        text_query=text_query,
        min_ranking_score=min_ranking_score,
        limit=limit,
    )

    return {
        **result,
        "replay_source": "explorer_memory_evidence",
        "explorer_memory_records_seen": len(source_records),
        "explorer_memory_records_replayed": len(local_memory_records),
        "explorer_memory_records_rejected": rejected_count,
        "catalog": {
            "type": catalog.get("type"),
            "catalog_status": catalog.get("catalog_status"),
            "input_count": _safe_int(catalog.get("input_count")),
            "item_count": _safe_int(catalog.get("item_count")),
            "deduped_count": _safe_int(catalog.get("deduped_count")),
            "rejected_count": _safe_int(catalog.get("rejected_count")),
            "by_domain": dict(catalog.get("by_domain", {}) or {}),
            "by_category": dict(catalog.get("by_category", {}) or {}),
            "by_topic_tag": dict(catalog.get("by_topic_tag", {}) or {}),
        },
        "testing_only": True,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay explorer useful evidence memory records into deterministic "
            "memory evidence catalog query output. Testing-only, local-only."
        )
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_CRDT_DB_PATH),
        help="Path to CRDT sqlite database to scan.",
    )
    parser.add_argument(
        "--json-input",
        default="",
        help="Optional JSON file to scan for explorer memory records.",
    )
    parser.add_argument(
        "--max-rows-per-table",
        type=int,
        default=5000,
        help="Maximum sqlite rows to scan per table.",
    )
    parser.add_argument("--domain", default="", help="Exact domain filter.")
    parser.add_argument(
        "--category",
        "--evidence-category",
        dest="evidence_category",
        default="",
        help="Exact evidence category filter.",
    )
    parser.add_argument(
        "--tag",
        dest="topic_tags",
        action="append",
        default=[],
        help="Required topic tag. Can be passed multiple times.",
    )
    parser.add_argument(
        "--text-query",
        default="",
        help="Text query for deterministic catalog filtering.",
    )
    parser.add_argument(
        "--min-ranking-score",
        type=float,
        default=0.0,
        help="Minimum catalog ranking score.",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--top-items-limit", type=int, default=100)
    parser.add_argument("--json", action="store_true", default=False)
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write replay query JSON result.",
    )
    parser.add_argument(
        "--check-contract",
        action="store_true",
        help="Validate replay query result with memory evidence query contract.",
    )
    return parser


def _print_human_summary(result: Mapping[str, Any]) -> None:
    print("Explorer memory evidence replay query")
    print(f"  source_records: {result.get('explorer_memory_records_seen', 0)}")
    print(f"  replayed:       {result.get('explorer_memory_records_replayed', 0)}")
    print(f"  rejected:       {result.get('explorer_memory_records_rejected', 0)}")
    print(f"  catalog_items:  {result.get('catalog', {}).get('item_count', 0)}")
    print(f"  matched:        {result.get('matched_count', 0)}")
    print(f"  returned:       {result.get('result_count', 0)}")

    results = result.get("results", [])
    if not results:
        print("  results:        none")
        return

    print("\nTop results:")
    for index, item in enumerate(results, start=1):
        print(
            f"{index}. score={item.get('ranking_score')} "
            f"domain={item.get('domain')} category={item.get('evidence_category')}"
        )
        print(f"   url: {item.get('url')}")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    records = load_explorer_memory_records(
        db_path=str(getattr(args, "db_path", "") or ""),
        json_path=str(getattr(args, "json_input", "") or ""),
        max_rows_per_table=max(0, int(args.max_rows_per_table or 0)),
    )

    result = replay_explorer_memory_evidence_query(
        records,
        text_query=str(args.text_query or ""),
        domain=str(args.domain or ""),
        evidence_category=str(args.evidence_category or ""),
        topic_tags=list(args.topic_tags or []),
        min_ranking_score=float(args.min_ranking_score or 0.0),
        limit=max(0, int(args.limit or 0)),
        top_items_limit=max(0, int(args.top_items_limit or 0)),
    )

    if bool(args.check_contract):
        assert_memory_evidence_query_contract(result)

    output = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )

    json_output = str(args.json_output or "").strip()
    if json_output:
        path = Path(json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output + "\n", encoding="utf-8")

    if bool(args.json):
        print(output)
    else:
        _print_human_summary(result)

    if bool(args.check_contract):
        print("✅ memory evidence query contract OK")


if __name__ == "__main__":
    main(sys.argv[1:])