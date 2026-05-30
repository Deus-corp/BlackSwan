import sys


def test_testing_package_import_is_lightweight() -> None:
    import src.testing  # noqa: F401

    assert "src.testing.swarm_runtime_smoke" not in sys.modules

def test_seed_directive_import_does_not_load_runtime_smoke() -> None:
    from src.testing.seed_directive import SAFE_SEED_ACTIONS

    assert "REDUCE_RISK" in SAFE_SEED_ACTIONS
    assert "src.testing.swarm_runtime_smoke" not in sys.modules