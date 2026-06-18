import asyncio
from pathlib import Path

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


def test_node_filters_static_and_schema_targets(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-static-filter-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    html = """
    <html>
      <body>
        <a href="https://realpython.com/python-context-engineering-ai/">article</a>
        <a href="https://github.githubassets.com/assets/font.woff2">font</a>
        <a href="https://github.blog/_static?abc=123">static</a>
        <a href="https://www.w3.org/1999/xlink">xlink</a>
        <a href="https://gmpg.org/xfn/11">xfn</a>
      </body>
    </html>
    """

    targets = node._extract_discovered_targets(
        html,
        base_url="https://realpython.com/",
        parent_depth=0,
    )
    urls = [item["url"] for item in targets]

    assert "https://realpython.com/python-context-engineering-ai" in urls
    assert "https://github.githubassets.com/assets/font.woff2" not in urls
    assert "https://github.blog/_static?abc=123" not in urls
    assert "https://www.w3.org/1999/xlink" not in urls
    assert "https://gmpg.org/xfn/11" not in urls


def test_meta_classifies_realpython_article_as_useful_not_frontier(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-realpython-useful-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-realpython-useful"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-realpython",
        "url": "https://realpython.com/python-context-engineering-ai",
        "domain": "realpython.com",
        "content_preview": (
            "Context engineering for AI agents explains how to build reliable "
            "Python systems with memory, retrieval, orchestration, runtime "
            "behavior, prompts, evaluation, and autonomous agent workflows."
        ),
        "content_hash": "hash-realpython-context",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-realpython",
        "provenance": {
            "exploration_run_id": "run-realpython-useful",
            "research_goal_id": "run-realpython-useful",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "discovered_target_count": 12,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-realpython",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"
    assert classified[0]["provenance"]["frontier_source"] is False
    assert classified[0]["provenance"]["fallback_quality_signals"][
        "concrete_evidence_page"
    ] is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]
    assert len(memory_records) == 1


def test_meta_keeps_docs_root_as_frontier(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-root-frontier-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    finding = {
        "url": "https://docs.github.com/",
        "domain": "docs.github.com",
        "content_preview": "GitHub Docs root page with links to many documentation sections.",
        "content_hash": "hash-docs-root",
        "fetch_status": "ok",
        "provenance": {
            "discovered_target_count": 12,
        },
    }

    signals = agent._fallback_quality_signals(finding)

    assert agent._is_frontier_source_finding(finding, signals) is True