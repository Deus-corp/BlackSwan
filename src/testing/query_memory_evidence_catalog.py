from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from src.memory.local_memory import LocalMemoryAPI
from src.swarms.memory.catalog import (
    build_memory_evidence_catalog_from_memory_records,
    query_memory_evidence_catalog,
)


def _json_default(value: Any) -> Any:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    if isinstance(value, Path):
        return str(value)

    return str(value)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for deterministic local memory evidence catalog queries."""
    parser = argparse.ArgumentParser(
        description=(
            "Query local memory evidence catalog records deterministically. "
            "Testing-only, local-only, no external writes."
        )
    )

    parser.add_argument(
        "--node-id",
        default="memory-query-cli",
        help="Local memory node id used to open LocalMemoryAPI.",
    )
    parser.add_argument(
        "--recent-limit",
        type=int,
        default=1000,
        help="Number of recent local memory records to load before building catalog.",
    )
    parser.add_argument(
        "--domain",
        default="",
        help="Exact domain filter, e.g. docs.python.org.",
    )
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
        help="Text query matched across URL, domain, summary, preview, category, and tags.",
    )
    parser.add_argument(
        "--min-ranking-score",
        type=float,
        default=0.0,
        help="Minimum catalog ranking score.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of query results.",
    )
    parser.add_argument(
        "--top-items-limit",
        type=int,
        default=100,
        help="Maximum number of catalog top items retained before query filtering.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print full JSON query result.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write full JSON query result.",
    )

    return parser


async def run_memory_evidence_catalog_query(
    args: argparse.Namespace,
    *,
    memory_backend: Any | None = None,
) -> dict[str, Any]:
    """Build and query local memory evidence catalog.

    This helper performs no external I/O beyond reading the configured local
    memory backend and optionally writing an operator-requested JSON file.
    """
    recent_limit = max(0, int(getattr(args, "recent_limit", 1000) or 1000))
    top_items_limit = max(0, int(getattr(args, "top_items_limit", 100) or 100))

    memory = memory_backend or LocalMemoryAPI(
        node_id=str(getattr(args, "node_id", "") or "memory-query-cli")
    )

    recent = await memory.recent(limit=recent_limit)

    catalog = build_memory_evidence_catalog_from_memory_records(
        recent,
        top_items_limit=top_items_limit,
    )

    query_result = query_memory_evidence_catalog(
        catalog,
        domain=str(getattr(args, "domain", "") or ""),
        evidence_category=str(getattr(args, "evidence_category", "") or ""),
        topic_tags=list(getattr(args, "topic_tags", []) or []),
        text_query=str(getattr(args, "text_query", "") or ""),
        min_ranking_score=float(
            getattr(args, "min_ranking_score", 0.0) or 0.0
        ),
        limit=int(getattr(args, "limit", 10) or 10),
    )

    result = {
        **query_result,
        "catalog": {
            "type": catalog.get("type"),
            "catalog_status": catalog.get("catalog_status"),
            "input_count": int(catalog.get("input_count", 0) or 0),
            "item_count": int(catalog.get("item_count", 0) or 0),
            "deduped_count": int(catalog.get("deduped_count", 0) or 0),
            "rejected_count": int(catalog.get("rejected_count", 0) or 0),
            "by_domain": dict(catalog.get("by_domain", {}) or {}),
            "by_category": dict(catalog.get("by_category", {}) or {}),
            "by_topic_tag": dict(catalog.get("by_topic_tag", {}) or {}),
        },
        "recent_limit": recent_limit,
        "top_items_limit": top_items_limit,
        "node_id": str(getattr(args, "node_id", "") or "memory-query-cli"),
        "testing_only": True,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }

    return result


def _print_human_summary(result: dict[str, Any]) -> None:
    print("Memory evidence catalog query")
    print(f"  catalog_items: {result.get('catalog', {}).get('item_count', 0)}")
    print(f"  matched:       {result.get('matched_count', 0)}")
    print(f"  returned:      {result.get('result_count', 0)}")

    results = result.get("results", [])
    if not results:
        print("  results:       none")
        return

    print("\nTop results:")
    for index, item in enumerate(results, start=1):
        print(
            f"{index}. score={item.get('ranking_score')} "
            f"domain={item.get('domain')} category={item.get('evidence_category')}"
        )
        print(f"   url: {item.get('url')}")
        summary = str(item.get("summary") or item.get("content_preview") or "")
        if summary:
            print(f"   summary: {summary[:220]}")


async def _async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = await run_memory_evidence_catalog_query(args)

    output = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )

    json_output = str(getattr(args, "json_output", "") or "").strip()
    if json_output:
        path = Path(json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output + "\n", encoding="utf-8")

    if bool(getattr(args, "json", False)):
        print(output)
    else:
        _print_human_summary(result)

    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(_async_main(argv)))


if __name__ == "__main__":
    main(sys.argv[1:])