from src.security.directive_validation import (
    validate_evidence_record,
    validate_runtime_evidence_memory_record,
    validate_runtime_record,
    validate_swarm_directive,
    validate_swarm_directive_result,
)


def test_validate_safe_swarm_directive() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "dir-1",
            "action": "REDUCE_RISK",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {
                "dry_run": True,
                "execution_enabled": False,
            },
        }
    )

    assert result.valid is True
    assert result.severity == "info"
    assert result.reasons == []


def test_validate_swarm_directive_rejects_live_execution_enable() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "dir-unsafe",
            "action": "SET_DRY_RUN",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {
                "dry_run": False,
                "execution_enabled": True,
            },
        }
    )

    assert result.valid is False
    assert result.severity == "critical"
    assert "execution_enabled_not_allowed" in result.reasons


def test_validate_swarm_directive_rejects_unknown_action() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "dir-bad",
            "action": "ENABLE_LIVE_TRADING",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {},
        }
    )

    assert result.valid is False
    assert "unsafe_or_unknown_action" in result.reasons


def test_validate_swarm_directive_result() -> None:
    result = validate_swarm_directive_result(
        {
            "type": "swarm_directive_result",
            "directive_id": "dir-1",
            "status": "applied",
            "source": "trade-1",
            "swarm": "trade",
        }
    )

    assert result.valid is True


def test_validate_evidence_record() -> None:
    result = validate_evidence_record(
        {
            "type": "evidence_record",
            "evidence_id": "ev-1",
            "subject": "runtime_directive_seed_check",
            "status": "passed",
            "checks": [
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_applied", "status": "passed"},
            ],
        }
    )

    assert result.valid is True


def test_validate_runtime_evidence_memory_record() -> None:
    result = validate_runtime_evidence_memory_record(
        {
            "type": "memory_record",
            "memory_id": "mem-1",
            "kind": "runtime_evidence",
            "status": "passed",
            "payload": {
                "evidence_id": "ev-1",
                "directive_id": "dir-1",
                "checks": [
                    {"name": "directive_seeded", "status": "passed"},
                ],
            },
        }
    )

    assert result.valid is True


def test_validate_runtime_record_dispatches_by_type() -> None:
    result = validate_runtime_record(
        {
            "type": "evidence_record",
            "evidence_id": "ev-1",
            "subject": "runtime_directive_seed_check",
            "status": "passed",
            "checks": [],
        }
    )

    assert result.valid is True
    assert result.record_type == "evidence_record"


def test_validate_runtime_record_rejects_unsupported_type() -> None:
    result = validate_runtime_record({"type": "unknown"})

    assert result.valid is False
    assert result.severity == "warning"
    assert "unsupported_record_type" in result.reasons