from src.memory.summary import MemorySummary, build_memory_summary


def test_build_memory_summary_counts_recognition_and_actions() -> None:
    records = [
        {
            "kind": "fact",
            "scope": "shared",
            "payload": {
                "message": "test_green milestone validated",
                "recognition": {"label": "valuable"},
                "recognition_policy": {
                    "actions": ["store", "gold_candidate"],
                },
            },
        },
        {
            "kind": "event",
            "scope": "shared",
            "payload": {
                "message": "private_key leak detected",
                "recognition": {"label": "dangerous"},
                "recognition_policy": {
                    "actions": ["store", "alert", "review", "quarantine_candidate"],
                },
            },
        },
    ]

    summary = build_memory_summary(records)

    assert isinstance(summary, MemorySummary)
    assert summary.total_records == 2
    assert summary.recognized_records == 2
    assert summary.recognition_counts["valuable"] == 1
    assert summary.recognition_counts["dangerous"] == 1
    assert summary.gold_candidates == 1
    assert summary.alert_candidates == 1
    assert summary.review_candidates == 1
    assert summary.quarantine_candidates == 1
    assert summary.by_kind["fact"] == 1
    assert summary.by_kind["event"] == 1
    assert summary.by_scope["shared"] == 2


def test_build_memory_summary_uses_runtime_counters_when_provided() -> None:
    summary = build_memory_summary(
        [],
        total_records=10,
        recognition_counts={"valuable": 3},
        recognition_action_counts={"gold_candidate": 2, "dedupe_candidate": 1},
    )

    assert summary.total_records == 10
    assert summary.recognized_records == 3
    assert summary.gold_candidates == 2
    assert summary.dedupe_candidates == 1


def test_memory_summary_serializes_to_dict() -> None:
    summary = build_memory_summary(
        [],
        degraded=True,
        reason="memory_swarm_reindexing",
    )

    data = summary.to_dict()

    assert data["degraded"] is True
    assert data["reason"] == "memory_swarm_reindexing"
    assert data["total_records"] == 0