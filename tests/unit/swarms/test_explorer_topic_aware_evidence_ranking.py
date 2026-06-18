from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.node import ExplorerNode


def test_node_prefers_topic_aligned_realpython_article_over_category(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-topic-ranking-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    html = """
    <html>
      <body>
        <a href="https://realpython.com/tutorials/data-viz/">category</a>
        <a href="https://realpython.com/python-context-engineering-ai/">article</a>
        <a href="https://support.github.com/">support</a>
        <a href="https://skills.github.com/">skills</a>
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
    assert "https://realpython.com/tutorials/data-viz" not in urls
    assert "https://support.github.com" not in urls
    assert "https://skills.github.com" not in urls

    article = next(
        item
        for item in targets
        if item["url"] == "https://realpython.com/python-context-engineering-ai"
    )
    assert article["preferred_evidence_target"] is True
    assert article["source_score"] > 0.0


def test_meta_treats_realpython_article_as_concrete_but_category_as_low_value(
    tmp_path: Path,
) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-topic-ranking-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    article = {
        "url": "https://realpython.com/python-context-engineering-ai",
        "domain": "realpython.com",
        "content_preview": (
            "Context engineering for AI agents with Python memory retrieval "
            "orchestration runtime and autonomous agent workflows."
        ),
        "content_hash": "hash-article",
        "fetch_status": "ok",
        "provenance": {},
    }
    category = {
        "url": "https://realpython.com/tutorials/data-viz",
        "domain": "realpython.com",
        "content_preview": "Real Python category page.",
        "content_hash": "hash-category",
        "fetch_status": "ok",
        "provenance": {},
    }

    article_signals = agent._fallback_quality_signals(article)

    assert agent._is_concrete_evidence_page(article, article_signals) is True
    assert article_signals["concrete_evidence_page"] is True

    assert agent._is_low_value_target_url(
        "https://realpython.com/tutorials/data-viz"
    )
    assert agent._is_low_value_target_url("https://support.github.com/")
    assert agent._is_low_value_target_url("https://skills.github.com/")