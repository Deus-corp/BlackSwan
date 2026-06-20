from __future__ import annotations

from copy import deepcopy

from src.testing.check_explorer_source_planned_evidence_loop import (
    validate_explorer_source_planned_evidence_loop,
)


def _audit() -> dict:
    return {
        "type": "safe_public_search_template_audit",
        "generated_count": 9,
        "accepted_count": 8,
        "rejected_count": 0,
        "unsafe_rejected_count": 0,
        "deduped_count": 1,
        "by_site": {
            "arxiv.org": 2,
            "docs.github.com": 1,
            "docs.python.org": 1,
            "github.blog": 2,
            "github.com": 1,
            "realpython.com": 1,
        },
        "by_kind": {
            "research_papers": 2,
            "official_docs": 2,
            "engineering_blog": 2,
            "engineering_changelog": 1,
            "github_repositories": 1,
        },
        "queries": [
            "site:arxiv.org autonomous agents memory systems paper research",
            "site:github.blog autonomous agents memory systems changelog",
        ],
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
    }


def _healthy_result() -> dict:
    return {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "ticks_requested": 3,
        "ticks_completed": 3,
        "total_memory_records_published": 7,
        "total_targets_published": 123,
        "total_findings_emitted": 10,
        "external_write_performed": False,
        "real_execution_enabled": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "source_plan_audit": {
            "safe_public_search_template_audit": _audit(),
        },
        "safe_public_search_template_audit": _audit(),
        "ticks": [
            {
                "tick": 3,
                "memory_records_published": 1,
                "targets_published": 0,
                "findings_emitted": 1,
                "node": {
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                    "source_adapter_targets_seen": {
                        "arxiv": 2,
                        "evidence": 20,
                        "github": 2,
                        "search": 5,
                        "sitemap": 3,
                    },
                    "source_adapter_targets_selected": {
                        "arxiv": 2,
                        "evidence": 7,
                        "github": 2,
                        "search": 1,
                    },
                    "source_adapter_rate_limits": {
                        "search:duckduckgo.com:robots_disallowed": 1,
                    },
                    "domain_rate_limits": {
                        "duckduckgo.com": 1,
                    },
                    "safe_public_search_templates_seen": 4,
                    "safe_public_search_templates_selected": 1,
                    "safe_public_search_templates_fetched": 1,
                    "safe_public_search_templates_blocked": 1,
                    "unsafe_public_search_templates_detected": 0,
                },
            }
        ],
    }


def test_checker_accepts_source_plan_audit_with_runtime_telemetry() -> None:
    errors = validate_explorer_source_planned_evidence_loop(_healthy_result())

    assert errors == []


def test_checker_rejects_audit_safety_flag_true() -> None:
    result = _healthy_result()
    result["source_plan_audit"]["safe_public_search_template_audit"][
        "external_write_performed"
    ] = True
    result["safe_public_search_template_audit"]["external_write_performed"] = True

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any(
        "safe public search template audit has unsafe flag true" in error
        for error in errors
    )


def test_checker_rejects_search_activity_with_empty_audit_acceptance() -> None:
    result = _healthy_result()
    result["source_plan_audit"]["safe_public_search_template_audit"][
        "accepted_count"
    ] = 0
    result["safe_public_search_template_audit"]["accepted_count"] = 0

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any(
        "accepted_count must be > 0" in error
        for error in errors
    )


def test_checker_rejects_unsafe_runtime_templates() -> None:
    result = _healthy_result()
    result["ticks"][0]["node"]["unsafe_public_search_templates_detected"] = 1

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert any(
        "unsafe public search templates detected" in error
        for error in errors
    )


def test_checker_accepts_robots_blocked_safe_template() -> None:
    result = _healthy_result()
    result["ticks"][0]["node"]["safe_public_search_templates_blocked"] = 1
    result["ticks"][0]["node"]["safe_public_search_templates_fetched"] = 1
    result["ticks"][0]["node"]["safe_public_search_templates_selected"] = 1

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert errors == []


def test_checker_remains_backward_compatible_without_audit() -> None:
    result = deepcopy(_healthy_result())
    result.pop("source_plan_audit", None)
    result.pop("safe_public_search_template_audit", None)

    # Simulate an older fixture without the new audit and without the new
    # template telemetry fields. Existing evidence/source-adapter contract
    # should still validate.
    node = result["ticks"][0]["node"]
    node.pop("safe_public_search_templates_seen", None)
    node.pop("safe_public_search_templates_selected", None)
    node.pop("safe_public_search_templates_fetched", None)
    node.pop("safe_public_search_templates_blocked", None)
    node.pop("unsafe_public_search_templates_detected", None)

    errors = validate_explorer_source_planned_evidence_loop(result)

    assert errors == []