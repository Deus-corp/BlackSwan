from pathlib import Path

from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.node import ExplorerNode


def test_explorer_node_filters_low_value_discovered_targets(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-evidence-frontier-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    html = """
    <html>
      <body>
        <a href="https://docs.python.org/3/library/asyncio.html">asyncio</a>
        <a href="https://peps.python.org/pep-0008/">PEP 8</a>
        <a href="https://www.googletagmanager.com/gtag/js?id=G-123">tracking</a>
        <a href="https://realpython.com/account/login/?next=/">login</a>
        <a href="https://donate.python.org/">donate</a>
        <a href="https://iana.org/domains/example">example domains</a>
      </body>
    </html>
    """

    targets = node._extract_discovered_targets(
        html,
        base_url="https://docs.python.org/3/",
        parent_depth=0,
    )
    urls = [item["url"] for item in targets]

    assert "https://docs.python.org/3/library/asyncio.html" in urls
    assert "https://peps.python.org/pep-0008" in urls
    assert "https://www.googletagmanager.com/gtag/js?id=G-123" not in urls
    assert "https://realpython.com/account/login?next=/" not in urls
    assert "https://donate.python.org" not in urls
    assert "https://iana.org/domains/example" not in urls

    asyncio_target = next(
        item for item in targets
        if item["url"] == "https://docs.python.org/3/library/asyncio.html"
    )
    assert asyncio_target["preferred_evidence_target"] is True
    assert asyncio_target["source_score"] > 0.0


def test_explorer_meta_filters_low_value_suggested_targets(tmp_path: Path) -> None:
    agent = ExplorerMetaAgent(
        node_id="exp-meta-evidence-frontier-test",
        memory_db=tmp_path / "explorer_meta.sqlite3",
    )

    assert agent._is_low_value_target_url(
        "https://www.googletagmanager.com/gtag/js?id=G-123"
    )
    assert agent._is_low_value_target_url(
        "https://realpython.com/account/login/?next=/"
    )
    assert agent._is_low_value_target_url("https://donate.python.org/")
    assert agent._is_low_value_target_url("https://iana.org/domains/example")

    assert not agent._is_low_value_target_url(
        "https://docs.python.org/3/library/asyncio.html"
    )
    assert not agent._is_low_value_target_url("https://peps.python.org/pep-0008/")