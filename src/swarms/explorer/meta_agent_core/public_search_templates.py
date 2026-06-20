from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import quote_plus
from collections import Counter


SAFE_PUBLIC_SEARCH_SITES = {
    "arxiv.org",
    "docs.github.com",
    "docs.python.org",
    "github.blog",
    "github.com",
    "realpython.com",
}

SAFE_PUBLIC_SEARCH_TEMPLATE_KINDS = {
    "research_papers",
    "official_docs",
    "engineering_changelog",
    "engineering_blog",
    "github_repositories",
    "technical_tutorials",
}

UNSAFE_PUBLIC_SEARCH_TERMS = {
    "admin",
    "apikey",
    "api_key",
    "aws_access_key_id",
    "credential",
    "credentials",
    "darkweb",
    "dark web",
    "dump",
    "exfil",
    "exploit",
    "exposed",
    "htpasswd",
    "index of",
    "intitle:index.of",
    "leak",
    "leaked",
    "password",
    "passwd",
    "private key",
    "secret",
    "secrets",
    "shadow",
    "ssh key",
    "token",
    "vulnerability",
}

DEFAULT_SAFE_PUBLIC_SEARCH_TEMPLATE_SCORE = 0.70
SAFE_PUBLIC_SEARCH_TEMPLATE_PRIORITY_CLASS = "safe_public_search_template"


@dataclass(frozen=True)
class PublicSearchTemplate:
    """Safe public search query template descriptor."""

    kind: str
    site: str
    query: str
    rationale: str


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _goal_terms(goal: str) -> list[str]:
    """Extract stable, non-empty goal terms for public search templates."""
    text = _clean_text(goal).lower()
    if not text:
        return []

    terms = re.findall(r"[a-z0-9][a-z0-9_\-]{2,}", text)
    seen: set[str] = set()
    out: list[str] = []

    for term in terms:
        normalized = term.strip("-_")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)

    return out


def _contains_unsafe_public_search_term(value: str) -> bool:
    haystack = _clean_text(value).lower()
    if not haystack:
        return False

    return any(term in haystack for term in UNSAFE_PUBLIC_SEARCH_TERMS)


def _template_to_dict(
    template: Mapping[str, Any] | PublicSearchTemplate,
) -> dict[str, Any]:
    if isinstance(template, PublicSearchTemplate):
        return {
            "kind": template.kind,
            "site": template.site,
            "query": template.query,
            "rationale": template.rationale,
        }

    return dict(template)


def _template_to_dict(
    template: Mapping[str, Any] | PublicSearchTemplate,
) -> dict[str, Any]:
    if isinstance(template, PublicSearchTemplate):
        return {
            "kind": template.kind,
            "site": template.site,
            "query": template.query,
            "rationale": template.rationale,
        }

    return dict(template)


def validate_public_search_template(
    template: Mapping[str, Any] | PublicSearchTemplate,
) -> list[str]:
    """Return validation errors for a public search template."""
    data = _template_to_dict(template)

    errors: list[str] = []

    kind = _clean_text(data.get("kind"))
    site = _clean_text(data.get("site")).lower()
    query = _clean_text(data.get("query"))

    if kind not in SAFE_PUBLIC_SEARCH_TEMPLATE_KINDS:
        errors.append(f"unsupported template kind: {kind!r}")

    if site not in SAFE_PUBLIC_SEARCH_SITES:
        errors.append(f"unsupported public search site: {site!r}")

    if not query:
        errors.append("query is required")

    expected_site_prefix = f"site:{site}"
    if query and expected_site_prefix not in query.lower():
        errors.append(f"query must include {expected_site_prefix!r}")

    if _contains_unsafe_public_search_term(query):
        errors.append("query contains unsafe public search term")

    return errors


def summarize_safe_public_search_templates(
    templates: Iterable[Mapping[str, Any] | PublicSearchTemplate],
    *,
    generated_count: int | None = None,
    rejected_count: int = 0,
    unsafe_rejected_count: int = 0,
    deduped_count: int = 0,
) -> dict[str, Any]:
    """Build a compact audit summary for safe public search templates."""
    accepted_templates: list[dict[str, Any]] = []

    for template in templates:
        data = _template_to_dict(template)
        if validate_public_search_template(data):
            continue
        accepted_templates.append(data)

    by_site = Counter()
    by_kind = Counter()
    queries: list[str] = []

    for template in accepted_templates:
        site = _clean_text(template.get("site")).lower()
        kind = _clean_text(template.get("kind"))
        query = _clean_text(template.get("query"))

        if site:
            by_site[site] += 1
        if kind:
            by_kind[kind] += 1
        if query:
            queries.append(query)

    generated = (
        int(generated_count)
        if generated_count is not None
        else len(accepted_templates) + int(rejected_count or 0)
    )

    return {
        "type": "safe_public_search_template_audit",
        "generated_count": generated,
        "accepted_count": len(accepted_templates),
        "rejected_count": int(rejected_count or 0),
        "unsafe_rejected_count": int(unsafe_rejected_count or 0),
        "deduped_count": int(deduped_count or 0),
        "by_site": dict(sorted(by_site.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "queries": sorted(set(queries)),
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def empty_safe_public_search_template_audit(
    *,
    unsafe_rejected_count: int = 0,
) -> dict[str, Any]:
    """Return an empty safe public search template audit summary."""
    return summarize_safe_public_search_templates(
        [],
        generated_count=0,
        rejected_count=0,
        unsafe_rejected_count=unsafe_rejected_count,
        deduped_count=0,
    )


def summarize_safe_public_search_templates(
    templates: Iterable[Mapping[str, Any] | PublicSearchTemplate],
    *,
    generated_count: int | None = None,
    rejected_count: int = 0,
    unsafe_rejected_count: int = 0,
    deduped_count: int = 0,
) -> dict[str, Any]:
    """Build a compact audit summary for safe public search templates."""
    accepted_templates: list[dict[str, Any]] = []

    for template in templates:
        data = _template_to_dict(template)
        if validate_public_search_template(data):
            continue
        accepted_templates.append(data)

    by_site = Counter()
    by_kind = Counter()
    queries: list[str] = []

    for template in accepted_templates:
        site = _clean_text(template.get("site")).lower()
        kind = _clean_text(template.get("kind"))
        query = _clean_text(template.get("query"))

        if site:
            by_site[site] += 1
        if kind:
            by_kind[kind] += 1
        if query:
            queries.append(query)

    generated = (
        int(generated_count)
        if generated_count is not None
        else len(accepted_templates) + int(rejected_count or 0)
    )

    return {
        "type": "safe_public_search_template_audit",
        "generated_count": generated,
        "accepted_count": len(accepted_templates),
        "rejected_count": int(rejected_count or 0),
        "unsafe_rejected_count": int(unsafe_rejected_count or 0),
        "deduped_count": int(deduped_count or 0),
        "by_site": dict(sorted(by_site.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "queries": sorted(set(queries)),
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def empty_safe_public_search_template_audit(
    *,
    unsafe_rejected_count: int = 0,
) -> dict[str, Any]:
    """Return an empty safe public search template audit summary."""
    return summarize_safe_public_search_templates(
        [],
        generated_count=0,
        rejected_count=0,
        unsafe_rejected_count=unsafe_rejected_count,
        deduped_count=0,
    )


def _template(
    *,
    kind: str,
    site: str,
    goal_terms: Iterable[str],
    extras: Iterable[str] = (),
    rationale: str,
) -> PublicSearchTemplate:
    terms = [
        _clean_text(term)
        for term in [*goal_terms, *extras]
        if _clean_text(term)
    ]

    query = " ".join([f"site:{site}", *terms])

    return PublicSearchTemplate(
        kind=kind,
        site=site,
        query=query,
        rationale=rationale,
    )


def build_safe_public_search_template_plan(
    goal: str,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Build safe public search templates plus planning-time audit summary."""
    if _contains_unsafe_public_search_term(goal):
        return {
            "templates": [],
            "audit": empty_safe_public_search_template_audit(
                unsafe_rejected_count=1,
            ),
        }

    terms = _goal_terms(goal)
    if not terms:
        return {
            "templates": [],
            "audit": empty_safe_public_search_template_audit(),
        }

    # Keep the query compact and deterministic. Too many goal terms make search
    # URLs noisy and less useful.
    compact_terms = terms[:6]
    goal_phrase = _clean_text(goal)

    candidates = [
        _template(
            kind="research_papers",
            site="arxiv.org",
            goal_terms=compact_terms,
            extras=("paper", "research"),
            rationale="Find public arXiv papers related to the research goal.",
        ),
        _template(
            kind="official_docs",
            site="docs.github.com",
            goal_terms=compact_terms,
            extras=("docs",),
            rationale="Find official GitHub documentation related to the research goal.",
        ),
        _template(
            kind="official_docs",
            site="docs.python.org",
            goal_terms=compact_terms,
            extras=("library", "documentation"),
            rationale="Find Python standard-library documentation relevant to implementation.",
        ),
        _template(
            kind="engineering_changelog",
            site="github.blog",
            goal_terms=compact_terms,
            extras=("changelog",),
            rationale="Find public GitHub engineering changelog entries.",
        ),
        _template(
            kind="engineering_blog",
            site="github.blog",
            goal_terms=compact_terms,
            extras=("engineering", "blog"),
            rationale="Find public GitHub engineering blog evidence.",
        ),
        _template(
            kind="github_repositories",
            site="github.com",
            goal_terms=compact_terms,
            extras=("repository", "framework"),
            rationale="Find public GitHub repositories related to the goal.",
        ),
        _template(
            kind="technical_tutorials",
            site="realpython.com",
            goal_terms=compact_terms,
            extras=("tutorial",),
            rationale="Find public technical tutorials relevant to implementation.",
        ),
    ]

    if goal_phrase:
        candidates.append(
            PublicSearchTemplate(
                kind="engineering_blog",
                site="github.blog",
                query=f'site:github.blog "{goal_phrase}"',
                rationale="Find exact-phrase public engineering blog evidence.",
            )
        )
        candidates.append(
            PublicSearchTemplate(
                kind="research_papers",
                site="arxiv.org",
                query=f'site:arxiv.org "{goal_phrase}"',
                rationale="Find exact-phrase public research paper evidence.",
            )
        )

    safe: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    rejected_count = 0
    unsafe_rejected_count = 0
    deduped_count = 0
    template_limit = max(0, int(limit or 0))

    for item in candidates:
        data = _template_to_dict(item)

        errors = validate_public_search_template(data)
        if errors:
            rejected_count += 1
            if any("unsafe public search term" in error for error in errors):
                unsafe_rejected_count += 1
            continue

        query_key = _clean_text(data.get("query")).lower()
        if query_key in seen_queries:
            deduped_count += 1
            continue

        seen_queries.add(query_key)

        if len(safe) < template_limit:
            safe.append(
                {
                    **data,
                    "safe_public_search_template": True,
                }
            )

    audit = summarize_safe_public_search_templates(
        safe,
        generated_count=len(candidates),
        rejected_count=rejected_count,
        unsafe_rejected_count=unsafe_rejected_count,
        deduped_count=deduped_count,
    )

    return {
        "templates": safe,
        "audit": audit,
    }


def build_safe_public_search_templates(
    goal: str,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Build safe allowlisted public search templates for a research goal."""
    plan = build_safe_public_search_template_plan(goal, limit=limit)
    return list(plan.get("templates", []) or [])


def build_safe_public_search_template_plan(
    goal: str,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Build safe public search templates plus planning-time audit summary."""
    if _contains_unsafe_public_search_term(goal):
        return {
            "templates": [],
            "audit": empty_safe_public_search_template_audit(
                unsafe_rejected_count=1,
            ),
        }

    terms = _goal_terms(goal)
    if not terms:
        return {
            "templates": [],
            "audit": empty_safe_public_search_template_audit(),
        }

    compact_terms = terms[:6]
    goal_phrase = _clean_text(goal)

    candidates = [
        _template(
            kind="research_papers",
            site="arxiv.org",
            goal_terms=compact_terms,
            extras=("paper", "research"),
            rationale="Find public arXiv papers related to the research goal.",
        ),
        _template(
            kind="official_docs",
            site="docs.github.com",
            goal_terms=compact_terms,
            extras=("docs",),
            rationale="Find official GitHub documentation related to the research goal.",
        ),
        _template(
            kind="official_docs",
            site="docs.python.org",
            goal_terms=compact_terms,
            extras=("library", "documentation"),
            rationale="Find Python standard-library documentation relevant to implementation.",
        ),
        _template(
            kind="engineering_changelog",
            site="github.blog",
            goal_terms=compact_terms,
            extras=("changelog",),
            rationale="Find public GitHub engineering changelog entries.",
        ),
        _template(
            kind="engineering_blog",
            site="github.blog",
            goal_terms=compact_terms,
            extras=("engineering", "blog"),
            rationale="Find public GitHub engineering blog evidence.",
        ),
        _template(
            kind="github_repositories",
            site="github.com",
            goal_terms=compact_terms,
            extras=("repository", "framework"),
            rationale="Find public GitHub repositories related to the goal.",
        ),
        _template(
            kind="technical_tutorials",
            site="realpython.com",
            goal_terms=compact_terms,
            extras=("tutorial",),
            rationale="Find public technical tutorials relevant to implementation.",
        ),
    ]

    if goal_phrase:
        candidates.append(
            PublicSearchTemplate(
                kind="engineering_blog",
                site="github.blog",
                query=f'site:github.blog "{goal_phrase}"',
                rationale="Find exact-phrase public engineering blog evidence.",
            )
        )
        candidates.append(
            PublicSearchTemplate(
                kind="research_papers",
                site="arxiv.org",
                query=f'site:arxiv.org "{goal_phrase}"',
                rationale="Find exact-phrase public research paper evidence.",
            )
        )

    safe: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    rejected_count = 0
    unsafe_rejected_count = 0
    deduped_count = 0

    for item in candidates:
        data = _template_to_dict(item)
        errors = validate_public_search_template(data)
        if errors:
            rejected_count += 1
            if any("unsafe public search term" in error for error in errors):
                unsafe_rejected_count += 1
            continue

        query_key = _clean_text(data.get("query")).lower()
        if query_key in seen_queries:
            deduped_count += 1
            continue

        seen_queries.add(query_key)
        safe.append(
            {
                **data,
                "safe_public_search_template": True,
            }
        )

        if len(safe) >= max(0, int(limit or 0)):
            break

    audit = summarize_safe_public_search_templates(
        safe,
        generated_count=len(candidates),
        rejected_count=rejected_count,
        unsafe_rejected_count=unsafe_rejected_count,
        deduped_count=deduped_count,
    )

    return {
        "templates": safe,
        "audit": audit,
    }


def public_search_template_to_candidate(
    template: Mapping[str, Any],
    *,
    goal: str = "",
    existing_score: float = DEFAULT_SAFE_PUBLIC_SEARCH_TEMPLATE_SCORE,
) -> dict[str, Any]:
    """Convert a safe public search template into an explorer source-plan candidate."""
    errors = validate_public_search_template(template)
    if errors:
        raise ValueError("; ".join(errors))

    query = _clean_text(template.get("query"))
    site = _clean_text(template.get("site")).lower()
    kind = _clean_text(template.get("kind"))

    url = f"https://duckduckgo.com/html?q={quote_plus(query)}"

    score = max(0.0, min(1.0, float(existing_score or 0.0)))

    return {
        "url": url,
        "domain": "duckduckgo.com",
        "source_adapter": "search",
        "source_kind": "public_search_html",
        "discovery_method": "safe_public_search_query_template",
        "search_query": query,
        "search_query_site": site,
        "search_query_template_kind": kind,
        "search_query_rationale": _clean_text(template.get("rationale")),
        "safe_public_search_template": True,
        "network_read_candidate": True,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "research_goal": _clean_text(goal),
        "goal": _clean_text(goal),
        "research_goal_text": _clean_text(goal),
        "source_priority_class": SAFE_PUBLIC_SEARCH_TEMPLATE_PRIORITY_CLASS,
        "planner_priority": score,
        "preferred_evidence_target": False,
        "score": score,
        "source_score": score,
        "quality_score": score,
        "system_relevance_score": max(0.68, min(0.74, score)),
        "authority_score": 0.55,
        "freshness_score": 0.50,
    }


def build_safe_public_search_candidates(
    goal: str,
    *,
    limit: int = 12,
    existing_score: float = DEFAULT_SAFE_PUBLIC_SEARCH_TEMPLATE_SCORE,
) -> list[dict[str, Any]]:
    """Build safe public-search source-plan candidates for a research goal."""
    templates = build_safe_public_search_templates(goal, limit=limit)
    return [
        public_search_template_to_candidate(
            template,
            goal=goal,
            existing_score=existing_score,
        )
        for template in templates
    ]