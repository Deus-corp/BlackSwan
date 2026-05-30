from src.swarms.overseer.overseer_core.brief_builder import build_global_swarm_brief
from src.swarms.overseer.overseer_core.collector import collect_memory_intelligence_from_heartbeats
from src.swarms.overseer.overseer_core.directive_emitter import build_directives_from_brief


def test_runtime_evidence_gold_scenario_proposes_memory_promotion() -> None:
    memory_intelligence = collect_memory_intelligence_from_heartbeats(
        [
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "node_id": "memory-1",
                "timestamp": 1.0,
                "status": "running",
                "metrics": {
                    "memory_summary": {
                        "total_records": 1,
                        "recognized_records": 1,
                        "gold_candidates": 0,
                        "review_candidates": 0,
                        "alert_candidates": 0,
                        "dedupe_candidates": 0,
                        "runtime_evidence_records": 1,
                        "runtime_evidence_gold_candidates": 1,
                        "runtime_evidence_review_candidates": 0,
                        "runtime_evidence_alert_candidates": 0,
                    }
                },
            }
        ]
    )

    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"memory": 1, "overseer": 1}},
        memory_intelligence=memory_intelligence,
    )

    directives = build_directives_from_brief(brief, source="overseer-test")

    assert memory_intelligence["aggregate"]["status"] == "valuable_activity"
    assert memory_intelligence["aggregate"]["reason"] == "runtime_evidence_gold_candidates_detected"

    assert brief.status == "healthy"
    assert brief.key_metrics["memory_runtime_evidence_gold_candidates"] == 1
    assert any("Runtime evidence" in item.get("title", "") for item in brief.opportunities)

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "PROMOTE_GOLD_CANDIDATES"
    assert directive.target == "memory"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-test"
    assert directive.payload["reason"] == "runtime_evidence_gold_candidates_detected"
    assert directive.payload["runtime_evidence_gold_candidates"] == 1
    assert directive.payload["brief_id"] == brief.brief_id


def test_runtime_evidence_alert_scenario_proposes_memory_observation() -> None:
    memory_intelligence = collect_memory_intelligence_from_heartbeats(
        [
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "node_id": "memory-1",
                "timestamp": 1.0,
                "status": "running",
                "metrics": {
                    "memory_summary": {
                        "total_records": 1,
                        "recognized_records": 1,
                        "gold_candidates": 0,
                        "review_candidates": 0,
                        "alert_candidates": 0,
                        "dedupe_candidates": 0,
                        "runtime_evidence_records": 1,
                        "runtime_evidence_gold_candidates": 0,
                        "runtime_evidence_review_candidates": 0,
                        "runtime_evidence_alert_candidates": 1,
                    }
                },
            }
        ]
    )

    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"memory": 1, "overseer": 1}},
        memory_intelligence=memory_intelligence,
    )

    directives = build_directives_from_brief(brief, source="overseer-test")

    assert memory_intelligence["aggregate"]["status"] == "danger_detected"
    assert memory_intelligence["aggregate"]["reason"] == "runtime_evidence_alert_candidates_detected"

    assert brief.status == "degraded"
    assert brief.key_metrics["memory_runtime_evidence_alert_candidates"] == 1
    assert any("Runtime evidence alerts" in item.get("title", "") for item in brief.risks)

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "OBSERVE"
    assert directive.target == "memory"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-test"
    assert directive.payload["reason"] == "runtime_evidence_alert_candidates_detected"
    assert directive.payload["runtime_evidence_alert_candidates"] == 1
    assert directive.payload["brief_id"] == brief.brief_id