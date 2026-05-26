"""Typed data models for market data, trade decisions, execution results, and node state."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


TradeAction = Literal["buy", "sell"]
ExecutionStatus = Literal["filled", "rejected", "skipped", "error", "simulated", "unknown"]
GenomeNiche = Literal["exploration", "capital", "survival", "exploitation"]


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Point-in-time market data for a trading instrument."""

    symbol: str
    price: float
    volume: float = 0.0
    timestamp: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clean_symbol = str(self.symbol or "").strip()
        if not clean_symbol:
            raise ValueError("symbol cannot be empty")

        object.__setattr__(self, "symbol", clean_symbol)
        object.__setattr__(self, "price", _require_positive(self.price, "price"))
        object.__setattr__(self, "volume", _require_non_negative(self.volume, "volume"))
        object.__setattr__(self, "timestamp", _require_non_negative(self.timestamp, "timestamp"))

        if not isinstance(self.extra, dict):
            object.__setattr__(self, "extra", {"raw_extra": self.extra})
        else:
            object.__setattr__(self, "extra", dict(self.extra))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp,
            "extra": dict(self.extra),
        }


@dataclass(frozen=True, slots=True)
class TradeDecision:
    """Validated intent to execute a market order."""

    action: TradeAction
    amount: float
    symbol: str
    price: float
    reason: str = ""

    def __post_init__(self) -> None:
        clean_action = str(self.action or "").strip().lower()
        clean_symbol = str(self.symbol or "").strip()

        if clean_action not in {"buy", "sell"}:
            raise ValueError("action must be 'buy' or 'sell'")
        if not clean_symbol:
            raise ValueError("symbol cannot be empty")

        object.__setattr__(self, "action", clean_action)
        object.__setattr__(self, "symbol", clean_symbol)
        object.__setattr__(self, "amount", _require_positive(self.amount, "amount"))
        object.__setattr__(self, "price", _require_positive(self.price, "price"))
        object.__setattr__(self, "reason", str(self.reason or ""))

    @property
    def notional(self) -> float:
        return self.amount * self.price

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "amount": self.amount,
            "symbol": self.symbol,
            "price": self.price,
            "notional": self.notional,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Terminal outcome of a trade execution request."""

    success: bool
    tx_hash: Optional[str] = None
    status: ExecutionStatus = "unknown"
    error: Optional[str] = None
    new_capital: Optional[float] = None

    def __post_init__(self) -> None:
        clean_status = str(self.status or "unknown").strip().lower()
        allowed = {"filled", "rejected", "skipped", "error", "simulated", "unknown"}
        if clean_status not in allowed:
            clean_status = "unknown"

        object.__setattr__(self, "status", clean_status)
        object.__setattr__(self, "tx_hash", str(self.tx_hash).strip() if self.tx_hash else None)
        object.__setattr__(self, "error", str(self.error).strip() if self.error else None)

        if self.new_capital is not None:
            object.__setattr__(self, "new_capital", _require_non_negative(self.new_capital, "new_capital"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tx_hash": self.tx_hash,
            "status": self.status,
            "error": self.error,
            "new_capital": self.new_capital,
        }


@dataclass(slots=True)
class NodeState:
    """Operational metrics and state of a trading node."""

    node_id: str
    capital: float
    dq: float
    liveness: float
    fitness: float
    diversity: float
    crdt_size: int
    niche: str
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.node_id = str(self.node_id or "").strip()
        if not self.node_id:
            raise ValueError("node_id cannot be empty")

        self.capital = _require_non_negative(self.capital, "capital")
        self.dq = _clamp(_safe_float(self.dq, 0.0), 0.0, 1.0)
        self.liveness = _clamp(_safe_float(self.liveness, 1.0), 0.0, 1.0)
        self.fitness = _safe_float(self.fitness, 0.0)
        self.diversity = _require_non_negative(self.diversity, "diversity")
        self.crdt_size = max(0, int(self.crdt_size))
        self.niche = str(self.niche or "exploration").strip() or "exploration"
        self.timestamp = _require_non_negative(self.timestamp, "timestamp")

    @property
    def is_alive(self) -> bool:
        return self.capital > 0 and self.liveness > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "capital": self.capital,
            "dq": self.dq,
            "liveness": self.liveness,
            "fitness": self.fitness,
            "diversity": self.diversity,
            "crdt_size": self.crdt_size,
            "niche": self.niche,
            "timestamp": self.timestamp,
            "is_alive": self.is_alive,
        }


@dataclass(slots=True)
class GenomeCandidate:
    """Parameter configuration for a trading strategy candidate."""

    params: dict[str, float]
    fitness: float = 0.0
    niche: str = "exploration"
    origin: str = ""
    lineage: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.params, dict):
            raise TypeError("params must be a dictionary")

        self.params = {str(key): _safe_float(value, 0.0) for key, value in self.params.items()}
        self.fitness = _safe_float(self.fitness, 0.0)
        self.niche = str(self.niche or "exploration").strip() or "exploration"
        self.origin = str(self.origin or "").strip()
        self.lineage = [str(item).strip() for item in self.lineage if str(item).strip()]
        self.timestamp = _require_non_negative(self.timestamp, "timestamp")

    def to_dict(self) -> dict[str, Any]:
        return {
            "params": dict(self.params),
            "fitness": self.fitness,
            "niche": self.niche,
            "origin": self.origin,
            "lineage": list(self.lineage),
            "timestamp": self.timestamp,
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _require_positive(value: Any, name: str) -> float:
    number = _safe_float(value, float("nan"))
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def _require_non_negative(value: Any, name: str) -> float:
    number = _safe_float(value, float("nan"))
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a non-negative finite number")
    return number


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))