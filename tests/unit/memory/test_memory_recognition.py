from src.memory.recognition import (
    MemoryRecognizer,
    RecognitionLabel,
    canonical_fingerprint,
)


def test_memory_recognizer_marks_duplicate_record() -> None:
    recognizer = MemoryRecognizer()

    existing = [
        {
            "id": "old-1",
            "kind": "event",
            "payload": {"message": "simulation scenario completed"},
            "confidence": 0.9,
        }
    ]

    result = recognizer.recognize(
        {
            "id": "new-1",
            "kind": "event",
            "payload": {"message": "simulation scenario completed"},
            "confidence": 0.9,
        },
        existing,
    )

    assert result.label == RecognitionLabel.DUPLICATE
    assert result.familiarity_score >= 0.98


def test_memory_recognizer_marks_dangerous_record() -> None:
    recognizer = MemoryRecognizer()

    result = recognizer.recognize(
        {
            "kind": "event",
            "payload": {"message": "private_key leak detected"},
            "confidence": 0.9,
        }
    )

    assert result.label == RecognitionLabel.DANGEROUS
    assert result.risk_score >= 0.75


def test_memory_recognizer_marks_suspicious_low_confidence_record() -> None:
    recognizer = MemoryRecognizer()

    result = recognizer.recognize(
        {
            "kind": "observation",
            "payload": {"message": "unexpected anomaly from unknown source"},
            "confidence": 0.2,
        }
    )

    assert result.label == RecognitionLabel.SUSPICIOUS
    assert result.confidence >= 0.5


def test_memory_recognizer_marks_verified_record_as_valuable() -> None:
    recognizer = MemoryRecognizer()

    result = recognizer.recognize(
        {
            "kind": "fact",
            "payload": {"message": "test_green milestone validated"},
            "verified": True,
            "confidence": 0.9,
        }
    )

    assert result.label == RecognitionLabel.VALUABLE
    assert result.value_score >= 0.75


def test_memory_recognizer_marks_related_record_as_familiar() -> None:
    recognizer = MemoryRecognizer()

    existing = [
        {
            "id": "arch-1",
            "kind": "fact",
            "topic": "architecture",
            "payload": {"message": "BlackSwan uses memory swarm and simulation swarm"},
        }
    ]

    result = recognizer.recognize(
        {
            "kind": "fact",
            "topic": "architecture",
            "payload": {"message": "simulation swarm publishes memory records"},
        },
        existing,
    )

    assert result.label in {RecognitionLabel.FAMILIAR, RecognitionLabel.NEW}
    assert result.familiarity_score > 0.0


def test_memory_recognizer_marks_unrelated_record_as_new() -> None:
    recognizer = MemoryRecognizer()

    result = recognizer.recognize(
        {
            "kind": "event",
            "payload": {"message": "first observation about a new module"},
            "confidence": 0.9,
        },
        existing_records=[],
    )

    assert result.label == RecognitionLabel.NEW
    assert result.novelty_score >= 0.9


def test_canonical_fingerprint_ignores_unstable_timestamps() -> None:
    left = {
        "id": "a",
        "payload": {"message": "same"},
        "timestamp": 1,
    }
    right = {
        "id": "a",
        "payload": {"message": "same"},
        "timestamp": 999,
    }

    assert canonical_fingerprint(left) == canonical_fingerprint(right)


def test_recognition_result_is_serializable() -> None:
    recognizer = MemoryRecognizer()
    result = recognizer.recognize(
        {
            "kind": "event",
            "payload": {"message": "validated release milestone"},
            "verified": True,
        }
    )

    data = result.to_dict()

    assert data["label"] in {label.value for label in RecognitionLabel}
    assert "signals" in data
    assert "fingerprint" in data

def test_canonical_fingerprint_ignores_recognition_annotations() -> None:
    raw = {
        "kind": "event",
        "scope": "shared",
        "payload": {"message": "same simulation memory event"},
        "source": {"originNodeId": "simulation-1", "swarm": "simulation"},
    }

    annotated = {
        "kind": "event",
        "scope": "shared",
        "payload": {
            "message": "same simulation memory event",
            "recognition": {
                "label": "new",
                "confidence": 1.0,
            },
            "tags": ["recognition:new", "risk:low"],
        },
        "source": {
            "originNodeId": "simulation-1",
            "swarm": "simulation",
            "recognition_label": "new",
            "recognition_confidence": 1.0,
        },
    }

    assert canonical_fingerprint(raw) == canonical_fingerprint(annotated)