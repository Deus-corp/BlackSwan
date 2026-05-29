import pytest

from src.swarms.common.protocols.directives import (
    Directive,
    DirectiveResult,
    DirectiveSeverity,
    DirectiveStatus,
    DirectiveTargetType,
    build_directive,
    build_directive_result,
    directive_is_expired,
    directive_result_to_record,
    directive_targets_node,
    directive_targets_swarm,
    directive_to_record,
    normalize_directive,
    normalize_directive_result,
    normalize_severity,
    normalize_status,
    normalize_target_type,
)


def test_build_directive_normalizes_fields() -> None:
    directive = build_directive(
        directive_id="dir-1",
        action=" reduce_risk ",
        source="overseer",
        target_type="SWARM",
        target=" trade ",
        payload={"dry_run": True},
        reason="risk elevated",
        severity="WARNING",
        ttl_ms=1000,
        created_at=10.0,
    )

    assert directive.directive_id == "dir-1"
    assert directive.action == "REDUCE_RISK"
    assert directive.source == "overseer"
    assert directive.target_type == DirectiveTargetType.SWARM.value
    assert directive.target == "trade"
    assert directive.payload == {"dry_run": True}
    assert directive.reason == "risk elevated"
    assert directive.severity == DirectiveSeverity.WARNING.value
    assert directive.status == DirectiveStatus.ISSUED.value
    assert directive.ttl_ms == 1000
    assert directive.created_at == 10.0


def test_normalize_directive_accepts_aliases() -> None:
    directive = normalize_directive(
        {
            "id": "dir-2",
            "command_type": "set_dry_run",
            "source_swarm": "overseer",
            "target_swarm": "trade",
            "payload": {"enabled": True},
            "timestamp": 11.0,
        }
    )

    assert isinstance(directive, Directive)
    assert directive.directive_id == "dir-2"
    assert directive.action == "SET_DRY_RUN"
    assert directive.source == "overseer"
    assert directive.target_type == DirectiveTargetType.SWARM.value
    assert directive.target == "trade"
    assert directive.created_at == 11.0


def test_directive_targeting_helpers() -> None:
    global_directive = build_directive(
        directive_id="dir-global",
        action="OBSERVE",
        source="overseer",
        target_type="global",
        target="*",
    )
    swarm_directive = build_directive(
        directive_id="dir-swarm",
        action="REDUCE_RISK",
        source="overseer",
        target_type="swarm",
        target="trade",
    )
    node_directive = build_directive(
        directive_id="dir-node",
        action="PAUSE",
        source="overseer",
        target_type="node",
        target="trade-1",
    )
    capability_directive = build_directive(
        directive_id="dir-cap",
        action="EXPORT_GOLD",
        source="overseer",
        target_type="capability",
        target="gold_export",
    )

    assert directive_targets_swarm(global_directive, swarm="memory") is True
    assert directive_targets_swarm(swarm_directive, swarm="trade") is True
    assert directive_targets_swarm(swarm_directive, swarm="memory") is False

    assert directive_targets_node(global_directive, swarm="security", node_id="sec-1") is True
    assert directive_targets_node(swarm_directive, swarm="trade", node_id="trade-2") is True
    assert directive_targets_node(node_directive, swarm="trade", node_id="trade-1") is True
    assert directive_targets_node(node_directive, swarm="trade", node_id="trade-2") is False
    assert directive_targets_node(
        capability_directive,
        swarm="memory",
        node_id="memory-1",
        capabilities=["gold_export"],
    ) is True


def test_directive_expiration() -> None:
    directive = build_directive(
        directive_id="dir-exp",
        action="OBSERVE",
        source="overseer",
        target_type="global",
        target="*",
        ttl_ms=1000,
        created_at=10.0,
    )

    assert directive_is_expired(directive, now=10.5) is False
    assert directive_is_expired(directive, now=11.1) is True


def test_directive_to_record_is_crdt_friendly() -> None:
    directive = build_directive(
        directive_id="dir-record",
        action="OBSERVE",
        source="overseer",
        target_type="global",
        target="*",
        created_at=12.0,
    )

    record = directive_to_record(directive)

    assert record["type"] == "swarm_directive"
    assert record["directive_id"] == "dir-record"
    assert record["action"] == "OBSERVE"
    assert record["status"] == DirectiveStatus.ISSUED.value


def test_build_directive_result_normalizes_fields() -> None:
    result = build_directive_result(
        result_id="res-1",
        directive_id="dir-1",
        status="APPLIED",
        source="trade-1",
        swarm="trade",
        node_id="trade-1",
        message="dry-run enabled",
        payload={"dry_run": True},
        created_at=13.0,
    )

    assert isinstance(result, DirectiveResult)
    assert result.result_id == "res-1"
    assert result.directive_id == "dir-1"
    assert result.status == DirectiveStatus.APPLIED.value
    assert result.source == "trade-1"
    assert result.swarm == "trade"
    assert result.node_id == "trade-1"
    assert result.payload == {"dry_run": True}
    assert result.created_at == 13.0


def test_normalize_directive_result_accepts_raw_mapping() -> None:
    result = normalize_directive_result(
        {
            "id": "res-2",
            "directive_id": "dir-2",
            "status": "acknowledged",
            "source": "memory-1",
            "source_swarm": "memory",
            "source_node": "memory-1",
            "message": "accepted",
            "timestamp": 14.0,
        }
    )

    assert result.result_id == "res-2"
    assert result.directive_id == "dir-2"
    assert result.status == DirectiveStatus.ACKNOWLEDGED.value
    assert result.swarm == "memory"
    assert result.node_id == "memory-1"
    assert result.created_at == 14.0


def test_directive_result_to_record_is_crdt_friendly() -> None:
    result = build_directive_result(
        result_id="res-record",
        directive_id="dir-record",
        status="applied",
        source="trade-1",
        swarm="trade",
        created_at=15.0,
    )

    record = directive_result_to_record(result)

    assert record["type"] == "swarm_directive_result"
    assert record["result_id"] == "res-record"
    assert record["directive_id"] == "dir-record"
    assert record["status"] == DirectiveStatus.APPLIED.value


def test_invalid_directive_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="action"):
        build_directive(
            directive_id="bad",
            action="",
            source="overseer",
            target_type="global",
            target="*",
        )


def test_normalizers_fallback_to_safe_defaults() -> None:
    assert normalize_status("bad") == DirectiveStatus.ISSUED.value
    assert normalize_severity("bad") == DirectiveSeverity.INFO.value
    assert normalize_target_type("bad") == DirectiveTargetType.GLOBAL.value