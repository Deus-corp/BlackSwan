from src.swarms.security.runtime_validation import (
    build_security_validation_heartbeat_metrics,
    summarize_runtime_validations,
    validate_runtime_records,
)


def test_validate_runtime_records_accepts_valid_directive_chain_records() -> None:
    records = [
        {
            "type": "swarm_directive",
            "directive_id": "dir-1",
            "action": "REDUCE_RISK",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {"dry_run": True, "execution_enabled": False},
        },
        {
            "type": "swarm_directive_result",
            "directive_id": "dir-1",
            "status": "applied",
            "source": "trade-1",
            "swarm": "trade",
        },
        {
            "type": "evidence_record",
            "evidence_id": "ev-1",
            "subject": "runtime_directive_seed_check",
            "status": "passed",
            "checks": [{"name": "directive_seeded", "status": "passed"}],
            "payload": {"directive_id": "dir-1"},
        },
        {
            "type": "memory_record",
            "memory_id": "mem-1",
            "kind": "runtime_evidence",
            "status": "passed",
            "payload": {
                "evidence_id": "ev-1",
                "directive_id": "dir-1",
                "checks": [{"name": "directive_seeded", "status": "passed"}],
            },
        },
    ]

    validations = validate_runtime_records(records)

    assert len(validations) == 4
    assert all(item["valid"] for item in validations)
    assert {item["record_type"] for item in validations} == {
        "swarm_directive",
        "swarm_directive_result",
        "evidence_record",
        "memory_record",
    }


def test_validate_runtime_records_flags_unsafe_directive() -> None:
    records = [
        {
            "type": "swarm_directive",
            "directive_id": "dir-bad",
            "action": "SET_DRY_RUN",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {"dry_run": False, "execution_enabled": True},
        }
    ]

    validations = validate_runtime_records(records)

    assert len(validations) == 1
    assert validations[0]["valid"] is False
    assert validations[0]["severity"] == "critical"
    assert "execution_enabled_not_allowed" in validations[0]["reasons"]


def test_summarize_runtime_validations_counts_invalid_and_critical() -> None:
    validations = [
        {
            "type": "security_validation_result",
            "record_type": "swarm_directive",
            "valid": True,
            "severity": "info",
            "reasons": [],
        },
        {
            "type": "security_validation_result",
            "record_type": "swarm_directive",
            "valid": False,
            "severity": "critical",
            "reasons": ["execution_enabled_not_allowed"],
        },
    ]

    summary = summarize_runtime_validations(validations)

    assert summary["validated_records"] == 2
    assert summary["valid_records"] == 1
    assert summary["invalid_records"] == 1
    assert summary["critical_records"] == 1
    assert summary["severity_counts"]["critical"] == 1
    assert summary["invalid_reasons"]["execution_enabled_not_allowed"] == 1


def test_build_security_validation_heartbeat_metrics() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [
            {
                "type": "swarm_directive",
                "directive_id": "dir-1",
                "action": "OBSERVE",
                "source": "overseer",
                "target_type": "swarm",
                "target": "memory",
                "payload": {},
            },
            {
                "type": "swarm_directive",
                "directive_id": "dir-bad",
                "action": "ENABLE_LIVE_TRADING",
                "source": "overseer",
                "target_type": "swarm",
                "target": "trade",
                "payload": {},
            },
        ]
    )

    assert metrics["security_validation_records"] == 2
    assert metrics["security_validation_valid_records"] == 1
    assert metrics["security_validation_invalid_records"] == 1
    assert metrics["security_validation_critical_records"] == 1
    assert metrics["security_validation_record_type_counts"]["swarm_directive"] == 2
    assert metrics["security_validation_invalid_reasons"]["unsafe_or_unknown_action"] == 1


def test_validate_runtime_records_ignores_non_runtime_evidence_memory_records() -> None:
    validations = validate_runtime_records(
        [
            {
                "type": "memory_record",
                "memory_id": "mem-normal",
                "kind": "note",
                "status": "passed",
                "payload": {},
            }
        ]
    )

    assert validations == []