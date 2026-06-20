from __future__ import annotations

from src.swarms.explorer.meta_agent_core.public_search_templates import (
    build_safe_public_search_template_plan,
    summarize_safe_public_search_templates,
)
from src.swarms.explorer.meta_agent_core.source_plan import (
    build_research_source_plan,
)


def test_safe_public_search_template_audit_counts_templates() -> None:
    plan = build_safe_public_search_template_plan(
        "autonomous agents memory systems",
        limit=8,
    )

    templates = plan["templates"]
    audit = plan["audit"]

    assert templates
    assert audit["type"] == "safe_public_search_template_audit"
    assert audit["generated_count"] >= len(templates)
    assert audit["accepted_count"] == len(templates)
    assert audit["rejected_count"] >= 0
    assert audit["unsafe_rejected_count"] == 0
    assert audit["external_write_performed"] is False
    assert audit["real_execution_enabled"] is False


def test_safe_public_search_template_audit_groups_by_site_and_kind() -> None:
    audit = build_safe_public_search_template_plan(
        "autonomous agents memory systems",
        limit=8,
    )["audit"]

    assert audit["by_site"]["arxiv.org"] >= 1
    assert audit["by_site"]["github.blog"] >= 1
    assert audit["by_kind"]["research_papers"] >= 1
    assert audit["by_kind"]["official_docs"] >= 1
    assert audit["queries"]


def test_unsafe_goal_produces_empty_template_plan_with_unsafe_audit() -> None:
    plan = build_safe_public_search_template_plan(
        "password token secret leak",
        limit=8,
    )

    assert plan["templates"] == []

    audit = plan["audit"]
    assert audit["accepted_count"] == 0
    assert audit["generated_count"] == 0
    assert audit["unsafe_rejected_count"] == 1
    assert audit["external_write_performed"] is False
    assert audit["real_execution_enabled"] is False


def test_summarize_safe_public_search_templates_rejects_invalid_items() -> None:
    audit = summarize_safe_public_search_templates(
        [
            {
                "kind": "research_papers",
                "site": "arxiv.org",
                "query": "site:arxiv.org autonomous agents memory",
                "rationale": "ok",
            },
            {
                "kind": "official_docs",
                "site": "pastebin.com",
                "query": "site:pastebin.com autonomous agents memory",
                "rationale": "bad",
            },
        ],
        generated_count=2,
        rejected_count=1,
    )

    assert audit["generated_count"] == 2
    assert audit["accepted_count"] == 1
    assert audit["rejected_count"] == 1
    assert audit["by_site"] == {"arxiv.org": 1}


def test_source_plan_includes_safe_public_search_template_audit_when_search_enabled() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=["https://docs.python.org/3/"],
        adapters=["github", "arxiv", "search", "sitemap"],
        limit=24,
    )

    audit = plan["safe_public_search_template_audit"]

    assert audit["type"] == "safe_public_search_template_audit"
    assert audit["accepted_count"] > 0
    assert audit["unsafe_rejected_count"] == 0
    assert audit["by_site"]
    assert audit["by_kind"]

    safe_candidates = [
        candidate
        for candidate in plan["candidates"]
        if candidate.get("safe_public_search_template") is True
    ]

    assert len(safe_candidates) == audit["accepted_count"]


def test_source_plan_omits_safe_public_search_template_audit_without_search_adapter() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=["https://docs.python.org/3/"],
        adapters=["github", "arxiv", "sitemap"],
        limit=24,
    )

    assert plan.get("safe_public_search_template_audit", {}) == {}

    assert not any(
        candidate.get("safe_public_search_template") is True
        for candidate in plan["candidates"]
    )


def test_source_plan_audit_safety_flags_false() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=[],
        adapters=["search"],
        limit=16,
    )

    audit = plan["safe_public_search_template_audit"]

    assert audit["external_write_performed"] is False
    assert audit["real_execution_enabled"] is False
    assert audit["production_paths_mutated"] is False
    assert audit["production_secrets_accessed"] is False