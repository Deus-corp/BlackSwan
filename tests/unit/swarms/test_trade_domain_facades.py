from src.swarms.trade.domain.capital import CapitalManager
from src.swarms.trade.domain.leader import select_leader
from src.swarms.trade.domain.models import ExecutionResult, MarketSnapshot, TradeDecision
from src.swarms.trade.market import MarketSnapshotService, select_best_market
from src.swarms.trade.domain.mutation_metrics import (
    get_llm_stats,
    note_llm_mutation,
    update_llm_impact,
)
from src.swarms.trade.domain.swarm_sync import SwarmSync

from src.swarms.trade.execution import (
    ExecutionBackend,
    LiveExecutionBackend,
    SimExecutionBackend,
    build_backend,
)


def test_trade_domain_facades_export_canonical_symbols() -> None:
    assert CapitalManager is not None
    assert select_leader is not None
    assert ExecutionResult is not None
    assert MarketSnapshot is not None
    assert TradeDecision is not None
    assert get_llm_stats is not None
    assert note_llm_mutation is not None
    assert update_llm_impact is not None
    assert SwarmSync is not None
    assert ExecutionBackend is not None
    assert LiveExecutionBackend is not None
    assert SimExecutionBackend is not None
    assert build_backend is not None
    assert MarketSnapshotService is not None
    assert select_best_market is not None
