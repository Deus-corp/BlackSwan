from pathlib import Path

from src.swarms.explorer.meta_agent_core.source_adapters import (
    build_source_adapter_targets,
)
from src.swarms.explorer.node import ExplorerNode


def test_source_adapters_build_goal_and_seed_targets() -> None:
    targets = build_source_adapter_targets(
        goal="autonomous agents memory systems",
        adapters=["rss", "sitemap", "github", "arxiv", "search"],
        seed_urls=["https://docs.python.org/3/"],
        limit=20,
    )

    urls = [item["url"] for item in targets]
    adapters = {item["source_adapter"] for item in targets}

    assert "rss" in adapters
    assert "sitemap" in adapters
    assert "github" in adapters
    assert "arxiv" in adapters
    assert "search" in adapters

    assert any(url.endswith("/sitemap.xml") for url in urls)
    assert any("github.com/search" in url for url in urls)
    assert any("export.arxiv.org/api/query" in url for url in urls)
    assert all(item["execution_risk_tier"] == "network_read" for item in targets)
    assert all(item["external_write_performed"] is False for item in targets)
    assert all(item["real_execution_enabled"] is False for item in targets)


def test_explorer_node_extracts_sitemap_rss_and_atom_links(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-source-adapter-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    content = """
    <urlset>
      <url><loc>https://example.com/docs/</loc></url>
      <url><loc>https://example.com/blog/post</loc></url>
    </urlset>
    <rss>
      <channel>
        <item><link>https://example.com/rss/item</link></item>
      </channel>
    </rss>
    <feed>
      <entry>
        <id>https://arxiv.org/abs/2501.00001</id>
        <link href="https://arxiv.org/pdf/2501.00001" />
      </entry>
    </feed>
    """

    targets = node._extract_discovered_targets(
        content,
        base_url="https://example.com/",
        parent_depth=0,
    )
    urls = [item["url"] for item in targets]

    assert "https://example.com/docs" in urls
    assert "https://example.com/blog/post" in urls
    assert "https://example.com/rss/item" in urls
    assert "https://arxiv.org/abs/2501.00001" in urls
    assert all(item["execution_risk_tier"] == "network_read" for item in targets)
    assert all(item["external_write_performed"] is False for item in targets)
    assert all(item["real_execution_enabled"] is False for item in targets)