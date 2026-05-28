from src.swarms.overseer.overseer_core.memory_intelligence import (
    MemoryIntelligenceStatus,
    aggregate_memory_assessments,
    assess_memory_heartbeat,
)


def test_assess_memory_heartbeat_with_gold_candidates() -> None:
    payload = {
        "type": "swarm_heartbeat",
        "swarm": "memory",
        "status": "running",
        "metrics": {
            "memory_summary": {
                "total_records": 3,
                "recognized_records": 2,
                "gold_candidates": 2,
                "review_candidates": 0,
                "alert_candidates": 0,
                "dedupe_candidates": 0,
                "degraded": False,
                "reason": "ok",
            }
        },
    }

    assessment = assess_memory_heartbeat(payload)

    assert assessment.status == MemoryIntelligenceStatus.VALUABLE_ACTIVITY
    assert assessment.total_records == 3
    assert assessment.gold_candidates == 2
    assert assessment.reason == "memory_gold_candidates_detected"


def test_assess_memory_heartbeat_with_alert_candidates() -> None:
    payload = {
        "status": "running",
        "metrics": {
            "memory_summary": {
                "total_records": 5,
                "recognized_records": 5,
                "gold_candidates": 1,
                "review_candidates": 1,
                "alert_candidates": 1,
            }
        },
    }

    assessment = assess_memory_heartbeat(payload)

    assert assessment.status == MemoryIntelligenceStatus.DANGER_DETECTED
    assert assessment.alert_candidates == 1
    assert assessment.reason == "memory_alert_candidates_detected"


def test_assess_memory_heartbeat_degraded_status_wins() -> None:
    payload = {
        "status": "degraded",
        "metrics": {
            "memory_summary": {
                "total_records": 10,
                "gold_candidates": 3,
                "degraded": True,
                "reason": "crdt_down",
            }
        },
    }

    assessment = assess_memory_heartbeat(payload)

    assert assessment.status == MemoryIntelligenceStatus.DEGRADED
    assert assessment.degraded is True
    assert assessment.reason == "crdt_down"


def test_aggregate_memory_assessments_prioritizes_alerts() -> None:
    first = assess_memory_heartbeat(
        {
            "status": "running",
            "metrics": {
                "memory_summary": {
                    "total_records": 2,
                    "recognized_records": 2,
                    "gold_candidates": 2,
                }
            },
        }
    )
    second = assess_memory_heartbeat(
        {
            "status": "running",
            "metrics": {
                "memory_summary": {
                    "total_records": 1,
                    "recognized_records": 1,
                    "alert_candidates": 1,
                }
            },
        }
    )

    aggregate = aggregate_memory_assessments([first, second])

    assert aggregate.status == MemoryIntelligenceStatus.DANGER_DETECTED
    assert aggregate.total_records == 3
    assert aggregate.gold_candidates == 2
    assert aggregate.alert_candidates == 1


def test_aggregate_memory_assessments_empty_is_unknown_degraded() -> None:
    aggregate = aggregate_memory_assessments([])

    assert aggregate.status == MemoryIntelligenceStatus.UNKNOWN
    assert aggregate.degraded is True
    assert aggregate.reason == "no_memory_heartbeats"

def test_assess_memory_heartbeat_with_wrapped_metrics_payload() -> None:
    payload = {
        "type": "swarm_heartbeat",
        "swarm": "memory",
        "status": "running",
        "payload": {
            "metrics": {
                "memory_summary": {
                    "total_records": 3,
                    "recognized_records": 2,
                    "gold_candidates": 2,
                    "review_candidates": 0,
                    "alert_candidates": 0,
                    "dedupe_candidates": 0,
                }
            }
        },
    }

    assessment = assess_memory_heartbeat(payload)

    assert assessment.status == MemoryIntelligenceStatus.VALUABLE_ACTIVITY
    assert assessment.gold_candidates == 2