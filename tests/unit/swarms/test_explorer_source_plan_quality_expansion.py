from src.swarms.explorer.meta_agent_core.source_plan import (
    build_research_source_plan_targets,
    goal_profile_tags,
    goal_terms,
)


def test_goal_profile_tags_detects_agents_memory_orchestration() -> None:
    terms = goal_terms("autonomous agents memory systems async runtime")

    tags = goal_profile_tags(terms)

    assert "agents" in tags
    assert "memory" in tags
    assert "orchestration" in tags


def test_source_plan_expands_curated_evidence_categories() -> None:
    targets = build_research_source_plan_targets(
        goal="autonomous agents memory systems",
        adapters=["github", "arxiv", "search", "sitemap"],
        limit=20,
    )

    evidence = [
        target
        for target in targets
        if target.get("source_adapter") == "evidence"
        and target.get("preferred_evidence_target") is True
    ]

    categories = {
        str(target.get("evidence_category") or "")
        for target in evidence
    }

    assert len(evidence) >= 6
    assert "python_llm_agents" in categories
    assert "python_async_runtime" in categories
    assert "python_persistence" in categories
    assert "github_code_search" in categories

    assert all(target.get("content_expectation") for target in evidence)
    assert all(target.get("topic_tags") for target in evidence)
    assert all(target.get("network_read_candidate") is True for target in evidence)
    assert all(target.get("external_write_performed") is False for target in evidence)
    assert all(target.get("real_execution_enabled") is False for target in evidence)


def test_source_plan_quality_expansion_keeps_ranked_evidence_first() -> None:
    targets = build_research_source_plan_targets(
        goal="autonomous agents memory systems",
        adapters=["github", "arxiv"],
        limit=10,
    )

    assert targets
    assert targets[0].get("preferred_evidence_target") is True
    assert float(targets[0].get("source_score", 0.0)) >= 0.70