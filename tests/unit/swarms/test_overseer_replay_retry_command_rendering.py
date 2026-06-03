import pytest

from src.swarms.overseer.overseer_core.replay_retry_command_rendering import (
    build_replay_lifecycle_retry_rendered_command,
)


def _plan(**overrides):
    plan = {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": "replay-retry-plan-test",
        "proposal_id": "replay-retry-proposal-test",
        "approval_id": "replay-retry-approval-test",
        "status": "planned",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command_template": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id <scenario_id> "
            "--action REDUCE_RISK "
            "--directive-id <new_directive_id> "
            "--timeout-profile standard "
            "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
        ),
    }
    plan.update(overrides)
    return plan


def test_build_replay_lifecycle_retry_rendered_command() -> None:
    rendered = build_replay_lifecycle_retry_rendered_command(
        _plan(),
        scenario_id="replay-render-test",
        new_directive_id="runtime-run-replay-render-test",
        source="overseer-test",
    )

    assert rendered["type"] == "replay_lifecycle_retry_rendered_command"
    assert rendered["status"] == "rendered"
    assert rendered["source"] == "overseer-test"
    assert rendered["execution_enabled"] is False
    assert rendered["scenario_id"] == "replay-render-test"
    assert rendered["new_directive_id"] == "runtime-run-replay-render-test"
    assert "<scenario_id>" not in rendered["command"]
    assert "<new_directive_id>" not in rendered["command"]
    assert "--scenario-id replay-render-test" in rendered["command"]
    assert "--directive-id runtime-run-replay-render-test" in rendered["command"]
    assert "--timeout-profile standard" in rendered["command"]
    assert rendered["payload"]["executed"] is False


def test_build_replay_lifecycle_retry_rendered_command_rejects_enabled_plan() -> None:
    with pytest.raises(ValueError, match="execution_enabled"):
        build_replay_lifecycle_retry_rendered_command(
            _plan(execution_enabled=True),
            scenario_id="replay-render-test",
            new_directive_id="runtime-run-replay-render-test",
        )


def test_build_replay_lifecycle_retry_rendered_command_rejects_missing_placeholders() -> None:
    with pytest.raises(ValueError, match="scenario_id"):
        build_replay_lifecycle_retry_rendered_command(
            _plan(command_template="python -m src.testing.run_replay_evidence_check"),
            scenario_id="replay-render-test",
            new_directive_id="runtime-run-replay-render-test",
        )


def test_build_replay_lifecycle_retry_rendered_command_rejects_unsafe_scenario_id() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        build_replay_lifecycle_retry_rendered_command(
            _plan(),
            scenario_id="replay-render-test; rm -rf /",
            new_directive_id="runtime-run-replay-render-test",
        )


def test_build_replay_lifecycle_retry_rendered_command_rejects_unsafe_directive_id() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        build_replay_lifecycle_retry_rendered_command(
            _plan(),
            scenario_id="replay-render-test",
            new_directive_id="runtime-run-replay-render-test && echo bad",
        )


def test_build_replay_lifecycle_retry_rendered_command_rejects_wrong_module() -> None:
    with pytest.raises(ValueError, match="run_replay_evidence_check"):
        build_replay_lifecycle_retry_rendered_command(
            _plan(
                command_template=(
                    "python -m src.testing.other_helper "
                    "--scenario-id <scenario_id> "
                    "--directive-id <new_directive_id> "
                    "--timeout-profile standard"
                )
            ),
            scenario_id="replay-render-test",
            new_directive_id="runtime-run-replay-render-test",
        )


def test_build_replay_lifecycle_retry_rendered_command_rejects_timeout_profile_mismatch() -> None:
    with pytest.raises(ValueError, match="timeout profile mismatch"):
        build_replay_lifecycle_retry_rendered_command(
            _plan(
                timeout_profile="patient",
                command_template=(
                    "python -m src.testing.run_replay_evidence_check "
                    "--scenario-id <scenario_id> "
                    "--directive-id <new_directive_id> "
                    "--timeout-profile standard"
                ),
            ),
            scenario_id="replay-render-test",
            new_directive_id="runtime-run-replay-render-test",
        )