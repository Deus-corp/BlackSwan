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


def test_html_content_preview_extracts_title_meta_headings_and_paragraphs(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-content-extract-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    preview = node._extract_html_content_preview_fallback(
        """
        <!doctype html>
        <html>
          <head>
            <title>Python asyncio — Asynchronous I/O</title>
            <meta name="description" content="asyncio is a library to write concurrent code using async and await syntax.">
            <meta property="og:title" content="asyncio — Python documentation">
          </head>
          <body>
            <main>
              <h1>asyncio — Asynchronous I/O</h1>
              <p>asyncio is used as a foundation for multiple Python asynchronous frameworks.</p>
              <p>It provides APIs for coroutines, tasks, event loops, subprocesses, streams, and synchronization primitives.</p>
            </main>
          </body>
        </html>
        """,
        url="https://docs.python.org/3/library/asyncio.html",
        target_quality_provenance={
            "source_adapter": "evidence",
            "source_kind": "curated_evidence_url",
            "research_goal": "autonomous agents memory systems",
        },
    )

    assert "Python asyncio" in preview
    assert "asyncio is a library" in preview
    assert "coroutines" in preview
    assert "event loops" in preview
    assert "<html" not in preview.lower()


def test_node_fetch_uses_html_preview_fallback_for_non_evidence_page(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-content-fetch-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "run-content-extraction"

    url = "https://docs.python.org/3/library/asyncio.html"
    node._target_context_by_url[url] = {
        "event_gid": "seed-content",
        "source_gids": ["seed-content"],
        "target_depth": 0,
        "exploration_run_id": "run-content-extraction",
        "source_adapter": "sitemap",
        "source_kind": "documentation_page",
        "source_score": 0.80,
        "quality_score": 0.80,
        "system_relevance_score": 0.80,
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
                <title>asyncio — Python documentation</title>
                <meta name="description" content="asyncio provides infrastructure for writing concurrent Python code.">
              </head>
              <body>
                <main>
                  <h1>asyncio — Asynchronous I/O</h1>
                  <p>asyncio supports coroutines, tasks, event loops, streams, subprocesses, and synchronization primitives.</p>
                </main>
              </body>
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
    finding = findings[0]

    assert finding["content_preview"]
    assert "asyncio" in finding["content_preview"]
    assert "event loops" in finding["content_preview"]
    assert finding["provenance"]["content_preview_source"] == (
        "html_content_preview_fallback"
    )
    assert finding["provenance"]["content_preview_chars"] >= 80