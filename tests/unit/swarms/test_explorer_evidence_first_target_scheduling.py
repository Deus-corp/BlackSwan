from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.node import ExplorerNode


def test_node_blocks_runtime_sink_domains_from_discovery(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-sink-filter-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    bad_urls = [
        "https://realpython.workable.com/",
        "https://apply.workable.com/realpython/",
        "https://workablehr.s3.amazonaws.com/",
        "https://workable-application-form.s3.amazonaws.com/",
        "https://www.youtube.com/realpython",
        "https://developers.google.com/youtube",
        "https://planetpython.org/",
        "https://wiki.python.org/moin/PythonEventsCalendar",
        "https://realpython.com/security",
        "https://realpython.com/books",
        "https://github.com/search?q=autonomous+agents+memory+systems+is%3Aprivate&type=repositories",
    ]

    assert all(node._is_low_value_discovered_target(url) for url in bad_urls)


def test_meta_blocks_runtime_sink_domains_from_suggestions(tmp_path: Path) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-sink-filter-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    bad_urls = [
        "https://realpython.workable.com/",
        "https://apply.workable.com/realpython/",
        "https://workablehr.s3.amazonaws.com/",
        "https://workable-application-form.s3.amazonaws.com/",
        "https://www.youtube.com/realpython",
        "https://developers.google.com/youtube",
        "https://planetpython.org/",
        "https://wiki.python.org/moin/PythonEventsCalendar",
        "https://realpython.com/security",
        "https://realpython.com/books",
        "https://github.com/search?q=autonomous+agents+memory+systems+is%3Aprivate&type=repositories",
    ]

    assert all(agent._is_low_value_target_url(url) for url in bad_urls)


def test_node_prioritizes_goal_aligned_evidence_target(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-evidence-first-priority-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    evidence_url = "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
    neutral_url = "https://realpython.com/python-news-june-2026"

    node._target_context_by_url[evidence_url] = {
        "preferred_evidence_target": True,
        "goal_alignment_score": 0.28,
        "source_score": 0.75,
        "source_adapter": "html_link",
    }
    node._target_context_by_url[neutral_url] = {
        "preferred_evidence_target": False,
        "goal_alignment_score": 0.0,
        "source_score": 0.90,
        "source_adapter": "html_link",
    }

    selected = node._select_domain_aware_targets([neutral_url, evidence_url])

    assert selected
    assert selected[0] == evidence_url