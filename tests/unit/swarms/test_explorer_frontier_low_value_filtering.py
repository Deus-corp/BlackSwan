from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.meta_agent_core.frontier_filters import (
    is_low_value_frontier_url,
)
from src.swarms.explorer.node import ExplorerNode


def test_shared_frontier_filter_rejects_low_value_urls() -> None:
    low_value = [
        "https://githubstatus.com/",
        "https://www.githubstatus.com",
        "https://au.githubstatus.com/",
        "https://subscriptions.statuspage.io/slack_authentication/kickoff?page_code=x",
        "https://slack.com/oauth/v2/authorize?client_id=1&redirect_uri=https%3A%2F%2Fexample.com",
        "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
        "https://support.github.com/request/landing",
        "https://realpython.com/account/login/?next=/",
        "https://realpython.com/community/",
        "https://donate.python.org/",
    ]

    for url in low_value:
        assert is_low_value_frontier_url(url), url


def test_shared_frontier_filter_allows_evidence_urls() -> None:
    useful = [
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/",
        "https://docs.python.org/3/library/asyncio.html",
        "https://docs.github.com/en/search-github/searching-on-github/searching-code",
        "https://github.blog/ai-and-ml/llms/",
        "https://github.com/search?q=autonomous+agents+memory+systems&type=repositories",
    ]

    for url in useful:
        assert not is_low_value_frontier_url(url), url


def test_node_filters_low_value_discovered_targets(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-low-value-frontier-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    html = """
    <html>
      <body>
        <a href="https://githubstatus.com/">status</a>
        <a href="https://subscriptions.statuspage.io/slack_authentication/kickoff?page_code=x">slack</a>
        <a href="https://docs.python.org/3/library/asyncio.html">asyncio</a>
        <a href="https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/">course</a>
      </body>
    </html>
    """

    targets = node._extract_discovered_targets(
        html,
        base_url="https://docs.python.org/3/",
        parent_depth=0,
        goal="autonomous agents memory systems",
    )

    urls = [target["url"] for target in targets]

    assert "https://docs.python.org/3/library/asyncio.html" in urls
    assert (
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
        in urls
    )
    assert "https://githubstatus.com" not in urls
    assert not any("slack_authentication" in url for url in urls)


def test_meta_filters_low_value_suggested_targets(tmp_path: Path) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-low-value-frontier-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    assert agent._is_low_value_target_url("https://githubstatus.com/")
    assert agent._is_low_value_target_url(
        "https://subscriptions.statuspage.io/slack_authentication/kickoff?page_code=x"
    )
    assert agent._is_low_value_target_url(
        "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"
    )

    assert not agent._is_low_value_target_url(
        "https://docs.python.org/3/library/asyncio.html"
    )