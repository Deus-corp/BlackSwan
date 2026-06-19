from pathlib import Path

from src.swarms.explorer.node import ExplorerNode


def test_node_preserves_discovered_target_metadata_by_url_on_ingest(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-discovered-metadata-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    url = "https://github.blog/changelog/2026-06-18-copilot-code-review-agents-md-support-and-ui-improvements"

    accepted = node._ingest_direct_targets(
        [url],
        event_gid="targets-discovered-1",
        source_gids=["finding-1"],
        provenance={
            "exploration_run_id": "run-discovered-metadata",
            "research_goal_id": "run-discovered-metadata",
            "discovered_target_metadata_by_url": {
                url: {
                    "source_adapter": "evidence",
                    "source_kind": "curated_evidence_url",
                    "discovery_method": "html_link_extraction",
                    "preferred_evidence_target": True,
                    "goal_alignment_score": 0.14,
                    "goal_terms_matched": ["agent", "agents", "improvement"],
                    "source_score": 0.75,
                    "quality_score": 0.75,
                    "system_relevance_score": 0.75,
                    "authority_score": 0.70,
                    "freshness_score": 0.90,
                    "evidence_category": "ai_code_assistance",
                    "topic_tags": ["agents", "code_improvement"],
                    "content_expectation": "AI code review agent update evidence",
                    "research_goal": "autonomous agents memory systems",
                    "target_depth": 1,
                }
            },
        },
    )

    assert accepted == [url]

    context = node._target_context_by_url[url]

    assert context["source_adapter"] == "evidence"
    assert context["source_kind"] == "curated_evidence_url"
    assert context["preferred_evidence_target"] is True
    assert context["goal_alignment_score"] == 0.14
    assert context["source_score"] == 0.75
    assert context["system_relevance_score"] == 0.75
    assert context["evidence_category"] == "ai_code_assistance"
    assert context["topic_tags"] == ["agents", "code_improvement"]
    assert context["content_expectation"] == "AI code review agent update evidence"
    assert context["target_depth"] == 1


def test_node_builds_discovered_target_metadata_by_url(tmp_path: Path) -> None:
    node = ExplorerNode(
        node_id="exp-node-discovered-metadata-map-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    targets = [
        {
            "url": "https://docs.python.org/3/library/asyncio.html",
            "source_adapter": "evidence",
            "source_kind": "curated_evidence_url",
            "preferred_evidence_target": True,
            "source_score": 0.88,
        },
        {
            "url": "https://githubstatus.com/",
            "source_adapter": "frontier",
            "preferred_evidence_target": False,
        },
    ]

    metadata = node._discovered_target_metadata_by_url(targets)

    assert metadata["https://docs.python.org/3/library/asyncio.html"][
        "source_adapter"
    ] == "evidence"
    assert metadata["https://docs.python.org/3/library/asyncio.html"][
        "preferred_evidence_target"
    ] is True
    assert "url" not in metadata["https://docs.python.org/3/library/asyncio.html"]