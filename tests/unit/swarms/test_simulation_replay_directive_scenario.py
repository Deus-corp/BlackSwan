from src.swarms.overseer.overseer_core.brief_builder import build_global_swarm_brief
from src.swarms.overseer.overseer_core.directive_emitter import build_directives_from_brief


def test_simulation_replay_pending_scenario_proposes_simulation_observation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"simulation": 1, "overseer": 1}},
        simulation_replay={
            "simulation_replay_scenarios": 2,
            "simulation_replay_pending": 2,
            "simulation_replay_completed": 0,
            "simulation_replay_failed": 0,
        },
    )

    directives = build_directives_from_brief(brief, source="overseer-test")

    assert brief.key_metrics["simulation_replay_pending"] == 2
    assert any("Simulation replay" in item.get("title", "") for item in brief.opportunities)

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "OBSERVE"
    assert directive.target == "simulation"
    assert directive.target_type == "swarm"
    assert directive.source == "overseer-test"
    assert directive.payload["brief_id"] == brief.brief_id
    assert directive.payload["reason"] == "simulation_replay_pending_detected"
    assert directive.payload["simulation_replay_pending"] == 2