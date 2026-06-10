import argparse

from src.core.crdt_adapter import CRDTAdapter
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary,
    inspect_retry_governance_trail,
    inspect_retry_governance_trail_from_records,
)


def _proposal(**overrides):
    item = {
        "type": "replay_lifecycle_retry_proposal",
        "proposal_id": "proposal-1",
        "status": "pending",
        "timeout_profile": "standard",
    }
    item.update(overrides)
    return item


def _approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": "approval-1",
        "proposal_id": "proposal-1",
        "status": "approved",
        "decision_mode": "manual",
    }
    item.update(overrides)
    return item


def _plan(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "planned",
        "decision_mode": "manual",
        "execution_enabled": False,
    }
    item.update(overrides)
    return item


def _rendered_command(**overrides):
    item = {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rendered",
        "timeout_profile": "standard",
        "decision_mode": "manual",
    }
    item.update(overrides)
    return item


def _rendered_command_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_rendered_command_result",
        "rendered_command_result_id": "rendered-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "skipped",
        "reason": "execution_disabled",
        "execution_enabled": False,
        "payload": {"executed": False},
    }
    item.update(overrides)
    return item

def _eligibility(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_eligibility",
        "eligibility_id": "eligibility-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "blocked",
        "reason": "execution_disabled",
        "execution_supported": False,
        "execution_enabled": False,
        "payload": {
            "status": "blocked",
            "reason": "execution_disabled",
            "execution_supported": False,
            "execution_enabled": False,
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def _result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_result",
        "result_id": "result-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "rendered_command_id": "rendered-1",
        "status": "skipped",
        "reason": "execution_disabled",
        "execution_enabled": False,
        "payload": {
            "rendered_command_id": "rendered-1",
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def test_inspect_retry_governance_trail_from_records_counts_chain() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            {"type": "swarm_heartbeat"},
        ]
    )

    assert summary["total_records"] == 7
    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["rendered_command_results"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["eligibilities"] == 1

    assert summary["approval_statuses"]["approved"] == 1
    assert summary["plan_statuses"]["planned"] == 1
    assert summary["rendered_command_statuses"]["rendered"] == 1
    assert summary["rendered_command_profiles"]["standard"] == 1
    assert summary["rendered_command_result_statuses"]["skipped"] == 1
    assert summary["rendered_command_result_reasons"]["execution_disabled"] == 1
    assert summary["result_statuses"]["skipped"] == 1
    assert summary["result_reasons"]["execution_disabled"] == 1
    assert summary["eligibility_statuses"]["blocked"] == 1
    assert summary["eligibility_reasons"]["execution_disabled"] == 1

    assert summary["decision_modes"]["manual"] == 3

    assert summary["chain_ids"]["proposal_ids"] == ["proposal-1"]
    assert summary["chain_ids"]["approval_ids"] == ["approval-1"]
    assert summary["chain_ids"]["plan_ids"] == ["plan-1"]
    assert summary["chain_ids"]["rendered_command_ids"] == ["rendered-1"]
    assert summary["chain_ids"]["rendered_command_result_ids"] == ["rendered-result-1"]
    assert summary["chain_ids"]["result_ids"] == ["result-1"]
    assert summary["chain_ids"]["eligibility_ids"] == ["eligibility-1"]

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []


def test_inspect_retry_governance_trail_from_records_filters_by_plan_id() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(proposal_id="proposal-1"),
            _plan(plan_id="plan-1", proposal_id="proposal-1"),
            _rendered_command(
                rendered_command_id="rendered-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
            ),
            _rendered_command_result(
                rendered_command_result_id="rendered-result-1",
                rendered_command_id="rendered-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
            ),
            _result(
                result_id="result-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
                rendered_command_id="rendered-1",
            ),
            _eligibility(
                eligibility_id="eligibility-1",
                rendered_command_id="rendered-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
            ),
            _plan(plan_id="plan-2", proposal_id="proposal-2"),
            _rendered_command(
                rendered_command_id="rendered-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
            ),
            _rendered_command_result(
                rendered_command_result_id="rendered-result-2",
                rendered_command_id="rendered-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
            ),
            _result(
                result_id="result-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
                rendered_command_id="rendered-2",
            ),
            _eligibility(
                eligibility_id="eligibility-2",
                rendered_command_id="rendered-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
            ),
        ],
        plan_id="plan-1",
    )

    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["rendered_command_results"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["eligibilities"] == 1
    assert summary["chain_ids"]["plan_ids"] == ["plan-1"]
    assert summary["chain_ids"]["rendered_command_ids"] == ["rendered-1"]
    assert summary["chain_ids"]["rendered_command_result_ids"] == ["rendered-result-1"]
    assert summary["chain_ids"]["eligibility_ids"] == ["eligibility-1"]


def test_inspect_retry_governance_trail_from_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)

    import asyncio

    async def seed():
        await crdt.add_genome(_proposal())
        await crdt.add_genome(_approval())
        await crdt.add_genome(_plan())
        await crdt.add_genome(_rendered_command())
        await crdt.add_genome(_rendered_command_result())
        await crdt.add_genome(_eligibility())
        await crdt.add_genome(_result())

    asyncio.run(seed())

    summary = inspect_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            proposal_id="",
            approval_id="",
            plan_id="",
        )
    )

    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["rendered_command_results"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["eligibilities"] == 1
    assert summary["chain_complete"] is True


def test_inspect_retry_governance_trail_reports_missing_stages() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert summary["missing_stages"] == [
        "approval",
        "plan",
        "rendered_command",
        "rendered_command_result",
        "execution_eligibility",
        "result",
    ]


def test_retry_governance_trail_exit_code_is_zero_by_default_when_incomplete() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert _exit_code_for_summary(summary, require_complete=False) == 0


def test_retry_governance_trail_exit_code_is_one_when_require_complete_and_incomplete() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert _exit_code_for_summary(summary, require_complete=True) == 1


def test_retry_governance_trail_exit_code_is_zero_when_require_complete_and_complete() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
        ]
    )

    assert summary["chain_complete"] is True
    assert _exit_code_for_summary(summary, require_complete=True) == 0


def _controlled_execution_result(**overrides):
    command_parse = {
        "type": "controlled_retry_command_parse_result",
        "valid": True,
        "allowlist_matched": True,
        "reasons": [],
        "module": "src.testing.run_replay_evidence_check",
        "args": {
            "scenario_id": "replay-controlled-test",
            "directive_id": "runtime-run-replay-controlled-test",
            "timeout_profile": "standard",
        },
        "execution_performed": False,
    }

    gate_evaluation = {
        "type": "controlled_retry_execution_gate_evaluation",
        "gate_status": "blocked",
        "would_execute": False,
        "would_execute_if_enabled": False,
        "reasons": [
            "controlled_execution_not_enabled",
            "controlled_execution_implementation_not_enabled",
        ],
        "controlled_execution_enabled": False,
        "implementation_enabled": False,
        "operator_authorized": False,
        "allowlist_matched": True,
        "command_parse_valid": True,
        "command_parse_allowlist_matched": True,
        "command_parse_execution_performed": False,
        "payload_executed": False,
        "execution_enabled": False,
        "readiness_score": 0,
        "min_readiness_score": 100,
        "execution_performed": False,
    }

    mock_execution = {
        "type": "controlled_retry_mock_execution",
        "status": "mock_executed",
        "reason": "mock_execution_completed",
        "mock_execution_enabled": True,
        "real_execution_enabled": False,
        "mock_execution": {
            "adapter_result": {
                "type": "controlled_retry_execution_adapter_result",
                "adapter": "mock",
                "mode": "mock",
                "status": "mock_executed",
                "reason": "mock_execution_completed",
                "controlled_execution_result_id": "controlled-result-1",
                "rendered_command_id": "rendered-1",
                "timeout_profile": "standard",
                "subprocess_invoked": False,
                "real_execution_enabled": False,
                "exit_code": 0,
                "stdout": "mock controlled retry execution",
                "stderr": "",
                "payload": {
                    "executed": False,
                    "mock_executed": True,
                    "subprocess_invoked": False,
                    "real_execution_enabled": False,
                    "adapter": "mock",
                    "mode": "mock",
                    "timeout_profile": "standard",
                },
            },
            "performed": True,
            "adapter": "mock",
            "subprocess_invoked": False,
            "exit_code": 0,
            "stdout": "mock controlled retry execution",
            "stderr": "",
            "reasons": [],
        },
        "payload": {
            "executed": False,
            "mock_executed": True,
            "subprocess_invoked": False,
        },
    }

    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "execution_enabled": False,
        "operator_authorized": False,
        "allowlist_matched": True,
        "command_parse": dict(command_parse),
        "gate_evaluation": dict(gate_evaluation),
        "mock_execution": dict(mock_execution),
        "real_execution_requested": False,
        "real_execution_performed": False,
        "real_execution_supported": False,
        "subprocess_invoked": False,
        "payload": {
            "executed": False,
            "operator_authorized": False,
            "allowlist_matched": True,
            "command_parse": dict(command_parse),
            "gate_evaluation": dict(gate_evaluation),
            "mock_execution": dict(mock_execution),
            "real_execution_requested": False,
            "real_execution_performed": False,
            "real_execution_supported": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def _real_preflight(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_preflight",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "blocked",
        "reason": "real_execution_not_supported",
        "real_execution_requested": True,
        "would_execute": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_adapter_requires_explicit_pr": True,
    }
    item.update(overrides)
    return item


def _real_approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_approval",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "approval_status": "pending",
        "reason": "real_execution_explicit_approval_required",
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
    }
    item.update(overrides)
    return item


def _real_approval_transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_approval_transition",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "from_status": "pending",
        "to_status": "approved",
        "reason": "real_execution_approval_transition_recorded",
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
    }
    item.update(overrides)
    return item


def test_inspect_retry_governance_trail_counts_controlled_execution_extension() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(),
            _real_preflight(),
            _real_approval(),
            _real_approval_transition(),
            _real_final_gate(),
        ]
    )

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []
    assert summary["total_records"] == 12
    assert summary["counts"]["controlled_execution_results"] == 1
    assert summary["extended_controlled_execution_observed"] is True
    assert summary["controlled_execution_result_statuses"]["rejected"] == 1
    assert (
        summary["controlled_execution_result_reasons"][
            "controlled_execution_not_implemented"
        ]
        == 1
    )
    assert summary["chain_ids"]["controlled_execution_result_ids"] == [
        "controlled-result-1"
    ]
    assert summary["controlled_command_parse_valid"]["true"] == 1
    assert summary["controlled_command_parse_allowlist_matched"]["true"] == 1
    assert summary["controlled_command_parse_execution_performed"]["false"] == 1
    assert summary["controlled_execution_operator_authorized"]["false"] == 1
    assert summary["controlled_gate_statuses"]["blocked"] == 1
    assert summary["controlled_gate_would_execute"]["false"] == 1
    assert summary["controlled_gate_execution_performed"]["false"] == 1
    assert summary["controlled_gate_reasons"]["controlled_execution_not_enabled"] == 1
    assert summary["controlled_mock_statuses"]["mock_executed"] == 1
    assert summary["controlled_mock_reasons"]["mock_execution_completed"] == 1
    assert summary["controlled_mock_performed"]["true"] == 1
    assert summary["controlled_mock_subprocess_invoked"]["false"] == 1
    assert summary["controlled_mock_adapter"]["mock"] == 1
    assert summary["controlled_mock_adapter_mode"]["mock"] == 1
    assert summary["controlled_mock_adapter_result_statuses"]["mock_executed"] == 1
    assert summary["controlled_mock_adapter_subprocess_invoked"]["false"] == 1
    assert summary["controlled_mock_adapter_real_execution_enabled"]["false"] == 1
    assert summary["controlled_mock_adapter_payload_executed"]["false"] == 1
    assert summary["controlled_real_execution_requested"]["false"] == 1
    assert summary["controlled_real_execution_performed"]["false"] == 1
    assert summary["controlled_real_execution_supported"]["false"] == 1
    assert summary["controlled_subprocess_invoked"]["false"] == 1
    assert summary["counts"]["real_execution_preflights"] == 1
    assert summary["chain_ids"]["real_execution_preflight_ids"] == [
        "real-preflight-1"
    ]
    assert summary["real_preflight_statuses"]["blocked"] == 1
    assert summary["real_preflight_reasons"]["real_execution_not_supported"] == 1
    assert summary["real_preflight_would_execute"]["false"] == 1
    assert summary["real_preflight_execution_performed"]["false"] == 1
    assert summary["real_preflight_subprocess_invoked"]["false"] == 1
    assert summary["real_preflight_requires_explicit_pr"]["true"] == 1
    assert summary["counts"]["real_execution_approvals"] == 1
    assert summary["chain_ids"]["real_execution_approval_ids"] == [
        "real-approval-1"
    ]
    assert summary["real_approval_statuses"]["pending"] == 1
    assert summary["real_approval_enabled"]["false"] == 1
    assert summary["real_approval_subprocess_enabled"]["false"] == 1
    assert summary["real_approval_execution_performed"]["false"] == 1
    assert summary["real_approval_subprocess_invoked"]["false"] == 1
    assert summary["real_linkage_complete"] is True
    assert summary["real_preflight_controlled_matches"] == 1
    assert summary["real_preflight_rendered_matches"] == 1
    assert summary["real_preflight_orphans"] == 0
    assert summary["real_approval_preflight_matches"] == 1
    assert summary["real_approval_controlled_matches"] == 1
    assert summary["real_approval_rendered_matches"] == 1
    assert summary["real_approval_orphans"] == 0
    assert summary["counts"]["real_execution_approval_transitions"] == 1
    assert summary["chain_ids"]["real_execution_approval_transition_ids"] == [
        "real-transition-1"
    ]
    assert summary["real_approval_transition_statuses"]["approved"] == 1
    assert summary["real_approval_transition_enabled"]["false"] == 1
    assert summary["real_approval_transition_subprocess_enabled"]["false"] == 1
    assert summary["real_approval_transition_execution_performed"]["false"] == 1
    assert summary["real_approval_transition_subprocess_invoked"]["false"] == 1
    assert summary["real_approval_latest_status"] == "approved"
    assert summary["counts"]["real_execution_final_gates"] == 1
    assert summary["chain_ids"]["real_execution_final_gate_ids"] == [
        "real-final-gate-1"
    ]
    assert summary["real_final_gate_statuses"]["blocked"] == 1
    assert summary["real_final_gate_would_execute"]["false"] == 1
    assert summary["real_final_gate_ready"]["false"] == 1
    assert summary["real_final_gate_real_execution_enabled"]["false"] == 1
    assert summary["real_final_gate_subprocess_enabled"]["false"] == 1
    assert summary["real_final_gate_execution_performed"]["false"] == 1
    assert summary["real_final_gate_subprocess_invoked"]["false"] == 1


def test_inspect_retry_governance_trail_does_not_require_controlled_execution_result() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
        ]
    )

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []
    assert summary["counts"]["controlled_execution_results"] == 0
    assert summary["extended_controlled_execution_observed"] is False
    assert summary["chain_ids"]["controlled_execution_result_ids"] == []


def test_inspect_retry_governance_trail_counts_operator_authorization_intent() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(operator_authorized=True),
        ]
    )

    assert summary["chain_complete"] is True
    assert summary["controlled_execution_operator_authorized"]["true"] == 1


def test_inspect_retry_governance_trail_counts_mock_subprocess_safety() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(),
        ]
    )

    assert summary["controlled_mock_performed"]["true"] == 1
    assert summary["controlled_mock_subprocess_invoked"]["false"] == 1
    assert summary["controlled_mock_subprocess_invoked"].get("true", 0) == 0


def _mock_execution_summary(**overrides):
    item = {
        "type": "replay_lifecycle_retry_mock_execution_summary",
        "mock_execution_summary_id": "mock-summary-1",
        "controlled_execution_result_id": "controlled-result-1",
        "source_controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "proposal_id": "proposal-1",
        "plan_id": "plan-1",
        "approval_id": "approval-1",
        "status": "mock_executed",
        "reason": "mock_execution_completed",
        "mock_performed": True,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "derived": True,
        "payload": {
            "executed": False,
            "derived": True,
        },
    }
    item.update(overrides)
    return item

def test_inspect_retry_governance_trail_counts_mock_execution_summary() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(),
            _mock_execution_summary(),
        ]
    )

    assert summary["counts"]["mock_execution_summaries"] == 1
    assert summary["chain_ids"]["mock_execution_summary_ids"] == ["mock-summary-1"]
    assert summary["mock_summary_statuses"]["mock_executed"] == 1
    assert summary["mock_summary_reasons"]["mock_execution_completed"] == 1
    assert summary["mock_summary_performed"]["true"] == 1
    assert summary["mock_summary_subprocess_invoked"]["false"] == 1


def test_inspect_retry_governance_trail_counts_real_execution_request_intent() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(
                reason="real_execution_not_supported",
                real_execution_requested=True,
            ),
        ]
    )

    assert summary["chain_complete"] is True
    assert summary["controlled_execution_result_reasons"][
        "real_execution_not_supported"
    ] == 1
    assert summary["controlled_real_execution_requested"]["true"] == 1
    assert summary["controlled_real_execution_performed"]["false"] == 1
    assert summary["controlled_real_execution_supported"]["false"] == 1
    assert summary["controlled_subprocess_invoked"]["false"] == 1


def test_inspect_retry_governance_trail_counts_real_approval_orphan() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(),
            _real_preflight(),
            _real_approval(real_execution_preflight_id="missing-preflight"),
        ]
    )

    assert summary["real_linkage_complete"] is False
    assert summary["real_approval_orphans"] == 1


def _real_final_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_final_gate",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "from_status": "pending",
        "to_status": "approved",
        "gate_status": "blocked",
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
    }
    item.update(overrides)
    return item
