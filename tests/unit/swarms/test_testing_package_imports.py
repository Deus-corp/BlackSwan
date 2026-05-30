import sys


def test_testing_package_import_is_lightweight() -> None:
    import src.testing  # noqa: F401

    assert "src.testing.swarm_runtime_smoke" not in sys.modules