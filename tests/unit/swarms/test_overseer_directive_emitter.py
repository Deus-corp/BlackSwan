from src.swarms.common.protocols.briefs import build_brief_item, build_swarm_brief
from src.swarms.common.protocols.directives import DirectiveTargetType
from src.swarms.overseer.overseer_core.directive_emitter import build_directives_from_brief


def test_build_directives_from_brief_emits_memory_gold_directive() -> None:
    brief = build_swarm_brief(
        brief_id="brief-1",
        scope="global",
        status="healthy",
        summary="memory has gold",
        recommended_actions=[
            build_brief_item(
                title="promote memory gold candidates",
                payload={"directive": "PROMOTE_GOLD_CANDIDATES"},
            )
        ],
    )

    directives = build_directives_from_brief(brief)

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "PROMOTE_GOLD_CANDIDATES"
    assert directive.target_type == DirectiveTargetType.SWARM.value
    assert directive.target == "memory"
    assert directive.payload["brief_id"] == "brief-1"


def test_build_directives_from_brief_emits_trade_reduce_risk_directive() -> None:
    brief = build_swarm_brief(
        brief_id="brief-2",
        scope="global",
        status="degraded",
        summary="trade risk elevated",
        recommended_actions=[
            build_brief_item(
                title="reduce trade risk",
                severity="warning",
                payload={"directive": "REDUCE_RISK"},
            )
        ],
    )

    directives = build_directives_from_brief(brief)

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "REDUCE_RISK"
    assert directive.target == "trade"
    assert directive.payload["dry_run"] is True
    assert directive.payload["execution_enabled"] is False


def test_build_directives_from_brief_ignores_unknown_directives() -> None:
    brief = build_swarm_brief(
        brief_id="brief-3",
        scope="global",
        status="healthy",
        summary="unknown action",
        recommended_actions=[
            build_brief_item(
                title="unknown",
                payload={"directive": "ENABLE_EXECUTION"},
            )
        ],
    )

    assert build_directives_from_brief(brief) == []

def test_build_directives_from_brief_emits_runtime_evidence_gold_directive() -> None:
    from src.swarms.common.protocols.briefs import build_swarm_brief

    brief = build_swarm_brief(
        scope="global",
        status="healthy",
        swarm="overseer",
        summary="Memory has verified runtime evidence.",
        recommended_actions=[
            {
                "title": "Promote runtime evidence",
                "payload": {
                    "directive": "PROMOTE_GOLD_CANDIDATES",
                    "target_swarm": "memory",
                    "runtime_evidence_gold_candidates": 1,
                },
            }
        ],
    )

    directives = build_directives_from_brief(brief, source="overseer-1")

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "PROMOTE_GOLD_CANDIDATES"
    assert directive.target == "memory"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-1"
    assert directive.payload["reason"] == "runtime_evidence_gold_candidates_detected"
    assert directive.payload["runtime_evidence_gold_candidates"] == 1

def test_build_directives_from_brief_emits_runtime_evidence_alert_observe() -> None:
    from src.swarms.common.protocols.briefs import build_swarm_brief

    brief = build_swarm_brief(
        scope="global",
        status="degraded",
        swarm="overseer",
        summary="Memory has runtime evidence alerts.",
        recommended_actions=[
            {
                "title": "Review runtime evidence alerts",
                "payload": {
                    "recommendation": "review_runtime_evidence_alerts",
                    "target_swarm": "memory",
                    "runtime_evidence_alert_candidates": 1,
                },
            }
        ],
    )

    directives = build_directives_from_brief(brief, source="overseer-1")

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "OBSERVE"
    assert directive.target == "memory"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-1"
    assert directive.payload["reason"] == "runtime_evidence_alert_candidates_detected"
    assert directive.payload["runtime_evidence_alert_candidates"] == 1
    assert directive.payload["brief_id"] == brief.brief_id
    assert "reason_item" in directive.payload

def test_build_directives_from_brief_emits_security_validation_observe() -> None:
    from src.swarms.common.protocols.briefs import build_swarm_brief

    brief = build_swarm_brief(
        scope="global",
        status="critical",
        swarm="overseer",
        summary="Security validation failure.",
        recommended_actions=[
            {
                "title": "Review security validation failures",
                "payload": {
                    "recommendation": "review_security_validation_failures",
                    "target_swarm": "security",
                    "security_validation_critical_records": 1,
                    "security_validation_invalid_records": 2,
                },
            }
        ],
    )

    directives = build_directives_from_brief(brief, source="overseer-1")

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "OBSERVE"
    assert directive.target == "security"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-1"
    assert directive.payload["brief_id"] == brief.brief_id
    assert directive.payload["reason"] == "security_validation_failures_detected"
    assert directive.payload["security_validation_critical_records"] == 1
    assert directive.payload["security_validation_invalid_records"] == 2
    assert "reason_item" in directive.payload

def test_build_directives_from_brief_emits_simulation_replay_observe() -> None:
    from src.swarms.common.protocols.briefs import build_swarm_brief

    brief = build_swarm_brief(
        scope="global",
        status="healthy",
        swarm="overseer",
        summary="Simulation has pending replay scenarios.",
        recommended_actions=[
            {
                "title": "Observe simulation replay queue",
                "payload": {
                    "recommendation": "observe_simulation_replay",
                    "target_swarm": "simulation",
                    "simulation_replay_pending": 2,
                },
            }
        ],
    )

    directives = build_directives_from_brief(brief, source="overseer-1")

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "OBSERVE"
    assert directive.target == "simulation"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-1"
    assert directive.payload["brief_id"] == brief.brief_id
    assert directive.payload["reason"] == "simulation_replay_pending_detected"
    assert directive.payload["simulation_replay_pending"] == 2
    assert "reason_item" in directive.payload