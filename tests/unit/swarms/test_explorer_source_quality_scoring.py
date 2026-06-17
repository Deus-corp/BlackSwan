from pathlib import Path

from src.swarms.explorer.meta_agent_core.source_adapters import (
    build_source_adapter_targets,
)
from src.swarms.explorer.meta_agent_core.source_scoring import score_source_target
from src.swarms.explorer.node import ExplorerNode


def test_source_scoring_prefers_authoritative_system_relevant_sources() -> None:
    python_docs = score_source_target(
        "https://docs.python.org/3/library/asyncio.html",
        source_adapter="sitemap",
        source_kind="sitemap_xml",
        discovery_method="sitemap_candidate",
        goal="python async runtime autonomous agents",
        existing_score=0.85,
    )
    random_blog = score_source_target(
        "https://unknown-example.test/old/post-2014.html",
        source_adapter="search",
        source_kind="public_search_html",
        discovery_method="public_search_query",
        goal="python async runtime autonomous agents",
        existing_score=0.50,
    )

    assert python_docs["authority_score"] > random_blog["authority_score"]
    assert python_docs["system_relevance_score"] > random_blog["system_relevance_score"]
    assert python_docs["source_score"] > random_blog["source_score"]


def test_source_adapter_targets_include_quality_scores() -> None:
    targets = build_source_adapter_targets(
        goal="autonomous agents memory systems",
        adapters=["github", "arxiv", "sitemap"],
        seed_urls=["https://docs.python.org/3/"],
        limit=20,
    )

    assert targets
    assert all("source_score" in item for item in targets)
    assert all("quality_score" in item for item in targets)
    assert all("authority_score" in item for item in targets)
    assert all("freshness_score" in item for item in targets)
    assert all("system_relevance_score" in item for item in targets)


def test_explorer_node_preserves_quality_scores_in_target_context(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-quality-score-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    accepted = node._ingest_direct_targets(
        [
            {
                "url": "https://docs.python.org/3/library/asyncio.html",
                "source_adapter": "sitemap",
                "source_kind": "sitemap_xml",
                "discovery_method": "sitemap_candidate",
                "score": 0.85,
                "goal": "python async runtime autonomous agents",
                "exploration_run_id": "run-quality",
            }
        ],
        event_gid="seed-quality",
        source_gids=["seed-quality"],
        provenance={
            "goal": "python async runtime autonomous agents",
            "exploration_run_id": "run-quality",
        },
    )

    assert accepted == ["https://docs.python.org/3/library/asyncio.html"]

    context = node._target_context_by_url[
        "https://docs.python.org/3/library/asyncio.html"
    ]

    assert context["source_score"] > 0.0
    assert context["quality_score"] > 0.0
    assert context["authority_score"] > 0.0
    assert context["system_relevance_score"] > 0.0
    assert context["exploration_run_id"] == "run-quality"