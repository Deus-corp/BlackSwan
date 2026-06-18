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


def test_node_extracts_preview_from_html_title_and_meta(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-preview-fallback-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    preview = node._extract_html_content_preview_fallback(
        """
        <html>
          <head>
            <title>Building Type-Safe LLM Agents With Pydantic AI</title>
            <meta name="description" content="Learn to build Python LLM agents with Pydantic AI, structured outputs, validation, workflows, and runtime orchestration.">
          </head>
          <body><script>ignored()</script></body>
        </html>
        """,
        url="https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        target_quality_provenance={
            "preferred_evidence_target": True,
            "source_kind": "goal_evidence_url",
            "research_goal": "autonomous agents memory systems",
        },
    )

    assert "Type-Safe LLM Agents" in preview
    assert "Pydantic AI" in preview
    assert "runtime orchestration" in preview


def test_node_fetch_uses_preview_fallback_for_seeded_evidence(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-preview-fetch-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "run-preview-fallback"

    url = "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
    node._target_context_by_url[url] = {
        "event_gid": "seed-preview",
        "source_gids": ["seed-preview"],
        "target_depth": 0,
        "exploration_run_id": "run-preview-fallback",
        "source_adapter": "evidence_seed",
        "source_kind": "goal_evidence_url",
        "preferred_evidence_target": True,
        "goal_alignment_score": 0.28,
        "source_score": 0.95,
        "quality_score": 0.95,
        "system_relevance_score": 0.92,
        "research_goal": "autonomous agents memory systems",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\\nAllow: /\\n")
        return httpx.Response(
            200,
            text="""
            <html>
              <head>
                <title>Building Type-Safe LLM Agents With Pydantic AI</title>
                <meta name="description" content="Python LLM agents with Pydantic AI, structured outputs, memory-aware workflows, and runtime orchestration.">
              </head>
              <body></body>
            </html>
            """,
        )

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
    assert findings[0]["content_preview"]
    assert "Pydantic AI" in findings[0]["content_preview"]
    assert findings[0]["provenance"]["preferred_evidence_target"] is True