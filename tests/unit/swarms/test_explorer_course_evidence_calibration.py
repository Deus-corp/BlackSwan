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


def test_node_allows_topic_aligned_course_but_filters_support_sinks(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-course-evidence-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    html = """
    <html>
      <body>
        <a href="https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/">
          Building Type-Safe LLM Agents With Pydantic AI
        </a>
        <a href="https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/continue">
          Continue Course
        </a>
        <a href="https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/discussion">
          Discussion
        </a>
        <a href="https://support.realpython.com/category/20-video-player">Support</a>
        <a href="https://www.helpscout.com/docs-refer?co=Real+Python">Help Scout</a>
      </body>
    </html>
    """

    targets = node._extract_discovered_targets(
        html,
        base_url="https://realpython.com/",
        parent_depth=0,
        goal="autonomous agents memory systems",
    )

    urls = [target["url"] for target in targets]

    assert (
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
        in urls
    )
    assert (
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/continue"
        not in urls
    )
    assert (
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/discussion"
        not in urls
    )
    assert "https://support.realpython.com/category/20-video-player" not in urls
    assert "https://www.helpscout.com/docs-refer?co=Real+Python" not in urls


def test_meta_classifies_topic_aligned_course_as_useful(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-course-evidence-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )
    agent.crdt = _FakeCRDT()
    agent.active_exploration_run_id = "run-course-evidence"

    finding = {
        "type": "explorer_finding",
        "source_gid": "source-course",
        "url": "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "domain": "realpython.com",
        "content_preview": (
            "Building type-safe LLM agents with Pydantic AI explains Python agent "
            "workflows, runtime orchestration, structured outputs, memory-aware "
            "systems, validation, and autonomous AI application architecture."
        ),
        "content_hash": "hash-course-pydantic-ai",
        "fetch_status": "ok",
        "classification": "unclassified",
        "confidence": 0.0,
        "reason": "network read completed",
        "timestamp": 1.0,
        "gid": "finding-course",
        "provenance": {
            "exploration_run_id": "run-course-evidence",
            "research_goal_id": "run-course-evidence",
            "external_write_performed": False,
            "real_execution_enabled": False,
            "discovered_target_count": 12,
        },
    }

    async def run():
        return await agent._fallback_classify_findings(
            [finding],
            batch_gid="batch-course",
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