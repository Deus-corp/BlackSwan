import pytest

from src.swarms.common.protocols.briefs import (
    BriefScope,
    BriefSeverity,
    BriefStatus,
    SwarmBrief,
    brief_to_record,
    build_brief_item,
    build_swarm_brief,
    normalize_scope,
    normalize_severity,
    normalize_status,
    normalize_swarm_brief,
)


def test_build_swarm_brief_normalizes_fields() -> None:
    brief = build_swarm_brief(
        scope="SWARM",
        status="HEALTHY",
        swarm=" trade ",
        node_id=" trade-1 ",
        summary=" Trade is operational ",
        key_metrics={"capital": 1000.0},
        risks=[{"title": "none"}],
        opportunities=[{"title": "gold candidates"}],
        recommended_actions=[{"title": "observe"}],
        evidence_ids=[123, "abc"],
        brief_id="brief-1",
        created_at=10.0,
    )

    assert brief.brief_id == "brief-1"
    assert brief.scope == BriefScope.SWARM.value
    assert brief.status == BriefStatus.HEALTHY.value
    assert brief.swarm == "trade"
    assert brief.node_id == "trade-1"
    assert brief.summary == "Trade is operational"
    assert brief.key_metrics == {"capital": 1000.0}
    assert brief.evidence_ids == ["123", "abc"]
    assert brief.created_at == 10.0


def test_normalize_swarm_brief_accepts_raw_mapping_aliases() -> None:
    brief = normalize_swarm_brief(
        {
            "id": "brief-2",
            "scope": "node",
            "status": "degraded",
            "source_swarm": "memory",
            "source_node": "memory-1",
            "summary": "memory lag detected",
            "metrics": {"lag": 2},
            "actions": [{"title": "inspect"}],
            "timestamp": 11.0,
        }
    )

    assert isinstance(brief, SwarmBrief)
    assert brief.brief_id == "brief-2"
    assert brief.scope == BriefScope.NODE.value
    assert brief.status == BriefStatus.DEGRADED.value
    assert brief.swarm == "memory"
    assert brief.node_id == "memory-1"
    assert brief.key_metrics == {"lag": 2}
    assert brief.recommended_actions == [{"title": "inspect"}]
    assert brief.created_at == 11.0


def test_brief_to_record_is_crdt_friendly() -> None:
    brief = build_swarm_brief(
        brief_id="brief-3",
        scope="global",
        status="healthy",
        summary="all good",
        created_at=12.0,
    )

    record = brief_to_record(brief, source="overseer")

    assert record["type"] == "swarm_brief"
    assert record["brief_id"] == "brief-3"
    assert record["source"] == "overseer"
    assert record["scope"] == "global"
    assert record["status"] == "healthy"
    assert record["payload"]["summary"] == "all good"
    assert record["timestamp"] == 12.0


def test_build_brief_item_normalizes_severity() -> None:
    item = build_brief_item(
        title=" inspect memory ",
        severity="WARNING",
        detail="gold candidates increased",
        payload={"gold": 2},
    )

    assert item == {
        "title": "inspect memory",
        "severity": BriefSeverity.WARNING.value,
        "detail": "gold candidates increased",
        "payload": {"gold": 2},
    }


def test_invalid_brief_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="brief_id"):
        SwarmBrief(
            brief_id="",
            scope="global",
            status="healthy",
            summary="bad",
        )


def test_normalizers_fallback_to_safe_defaults() -> None:
    assert normalize_scope("bad") == BriefScope.GLOBAL.value
    assert normalize_status("bad") == BriefStatus.UNKNOWN.value
    assert normalize_severity("bad") == BriefSeverity.INFO.value