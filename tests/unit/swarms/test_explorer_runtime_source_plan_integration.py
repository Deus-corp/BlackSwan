from argparse import Namespace

from src.testing.run_explorer_network_read_loop import (
    _build_runtime_research_source_plan,
)


def test_runtime_source_plan_disabled_by_default() -> None:
    args = Namespace(
        source_plan=False,
        goal="autonomous agents memory systems",
        source_adapter=["github", "arxiv"],
        source_plan_limit=10,
    )

    result = _build_runtime_research_source_plan(
        args,
        seed_urls=["https://docs.python.org/3"],
    )

    assert result["enabled"] is False
    assert result["plan"] is None
    assert result["targets"] == []


def test_runtime_source_plan_builds_goal_aligned_targets() -> None:
    args = Namespace(
        source_plan=True,
        goal="autonomous agents memory systems",
        source_adapter=["github", "arxiv", "search", "sitemap"],
        source_plan_limit=12,
    )

    result = _build_runtime_research_source_plan(
        args,
        seed_urls=["https://docs.python.org/3"],
    )

    assert result["enabled"] is True

    plan = result["plan"]
    targets = result["targets"]

    assert plan["type"] == "explorer_research_source_plan"
    assert plan["execution_risk_tier"] == "network_read"
    assert plan["external_write_performed"] is False
    assert plan["real_execution_enabled"] is False
    assert targets

    assert any(
        target.get("preferred_evidence_target")
        and target.get("source_adapter") == "evidence"
        for target in targets
    )
    assert any(
        target.get("source_adapter") == "github"
        and target.get("source_kind") == "github_repository_search"
        for target in targets
    )
    assert all(target.get("network_read_candidate") is True for target in targets)
    assert all(target.get("external_write_performed") is False for target in targets)
    assert all(target.get("real_execution_enabled") is False for target in targets)