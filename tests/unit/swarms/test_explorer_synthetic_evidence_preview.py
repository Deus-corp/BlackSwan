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


def test_node_builds_synthetic_preview_for_seeded_evidence(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-synthetic-preview-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    preview = node._build_synthetic_evidence_preview(
        url="https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        target_quality_provenance={
            "preferred_evidence_target": True,
            "source_adapter": "evidence_seed",
            "source_kind": "goal_evidence_url",
            "research_goal": "autonomous agents memory systems",
            "goal_terms_matched": ["agents"],
        },
    )

    assert "Building Type Safe Llm Agents With Pydantic Ai" in preview
    assert "Seeded explorer evidence target" in preview
    assert "autonomous agents memory systems" in preview


def test_node_fetch_uses_synthetic_preview_when_html_preview_is_empty(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-synthetic-preview-fetch-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "run-synthetic-preview"

    url = "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
    node._target_context_by_url[url] = {
        "event_gid": "seed-synthetic",
        "source_gids": ["seed-synthetic"],
        "target_depth": 0,
        "exploration_run_id": "run-synthetic-preview",
        "source_adapter": "evidence_seed",
        "source_kind": "goal_evidence_url",
        "preferred_evidence_target": True,
        "goal_alignment_score": 0.28,
        "goal_terms_matched": ["agents"],
        "source_score": 0.95,
        "quality_score": 0.95,
        "system_relevance_score": 0.92,
        "research_goal": "autonomous agents memory systems",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\\nAllow: /\\n")
        return httpx.Response(200, text="<html><head></head><body></body></html>")

    async def run() -> str:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
            headers={"User-Agent": node.policy.user_agent},
        ) as client:
            return await node._fetch_and_emit(client, url)

    result = asyncio.run(run())

    assert result in {"finding_published", "targets_discovered"}

    findings = [
        record
        for record in node.crdt.records
        if isinstance(record, dict) and record.get("type") == "explorer_finding"
    ]

    assert findings
    finding = findings[0]

    assert finding["content_preview"]
    assert "Seeded explorer evidence target" in finding["content_preview"]
    assert finding["provenance"]["preferred_evidence_target"] is True
    assert finding["provenance"]["content_preview_source"] == (
        "synthetic_evidence_preview"
    )
    assert finding["provenance"]["content_preview_chars"] >= 30