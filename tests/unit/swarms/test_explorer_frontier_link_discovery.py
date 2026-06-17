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


def test_explorer_node_discovers_and_publishes_frontier_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-frontier-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.discovered_target_limit = 5
    node.max_target_depth = 2

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
                <a href="https://example.com/file.pdf">PDF should be skipped</a>
                <a href="mailto:test@example.com">Mail should be skipped</a>
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

    targets = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_targets"
    ]
    findings = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_finding"
    ]

    assert len(findings) == 1
    assert targets

    urls = targets[0]["data"]["urls"]
    assert "https://example.com/docs" in urls
    assert "https://example.com/blog/post" in urls
    assert all(not url.endswith(".pdf") for url in urls)

    assert targets[0]["provenance"]["discovery_method"] == "html_link_extraction"
    assert targets[0]["provenance"]["execution_risk_tier"] == "network_read"
    assert targets[0]["provenance"]["external_write_performed"] is False
    assert targets[0]["provenance"]["real_execution_enabled"] is False

    finding_provenance = findings[0]["provenance"]
    assert finding_provenance["discovered_target_count"] >= 2
    assert finding_provenance["discovered_targets"]


def test_explorer_meta_dedupes_legacy_and_canonical_findings(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-dedupe-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    findings = [
        {
            "type": "explorer_finding",
            "source_gid": "legacy-source",
            "url": "https://example.com/",
            "content_hash": "same-hash",
            "fetch_status": "ok",
            "classification": "unclassified",
            "confidence": 0.0,
            "reason": "",
            "timestamp": 1.0,
            "gid": "legacy-finding",
            "provenance": {},
        },
        {
            "type": "explorer_finding",
            "source_gid": "canonical-source",
            "url": "https://example.com/",
            "content_hash": "same-hash",
            "fetch_status": "ok",
            "classification": "unclassified",
            "confidence": 0.0,
            "reason": "",
            "timestamp": 2.0,
            "gid": "canonical-finding",
            "provenance": {},
        },
    ]

    deduped = agent._dedupe_findings(findings)

    assert len(deduped) == 1
    assert deduped[0]["url"] == "https://example.com/"