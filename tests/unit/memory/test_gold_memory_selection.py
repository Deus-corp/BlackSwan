from src.memory.gold_filter import (
    ExperienceSample,
    memory_record_to_experience_sample,
    select_gold_memory_samples,
)


def test_memory_record_to_experience_sample_from_gold_candidate() -> None:
    record = {
        "id": "mem-1",
        "kind": "fact",
        "scope": "shared",
        "topic": "milestone",
        "payload": {
            "message": "test_green milestone validated",
            "recognition": {
                "label": "valuable",
                "confidence": 0.75,
                "value_score": 0.75,
            },
            "recognition_policy": {
                "actions": ["store", "gold_candidate"],
                "severity": "info",
                "reason": "valuable_memory_detected",
                "labels": ["valuable", "value:high"],
            },
        },
        "source": {
            "originNodeId": "simulation-1",
            "swarm": "simulation",
        },
        "confidence": 0.95,
    }

    sample = memory_record_to_experience_sample(record)

    assert isinstance(sample, ExperienceSample)
    assert sample.score >= 0.75
    assert "milestone" in sample.instruction
    assert sample.output_text == "test_green milestone validated"
    assert sample.meta["record_id"] == "mem-1"
    assert sample.meta["swarm"] == "simulation"


def test_memory_record_to_experience_sample_ignores_non_gold_candidate() -> None:
    record = {
        "id": "mem-1",
        "kind": "event",
        "payload": {
            "message": "ordinary event",
            "recognition_policy": {
                "actions": ["store"],
            },
        },
    }

    assert memory_record_to_experience_sample(record) is None


def test_select_gold_memory_samples_deduplicates_samples() -> None:
    record = {
        "id": "mem-1",
        "kind": "fact",
        "scope": "shared",
        "topic": "milestone",
        "payload": {
            "message": "same validated milestone",
            "recognition": {
                "label": "valuable",
                "value_score": 0.8,
            },
            "recognition_policy": {
                "actions": ["store", "gold_candidate"],
            },
        },
    }

    samples = select_gold_memory_samples([record, {**record, "id": "mem-2"}])

    assert len(samples) == 1
    assert samples[0].score == 0.8