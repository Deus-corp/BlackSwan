import pytest
from mvp.lab_swarm_demo.node_agent import SwarmNode

@pytest.mark.asyncio
async def test_main_loop_has_required_methods():
    """Проверяем, что после PR-6 существуют необходимые методы."""
    assert hasattr(SwarmNode, '_collect_market_snapshot')
    assert hasattr(SwarmNode, '_evaluate_survival_and_trade')
    assert hasattr(SwarmNode, '_tick_evolution')
    assert hasattr(SwarmNode, '_sync_swarm')
    assert hasattr(SwarmNode, '_periodic_tasks')