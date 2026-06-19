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


ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2606.12345v1</id>
    <updated>2026-06-18T00:00:00Z</updated>
    <published>2026-06-18T00:00:00Z</published>
    <title>Autonomous Agents with Long-Term Memory Systems</title>
    <summary>
      We study autonomous LLM agents that use memory systems, retrieval,
      orchestration, and evaluation loops for robust task execution.
    </summary>
    <author><name>Alice Example</name></author>
    <category term="cs.AI"/>
    <category term="cs.CL"/>
  </entry>
</feed>
"""


def test_node_extracts_arxiv_atom_entries_as_evidence_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-arxiv-result-expansion-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    targets = node._extract_arxiv_atom_result_targets(
        ARXIV_ATOM,
        base_url=(
            "https://export.arxiv.org/api/query?"
            "search_query=all%3Aautonomous+agents+memory+systems"
        ),
        parent_depth=0,
        goal="autonomous agents memory systems",
    )

    assert targets
    target = targets[0]

    assert target["url"] == "https://arxiv.org/abs/2606.12345v1"
    assert target["source_adapter"] == "evidence"
    assert target["source_kind"] == "arxiv_paper_abs"
    assert target["discovery_method"] == "arxiv_api_result_entry"
    assert target["preferred_evidence_target"] is True
    assert target["evidence_category"] == "arxiv_research_paper"
    assert target["source_score"] >= 0.86
    assert target["system_relevance_score"] >= 0.75
    assert "agents" in target["goal_terms_matched"]
    assert "memory" in target["goal_terms_matched"]
    assert target["network_read_candidate"] is True
    assert target["external_write_performed"] is False
    assert target["real_execution_enabled"] is False


def test_node_fetch_arxiv_api_publishes_paper_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-arxiv-fetch-expansion-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "run-arxiv-expansion"
    node.discovered_target_limit = 5
    node.max_target_depth = 2

    url = (
        "https://export.arxiv.org/api/query?"
        "search_query=all%3Aautonomous+agents+memory+systems"
    )
    node._target_context_by_url[url] = {
        "event_gid": "seed-arxiv",
        "source_gids": ["seed-arxiv"],
        "target_depth": 0,
        "exploration_run_id": "run-arxiv-expansion",
        "research_goal": "autonomous agents memory systems",
        "source_adapter": "arxiv",
        "source_kind": "arxiv_api_query",
        "source_score": 0.90,
        "quality_score": 0.90,
        "system_relevance_score": 0.82,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\\nAllow: /\\n")
        return httpx.Response(200, text=ARXIV_ATOM)

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            return await node._fetch_and_emit(client, url)

    result = asyncio.run(run())

    assert result in {"finding_published", "targets_discovered"}

    targets = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_targets"
    ]

    assert targets
    urls = targets[0]["data"]["urls"]

    assert "https://arxiv.org/abs/2606.12345v1" in urls

    metadata_by_url = targets[0]["provenance"]["discovered_target_metadata_by_url"]
    paper_metadata = metadata_by_url["https://arxiv.org/abs/2606.12345v1"]

    assert paper_metadata["source_adapter"] == "evidence"
    assert paper_metadata["source_kind"] == "arxiv_paper_abs"
    assert paper_metadata["preferred_evidence_target"] is True
    assert paper_metadata["evidence_category"] == "arxiv_research_paper"