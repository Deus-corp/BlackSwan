from src.swarms.explorer.meta_agent_core.source_plan import (
    build_research_source_plan,
    build_research_source_plan_targets,
    goal_terms,
    normalize_plan_url,
)


def test_goal_terms_extracts_stable_research_terms() -> None:
    terms = goal_terms("autonomous agents memory systems")

    assert "autonomous" in terms
    assert "agents" in terms
    assert "memory" in terms
    assert "systems" not in terms


def test_research_source_plan_builds_ranked_network_read_candidates() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=["https://docs.python.org/3/"],
        adapters=["github", "arxiv", "search", "sitemap"],
        limit=12,
    )

    assert plan["type"] == "explorer_research_source_plan"
    assert plan["execution_risk_tier"] == "network_read"
    assert plan["external_write_performed"] is False
    assert plan["real_execution_enabled"] is False
    assert plan["candidate_count"] > 0

    candidates = plan["candidates"]
    urls = [candidate["url"] for candidate in candidates]

    assert "https://docs.python.org/3" in urls
    assert any(
        candidate["source_adapter"] == "github"
        and candidate["source_kind"] == "github_repository_search"
        for candidate in candidates
    )
    assert any(
        candidate["source_adapter"] == "arxiv"
        and candidate["source_kind"] == "arxiv_api_query"
        for candidate in candidates
    )
    assert any(
        candidate["source_adapter"] == "search"
        and candidate["source_kind"] == "public_search_html"
        for candidate in candidates
    )

    assert all(candidate["network_read_candidate"] is True for candidate in candidates)
    assert all(
        candidate["external_write_performed"] is False
        for candidate in candidates
    )
    assert all(candidate["real_execution_enabled"] is False for candidate in candidates)

    ranks = [candidate["plan_rank"] for candidate in candidates]
    assert ranks == list(range(1, len(candidates) + 1))


def test_research_source_plan_emits_preferred_evidence_candidates() -> None:
    targets = build_research_source_plan_targets(
        goal="autonomous agents memory systems",
        adapters=["github", "arxiv"],
        limit=10,
    )

    evidence_targets = [
        target
        for target in targets
        if target.get("preferred_evidence_target")
    ]

    assert evidence_targets

    top = evidence_targets[0]
    assert top["source_adapter"] in {"evidence", "seed"}
    assert top["source_score"] >= 0.70
    assert top["goal_alignment_score"] > 0.0
    assert top["goal_terms_matched"]


def test_research_source_plan_dedupes_normalized_urls() -> None:
    assert normalize_plan_url("https://docs.python.org/3/") == (
        "https://docs.python.org/3"
    )

    targets = build_research_source_plan_targets(
        goal="python async runtime agents",
        seed_urls=[
            "https://docs.python.org/3/",
            "https://docs.python.org/3",
        ],
        adapters=["sitemap"],
        limit=20,
    )

    urls = [target["url"] for target in targets]
    assert urls.count("https://docs.python.org/3") == 1