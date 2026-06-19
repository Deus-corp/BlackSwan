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
from src.swarms.explorer.meta_agent_core.source_plan import (
    build_research_source_plan,
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
        "--source-plan",
        action="store_true",
        default=False,
        help=(
            "Enable deterministic research-goal source planning. The planner "
            "adds ranked network_read candidates derived from --goal."
        ),
    )
    parser.add_argument(
        "--source-plan-limit",
        type=int,
        default=20,
        help="Maximum number of source-plan candidates to add to the seed frontier.",
    )
    parser.add_argument(
        "--exploration-run-id",
        default="",
        help="Optional stable exploration run id. Generated when omitted.",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=1,
        help="Number of explorer node/meta cycles to run.",
    )
    parser.add_argument(
        "--tick-delay-seconds",
        type=float,
        default=0.0,
        help="Optional delay between explorer ticks.",
    )
    parser.add_argument(
        "--evidence-url",
        action="append",
        default=[],
        help=(
            "High-priority evidence URL to seed directly into the explorer "
            "frontier. Can be passed multiple times."
        ),
    )
    parser.add_argument(
        "--json-output",
        default="",
        help=(
            "Optional path for writing a clean JSON runtime result. "
            "Useful when logs make stdout unsuitable for contract checks."
        ),
    )
    parser.add_argument("--node-id", default="exp-node-network-read-loop")
    parser.add_argument("--meta-agent-id", default="exp-meta-network-read-loop")
    parser.add_argument("--skip-meta", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


async def run_explorer_network_read_loop(args: argparse.Namespace) -> dict[str, Any]:
    urls = [normalize_url(url) for url in list(args.url or [])]
    urls = [url for url in urls if url]

    evidence_urls = [
        normalize_url(url)
        for url in list(getattr(args, "evidence_url", []) or [])
    ]
    evidence_urls = [url for url in evidence_urls if url]

    initial_urls_for_run_id = _dedupe_urls([*evidence_urls, *urls])
    if not initial_urls_for_run_id:
        initial_urls_for_run_id = ["https://example.com/"]

    exploration_run_id = (
        str(getattr(args, "exploration_run_id", "") or "").strip()
        or _make_exploration_run_id(
            goal=str(getattr(args, "goal", "") or ""),
            urls=initial_urls_for_run_id,
        )
    )

    evidence_seed_targets = _build_evidence_seed_targets(
        evidence_urls,
        goal=str(getattr(args, "goal", "") or ""),
        exploration_run_id=exploration_run_id,
    )

    source_plan_result = _build_runtime_research_source_plan(
        args,
        seed_urls=_dedupe_urls([*evidence_urls, *urls]),
    )
    source_plan_targets = list(source_plan_result.get("targets", []) or [])

    source_targets = build_source_adapter_targets(
        goal=str(getattr(args, "goal", "") or ""),
        adapters=list(getattr(args, "source_adapter", []) or []),
        seed_urls=urls,
        limit=int(getattr(args, "source_limit", 20) or 20),
    )

    source_targets = [
        *evidence_seed_targets,
        *source_plan_targets,
        *source_targets,
    ]

    adapter_urls = [
        str(item.get("url") or "").strip()
        for item in source_targets
        if str(item.get("url") or "").strip()
    ]

    urls = _dedupe_urls([*evidence_urls, *urls, *adapter_urls])

    if not urls:
        urls = ["https://example.com/"]

    ticks = max(1, int(getattr(args, "ticks", 1) or 1))
    tick_delay_seconds = max(
        0.0,
        float(getattr(args, "tick_delay_seconds", 0.0) or 0.0),
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

    def _node_counters() -> dict[str, int]:
        return {
            "targets_seen_last_tick": int(
                getattr(node, "_targets_seen_last_tick", 0) or 0
            ),
            "fetches_attempted": int(getattr(node, "_fetches_attempted", 0) or 0),
            "fetches_failed": int(getattr(node, "_fetches_failed", 0) or 0),
            "findings_emitted": int(getattr(node, "_findings_emitted", 0) or 0),
            "targets_discovered": int(getattr(node, "_targets_discovered", 0) or 0),
            "targets_published": int(getattr(node, "_targets_published", 0) or 0),
        }

    def _delta(after: Mapping[str, int], before: Mapping[str, int], key: str) -> int:
        return max(0, int(after.get(key, 0) or 0) - int(before.get(key, 0) or 0))

    def _build_node_result(*, did_work: bool) -> dict[str, Any]:
        counters = _node_counters()
        return {
            "node_id": node.node_id,
            "did_work": bool(did_work),
            "targets_seen_last_tick": counters["targets_seen_last_tick"],
            "fetches_attempted": counters["fetches_attempted"],
            "fetches_failed": counters["fetches_failed"],
            "findings_emitted": counters["findings_emitted"],
            "targets_discovered": counters["targets_discovered"],
            "targets_published": counters["targets_published"],
            "execution_risk_tier": "network_read",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "exploration_run_id": exploration_run_id,
            "source_adapter_targets_seen": dict(
                getattr(node, "_source_adapter_targets_seen", {}) or {}
            ),
            "source_adapter_targets_selected": dict(
                getattr(node, "_source_adapter_targets_selected", {}) or {}
            ),
            "source_adapter_rate_limits": dict(
                getattr(node, "_source_adapter_rate_limits", {}) or {}
            ),
            "source_adapter_blocked_targets": dict(
                getattr(node, "_source_adapter_blocked_targets", {}) or {}
            ),
            "domain_rate_limits": dict(
                getattr(node, "_domain_rate_limits", {}) or {}
            ),
        }

    def _build_skipped_meta_result() -> dict[str, Any]:
        return {
            "skipped": True,
            "snapshot_findings": 0,
            "decision_action": None,
            "targets_published": 0,
            "classifications_published": 0,
            "exploration_run_id": exploration_run_id,
            "memory_records_published": 0,
            "memory_handoff_skips": [],
        }

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

        tick_results: list[dict[str, Any]] = []
        final_node_result: dict[str, Any] = _build_node_result(did_work=False)
        final_meta_result: dict[str, Any] = _build_skipped_meta_result()

        async with httpx.AsyncClient(
            timeout=node.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            for tick_index in range(1, ticks + 1):
                if callable(refresh):
                    refresh()

                before_node_counters = _node_counters()

                did_node_work = await node._consume_targets_and_explore(client)

                after_node_counters = _node_counters()
                node_result = _build_node_result(did_work=did_node_work)

                if callable(refresh):
                    refresh()

                meta_result: dict[str, Any] = _build_skipped_meta_result()

                if not bool(getattr(args, "skip_meta", False)):
                    snapshot = await meta.collect()
                    decision = await meta.decide(snapshot)
                    commands = await meta.issue_commands(decision, snapshot)
                    await meta.persist_decision(decision, snapshot, commands)

                    meta_result = {
                        "skipped": False,
                        "snapshot_findings": len(
                            getattr(snapshot, "findings", []) or []
                        ),
                        "decision_action": _extract_mapping_value(
                            decision,
                            "action",
                        ),
                        "targets_published": int(
                            getattr(meta, "_last_targets_published", 0) or 0
                        ),
                        "classifications_published": int(
                            getattr(
                                meta,
                                "_last_classifications_published",
                                0,
                            )
                            or 0
                        ),
                        "exploration_run_id": exploration_run_id,
                        "memory_records_published": int(
                            getattr(
                                meta,
                                "_last_memory_records_published",
                                0,
                            )
                            or 0
                        ),
                        "memory_handoff_skips": list(
                            getattr(meta, "_last_memory_handoff_skips", []) or []
                        )[-20:],
                    }

                if callable(refresh):
                    refresh()

                tick_results.append(
                    {
                        "tick": tick_index,
                        "node": node_result,
                        "meta_agent": meta_result,
                        "fetches_attempted": _delta(
                            after_node_counters,
                            before_node_counters,
                            "fetches_attempted",
                        ),
                        "fetches_failed": _delta(
                            after_node_counters,
                            before_node_counters,
                            "fetches_failed",
                        ),
                        "findings_emitted": _delta(
                            after_node_counters,
                            before_node_counters,
                            "findings_emitted",
                        ),
                        "targets_discovered": _delta(
                            after_node_counters,
                            before_node_counters,
                            "targets_discovered",
                        ),
                        "targets_published": _delta(
                            after_node_counters,
                            before_node_counters,
                            "targets_published",
                        ),
                        "classifications_published": int(
                            meta_result.get("classifications_published", 0) or 0
                        ),
                        "meta_targets_published": int(
                            meta_result.get("targets_published", 0) or 0
                        ),
                        "memory_records_published": int(
                            meta_result.get("memory_records_published", 0) or 0
                        ),
                    }
                )

                final_node_result = node_result
                final_meta_result = meta_result

                if tick_delay_seconds and tick_index < ticks:
                    await asyncio.sleep(tick_delay_seconds)

        if callable(refresh):
            refresh()

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
            "evidence_seed_urls": evidence_urls,
            "evidence_seed_targets": evidence_seed_targets,
            "source_plan_enabled": bool(getattr(args, "source_plan", False)),
            "source_plan": source_plan_result.get("plan"),
            "source_plan_targets": source_plan_targets,
            "seed_record_gid": seed_record["gid"],
            "ticks_requested": ticks,
            "ticks_completed": len(tick_results),
            "tick_results": tick_results,
            "total_fetches_attempted": sum(
                item.get("fetches_attempted", 0) for item in tick_results
            ),
            "total_fetches_failed": sum(
                item.get("fetches_failed", 0) for item in tick_results
            ),
            "total_findings_emitted": sum(
                item.get("findings_emitted", 0) for item in tick_results
            ),
            "total_targets_discovered": sum(
                item.get("targets_discovered", 0) for item in tick_results
            ),
            "total_targets_published": sum(
                item.get("targets_published", 0) for item in tick_results
            ),
            "total_meta_targets_published": sum(
                item.get("meta_targets_published", 0) for item in tick_results
            ),
            "total_memory_records_published": sum(
                item.get("memory_records_published", 0) for item in tick_results
            ),
            "node": final_node_result,
            "meta_agent": final_meta_result,
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


def _goal_terms_for_seed(goal: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "system",
        "systems",
    }

    terms: list[str] = []
    for raw in str(goal or "").replace("-", " ").replace("_", " ").split():
        term = raw.strip().lower()
        if len(term) < 3:
            continue
        if term in stopwords:
            continue
        if term not in terms:
            terms.append(term)

    return terms


def _build_runtime_research_source_plan(
    args: argparse.Namespace,
    *,
    seed_urls: list[str],
) -> dict[str, Any]:
    """Build a deterministic research source plan for runtime seeding."""
    if not bool(getattr(args, "source_plan", False)):
        return {
            "enabled": False,
            "plan": None,
            "targets": [],
        }

    goal = str(getattr(args, "goal", "") or "").strip()
    adapters = list(getattr(args, "source_adapter", []) or [])
    limit = int(getattr(args, "source_plan_limit", 20) or 20)

    plan = build_research_source_plan(
        goal=goal,
        seed_urls=seed_urls,
        adapters=adapters,
        limit=limit,
    )

    targets = [
        item
        for item in list(plan.get("candidates", []) or [])
        if isinstance(item, dict) and str(item.get("url") or "").strip()
    ]

    return {
        "enabled": True,
        "plan": plan,
        "targets": targets,
    }


def _build_evidence_seed_targets(
    evidence_urls: list[str],
    *,
    goal: str,
    exploration_run_id: str,
) -> list[dict[str, Any]]:
    terms = _goal_terms_for_seed(goal)
    targets: list[dict[str, Any]] = []

    for raw_url in evidence_urls:
        url = normalize_url(str(raw_url or ""))
        if not url:
            continue

        haystack = url.lower().replace("-", " ").replace("_", " ")
        matched_terms = [term for term in terms if term in haystack]

        goal_alignment_score = 0.28 if matched_terms else 0.14
        source_score = 0.95 if matched_terms else 0.88

        targets.append(
            {
                "url": url,
                "source_adapter": "evidence_seed",
                "source_kind": "goal_evidence_url",
                "discovery_method": "operator_seeded_evidence_url",
                "score": source_score,
                "seed_score": 1.0,
                "source_type_score": 0.95,
                "authority_score": 0.80,
                "freshness_score": 0.50,
                "system_relevance_score": 0.92 if matched_terms else 0.75,
                "quality_score": source_score,
                "source_score": source_score,
                "preferred_evidence_target": True,
                "goal_alignment_score": goal_alignment_score,
                "goal_terms_matched": matched_terms,
                "goal": goal,
                "research_goal": goal,
                "research_goal_text": goal,
                "exploration_run_id": exploration_run_id,
                "research_goal_id": exploration_run_id,
                "execution_risk_tier": "network_read",
                "coordination_channel": "crdt_genomes",
                "network_read_candidate": True,
                "external_write_performed": False,
                "real_execution_enabled": False,
            }
        )

    return targets


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
            "goal": goal,
            "research_goal": goal,
            "research_goal_text": goal,
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


def _counter_delta(after: int, before: int) -> int:
    return max(0, int(after or 0) - int(before or 0))


def _snapshot_explorer_counters(node: Any, meta: Any) -> dict[str, int]:
    return {
        "fetches_attempted": int(getattr(node, "_fetches_attempted", 0) or 0),
        "fetches_failed": int(getattr(node, "_fetches_failed", 0) or 0),
        "findings_emitted": int(getattr(node, "_findings_emitted", 0) or 0),
        "targets_discovered": int(getattr(node, "_targets_discovered", 0) or 0),
        "targets_published": int(getattr(node, "_targets_published", 0) or 0),
        "classifications_published": int(
            getattr(meta, "_last_classifications_published", 0) or 0
        ),
        "meta_targets_published": int(
            getattr(meta, "_last_targets_published", 0) or 0
        ),
        "memory_records_published": int(
            getattr(meta, "_last_memory_records_published", 0) or 0
        ),
    }


def _tick_delta(
    *,
    tick_index: int,
    before: dict[str, int],
    after: dict[str, int],
    node_result: Mapping[str, Any],
    meta_result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "tick": tick_index,
        "node": dict(node_result),
        "meta_agent": dict(meta_result),
        "fetches_attempted": _counter_delta(
            after.get("fetches_attempted", 0),
            before.get("fetches_attempted", 0),
        ),
        "fetches_failed": _counter_delta(
            after.get("fetches_failed", 0),
            before.get("fetches_failed", 0),
        ),
        "findings_emitted": _counter_delta(
            after.get("findings_emitted", 0),
            before.get("findings_emitted", 0),
        ),
        "targets_discovered": _counter_delta(
            after.get("targets_discovered", 0),
            before.get("targets_discovered", 0),
        ),
        "targets_published": _counter_delta(
            after.get("targets_published", 0),
            before.get("targets_published", 0),
        ),
        "classifications_published": int(
            meta_result.get("classifications_published", 0) or 0
        ),
        "meta_targets_published": int(
            meta_result.get("targets_published", 0) or 0
        ),
        "memory_records_published": int(
            meta_result.get("memory_records_published", 0) or 0
        ),
    }


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
        f"memory_records_published={meta.get('memory_records_published', 0)} "
        f"external_write_performed={str(bool(result.get('external_write_performed'))).lower()} "
        f"real_execution_enabled={str(bool(result.get('real_execution_enabled'))).lower()}"
        f"ticks={result.get('ticks_completed', 1)} "
        f"total_fetches_attempted={result.get('total_fetches_attempted', 0)} "
        f"total_findings_emitted={result.get('total_findings_emitted', 0)} "
        f"total_targets_discovered={result.get('total_targets_discovered', 0)} "
        f"total_memory_records_published={result.get('total_memory_records_published', 0)} "
    )


def _write_json_output(path_value: str, result: Mapping[str, Any]) -> None:
    path_text = str(path_value or "").strip()
    if not path_text:
        return

    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


async def _async_main() -> None:
    args = build_parser().parse_args()
    result = await run_explorer_network_read_loop(args)

    _write_json_output(
        str(getattr(args, "json_output", "") or ""),
        result,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()