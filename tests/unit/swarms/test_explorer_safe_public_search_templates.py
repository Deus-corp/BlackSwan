from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from src.swarms.explorer.meta_agent_core.public_search_templates import (
    build_safe_public_search_candidates,
    build_safe_public_search_templates,
    public_search_template_to_candidate,
    validate_public_search_template,
)
from src.swarms.explorer.meta_agent_core.source_plan import (
    build_research_source_plan,
)


def test_builds_safe_public_search_templates_for_goal() -> None:
    templates = build_safe_public_search_templates(
        "autonomous agents memory systems",
        limit=12,
    )

    assert templates
    assert all(template["safe_public_search_template"] is True for template in templates)
    assert any(template["site"] == "arxiv.org" for template in templates)
    assert any(template["site"] == "docs.github.com" for template in templates)
    assert any(template["site"] == "github.blog" for template in templates)
    assert all("site:" in template["query"] for template in templates)


def test_safe_public_search_template_rejects_unsafe_terms() -> None:
    errors = validate_public_search_template(
        {
            "kind": "official_docs",
            "site": "github.com",
            "query": "site:github.com password token secret leak",
            "rationale": "bad",
        }
    )

    assert "query contains unsafe public search term" in errors


def test_safe_public_search_template_rejects_unapproved_site() -> None:
    errors = validate_public_search_template(
        {
            "kind": "official_docs",
            "site": "pastebin.com",
            "query": "site:pastebin.com autonomous agents memory",
            "rationale": "bad",
        }
    )

    assert any("unsupported public search site" in error for error in errors)


def test_public_search_template_to_candidate_uses_public_search_html() -> None:
    template = {
        "kind": "research_papers",
        "site": "arxiv.org",
        "query": "site:arxiv.org autonomous agents memory systems",
        "rationale": "Find public arXiv papers.",
    }

    candidate = public_search_template_to_candidate(
        template,
        goal="autonomous agents memory systems",
    )

    assert candidate["source_adapter"] == "search"
    assert candidate["source_kind"] == "public_search_html"
    assert candidate["discovery_method"] == "safe_public_search_query_template"
    assert candidate["safe_public_search_template"] is True
    assert candidate["network_read_candidate"] is True
    assert candidate["external_write_performed"] is False
    assert candidate["real_execution_enabled"] is False
    assert candidate["search_query_site"] == "arxiv.org"

    parsed = urlparse(candidate["url"])
    query = parse_qs(parsed.query)["q"][0]

    assert parsed.netloc == "duckduckgo.com"
    assert "site:arxiv.org" in query
    assert "autonomous agents memory systems" in query


def test_build_safe_public_search_candidates_are_policy_safe() -> None:
    candidates = build_safe_public_search_candidates(
        "autonomous agents memory systems",
        limit=8,
    )

    assert candidates
    assert all(candidate["source_adapter"] == "search" for candidate in candidates)
    assert all(candidate["source_kind"] == "public_search_html" for candidate in candidates)
    assert all(candidate["safe_public_search_template"] is True for candidate in candidates)
    assert all(candidate["external_write_performed"] is False for candidate in candidates)
    assert all(candidate["real_execution_enabled"] is False for candidate in candidates)


def test_research_source_plan_includes_safe_public_search_templates() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=["https://docs.python.org/3/"],
        adapters=["github", "arxiv", "search", "sitemap"],
        limit=24,
    )

    candidates = plan["candidates"]

    safe_search_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("discovery_method") == "safe_public_search_query_template"
    ]

    assert safe_search_candidates
    assert any(
        candidate.get("search_query_site") == "arxiv.org"
        for candidate in safe_search_candidates
    )
    assert any(
        candidate.get("search_query_site") == "docs.github.com"
        for candidate in safe_search_candidates
    )

    assert all(
        candidate.get("source_adapter") == "search"
        and candidate.get("source_kind") == "public_search_html"
        for candidate in safe_search_candidates
    )


def test_research_source_plan_does_not_include_safe_templates_without_search_adapter() -> None:
    plan = build_research_source_plan(
        goal="autonomous agents memory systems",
        seed_urls=["https://docs.python.org/3/"],
        adapters=["github", "arxiv", "sitemap"],
        limit=24,
    )

    assert not any(
        candidate.get("discovery_method") == "safe_public_search_query_template"
        for candidate in plan["candidates"]
    )


@pytest.mark.parametrize(
    "bad_goal",
    [
        "password token leak",
        "admin panel exposed credentials",
        "private key secret dump",
    ],
)
def test_unsafe_goal_does_not_generate_public_search_templates(bad_goal: str) -> None:
    templates = build_safe_public_search_templates(bad_goal)

    assert templates == []