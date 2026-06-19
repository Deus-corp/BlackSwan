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


GITHUB_REPO_HTML = """
<html>
  <head>
    <meta property="og:title" content="langchain-ai/langchain">
    <meta name="description" content="Build context-aware reasoning applications with agents, retrieval, and memory systems.">
  </head>
  <body>
    <article class="markdown-body">
      <h1>LangChain</h1>
      <p>LangChain helps build autonomous agents with tool use, memory, retrieval,
      orchestration, and evaluation loops.</p>
    </article>
  </body>
</html>
"""


GITHUB_BLOB_HTML = """
<html>
  <head>
    <meta property="og:title" content="autogen/README.md at main">
  </head>
  <body>
    <table>
      <tr><td class="blob-code blob-code-inner"># AutoGen</td></tr>
      <tr><td class="blob-code blob-code-inner">Multi-agent orchestration framework for autonomous agents.</td></tr>
      <tr><td class="blob-code blob-code-inner">Includes memory, planning, tools, and evaluation examples.</td></tr>
    </table>
  </body>
</html>
"""


def test_node_extracts_github_repository_preview(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-github-repo-preview-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    preview = node._extract_github_evidence_content_preview(
        GITHUB_REPO_HTML,
        url="https://github.com/langchain-ai/langchain",
        target_quality_provenance={
            "source_adapter": "evidence",
            "source_kind": "github_repository",
            "preferred_evidence_target": True,
        },
    )

    assert preview
    assert "GitHub repository evidence" in preview
    assert "langchain-ai/langchain" in preview
    assert "autonomous agents" in preview
    assert "memory" in preview


def test_node_extracts_github_blob_preview(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-github-blob-preview-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    preview = node._extract_github_evidence_content_preview(
        GITHUB_BLOB_HTML,
        url="https://github.com/microsoft/autogen/blob/main/README.md",
        target_quality_provenance={
            "source_adapter": "evidence",
            "source_kind": "github_code_blob",
            "preferred_evidence_target": True,
        },
    )

    assert preview
    assert "GitHub code evidence" in preview
    assert "Multi-agent orchestration" in preview
    assert "memory" in preview


def test_node_fetch_github_repository_uses_github_preview_fallback(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-github-repo-fetch-preview-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "run-github-preview"

    url = "https://github.com/langchain-ai/langchain"
    node._target_context_by_url[url] = {
        "event_gid": "seed-github-preview",
        "source_gids": ["seed-github-preview"],
        "target_depth": 0,
        "exploration_run_id": "run-github-preview",
        "research_goal": "autonomous agents memory systems",
        "source_adapter": "evidence",
        "source_kind": "github_repository",
        "preferred_evidence_target": True,
        "source_score": 0.90,
        "quality_score": 0.90,
        "system_relevance_score": 0.82,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\\nAllow: /\\n")
        return httpx.Response(200, text=GITHUB_REPO_HTML)

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
    assert "GitHub repository evidence" in finding["content_preview"]
    assert finding["provenance"]["content_preview_source"] == (
        "github_evidence_content_preview"
    )