from pathlib import Path

from src.swarms.explorer.node import ExplorerNode


def test_node_boosts_goal_aligned_discovered_links(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-anchor-goal-ranking-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    goal = "autonomous agents memory systems"

    html = """
    <html>
      <body>
        <a href="https://realpython.com/python-context-engineering-ai/">
          Context engineering for AI agents with memory
        </a>
        <a href="https://realpython.com/python-news-june-2026/">
          Python News June 2026
        </a>
      </body>
    </html>
    """

    targets = node._extract_discovered_targets(
        html,
        base_url="https://realpython.com/",
        parent_depth=0,
        goal=goal,
    )

    urls = [target["url"] for target in targets]

    assert "https://realpython.com/python-context-engineering-ai" in urls
    assert "https://realpython.com/python-news-june-2026" in urls

    context_target = next(
        target
        for target in targets
        if target["url"] == "https://realpython.com/python-context-engineering-ai"
    )
    news_target = next(
        target
        for target in targets
        if target["url"] == "https://realpython.com/python-news-june-2026"
    )

    assert context_target["goal_alignment_score"] > news_target[
        "goal_alignment_score"
    ]
    assert "agents" in context_target["goal_terms_matched"]
    assert "memory" in context_target["goal_terms_matched"]
    assert context_target["source_score"] >= news_target["source_score"]


def test_node_preserves_goal_metadata_when_ingesting_discovered_target(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-anchor-goal-ingest-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    accepted = node._ingest_direct_targets(
        [
            {
                "url": "https://realpython.com/python-context-engineering-ai",
                "anchor_text": "Context engineering for AI agents with memory",
                "goal": "autonomous agents memory systems",
                "research_goal": "autonomous agents memory systems",
                "research_goal_text": "autonomous agents memory systems",
                "goal_alignment_score": 0.28,
                "goal_terms_matched": ["agents", "memory"],
                "source_adapter": "html_link",
                "source_kind": "html_link",
                "score": 0.9,
                "exploration_run_id": "run-anchor-goal",
            }
        ],
        event_gid="seed-anchor-goal",
        source_gids=["seed-anchor-goal"],
        provenance={
            "exploration_run_id": "run-anchor-goal",
            "goal": "autonomous agents memory systems",
        },
    )

    assert accepted == ["https://realpython.com/python-context-engineering-ai"]

    context = node._target_context_by_url[
        "https://realpython.com/python-context-engineering-ai"
    ]

    assert context["goal"] == "autonomous agents memory systems"
    assert context["anchor_text"] == "Context engineering for AI agents with memory"
    assert context["goal_alignment_score"] == 0.28
    assert context["goal_terms_matched"] == ["agents", "memory"]