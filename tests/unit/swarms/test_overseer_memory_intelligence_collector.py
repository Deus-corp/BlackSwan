from src.swarms.overseer.overseer_core.collector import (
    collect_memory_intelligence_from_heartbeats,
)
from src.swarms.overseer.overseer_core.collector import find_memory_heartbeats_from_snapshot


def test_collector_builds_memory_intelligence_from_memory_heartbeats() -> None:
    result = collect_memory_intelligence_from_heartbeats(
        [
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "status": "running",
                "metrics": {
                    "memory_summary": {
                        "total_records": 3,
                        "recognized_records": 2,
                        "gold_candidates": 2,
                        "review_candidates": 0,
                        "alert_candidates": 0,
                        "dedupe_candidates": 0,
                    }
                },
            },
            {
                "type": "swarm_heartbeat",
                "swarm": "simulation",
                "status": "running",
                "metrics": {},
            },
        ]
    )

    assert result["aggregate"]["status"] == "valuable_activity"
    assert result["aggregate"]["gold_candidates"] == 2
    assert len(result["nodes"]) == 1

def test_collector_accepts_memory_heartbeat_without_type() -> None:
    result = collect_memory_intelligence_from_heartbeats(
        [
            {
                "swarm": "memory",
                "status": "running",
                "metrics": {
                    "memory_summary": {
                        "total_records": 3,
                        "recognized_records": 2,
                        "gold_candidates": 2,
                    }
                },
            }
        ]
    )

    assert result["aggregate"]["status"] == "valuable_activity"
    assert result["aggregate"]["gold_candidates"] == 2

def test_collector_uses_latest_memory_heartbeat_per_node() -> None:
    result = collect_memory_intelligence_from_heartbeats(
        [
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "node_id": "memory-1",
                "timestamp": 1.0,
                "status": "running",
                "metrics": {
                    "heartbeats_published": 0,
                    "memory_summary": {
                        "total_records": 1,
                        "recognized_records": 0,
                        "gold_candidates": 0,
                    },
                },
            },
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "node_id": "memory-1",
                "timestamp": 2.0,
                "status": "running",
                "metrics": {
                    "heartbeats_published": 2,
                    "memory_summary": {
                        "total_records": 3,
                        "recognized_records": 2,
                        "gold_candidates": 2,
                    },
                },
            },
        ]
    )

    assert result["aggregate"]["status"] == "valuable_activity"
    assert result["aggregate"]["total_records"] == 3
    assert result["aggregate"]["gold_candidates"] == 2
    assert len(result["nodes"]) == 1

class DummySnapshot:
    recent_heartbeats_by_swarm = {
        "weird_key": [
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "node_id": "memory-1",
                "timestamp": 2,
                "metrics": {"gold_candidates": 2},
            }
        ]
    }
    latest_swarm_heartbeats = {}


def test_find_memory_heartbeats_from_snapshot_by_payload_swarm() -> None:
    heartbeats = find_memory_heartbeats_from_snapshot(DummySnapshot())

    assert len(heartbeats) == 1
    assert heartbeats[0]["swarm"] == "memory"

def test_collector_aggregates_runtime_evidence_metrics_from_memory_heartbeats() -> None:
    result = collect_memory_intelligence_from_heartbeats(
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

    assert result["aggregate"]["status"] == "valuable_activity"
    assert result["aggregate"]["reason"] == "runtime_evidence_gold_candidates_detected"
    assert result["aggregate"]["runtime_evidence_records"] == 1
    assert result["aggregate"]["runtime_evidence_gold_candidates"] == 1
    assert result["aggregate"]["runtime_evidence_review_candidates"] == 0
    assert result["aggregate"]["runtime_evidence_alert_candidates"] == 0

    assert result["nodes"][0]["runtime_evidence_records"] == 1
    assert result["nodes"][0]["runtime_evidence_gold_candidates"] == 1

def test_collector_aggregates_runtime_evidence_alert_candidates_from_memory_heartbeats() -> None:
    result = collect_memory_intelligence_from_heartbeats(
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

    assert result["aggregate"]["status"] == "danger_detected"
    assert result["aggregate"]["reason"] == "runtime_evidence_alert_candidates_detected"
    assert result["aggregate"]["runtime_evidence_records"] == 1
    assert result["aggregate"]["runtime_evidence_alert_candidates"] == 1

def test_collector_reports_replay_execution_evidence_from_memory_summary() -> None:
    result = collect_memory_intelligence_from_heartbeats(
        [
            {
                "type": "swarm_heartbeat",
                "swarm": "memory",
                "node_id": "memory-1",
                "status": "running",
                "metrics": {
                    "memory_summary": {
                        "total_records": 1,
                        "recognized_records": 1,
                        "gold_candidates": 0,
                        "review_candidates": 0,
                        "alert_candidates": 0,
                        "dedupe_candidates": 0,
                        "replay_execution_evidence_records": 1,
                        "replay_execution_evidence_passed": 1,
                        "replay_execution_evidence_failed": 0,
                    }
                },
            }
        ]
    )

    assert result["aggregate"]["status"] == "valuable_activity"
    assert result["aggregate"]["reason"] == "replay_execution_evidence_detected"
    assert result["aggregate"]["replay_execution_evidence_records"] == 1
    assert result["aggregate"]["replay_execution_evidence_passed"] == 1
    assert result["aggregate"]["replay_execution_evidence_failed"] == 0
    assert result["nodes"][0]["replay_execution_evidence_records"] == 1