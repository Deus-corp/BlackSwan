from pathlib import Path

from src.swarms.explorer.node import ExplorerNode


def test_node_prioritizes_planner_evidence_targets_within_tick_budget(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-evidence-budget-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.targets_per_tick = 5

    evidence_urls = [
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai",
        "https://docs.python.org/3/library/asyncio.html",
        "https://docs.python.org/3/library/sqlite3.html",
        "https://docs.github.com/en/search-github/searching-on-github/searching-code",
    ]
    other_urls = [
        "https://github.com/search?q=autonomous+agents+memory+systems&type=repositories",
        "https://github.com/search?q=autonomous+agents+memory+systems&type=code",
        "https://duckduckgo.com/html?q=autonomous+agents+memory+systems",
        "https://docs.python.org/3",
    ]

    for index, url in enumerate(evidence_urls):
        node._target_context_by_url[url] = {
            "source_adapter": "evidence",
            "source_kind": "curated_evidence_url",
            "preferred_evidence_target": True,
            "source_score": 0.90 - index * 0.02,
            "goal_alignment_score": 0.20,
        }

    for url in other_urls:
        node._target_context_by_url[url] = {
            "source_adapter": "github",
            "source_kind": "github_repository_search",
            "source_score": 0.95,
            "goal_alignment_score": 0.30,
        }

    selected = node._select_domain_aware_targets([*other_urls, *evidence_urls])

    assert len(selected) == 5
    assert selected[0] in evidence_urls

    selected_evidence = [url for url in selected if url in evidence_urls]
    assert len(selected_evidence) >= 3

    assert "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai" in selected