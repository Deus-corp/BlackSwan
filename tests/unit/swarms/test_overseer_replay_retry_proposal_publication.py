from types import SimpleNamespace

import pytest

from src.swarms.overseer.node import OverseerNode


class DummyCRDT:
    def __init__(self) -> None:
        self.state = {}
        self.published = []

    async def add_genome(self, payload):
        self.published.append(payload)
        self.state[payload["proposal_id"]] = payload


def make_node() -> OverseerNode:
    try:
        node = OverseerNode(node_id="overseer-test")
    except TypeError:
        node = OverseerNode()
        node.node_id = "overseer-test"

    node.crdt = DummyCRDT()
    return node


def retry_brief():
    return SimpleNamespace(
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


@pytest.mark.asyncio
async def test_overseer_publishes_replay_lifecycle_retry_proposal() -> None:
    node = make_node()

    published = await node._publish_replay_lifecycle_retry_proposals(retry_brief())

    assert published == 1
    assert node.crdt.published

    proposal = node.crdt.published[0]
    assert proposal["type"] == "replay_lifecycle_retry_proposal"
    assert proposal["status"] == "pending"
    assert proposal["source"] == "overseer-test"
    assert proposal["timeout_profile"] == "standard"


@pytest.mark.asyncio
async def test_overseer_skips_duplicate_replay_lifecycle_retry_proposal() -> None:
    node = make_node()

    first = await node._publish_replay_lifecycle_retry_proposals(retry_brief())
    second = await node._publish_replay_lifecycle_retry_proposals(retry_brief())

    assert first == 1
    assert second == 0
    assert len(node.crdt.published) == 1