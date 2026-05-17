import pytest
from mvp.lab_swarm_demo.trade_node_agent import SwarmNode

@pytest.mark.asyncio
async def test_main_loop_has_required_methods():
    """Проверяем, что после PR-6 существуют необходимые методы."""
    assert hasattr(SwarmNode, '_collect_market_snapshot')
    assert hasattr(SwarmNode, '_evaluate_survival_and_trade')
    assert hasattr(SwarmNode, '_tick_evolution')
    assert hasattr(SwarmNode, '_sync_swarm')
    assert hasattr(SwarmNode, '_periodic_tasks')

def test_evolution_engine_exists():
    """Проверяем, что EvolutionEngine создаётся при инициализации узла."""
    import swarm_config
    from swarm_config import SwarmConfig
    swarm_config.config = SwarmConfig()
    from mvp.lab_swarm_demo.trade_node_agent import SwarmNode
    node = SwarmNode()
    assert hasattr(node, 'evolution_engine')

def test_swarm_sync_exists():
    """Проверяем, что SwarmSync создаётся при инициализации узла."""
    import swarm_config
    from swarm_config import SwarmConfig
    swarm_config.config = SwarmConfig()
    from mvp.lab_swarm_demo.trade_node_agent import SwarmNode
    node = SwarmNode()
    assert hasattr(node, 'swarm_sync')