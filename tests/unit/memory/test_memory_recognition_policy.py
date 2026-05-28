from src.memory.recognition import MemoryRecognizer, RecognitionLabel
from src.memory.recognition_policy import (
    MemoryRecognitionPolicy,
    RecognitionAction,
)


def actions_of(record: dict) -> set[RecognitionAction]:
    recognizer = MemoryRecognizer()
    policy = MemoryRecognitionPolicy()
    result = recognizer.recognize(record)
    decision = policy.decide(result)
    return set(decision.actions)


def test_policy_marks_valuable_as_gold_candidate() -> None:
    actions = actions_of(
        {
            "kind": "fact",
            "payload": {"message": "test_green milestone validated"},
            "verified": True,
            "confidence": 0.95,
        }
    )

    assert RecognitionAction.STORE in actions
    assert RecognitionAction.GOLD_CANDIDATE in actions


def test_policy_marks_dangerous_as_alert_and_review() -> None:
    recognizer = MemoryRecognizer()
    policy = MemoryRecognitionPolicy()

    result = recognizer.recognize(
        {
            "kind": "event",
            "payload": {"message": "private_key leak detected"},
            "confidence": 0.9,
        }
    )
    decision = policy.decide(result)

    assert result.label == RecognitionLabel.DANGEROUS
    assert RecognitionAction.STORE in decision.actions
    assert RecognitionAction.ALERT in decision.actions
    assert RecognitionAction.REVIEW in decision.actions
    assert RecognitionAction.QUARANTINE_CANDIDATE in decision.actions
    assert decision.severity == "critical"


def test_policy_marks_suspicious_as_review() -> None:
    actions = actions_of(
        {
            "kind": "observation",
            "payload": {"message": "unexpected anomaly from unknown source"},
            "confidence": 0.2,
        }
    )

    assert RecognitionAction.STORE in actions
    assert RecognitionAction.REVIEW in actions
    assert RecognitionAction.QUARANTINE_CANDIDATE in actions


def test_policy_marks_duplicate_as_dedupe_and_compress_candidate() -> None:
    recognizer = MemoryRecognizer()
    policy = MemoryRecognitionPolicy()

    existing = [
        {
            "id": "old-1",
            "kind": "event",
            "payload": {"message": "same simulation memory event"},
            "confidence": 0.95,
        }
    ]

    result = recognizer.recognize(
        {
            "id": "new-1",
            "kind": "event",
            "payload": {"message": "same simulation memory event"},
            "confidence": 0.95,
        },
        existing,
    )
    decision = policy.decide(result)

    assert result.label == RecognitionLabel.DUPLICATE
    assert RecognitionAction.DEDUPE_CANDIDATE in decision.actions
    assert RecognitionAction.COMPRESS_CANDIDATE in decision.actions


def test_policy_decision_is_serializable() -> None:
    recognizer = MemoryRecognizer()
    policy = MemoryRecognitionPolicy()

    result = recognizer.recognize(
        {
            "kind": "event",
            "payload": {"message": "new observation"},
        }
    )
    decision = policy.decide(result)
    data = decision.to_dict()

    assert "actions" in data
    assert "store" in data["actions"]
    assert data["severity"] in {"info", "warning", "critical"}