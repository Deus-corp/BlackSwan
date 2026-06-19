import asyncio
from pathlib import Path

import httpx

from src.swarms.explorer.node import ExplorerNode


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


def test_node_records_source_adapter_http_429_rate_limit(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-source-rate-limit-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()

    url = "https://github.com/search?q=agents&type=code"
    node._target_context_by_url[url] = {
        "source_adapter": "github",
        "source_kind": "github_code_search",
        "target_depth": 0,
        "exploration_run_id": "run-rate-limit",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\\nAllow: /\\n")
        return httpx.Response(429, text="rate limited")

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            return await node._fetch_and_emit(client, url)

    result = asyncio.run(run())

    assert result in {"finding_published", "targets_discovered"}

    assert node._domain_rate_limits["github.com"] == 1
    assert node._source_adapter_rate_limits["github:github.com:http_429"] == 1
    assert "github.com" in node._rate_limited_domains_seen_this_run

    findings = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_finding"
    ]

    assert findings
    assert findings[0]["fetch_status"] == "http_429"
    assert findings[0]["provenance"]["source_adapter_rate_limited"] is True
    assert findings[0]["provenance"]["source_adapter_backoff_domain"] == "github.com"


def test_node_skips_source_adapter_targets_on_backoff_but_keeps_evidence(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-source-backoff-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 5
    node.max_targets_per_domain_per_tick = 5

    source_url = "https://github.com/search?q=agents&type=repositories"
    evidence_url = "https://github.com/langchain-ai/langchain"

    node._target_context_by_url[source_url] = {
        "source_adapter": "github",
        "source_kind": "github_repository_search",
    }
    node._target_context_by_url[evidence_url] = {
        "source_adapter": "evidence",
        "source_kind": "github_repository",
        "preferred_evidence_target": True,
        "source_score": 0.90,
    }

    node._rate_limited_domains_seen_this_run.add("github.com")

    selected = node._select_domain_aware_targets([source_url, evidence_url])

    assert source_url not in selected
    assert evidence_url in selected
    assert node._source_adapter_blocked_targets["github"] == 1


def test_node_records_robots_disallowed_for_source_adapter(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-source-robots-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.policy.respect_robots = True

    url = "https://duckduckgo.com/html?q=agents"
    node._target_context_by_url[url] = {
        "source_adapter": "search",
        "source_kind": "public_search_html",
        "target_depth": 0,
        "exploration_run_id": "run-robots",
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
    assert node._source_adapter_rate_limits[
        "search:duckduckgo.com:robots_disallowed"
    ] == 1
    assert node._domain_rate_limits["duckduckgo.com"] == 1