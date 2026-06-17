import asyncio
from pathlib import Path

import httpx

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


def test_explorer_fetch_emits_network_read_evidence(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="<html><body>Hello explorer</body></html>")

    transport = httpx.MockTransport(handler)

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            return await node._fetch_and_emit(client, "https://example.com/page")

    result = asyncio.run(run())

    assert result == "finding_published"

    findings = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_finding"
    ]
    canonical = [
        record
        for record in node.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "swarm_event"
        and record.get("event_type") == "explorer_finding"
    ]

    assert len(findings) == 1
    assert len(canonical) == 1

    finding = findings[0]
    provenance = finding["provenance"]

    assert finding["url"] == "https://example.com/page"
    assert finding["fetch_status"] == "ok"
    assert finding["content_hash"]
    assert provenance["execution_risk_tier"] == "network_read"
    assert provenance["network_read_performed"] is True
    assert provenance["external_write_performed"] is False
    assert provenance["real_execution_enabled"] is False
    assert provenance["production_paths_mutated"] is False
    assert provenance["production_secrets_accessed"] is False
    assert provenance["memory_ingestion_candidate"] is True

    payload = canonical[0]["payload"]
    assert payload["execution_risk_tier"] == "network_read"
    assert payload["network_read_performed"] is True
    assert payload["external_write_performed"] is False
    assert payload["memory_ingestion_candidate"] is True