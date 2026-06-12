import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_repair_action_bundle import (
    READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE,
    build_real_execution_read_only_repair_action_bundle_record,
    build_real_execution_read_only_repair_action_bundle_records,
)


def _repair_plan(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_repair_plan",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "real_execution_read_only_approval_transition_id": "transition-1",
        "real_execution_read_only_approval_id": "approval-1",
        "real_execution_read_only_final_gate_id": "final-gate-1",
        "real_execution_read_only_promotion_id": "promotion-1",
        "real_execution_noop_result_id": "noop-1",
        "real_execution_dry_run_envelope_id": "envelope-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "repair_plan_status": "planned",
        "repair_item_count": 2,
        "repair_targets": ["execution_published", "evidence_published"],
        "repair_items": [
            {
                "target": "execution_published",
                "recommended_action": "publish_or_verify_execution_record",
                "priority": "high",
                "source": "read_only_execution_feedback",
                "execution_required": False,
                "subprocess_required": False,
            },
            {
                "target": "evidence_published",
                "recommended_action": "publish_or_verify_replay_evidence",
                "priority": "high",
                "source": "read_only_execution_feedback",
                "execution_required": False,
                "subprocess_required": False,
            },
        ],
        "recommended_next_action": "review_replay_evidence_repair_plan",
        "requires_operator_review": True,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
    }
    item.update(overrides)
    return item


def test_build_read_only_repair_action_bundle_from_planned_repair_plan() -> None:
    record = build_real_execution_read_only_repair_action_bundle_record(
        _repair_plan()
    )

    assert record["type"] == READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE
    assert record["bundle_status"] == "assembled"
    assert record["source_repair_plan_status"] == "planned"
    assert record["source_feedback_status"] == "actionable"
    assert record["source_status"] == "failed"
    assert record["source_exit_code"] == 1
    assert record["source_repair_item_count"] == 2
    assert record["bundle_item_count"] == 2
    assert record["bundle_targets"] == ["execution_published", "evidence_published"]
    assert record["recommended_next_action"] == "review_repair_action_bundle"
    assert record["requires_operator_review"] is True
    assert record["bundle_reviewed"] is False
    assert record["bundle_execution_enabled"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["bundle_execution_performed"] is False
    assert record["bundle_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert all(item["execution_allowed"] is False for item in record["bundle_items"])
    assert all(item["subprocess_allowed"] is False for item in record["bundle_items"])


def test_build_read_only_repair_action_bundle_uses_manual_review_fallback() -> None:
    record = build_real_execution_read_only_repair_action_bundle_record(
        _repair_plan(repair_items=[], repair_item_count=0, repair_targets=[])
    )

    assert record["bundle_status"] == "assembled"
    assert record["bundle_item_count"] == 1
    assert record["bundle_targets"] == ["manual_repair_plan_review"]
    assert record["bundle_items"][0]["recommended_action"] == (
        "review_replay_evidence_repair_plan"
    )
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_action_bundle_rejects_missing_repair_plan_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_repair_plan_id is required",
    ):
        build_real_execution_read_only_repair_action_bundle_record(
            _repair_plan(real_execution_read_only_repair_plan_id="")
        )


@pytest.mark.asyncio
async def test_build_read_only_repair_action_bundle_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_repair_plan())

    first = await build_real_execution_read_only_repair_action_bundle_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-repair-action-bundle-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_repair_plan_id="",
            json=False,
        )
    )
    second = await build_real_execution_read_only_repair_action_bundle_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-repair-action-bundle-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_repair_plan_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["bundle_status"] == "assembled"
    assert first[0]["bundle_execution_performed"] is False
    assert first[0]["bundle_subprocess_invoked"] is False