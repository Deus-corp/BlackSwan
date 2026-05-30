from src.memory.runtime_evidence import (
    classify_runtime_evidence_record,
    enrich_runtime_evidence_record,
    is_runtime_evidence_record,
)


def _record(status="passed", checks=None):
    return {
        "type": "memory_record",
        "kind": "runtime_evidence",
        "status": status,
        "subject": "runtime_directive_seed_check",
        "importance": 0.5,
        "tags": ["runtime_evidence"],
        "payload": {
            "directive_id": "runtime-reduce-risk-1",
            "checks": checks
            if checks is not None
            else [
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_result_published", "status": "passed"},
                {"name": "directive_applied", "status": "passed"},
            ],
        },
    }


def test_is_runtime_evidence_record() -> None:
    assert is_runtime_evidence_record(_record()) is True
    assert is_runtime_evidence_record({"type": "memory_record", "kind": "other"}) is False


def test_classify_passed_runtime_evidence_as_gold_candidate() -> None:
    classification = classify_runtime_evidence_record(_record())

    assert classification["is_runtime_evidence"] is True
    assert classification["valuable"] is True
    assert classification["gold_candidate"] is True
    assert classification["review_candidate"] is False
    assert classification["alert_candidate"] is False
    assert classification["passed_checks"] == 3
    assert classification["total_checks"] == 3
    assert classification["directive_id"] == "runtime-reduce-risk-1"


def test_classify_failed_runtime_evidence_as_alert_candidate() -> None:
    classification = classify_runtime_evidence_record(
        _record(
            status="failed",
            checks=[
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_result_published", "status": "failed"},
            ],
        )
    )

    assert classification["gold_candidate"] is False
    assert classification["alert_candidate"] is True
    assert classification["review_candidate"] is False
    assert classification["reason"] == "runtime_evidence_failed"


def test_classify_partial_runtime_evidence_as_review_candidate() -> None:
    classification = classify_runtime_evidence_record(
        _record(
            status="partial",
            checks=[
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_applied", "status": "failed"},
            ],
        )
    )

    assert classification["gold_candidate"] is False
    assert classification["review_candidate"] is True
    assert classification["alert_candidate"] is False


def test_enrich_runtime_evidence_record_adds_classification_tags_and_importance() -> None:
    enriched = enrich_runtime_evidence_record(_record())

    classification = enriched["payload"]["runtime_evidence_classification"]

    assert classification["gold_candidate"] is True
    assert "gold_candidate" in enriched["tags"]
    assert "directive:runtime-reduce-risk-1" in enriched["tags"]
    assert enriched["importance"] == 0.9