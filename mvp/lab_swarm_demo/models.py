"""
Типизированные модели данных для взаимодействия сервисов.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    volume: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeDecision:
    action: str          # "buy" / "sell"
    amount: float
    symbol: str
    price: float


@dataclass
class ExecutionResult:
    success: bool
    tx_hash: Optional[str] = None
    status: str = "unknown"
    error: Optional[str] = None


@dataclass
class NodeState:
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
    params: Dict[str, float]
    fitness: float = 0.0
    niche: str = "exploration"
    origin: str = ""
    lineage: list = field(default_factory=list)