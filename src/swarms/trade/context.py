"""Typed configuration and runtime context for the trade swarm node.

This module acts as a strictly typed dependency injection container.
It purposefully avoids business logic to prevent circular dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SupportsState(Protocol):
    """Protocol for entities capable of returning a state snapshot."""
    @property
    def state(self) -> Dict[str, Any]:
        """Return a current CRDT-backed state snapshot."""


@runtime_checkable
class SupportsGenomeWrite(Protocol):
    """Protocol for entities capable of persisting genomes."""
    async def add_genome(self, genome: Dict[str, Any]) -> None:
        """Persist a genome / command / heartbeat into the shared state layer."""


@runtime_checkable
class SupportsClose(Protocol):
    """Protocol for entities that require graceful resource cleanup."""
    async def close(self) -> None:
        """Close underlying resources if supported."""


@dataclass(slots=True, frozen=True)
class TradeNodeConfig:
    """Validated configuration immutable container for the trade node."""
    node_id: str
    port: int
    peers: List[str]
    total_nodes: int

    market_mode: str
    market_url: Optional[str]
    trading_symbols: List[str]

    burn_rate: float
    failure_prob: float
    gossip_interval: float
    max_state: int
    ttl: int
    max_import: int
    import_cooldown: int

    memory_api_enabled: bool
    tradingview_webhook_enabled: bool
    tradingview_webhook_port: int
    orderbook_analysis_enabled: bool

    expected_return_rate: float
    max_normalized_capital: float
    capital_alert_threshold: float
    capital_watchdog_threshold: float
    hedge_ratio: float

    test_web3_swap_side: str
    test_web3_swap_amount: float

    log_level: str = "INFO"


@dataclass(slots=True)
class RuntimeContext:
    """Dependency container for the trade swarm runtime execution environment."""
    config: TradeNodeConfig
    crdt: SupportsState & SupportsGenomeWrite

    # Infrastructure and Core Services
    reputation: Any = None
    telemetry: Any = None
    event_store: Any = None
    memory_api: Any = None
    key_manager: Any = None
    crypto: Any = None

    # Trading Logic Components
    capital_manager: Any = None
    risk_manager: Any = None
    market_adapter: Any = None
    market_service: Any = None
    market_collector: Any = None
    trading_controller: Any = None
    executor: Any = None
    orderbook_analyzers: Dict[str, Any] = field(default_factory=dict)

    # Intelligence and Evolution
    survival: Any = None
    curiosity: Any = None
    llm: Any = None
    memory: Any = None
    semantic: Any = None
    mutation_engine: Any = None
    evolution_engine: Any = None
    engine: Any = None
    meta_agent: Any = None
    dispatcher: Any = None

    # Networking and Sync
    swarm_sync: Any = None
    heartbeat_publisher: Any = None
    node_index: int = 0
    gossip_seq_no: int = 0
    gossip_lamport_ts: int = 0
    gossip_private_key: Any = None
    gossip_public_bytes: bytes = b""
    gossip_key_id: str = ""

    # External Integrations
    internet_researcher: Any = None
    telegram_notifier: Any = None
    tradingview_webhook: Any = None
    maintenance_service: Any = None

    # State Tracking
    capital: float = 1000.0
    step_count: int = 0
    last_import_step: int = 0
    prev_price: float = 100.0
    prev_prev_price: float = 100.0
    last_market: Optional[Dict[str, Any]] = None
    trace_id: str = ""

    primary_symbol: str = "BTC/USDT"
    symbols_list: List[str] = field(default_factory=list)
    current_params: Dict[str, Any] = field(default_factory=dict)

    # Lifecycle Management
    shutdown_event: Any = None
    evolution_task: Any = None
    sync_task: Any = None
    trade_flow: Any = None