"""Run a minimal live explorer network-read dataflow loop.

This helper executes the useful Explorer path:

    seed explorer_targets
    -> ExplorerNode fetches network_read evidence
    -> ExplorerMetaAgent reconciles explorer_finding
    -> ExplorerMetaAgent classifies with LLM or deterministic fallback
    -> ExplorerMetaAgent publishes follow-up explorer_targets

It does not perform external writes, production writes, subprocess execution,
wallet access, or real financial execution.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Mapping

import httpx
import hashlib

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.node import ExplorerNode
from src.swarms.explorer.node_core.utils import normalize_url
from src.swarms.common import utc_ts
from swarm_config import config

from src.swarms.explorer.meta_agent_core.source_adapters import (
    build_source_adapter_targets,
)

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one explorer seed-fetch-reconcile network-read loop.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Seed URL. Can be repeated.",
    )
    parser.add_argument(
        "--node-memory-db",
        default="data/explorer_node_network_read_loop.sqlite3",
    )
    parser.add_argument(
        "--meta-memory-db",
        default="data/explorer_meta_network_read_loop.sqlite3",
    )
    parser.add_argument(
        "--goal",
        default="",
        help="Research goal used by explorer source adapters.",
    )
    parser.add_argument(
        "--source-adapter",
        action="append",
        default=[],
        choices=["rss", "sitemap", "github", "arxiv", "search"],
        help="Source adapter to seed. Can be repeated.",
    )
    parser.add_argument(
        "--source-limit",
        type=int,
        default=20,
        help="Maximum source-adapter targets to seed.",
    )
    parser.add_argument(
        "--exploration-run-id",
        default="",
        help="Optional stable exploration run id. Generated when omitted.",
    )
    parser.add_argument("--node-id", default="exp-node-network-read-loop")
    parser.add_argument("--meta-agent-id", default="exp-meta-network-read-loop")
    parser.add_argument("--skip-meta", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


async def run_explorer_network_read_loop(args: argparse.Namespace) -> dict[str, Any]:
    urls = [normalize_url(url) for url in list(args.url or [])]
    urls = [url for url in urls if url]

    source_targets = build_source_adapter_targets(
        goal=str(getattr(args, "goal", "") or ""),
        adapters=list(getattr(args, "source_adapter", []) or []),
        seed_urls=urls,
        limit=int(getattr(args, "source_limit", 20) or 20),
    )

    adapter_urls = [
        str(item.get("url") or "").strip()
        for item in source_targets
        if str(item.get("url") or "").strip()
    ]

    urls = _dedupe_urls([*urls, *adapter_urls])

    if not urls:
        urls = ["https://example.com/"]
    
    exploration_run_id = (
        str(getattr(args, "exploration_run_id", "") or "").strip()
        or _make_exploration_run_id(
            goal=str(getattr(args, "goal", "") or ""),
            urls=urls,
        )
    )

    db_path = str(args.db_path or config.crdt_db_path)

    crdt = CRDTAdapter(
        node_id="explorer-network-read-loop-runner",
        db_path=db_path,
    )

    node = ExplorerNode(
        node_id=str(args.node_id or "exp-node-network-read-loop"),
        memory_db=Path(args.node_memory_db),
    )
    meta = ExplorerMetaAgent(
        node_id=str(args.meta_agent_id or "exp-meta-network-read-loop"),
        memory_db=Path(args.meta_memory_db),
    )
    node.active_exploration_run_id = exploration_run_id
    meta.active_exploration_run_id = exploration_run_id

    _replace_crdt(node, crdt)
    _replace_crdt(meta, crdt)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        seed_record = _build_seed_targets(
            urls,
            goal=str(getattr(args, "goal", "") or ""),
            source_adapters=list(getattr(args, "source_adapter", []) or []),
            source_targets=source_targets,
            exploration_run_id=exploration_run_id,
        )
        await crdt.add_genome(seed_record)

        async with httpx.AsyncClient(
            timeout=node.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            did_node_work = await node._consume_targets_and_explore(client)

        if callable(refresh):
            refresh()

        meta_result: dict[str, Any] = {
            "skipped": bool(args.skip_meta),
            "snapshot_findings": 0,
            "decision_action": None,
            "targets_published": 0,
            "classifications_published": 0,
            "exploration_run_id": exploration_run_id,
        }

        if not args.skip_meta:
            snapshot = await meta.collect()
            decision = await meta.decide(snapshot)
            commands = await meta.issue_commands(decision, snapshot)
            await meta.persist_decision(decision, snapshot, commands)

            meta_result = {
                "skipped": False,
                "snapshot_findings": len(getattr(snapshot, "findings", []) or []),
                "decision_action": _extract_mapping_value(decision, "action"),
                "targets_published": int(
                    getattr(meta, "_last_targets_published", 0) or 0
                ),
                "classifications_published": int(
                    getattr(meta, "_last_classifications_published", 0) or 0
                ),
                "exploration_run_id": exploration_run_id,
            }

        state = getattr(crdt, "state", {}) or {}
        records = [value for value in state.values() if isinstance(value, Mapping)]

        return {
            "type": "explorer_network_read_loop_result",
            "status": "completed",
            "seed_urls": urls,
            "research_goal": str(getattr(args, "goal", "") or ""),
            "exploration_run_id": exploration_run_id,
            "source_adapters": list(getattr(args, "source_adapter", []) or []),
            "source_adapter_targets": source_targets,
            "seed_record_gid": seed_record["gid"],
            "node": {
                "node_id": node.node_id,
                "did_work": bool(did_node_work),
                "targets_seen_last_tick": int(
                    getattr(node, "_targets_seen_last_tick", 0) or 0
                ),
                "fetches_attempted": int(getattr(node, "_fetches_attempted", 0) or 0),
                "fetches_failed": int(getattr(node, "_fetches_failed", 0) or 0),
                "findings_emitted": int(getattr(node, "_findings_emitted", 0) or 0),
                "targets_discovered": int(
                    getattr(node, "_targets_discovered", 0) or 0
                ),
                "targets_published": int(
                    getattr(node, "_targets_published", 0) or 0
                ),
                "execution_risk_tier": "network_read",
                "external_write_performed": False,
                "real_execution_enabled": False,
                "exploration_run_id": exploration_run_id,
            },
            "meta_agent": meta_result,
            "record_counts": _record_counts(records),
            "external_write_performed": False,
            "real_execution_enabled": False,
            "production_paths_mutated": False,
            "production_secrets_accessed": False,
        }
    finally:
        await _safe_aclose(getattr(node, "http_client", None))
        _safe_close(crdt)


def _make_exploration_run_id(*, goal: str, urls: list[str]) -> str:
    raw = "|".join(
        [
            "explorer",
            "network_read",
            " ".join(str(goal or "").split()),
            *[str(url or "").strip() for url in urls[:10]],
            str(int(utc_ts())),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"exp_run_{int(utc_ts())}_{digest}"


def _dedupe_urls(urls: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for raw in urls:
        url = normalize_url(str(raw or ""))
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)

    return out


def _build_seed_targets(
    urls: list[str],
    *,
    goal: str = "",
    source_adapters: list[str] | None = None,
    source_targets: list[Mapping[str, Any]] | None = None,
    exploration_run_id: str = "",
) -> dict[str, Any]:
    return {
        "type": "explorer_targets",
        "event_type": "targets_suggested",
        "gid": f"exp_seed_{int(utc_ts())}",
        "timestamp": utc_ts(),
        "source_gids": [],
        "data": {
            "urls": urls,
            "targets": list(source_targets or []),
            "goal": goal,
            "source_adapters": list(source_adapters or []),
            "exploration_run_id": exploration_run_id,
            "research_goal_id": exploration_run_id,
        },
        "provenance": {
            "agent": "explorer-network-read-loop-runner",
            "source": "manual_seed",
            "execution_risk_tier": "network_read",
            "coordination_channel": "crdt_genomes",
            "network_read_candidate": True,
            "external_write_performed": False,
            "real_execution_enabled": False,
            "goal": goal,
            "source_adapters": list(source_adapters or []),
            "source_adapter_target_count": len(source_targets or []),
            "exploration_run_id": exploration_run_id,
            "research_goal_id": exploration_run_id,
        },
    }


def _record_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for record in records:
        record_type = str(record.get("type") or "unknown")
        event_type = str(record.get("event_type") or "")

        counts[record_type] = counts.get(record_type, 0) + 1

        if record_type == "swarm_event" and event_type:
            key = f"swarm_event:{event_type}"
            counts[key] = counts.get(key, 0) + 1

    return dict(sorted(counts.items()))


def _replace_crdt(obj: Any, crdt: CRDTAdapter) -> None:
    old = getattr(obj, "crdt", None)
    if old is not crdt:
        _safe_close(old)
    setattr(obj, "crdt", crdt)


def _safe_close(obj: Any) -> None:
    close = getattr(obj, "close", None)
    if callable(close):
        close()


async def _safe_aclose(obj: Any) -> None:
    close = getattr(obj, "aclose", None)
    if callable(close):
        await close()


def _extract_mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _format_result(result: Mapping[str, Any]) -> str:
    node = result.get("node") if isinstance(result.get("node"), Mapping) else {}
    meta = (
        result.get("meta_agent")
        if isinstance(result.get("meta_agent"), Mapping)
        else {}
    )

    return (
        "Explorer network-read loop: "
        f"status={result.get('status')} "
        f"seed_urls={len(result.get('seed_urls') or [])} "
        f"exploration_run_id={result.get('exploration_run_id') or ''} "
        f"source_adapters={len(result.get('source_adapters') or [])} "
        f"source_adapter_targets={len(result.get('source_adapter_targets') or [])} "
        f"node_did_work={str(bool(node.get('did_work'))).lower()} "
        f"fetches_attempted={node.get('fetches_attempted', 0)} "
        f"findings_emitted={node.get('findings_emitted', 0)} "
        f"targets_discovered={node.get('targets_discovered', 0)} "
        f"targets_published={node.get('targets_published', 0)} "
        f"meta_snapshot_findings={meta.get('snapshot_findings', 0)} "
        f"classifications_published={meta.get('classifications_published', 0)} "
        f"targets_published={meta.get('targets_published', 0)} "
        f"external_write_performed={str(bool(result.get('external_write_performed'))).lower()} "
        f"real_execution_enabled={str(bool(result.get('real_execution_enabled'))).lower()}"
    )


async def _async_main() -> None:
    args = build_parser().parse_args()
    result = await run_explorer_network_read_loop(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()