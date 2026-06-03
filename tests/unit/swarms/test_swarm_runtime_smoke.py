import sys

import pytest


@pytest.fixture(autouse=True)
def cleanup_swarm_runtime_smoke_import():
    yield
    sys.modules.pop("src.testing.swarm_runtime_smoke", None)


@pytest.mark.asyncio
async def test_swarm_runtime_smoke_runs_retry_governance_smoke() -> None:
    from src.testing.swarm_runtime_smoke import _check_retry_governance_smoke

    result = await _check_retry_governance_smoke()

    assert result["name"] == "retry_governance_smoke"
    assert result["passed"] is True
    assert result["status"] == "passed"
    assert result["records_seeded"] == 4
    assert result["chain_complete"] is True
    assert result["observability"] == "passed"