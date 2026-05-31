from src.swarms.overseer.overseer_core.brief_builder import build_global_swarm_brief
from src.swarms.overseer.overseer_core.directive_emitter import build_directives_from_brief


def test_security_validation_critical_scenario_proposes_security_observation() -> None:
    brief = build_global_swarm_brief(
        snapshot={
            "active_swarm_counts": {"security": 1, "overseer": 1},
        },
        security_validation={
            "security_validation_records": 2,
            "security_validation_invalid_records": 2,
            "security_validation_critical_records": 1,
        },
    )

    directives = build_directives_from_brief(brief, source="overseer-test")

    assert brief.status == "critical"
    assert brief.key_metrics["security_validation_critical_records"] == 1
    assert any("Critical security validation" in item.get("title", "") for item in brief.risks)

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "OBSERVE"
    assert directive.target == "security"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-test"
    assert directive.payload["reason"] == "security_validation_failures_detected"
    assert directive.payload["security_validation_critical_records"] == 1
    assert directive.payload["security_validation_invalid_records"] == 2
    assert directive.payload["brief_id"] == brief.brief_id