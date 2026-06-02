from types import SimpleNamespace

from src.swarms.overseer.overseer_core.replay_retry_proposals import (
    build_replay_lifecycle_retry_proposals_from_brief,
)


def test_build_replay_lifecycle_retry_proposals_from_brief() -> None:
    brief = SimpleNamespace(
        recommended_actions=[
            {
                "title": "Retry replay lifecycle check",
                "payload": {
                    "recommendation": "retry_replay_lifecycle_check",
                    "timeout_profile": "standard",
                    "suggested_wait_seconds": 15.0,
                    "suggested_poll_interval": 0.5,
                    "reason": "execution_not_observed_before_timeout",
                    "security_replay_lifecycle_timeouts": 1,
                    "command_template": (
                        "python -m src.testing.run_replay_evidence_check "
                        "--scenario-id <scenario_id> "
                        "--action REDUCE_RISK "
                        "--directive-id <new_directive_id> "
                        "--timeout-profile standard "
                        "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
                    ),
                },
            }
        ]
    )

    proposals = build_replay_lifecycle_retry_proposals_from_brief(brief, source="overseer-test")

    assert len(proposals) == 1

    proposal = proposals[0]
    assert proposal["type"] == "replay_lifecycle_retry_proposal"
    assert proposal["status"] == "pending"
    assert proposal["source"] == "overseer-test"
    assert proposal["recommendation"] == "retry_replay_lifecycle_check"
    assert proposal["reason"] == "execution_not_observed_before_timeout"
    assert proposal["timeout_profile"] == "standard"
    assert "--timeout-profile standard" in proposal["command_template"]
    assert proposal["payload"]["suggested_wait_seconds"] == 15.0
    assert proposal["payload"]["suggested_poll_interval"] == 0.5


def test_build_replay_lifecycle_retry_proposals_ignores_incomplete_actions() -> None:
    brief = SimpleNamespace(
        recommended_actions=[
            {
                "title": "Retry replay lifecycle check",
                "payload": {
                    "recommendation": "retry_replay_lifecycle_check",
                    "timeout_profile": "standard",
                    "reason": "execution_not_observed_before_timeout",
                    # missing command_template
                },
            },
            {
                "title": "Other",
                "payload": {
                    "recommendation": "review_security_validation_failures",
                },
            },
        ]
    )

    assert build_replay_lifecycle_retry_proposals_from_brief(brief) == []