import sys


def test_testing_package_import_is_lightweight() -> None:
    import src.testing  # noqa: F401

    assert "src.testing.swarm_runtime_smoke" not in sys.modules

def test_seed_directive_import_does_not_load_runtime_smoke() -> None:
    from src.testing.seed_directive import SAFE_SEED_ACTIONS

    assert "REDUCE_RISK" in SAFE_SEED_ACTIONS
    assert "src.testing.swarm_runtime_smoke" not in sys.modules

def test_publish_directive_evidence_import_does_not_load_runtime_smoke() -> None:
    from src.testing.publish_directive_evidence import publish_directive_evidence

    assert callable(publish_directive_evidence)
    assert "src.testing.swarm_runtime_smoke" not in sys.modules

def test_evidence_memory_bridge_import_does_not_load_runtime_smoke() -> None:
    from src.testing.evidence_memory_bridge import build_memory_record_from_evidence

    assert callable(build_memory_record_from_evidence)
    assert "src.testing.swarm_runtime_smoke" not in sys.modules

def test_publish_replay_scenarios_import_does_not_load_runtime_smoke() -> None:
    from src.testing.publish_replay_scenarios import publish_replay_scenarios

    assert callable(publish_replay_scenarios)
    assert "src.testing.swarm_runtime_smoke" not in sys.modules