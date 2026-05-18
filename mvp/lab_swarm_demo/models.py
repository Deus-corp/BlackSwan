"""
Типизированные модели данных для взаимодействия сервисов.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class MarketSnapshot:
    """
    Represents a snapshot of market data for a specific symbol.
    """
    symbol: str
    price: float
    volume: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeDecision:
    """
    Represents a decision made to execute a trade.
    """
    action: str          # "buy" / "sell"
    amount: float
    symbol: str
    price: float


@dataclass
class ExecutionResult:
    """
    Represents the result of a trade execution.
    """
    success: bool
    tx_hash: Optional[str] = None
    status: str = "unknown"
    error: Optional[str] = None


@dataclass
class NodeState:
    """
    Represents the current state of a trading node in the swarm.
    """
    node_id: str
    capital: float
    dq: float
    liveness: float
    fitness: float
    diversity: float
    crdt_size: int
    niche: str


@dataclass
class GenomeCandidate:
    """
    Represents a candidate genome (set of parameters) for evaluation.
    """
    params: Dict[str, float]
    fitness: float = 0.0
    niche: str = "exploration"
    origin: str = ""
    lineage: List[str] = field(default_factory=list)