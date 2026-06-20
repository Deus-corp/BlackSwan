from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from src.swarms.explorer.node import ExplorerNode
from src.testing.check_explorer_source_planned_evidence_loop import (
    validate_explorer_source_planned_evidence_loop,
)


class _FakeCRDT:
    def __init__(self) -> None:
        self.records = []
        self.state = {}

    async def add_genome(self, record):
        self.records.append(record)
        gid = record.get("gid") if isinstance(record, dict) else None
        if gid:
            self.state[gid] = record
        return record


def _safe_template_url() -> str:
    return (
        "https://duckduckgo.com/html?"
        "q=site%3Aarxiv.org+autonomous+agents+memory+systems"
    )


def _safe_template_context() -> dict:
    return {
        "source_adapter": "search",
        "source_kind": "public_search_html",
        "discovery_method": "safe_public_search_query_template",
        "safe_public_search_template": True,
        "search_query": "site:arxiv.org autonomous agents memory systems",
        "search_query_site": "arxiv.org",
        "search_query_template_kind": "research_papers",
        "search_query_rationale": "Find public arXiv papers.",
        "source_score": 0.62,
        "quality_score": 0.62,
        "system_relevance_score": 0.68,
    }


def test_node_counts_safe_public_search_template_seen_and_selected(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-safe-search-template-select-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 1

    url = _safe_template_url()
    node._target_context_by_url[url] = _safe_template_context()

    selected = node._select_domain_aware_targets([url])

    assert selected == [url]
    assert node._safe_public_search_templates_seen == 1
    assert node._safe_public_search_templates_selected == 1
    assert node._unsafe_public_search_templates_detected == 0


def test_node_counts_safe_public_search_template_blocked_by_robots(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-safe-search-template-robots-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.policy.respect_robots = True

    url = _safe_template_url()
    node._target_context_by_url[url] = {
        **_safe_template_context(),
        "target_depth": 0,
        "exploration_run_id": "run-safe-template-robots",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text="should not be fetched")

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            return await node._fetch_and_emit(client, url)

    result = asyncio.run(run())

    assert result == "robots_disallowed"
    assert node._safe_public_search_templates_fetched == 1
    assert node._safe_public_search_templates_blocked == 1
    assert node._unsafe_public_search_templates_detected == 0


def test_node_counts_unsafe_public_search_template_metadata_once(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-unsafe-search-template-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 1

    url = _safe_template_url()
    node._target_context_by_url[url] = {
        **_safe_template_context(),
        "search_query": "site:github.com password token secret leak",
        "search_query_site": "github.com",
        "search_query_template_kind": "official_docs",
    }

    selected = node._select_domain_aware_targets([url])

    assert selected == [url]
    assert node._safe_public_search_templates_seen == 1
    assert node._safe_public_search_templates_selected == 1
    assert node._unsafe_public_search_templates_detected == 1

    node._select_domain_aware_targets([url])

    assert node._unsafe_public_search_templates_detected == 1


def _healthy_result() -> dict:
    return {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": 7,
        "total_targets_published": 123,
        "total_findings_emitted": 10,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "ticks": [
            {
                "tick": 3,
                "memory_records_published": 1,
                "targets_published": 0,
                "findings_emitted": 1,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "evidence": 20,
                        "search": 5,
                    },
                    "source_adapter_targets_selected": {
                        "evidence": 7,
                        "search": 1,
                    },
                    "source_adapter_rate_limits": {
                        "search:duckduckgo.com:robots_disallowed": 1,
                    },
                    "domain_rate_limits": {
                        "duckduckgo.com": 1,
                    },
                    "safe_public_search_templates_seen": 5,
                    "safe_public_search_templates_selected": 1,
                    "safe_public_search_templates_fetched": 1,
                    "safe_public_search_templates_blocked": 1,
                    "unsafe_public_search_templates_detected": 0,
                },
            }
        ],
    }


def test_checker_accepts_safe_public_search_template_telemetry() -> None:
    errors = validate_explorer_source_planned_evidence_loop(_healthy_result())

    assert errors == []


def test_checker_rejects_unsafe_public_search_template_telemetry() -> None:
    result = _healthy_result()
    result["ticks"][0]["node"]["unsafe_public_search_templates_detected"] = 1

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("unsafe public search templates detected" in error for error in errors)


def test_checker_rejects_invalid_safe_template_counter_order() -> None:
    result = _healthy_result()
    result["ticks"][0]["node"]["safe_public_search_templates_selected"] = 6

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any("selected must be <= seen" in error for error in errors)