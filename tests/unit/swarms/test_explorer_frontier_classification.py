import asyncio
from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent


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


def test_fallback_classifies_sitemap_as_frontier_not_memory(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-frontier-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-sitemap",
        "url": "https://docs.python.org/sitemap.xml",
        "domain": "docs.python.org",
        "content_preview": (
            "https://docs.python.org/3/library/asyncio.html "
            "https://docs.python.org/3/library/concurrent.futures.html "
            "https://docs.python.org/3/library/sqlite3.html "
            "https://docs.python.org/3/library/unittest.html"
        ),
        "content_hash": "hash-sitemap",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-sitemap",
        "provenance": {
            "exploration_run_id": "run-frontier",
            "source_kind": "sitemap_xml",
            "discovery_method": "sitemap_candidate",
            "discovered_target_count": 12,
            "source_score": 0.74,
            "quality_score": 0.74,
            "system_relevance_score": 0.55,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-frontier",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "FRONTIER"
    assert classified[0]["provenance"]["frontier_source"] is True

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict) and record.get("type") == "memory_record"
    ]
    assert memory_records == []


def test_fallback_classifies_concrete_docs_page_as_useful(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-useful-doc-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-useful-doc"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-doc",
        "url": "https://docs.python.org/3/library/asyncio.html",
        "domain": "docs.python.org",
        "content_preview": (
            "asyncio is a Python library to write concurrent code using async and "
            "await syntax. It is useful for autonomous agents, runtime orchestration, "
            "network clients, testing, and system improvement architecture."
        ),
        "content_hash": "hash-asyncio",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-doc",
        "provenance": {
            "exploration_run_id": "run-useful-doc",
            "source_score": 0.85,
            "quality_score": 0.85,
            "system_relevance_score": 0.90,
            "authority_score": 0.96,
            "external_write_performed": False,
            "real_execution_enabled": False,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-useful",
            prompt_h="prompt",
            model_name="noop",
            fallback_reason="test",
        )

    classified, _ = asyncio.run(run())

    assert classified[0]["classification"] == "USEFUL"

    memory_records = [
        record
        for record in agent.crdt.records
        if isinstance(record, dict)
        and record.get("type") == "memory_record"
        and record.get("record_kind") == "explorer_useful_evidence"
    ]
    assert len(memory_records) == 1