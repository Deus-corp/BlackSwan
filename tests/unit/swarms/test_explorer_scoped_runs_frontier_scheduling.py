import asyncio
from pathlib import Path

import httpx

from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.node import ExplorerNode


class _FakeCRDT:
    def __init__(self) -> None:
        self.state = {}
        self.records = []

    async def add_genome(self, record):
        self.records.append(record)
        gid = record.get("gid") if isinstance(record, dict) else None
        if gid:
            self.state[gid] = record
        return record

    def close(self) -> None:
        return None


def test_explorer_node_domain_aware_frontier_selection(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-domain-aware-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 4
    node.max_targets_per_domain_per_tick = 1

    selected = node._select_domain_aware_targets(
        [
            "https://a.example/1",
            "https://a.example/2",
            "https://a.example/3",
            "https://b.example/1",
            "https://b.example/2",
            "https://c.example/1",
        ]
    )

    assert len(selected) == 3
    assert selected == [
        "https://a.example/1",
        "https://b.example/1",
        "https://c.example/1",
    ]


def test_explorer_node_propagates_exploration_run_id_to_findings_and_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-run-scope-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "exp-run-test"
    node.discovered_target_limit = 5
    node.max_target_depth = 2

    node._target_context_by_url["https://example.com"] = {
        "event_gid": "seed-event",
        "source_gids": ["seed-event"],
        "target_depth": 0,
        "exploration_run_id": "exp-run-test",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200,
            text="""
            <html>
              <body>
                <a href="/docs/">Docs</a>
                <a href="https://example.com/blog/post">Blog</a>
              </body>
            </html>
            """,
        )

    transport = httpx.MockTransport(handler)

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            return await node._fetch_and_emit(client, "https://example.com/")

    result = asyncio.run(run())

    assert result in {"finding_published", "targets_discovered"}

    findings = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_finding"
    ]
    targets = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_targets"
    ]

    assert findings
    assert findings[0]["provenance"]["exploration_run_id"] == "exp-run-test"

    assert targets
    assert targets[0]["data"]["exploration_run_id"] == "exp-run-test"
    assert targets[0]["provenance"]["exploration_run_id"] == "exp-run-test"


def test_explorer_meta_agent_filters_findings_by_active_run(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-run-filter-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.active_exploration_run_id = "run-current"

    findings = [
        {
            "url": "https://current.example/",
            "content_hash": "hash-current",
            "fetch_status": "ok",
            "source_gid": "source-current",
            "provenance": {"exploration_run_id": "run-current"},
        },
        {
            "url": "https://old.example/",
            "content_hash": "hash-old",
            "fetch_status": "ok",
            "source_gid": "source-old",
            "provenance": {"exploration_run_id": "run-old"},
        },
    ]

    deduped = agent._dedupe_findings(findings)

    assert len(deduped) == 1
    assert deduped[0]["url"] == "https://current.example/"