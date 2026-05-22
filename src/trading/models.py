"""
Typed data models for inter-service communication.

Provides robust data structures for market monitoring, trade execution,
node state synchronization, and evolutionary genome management.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Represents a point-in-time snapshot of market data for a specific instrument.

    Attributes:
        symbol: The ticker symbol (e.g., "BTC/USD").
        price: The current market price.
        volume: The total trading volume at the time of snapshot.
        extra: Dictionary for additional unstructured metadata.
    """
    symbol: str
    price: float
    volume: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeDecision:
    """
    Represents a validated decision to execute a specific market order.

    Attributes:
        action: Execution intent, specifically 'buy' or 'sell'.
        amount: Quantity of the asset to be traded.
        symbol: Target trading pair.
        price: Target limit or reference price for the execution.
    """
    action: str
    amount: float
    symbol: str
    price: float


@dataclass(frozen=True)
class ExecutionResult:
    """
    Represents the terminal outcome of a trade execution request.

    Attributes:
        success: Whether the transaction was successfully processed.
        tx_hash: Optional unique identifier for the transaction.
        status: Lifecycle state (e.g., 'completed', 'pending', 'failed').
        error: Description of failure if applicable.
    """
    success: bool
    tx_hash: Optional[str] = None
    status: str = "unknown"
    error: Optional[str] = None


@dataclass
class NodeState:
    """
    Represents the operational metrics and state of a trading node.

    Attributes:
        node_id: Unique identifier for the agent instance.
        capital: Available liquidity for trading.
        dq: Data Quality score.
        liveness: Heartbeat/responsiveness metric.
        fitness: Current performance/reward metric.
        diversity: Strategy innovation index.
        crdt_size: Payload size of synchronized state data.
        niche: Defined operational strategy or role.
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
    Represents a parameter configuration for a trading strategy candidate.

    Attributes:
        params: Mapping of hyper-parameters defining the strategy.
        fitness: Evaluated success score of the strategy.
        niche: Strategic category (e.g., 'exploration', 'exploitation').
        origin: Source of evolution (e.g., 'mutation', 'crossover').
        lineage: List of parent node/genome IDs for path tracing.
    """
    params: Dict[str, float]
    fitness: float = 0.0
    niche: str = "exploration"
    origin: str = ""
    lineage: List[str] = field(default_factory=list)