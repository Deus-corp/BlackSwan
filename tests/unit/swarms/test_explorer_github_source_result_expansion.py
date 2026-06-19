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


GITHUB_SEARCH_HTML = """
<html>
  <body>
    <a href="/langchain-ai/langchain">
      LangChain framework for agents and retrieval memory systems
    </a>
    <a href="/microsoft/autogen">
      AutoGen multi-agent orchestration framework
    </a>
    <a href="/login?return_to=%2Fsearch">login should be skipped</a>
    <a href="/topics/agents">topic should be skipped</a>
  </body>
</html>
"""


GITHUB_CODE_SEARCH_HTML = """
<html>
  <body>
    <a href="/microsoft/autogen/blob/main/README.md">
      README for autonomous agent orchestration and memory examples
    </a>
    <a href="/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/__init__.py">
      LangChain agents package source
    </a>
  </body>
</html>
"""


def test_node_extracts_github_repository_search_results_as_evidence_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-github-result-expansion-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    targets = node._extract_github_search_result_targets(
        GITHUB_SEARCH_HTML,
        base_url=(
            "https://github.com/search?"
            "q=autonomous+agents+memory+systems&type=repositories"
        ),
        parent_depth=0,
        goal="autonomous agents memory systems",
        source_kind="github_repository_search",
    )

    urls = [target["url"] for target in targets]

    assert "https://github.com/langchain-ai/langchain" in urls
    assert "https://github.com/microsoft/autogen" in urls
    assert not any("login" in url for url in urls)
    assert not any("/topics/" in url for url in urls)

    first = targets[0]
    assert first["source_adapter"] == "evidence"
    assert first["source_kind"] == "github_repository"
    assert first["discovery_method"] == "github_search_result_link"
    assert first["preferred_evidence_target"] is True
    assert first["evidence_category"] == "github_repository_evidence"
    assert first["source_score"] >= 0.84
    assert first["system_relevance_score"] >= 0.72
    assert first["network_read_candidate"] is True
    assert first["external_write_performed"] is False
    assert first["real_execution_enabled"] is False


def test_node_extracts_github_code_search_results_as_blob_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-github-code-expansion-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    targets = node._extract_github_search_result_targets(
        GITHUB_CODE_SEARCH_HTML,
        base_url=(
            "https://github.com/search?"
            "q=autonomous+agents+memory+systems&type=code"
        ),
        parent_depth=0,
        goal="autonomous agents memory systems",
        source_kind="github_code_search",
    )

    urls = [target["url"] for target in targets]

    assert "https://github.com/microsoft/autogen/blob/main/README.md" in urls
    assert any("langchain/agents" in url for url in urls)

    assert all(target["source_adapter"] == "evidence" for target in targets)
    assert all(target["source_kind"] == "github_code_blob" for target in targets)
    assert all(target["preferred_evidence_target"] is True for target in targets)


def test_node_fetch_github_search_publishes_repo_targets(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-github-fetch-expansion-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.crdt = _FakeCRDT()
    node.active_exploration_run_id = "run-github-expansion"
    node.discovered_target_limit = 5
    node.max_target_depth = 2

    url = (
        "https://github.com/search?"
        "q=autonomous+agents+memory+systems&type=repositories"
    )
    node._target_context_by_url[url] = {
        "event_gid": "seed-github",
        "source_gids": ["seed-github"],
        "target_depth": 0,
        "exploration_run_id": "run-github-expansion",
        "research_goal": "autonomous agents memory systems",
        "source_adapter": "github",
        "source_kind": "github_repository_search",
        "source_score": 0.90,
        "quality_score": 0.90,
        "system_relevance_score": 0.82,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\\nAllow: /\\n")
        return httpx.Response(200, text=GITHUB_SEARCH_HTML)

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

    assert "https://github.com/langchain-ai/langchain" in urls
    assert "https://github.com/microsoft/autogen" in urls

    metadata_by_url = targets[0]["provenance"]["discovered_target_metadata_by_url"]
    repo_metadata = metadata_by_url["https://github.com/langchain-ai/langchain"]

    assert repo_metadata["source_adapter"] == "evidence"
    assert repo_metadata["source_kind"] == "github_repository"
    assert repo_metadata["preferred_evidence_target"] is True
    assert repo_metadata["evidence_category"] == "github_repository_evidence"