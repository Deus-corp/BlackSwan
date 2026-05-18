"""
Typed data models for inter-service communication.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class MarketSnapshot:
    """
    Represents a snapshot of market data for a specific symbol.

    Attributes:
        symbol: The identifier for the market instrument (e.g., "BTC/USD").
        price: The current price of the instrument.
        volume: The trading volume at the time of the snapshot. Defaults to 0.0.
        extra: A dictionary for any additional, unstructured market data.
    """
    symbol: str
    price: float
    volume: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeDecision:
    """
    Represents a decision made to execute a trade.

    Attributes:
        action: The type of trade action, typically "buy" or "sell".
        amount: The quantity of the asset to trade.
        symbol: The identifier for the market instrument to trade.
        price: The price at which the trade is intended to be executed.
    """
    action: str          # "buy" / "sell"
    amount: float
    symbol: str
    price: float


@dataclass
class ExecutionResult:
    """
    Represents the result of a trade execution.

    Attributes:
        success: A boolean indicating whether the trade execution was successful.
        tx_hash: An optional transaction hash or identifier for the executed trade.
        status: A string describing the status of the execution (e.g., "completed", "pending", "failed").
        error: An optional error message if the execution failed.
    """
    success: bool
    tx_hash: Optional[str] = None
    status: str = "unknown"
    error: Optional[str] = None


@dataclass
class NodeState:
    """
    Represents the current state of a trading node in the swarm.

    Attributes:
        node_id: A unique identifier for the trading node.
        capital: The current financial capital available to the node.
        dq: A metric for data quality or decision quality.
        liveness: A metric indicating the node's activity or responsiveness.
        fitness: An overall performance metric for the node.
        diversity: A metric indicating the uniqueness or spread of the node's strategy.
        crdt_size: The size of the Conflict-free Replicated Data Type (CRDT) data managed by the node.
        niche: A string describing the strategic niche or role of the node.
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
    Represents a candidate genome (set of parameters) for evaluation in the swarm.

    Attributes:
        params: A dictionary of parameters defining the genome.
        fitness: The evaluated fitness score of this genome. Defaults to 0.0.
        niche: A string describing the strategic niche of the genome (e.g., "exploration", "exploitation").
        origin: A string indicating where this genome originated (e.g., "mutation", "crossover", "initial").
        lineage: A list of identifiers for parent genomes, tracing its evolutionary path.
    """
    params: Dict[str, float]
    fitness: float = 0.0
    niche: str = "exploration"
    origin: str = ""
    lineage: List[str] = field(default_factory=list)