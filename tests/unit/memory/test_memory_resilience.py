from src.memory.resilience import (
    MemoryAvailability,
    MemoryHealth,
    MemoryLayer,
    MemoryResiliencePolicy,
    MemoryResilienceStatus,
    assess_memory_resilience,
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

def test_memory_resilience_assessment_primary_ok() -> None:
    assessment = assess_memory_resilience(
        MemoryHealth(),
        total_records=3,
        shared_seen_records=2,
        shared_accepted_records=2,
        shared_rejected_records=0,
        shared_skipped_records=3,
    )

    assert assessment.status == MemoryResilienceStatus.PRIMARY_OK
    assert assessment.degraded is False
    assert assessment.reason == "ok"


def test_memory_resilience_assessment_recovery_needed_when_crdt_down() -> None:
    assessment = assess_memory_resilience(
        MemoryHealth(crdt_available=False),
        total_records=3,
    )

    assert assessment.status == MemoryResilienceStatus.RECOVERY_NEEDED
    assert assessment.recovery_needed is True
    assert assessment.degraded is True


def test_memory_resilience_assessment_bridge_lagging_when_no_progress() -> None:
    assessment = assess_memory_resilience(
        MemoryHealth(),
        total_records=3,
        shared_seen_records=3,
        shared_accepted_records=0,
        shared_rejected_records=0,
        shared_skipped_records=50,
    )

    assert assessment.status == MemoryResilienceStatus.SHARED_BRIDGE_LAGGING
    assert assessment.shared_bridge_lagging is True


def test_memory_resilience_assessment_fallback_active_when_memory_swarm_unseen() -> None:
    assessment = assess_memory_resilience(
        MemoryHealth(memory_swarm_seen=False),
        total_records=3,
    )

    assert assessment.status in {
        MemoryResilienceStatus.FALLBACK_ACTIVE,
        MemoryResilienceStatus.DEGRADED,
    }
    assert assessment.fallback_active is True


def test_memory_resilience_policy_still_routes_to_local_and_own_when_shared_down() -> None:
    policy = MemoryResiliencePolicy()
    health = MemoryHealth(shared=MemoryAvailability.UNAVAILABLE, crdt_available=False)

    plan = policy.choose_write_targets(health)

    assert "local" in plan.to_dict()["write_targets"]
    assert "own" in plan.to_dict()["write_targets"]
    assert plan.queue_for_later is True
    assert plan.degraded is True

def test_memory_resilience_assessment_not_lagging_when_accepting_records() -> None:
    assessment = assess_memory_resilience(
        MemoryHealth(),
        total_records=3,
        shared_seen_records=4,
        shared_accepted_records=1,
        shared_rejected_records=0,
        shared_skipped_records=100,
    )

    assert assessment.status == MemoryResilienceStatus.PRIMARY_OK
    assert assessment.shared_bridge_lagging is False