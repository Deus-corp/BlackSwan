from argparse import Namespace

from src.testing.run_explorer_network_read_loop import (
    _build_evidence_seed_targets,
)


def test_build_evidence_seed_targets_marks_goal_aligned_urls_high_priority() -> None:
    targets = _build_evidence_seed_targets(
        [
            "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai/",
        ],
        goal="autonomous agents memory systems",
        exploration_run_id="run-evidence-seed",
    )

    assert len(targets) == 1

    target = targets[0]

    assert target["url"] == (
        "https://realpython.com/courses/building-type-safe-llm-agents-with-pydantic-ai"
    )
    assert target["source_adapter"] == "evidence_seed"
    assert target["source_kind"] == "goal_evidence_url"
    assert target["preferred_evidence_target"] is True
    assert target["goal_alignment_score"] > 0.0
    assert target["source_score"] >= 0.88
    assert target["exploration_run_id"] == "run-evidence-seed"
    assert target["network_read_candidate"] is True
    assert target["external_write_performed"] is False
    assert target["real_execution_enabled"] is False