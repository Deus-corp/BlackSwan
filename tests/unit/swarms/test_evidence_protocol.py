import pytest

from src.swarms.common.protocols.evidence import (
    EvidenceCheck,
    EvidenceRecord,
    EvidenceSeverity,
    EvidenceStatus,
    build_evidence_check,
    build_evidence_record,
    evidence_to_record,
    normalize_evidence_record,
    normalize_severity,
    normalize_status,
)


def test_build_evidence_check_normalizes_fields() -> None:
    check = build_evidence_check(
        name=" pytest ",
        status="PASSED",
        value="236 passed",
        detail="unit suite green",
        payload={"duration": 39.88},
    )

    assert check.name == "pytest"
    assert check.status == EvidenceStatus.PASSED.value
    assert check.value == "236 passed"
    assert check.detail == "unit suite green"
    assert check.payload == {"duration": 39.88}


def test_build_evidence_record_normalizes_fields() -> None:
    check = build_evidence_check(name="runtime_smoke", status="passed")

    evidence = build_evidence_record(
        evidence_id="ev-1",
        subject="runtime_directive_seed_check",
        source="trade-1",
        status="PASSED",
        confidence=1.5,
        severity="WARNING",
        checks=[check],
        payload={"directive_id": "runtime-reduce-risk-1"},
        created_at=10.0,
    )

    assert evidence.evidence_id == "ev-1"
    assert evidence.subject == "runtime_directive_seed_check"
    assert evidence.source == "trade-1"
    assert evidence.status == EvidenceStatus.PASSED.value
    assert evidence.confidence == 1.0
    assert evidence.severity == EvidenceSeverity.WARNING.value
    assert evidence.checks == [check.to_dict()]
    assert evidence.created_at == 10.0


def test_normalize_evidence_record_accepts_raw_mapping_aliases() -> None:
    evidence = normalize_evidence_record(
        {
            "id": "ev-2",
            "subject": "seed_check",
            "source": "test",
            "status": "partial",
            "confidence": 0.75,
            "checks": [
                {"name": "seeded_directive", "status": "passed", "value": True},
                {"name": "", "status": "failed"},
            ],
            "timestamp": 11.0,
        }
    )

    assert isinstance(evidence, EvidenceRecord)
    assert evidence.evidence_id == "ev-2"
    assert evidence.status == EvidenceStatus.PARTIAL.value
    assert evidence.confidence == 0.75
    assert evidence.checks == [
        {
            "name": "seeded_directive",
            "status": EvidenceStatus.PASSED.value,
            "value": True,
            "detail": "",
            "payload": {},
        }
    ]
    assert evidence.created_at == 11.0


def test_evidence_to_record_is_crdt_friendly() -> None:
    evidence = build_evidence_record(
        evidence_id="ev-3",
        subject="directive_result",
        source="trade-1",
        status="passed",
        confidence=0.9,
        created_at=12.0,
    )

    record = evidence_to_record(evidence)

    assert record["type"] == "evidence_record"
    assert record["evidence_id"] == "ev-3"
    assert record["subject"] == "directive_result"
    assert record["status"] == EvidenceStatus.PASSED.value
    assert record["confidence"] == 0.9
    assert record["created_at"] == 12.0


def test_invalid_evidence_required_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="subject"):
        build_evidence_record(
            evidence_id="ev-bad",
            subject="",
            source="test",
        )


def test_normalizers_fallback_to_safe_defaults() -> None:
    assert normalize_status("bad") == EvidenceStatus.UNKNOWN.value
    assert normalize_severity("bad") == EvidenceSeverity.INFO.value