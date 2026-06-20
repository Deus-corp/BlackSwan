from __future__ import annotations

from src.swarms.explorer.meta_agent_core.public_search_templates import (
    build_safe_public_search_candidates,
    public_search_template_to_candidate,
)
from src.swarms.explorer.meta_agent_core.source_plan import (
    build_research_source_plan,
)
from src.swarms.explorer.node import ExplorerNode


def _safe_template_candidate() -> dict:
    return public_search_template_to_candidate(
        {
            "kind": "research_papers",
            "site": "arxiv.org",
            "query": "site:arxiv.org autonomous agents memory systems",
            "rationale": "Find public arXiv papers.",
        },
        goal="autonomous agents memory systems",
        existing_score=0.70,
    )


def test_safe_public_search_candidate_has_priority_metadata() -> None:
    candidate = _safe_template_candidate()

    assert candidate["safe_public_search_template"] is True
    assert candidate["source_priority_class"] == "safe_public_search_template"
    assert candidate["planner_priority"] == 0.70
    assert candidate["source_score"] == 0.70
    assert candidate["quality_score"] == 0.70
    assert candidate["preferred_evidence_target"] is False
    assert candidate["external_write_performed"] is False
    assert candidate["real_execution_enabled"] is False


def test_safe_public_search_candidates_use_calibrated_score() -> None:
    candidates = build_safe_public_search_candidates(
        "autonomous agents memory systems",
        limit=4,
        existing_score=0.71,
    )

    assert candidates
    assert all(candidate["planner_priority"] == 0.71 for candidate in candidates)
    assert all(candidate["source_score"] == 0.71 for candidate in candidates)
    assert all(
        candidate["source_priority_class"] == "safe_public_search_template"
        for candidate in candidates
    )


def test_source_plan_includes_safe_templates_with_priority_metadata() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=["https://docs.python.org/3/"],
        adapters=["github", "arxiv", "search", "sitemap"],
        limit=24,
    )

    safe_templates = [
        candidate
        for candidate in plan["candidates"]
        if candidate.get("safe_public_search_template") is True
    ]

    assert safe_templates
    assert all(
        candidate.get("source_priority_class") == "safe_public_search_template"
        for candidate in safe_templates
    )
    assert all(candidate.get("planner_priority", 0.0) >= 0.70 for candidate in safe_templates)


def test_node_ranks_safe_template_above_generic_search_when_budget_allows(
    tmp_path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-safe-template-ranking-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 2
    node.max_targets_per_domain_per_tick = 2

    safe_url = (
        "https://duckduckgo.com/html?"
        "q=site%3Aarxiv.org+autonomous+agents+memory+systems"
    )
    generic_url = "https://duckduckgo.com/html?q=autonomous+agents+memory+systems"

    node._target_context_by_url[safe_url] = {
        "source_adapter": "search",
        "source_kind": "public_search_html",
        "discovery_method": "safe_public_search_query_template",
        "safe_public_search_template": True,
        "search_query": "site:arxiv.org autonomous agents memory systems",
        "search_query_site": "arxiv.org",
        "search_query_template_kind": "research_papers",
        "search_query_rationale": "Find public arXiv papers.",
        "source_priority_class": "safe_public_search_template",
        "planner_priority": 0.70,
        "source_score": 0.70,
        "quality_score": 0.70,
        "system_relevance_score": 0.70,
    }
    node._target_context_by_url[generic_url] = {
        "source_adapter": "search",
        "source_kind": "public_search_html",
        "discovery_method": "public_search",
        "source_score": 0.65,
        "quality_score": 0.65,
        "system_relevance_score": 0.65,
    }

    selected = node._select_domain_aware_targets([generic_url, safe_url])

    assert selected[0] == safe_url
    assert safe_url in selected
    assert node._safe_public_search_templates_selected == 1


def test_node_keeps_curated_evidence_above_safe_template_under_tight_budget(
    tmp_path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-safe-template-evidence-priority-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 1
    node.max_targets_per_domain_per_tick = 2

    evidence_url = "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
    safe_url = (
        "https://duckduckgo.com/html?"
        "q=site%3Aarxiv.org+autonomous+agents+memory+systems"
    )

    node._target_context_by_url[evidence_url] = {
        "source_adapter": "evidence",
        "source_kind": "curated_evidence_url",
        "preferred_evidence_target": True,
        "source_score": 0.80,
        "quality_score": 0.80,
        "system_relevance_score": 0.90,
    }
    node._target_context_by_url[safe_url] = {
        "source_adapter": "search",
        "source_kind": "public_search_html",
        "discovery_method": "safe_public_search_query_template",
        "safe_public_search_template": True,
        "search_query": "site:arxiv.org autonomous agents memory systems",
        "search_query_site": "arxiv.org",
        "search_query_template_kind": "research_papers",
        "search_query_rationale": "Find public arXiv papers.",
        "source_priority_class": "safe_public_search_template",
        "planner_priority": 0.70,
        "source_score": 0.70,
        "quality_score": 0.70,
        "system_relevance_score": 0.70,
    }

    selected = node._select_domain_aware_targets([safe_url, evidence_url])

    assert selected == [evidence_url]
    assert node._safe_public_search_templates_seen == 1
    assert node._safe_public_search_templates_selected == 0