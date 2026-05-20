"""Typed configuration and runtime context for the trade swarm node.

This module is the foundation for the structured refactor.
It intentionally centralizes the node's external dependencies and runtime flags,
so the rest of the trade subsystem can be split into focused services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SupportsState(Protocol):
    @property
    def state(self) -> Dict[str, Any]:
        """Return a current CRDT-backed state snapshot."""


@runtime_checkable
class SupportsGenomeWrite(Protocol):
    async def add_genome(self, genome: Dict[str, Any]) -> None:
        """Persist a genome / command / heartbeat into the shared state layer."""


@runtime_checkable
class SupportsClose(Protocol):
    async def close(self) -> None:
        """Close underlying resources if supported."""


@dataclass(slots=True)
class TradeNodeConfig:
    """Validated configuration subset used by the trade node.

    This is intentionally narrower than the global config object.
    Keep the surface area small so downstream services depend only on what they need.
    """

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
    """Dependency container for the trade swarm runtime."""

    config: TradeNodeConfig

    crdt: SupportsState & SupportsGenomeWrite
    reputation: Any
    telemetry: Any
    event_store: Any

    capital_manager: Any
    risk_manager: Any
    survival: Any
    curiosity: Any
    llm: Any
    memory: Any
    semantic: Any

    key_manager: Any
    crypto: Any

    market_adapter: Any
    market_service: Any
    trading_controller: Any
    executor: Any
    mutation_engine: Any
    evolution_engine: Any
    swarm_sync: Any

    internet_researcher: Any
    telegram_notifier: Any
    tradingview_webhook: Any | None = None
    orderbook_analyzers: Dict[str, Any] = field(default_factory=dict)

    engine: Any = None
    meta_agent: Any = None

    node_index: int = 0
    gossip_seq_no: int = 0
    gossip_lamport_ts: int = 0
    gossip_private_key: Any = None
    gossip_public_bytes: bytes = b""
    gossip_key_id: str = ""

    capital: float = 1000.0
    step_count: int = 0
    last_import_step: int = 0
    prev_price: float = 100.0
    prev_prev_price: float = 100.0
    last_market: Optional[Dict[str, Any]] = None
    trace_id: str = ""

    primary_symbol: str = "BTC/USDT"
    symbols_list: List[str] = field(default_factory=list)

    shutdown_event: Any = None
    evolution_task: Any = None
    sync_task: Any = None

    market_adapter: Any
    dispatcher: Any

    current_params: Dict[str, Any]

    trace_id: str
    step_count: int

    capital: float

    executor: Any
    capital_manager: Any

    def to_heartbeat_payload(self) -> Dict[str, Any]:
        """Return a compact, typed heartbeat payload for swarm coordination."""
        return {
            "type": "trade_heartbeat",
            "node_id": self.config.node_id,
            "timestamp": __import__("time").time(),
            "capital": self.capital,
            "dq": float(getattr(self.survival, "dq", 0.0)),
            "fitness": float(self._current_fitness()),
            "diversity": float(self._population_diversity()),
            "crdt_size": len(getattr(self.crdt, "state", {})),
            "llm_mutations": self._llm_mutations(),
            "niche_counts": self._niche_counts(),
            "trace_id": self.trace_id,
            "origin_pubkey_hex": getattr(self.crypto, "public_bytes_hex", ""),
            "schema_version": 1,
        }

    def _current_fitness(self) -> float:
        try:
            champ = getattr(self.engine, "champion", None)
            if not champ:
                return 0.0
            # Champion may be a tuple/list or object depending on the engine implementation.
            if isinstance(champ, (list, tuple)) and len(champ) > 1:
                return float(champ[1])
            if hasattr(champ, "fitness"):
                return float(champ.fitness)
            return 0.0
        except Exception:
            return 0.0

    def _population_diversity(self) -> float:
        try:
            if self.engine and hasattr(self.engine, "diversity"):
                return float(self.engine.diversity())
            return 0.0
        except Exception:
            return 0.0

    def _llm_mutations(self) -> int:
        try:
            if self.engine and hasattr(self.engine, "llm_mutations"):
                return int(self.engine.llm_mutations)
            return 0
        except Exception:
            return 0

    def _niche_counts(self) -> Dict[str, int]:
        try:
            if self.engine and hasattr(self.engine, "population"):
                counts = {"survival": 0, "capital": 0, "exploration": 0}
                for item in self.engine.population:
                    niche = getattr(item, "niche", None)
                    if niche is None and isinstance(item, dict):
                        niche = item.get("niche", "exploration")
                    if niche in counts:
                        counts[niche] += 1
                return counts
            return {"survival": 0, "capital": 0, "exploration": 0}
        except Exception:
            return {"survival": 0, "capital": 0, "exploration": 0}
