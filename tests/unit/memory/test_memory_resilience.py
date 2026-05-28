from src.memory.resilience import (
    MemoryAvailability,
    MemoryHealth,
    MemoryLayer,
    MemoryResiliencePolicy,
)


def test_memory_policy_normal_write_targets() -> None:
    policy = MemoryResiliencePolicy()
    health = MemoryHealth()

    plan = policy.choose_write_targets(health)

    assert plan.write_targets == (
        MemoryLayer.LOCAL,
        MemoryLayer.OWN,
        MemoryLayer.SHARED,
    )
    assert plan.queue_for_later is False
    assert plan.degraded is False
    assert plan.reason == "ok"


def test_memory_policy_degrades_when_crdt_down() -> None:
    policy = MemoryResiliencePolicy()
    health = MemoryHealth(
        shared=MemoryAvailability.DEGRADED,
        crdt_available=False,
        last_error="crdt down",
    )

    plan = policy.choose_write_targets(health)

    assert plan.write_targets == (
        MemoryLayer.LOCAL,
        MemoryLayer.OWN,
    )
    assert plan.queue_for_later is True
    assert plan.degraded is True
    assert "shared_unavailable_or_crdt_down" in plan.reason


def test_memory_policy_read_order_without_memory_swarm() -> None:
    policy = MemoryResiliencePolicy()
    health = MemoryHealth(
        global_memory=MemoryAvailability.UNAVAILABLE,
        memory_swarm_seen=False,
    )

    plan = policy.choose_read_order(health)

    assert plan.read_order == (
        MemoryLayer.LOCAL,
        MemoryLayer.OWN,
        MemoryLayer.SHARED,
    )
    assert plan.degraded is True
    assert "memory_swarm_unseen" in plan.reason


def test_memory_policy_global_last_when_enabled() -> None:
    policy = MemoryResiliencePolicy(write_global=True)
    health = MemoryHealth()

    write_plan = policy.choose_write_targets(health)
    read_plan = policy.choose_read_order(health)

    assert write_plan.write_targets == (
        MemoryLayer.LOCAL,
        MemoryLayer.OWN,
        MemoryLayer.SHARED,
        MemoryLayer.GLOBAL,
    )
    assert read_plan.read_order[-1] == MemoryLayer.GLOBAL


def test_memory_policy_total_failure_has_empty_read_order() -> None:
    policy = MemoryResiliencePolicy()
    health = MemoryHealth(
        local=MemoryAvailability.UNAVAILABLE,
        own=MemoryAvailability.UNAVAILABLE,
        shared=MemoryAvailability.UNAVAILABLE,
        global_memory=MemoryAvailability.UNAVAILABLE,
        memory_swarm_seen=False,
        crdt_available=False,
    )

    plan = policy.choose_read_order(health)

    assert plan.read_order == ()
    assert plan.degraded is True
    assert "no_memory_layers_available" in plan.reason


def test_memory_policy_combined_plan_is_serializable() -> None:
    policy = MemoryResiliencePolicy()
    health = MemoryHealth(crdt_available=False)

    plan = policy.plan(health)

    assert plan["health"]["crdt_available"] is False
    assert plan["write"]["queue_for_later"] is True
    assert plan["read"]["degraded"] is True