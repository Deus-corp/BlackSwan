import argparse

import pytest

from src.swarms.common.protocols.directives import DirectiveTargetType
from src.testing.seed_directive import SAFE_SEED_ACTIONS, seed_directive


@pytest.mark.asyncio
async def test_seed_directive_rejects_unsafe_action(tmp_path) -> None:
    args = argparse.Namespace(
        action="ENABLE_EXECUTION",
        target="trade",
        target_type=DirectiveTargetType.SWARM.value,
        source="test-seed",
        ttl_ms=300_000,
        directive_id="",
        db_path=str(tmp_path / "crdt.db"),
    )

    with pytest.raises(ValueError, match="Unsafe seed action"):
        await seed_directive(args)


@pytest.mark.asyncio
async def test_seed_directive_writes_safe_directive(tmp_path) -> None:
    args = argparse.Namespace(
        action="REDUCE_RISK",
        target="trade",
        target_type=DirectiveTargetType.SWARM.value,
        source="test-seed",
        ttl_ms=300_000,
        directive_id="dir-seed-test",
        db_path=str(tmp_path / "crdt.db"),
    )

    directive = await seed_directive(args)

    assert directive["type"] == "swarm_directive"
    assert directive["directive_id"] == "dir-seed-test"
    assert directive["action"] == "REDUCE_RISK"
    assert directive["target"] == "trade"
    assert directive["payload"]["dry_run"] is True
    assert directive["payload"]["execution_enabled"] is False
    assert "REDUCE_RISK" in SAFE_SEED_ACTIONS

@pytest.mark.asyncio
async def test_seed_directive_accepts_payload_json(tmp_path) -> None:
    args = argparse.Namespace(
        action="RUN_REPLAY",
        target="simulation",
        target_type=DirectiveTargetType.SWARM.value,
        source="overseer-seed",
        ttl_ms=120_000,
        directive_id="run-replay-seed-test",
        db_path=str(tmp_path / "crdt.db"),
        payload_json='{"scenario_id":"replay-runtime-reduce-risk-1","dry_run":true}',
    )

    directive = await seed_directive(args)

    assert directive["type"] == "swarm_directive"
    assert directive["directive_id"] == "run-replay-seed-test"
    assert directive["action"] == "RUN_REPLAY"
    assert directive["target"] == "simulation"
    assert directive["payload"]["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert directive["payload"]["dry_run"] is True

@pytest.mark.asyncio
async def test_seed_directive_rejects_invalid_payload_json(tmp_path) -> None:
    args = argparse.Namespace(
        action="RUN_REPLAY",
        target="simulation",
        target_type=DirectiveTargetType.SWARM.value,
        source="overseer-seed",
        ttl_ms=120_000,
        directive_id="run-replay-bad-json",
        db_path=str(tmp_path / "crdt.db"),
        payload_json="{bad-json",
    )

    with pytest.raises(ValueError, match="payload-json"):
        await seed_directive(args)