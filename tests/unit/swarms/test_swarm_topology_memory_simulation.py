from src.swarms.common import (
    command_allowed_for_swarm,
    is_advisory_swarm,
    is_known_role,
    is_known_swarm,
    known_swarms,
)


def test_memory_and_simulation_are_known_swarms() -> None:
    swarms = known_swarms()

    assert "memory" in swarms
    assert "simulation" in swarms
    assert is_known_swarm("memory")
    assert is_known_swarm("simulation")


def test_memory_and_simulation_are_advisory_swarms() -> None:
    assert is_advisory_swarm("memory")
    assert is_advisory_swarm("simulation")


def test_memory_and_simulation_roles_are_known() -> None:
    assert is_known_role("memory", "node")
    assert is_known_role("memory", "meta_agent")
    assert is_known_role("simulation", "node")
    assert is_known_role("simulation", "meta_agent")


def test_memory_and_simulation_commands_are_registered() -> None:
    assert command_allowed_for_swarm("memory", "CONSOLIDATE")
    assert command_allowed_for_swarm("memory", "EXPORT_GOLD_SAMPLES")
    assert command_allowed_for_swarm("simulation", "RUN_SCENARIO")
    assert command_allowed_for_swarm("simulation", "EVALUATE_POLICY")