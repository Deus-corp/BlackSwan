"""Market snapshot service with live adapter support and simulation fallback."""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Any, Final, Optional, Protocol

import aiohttp
from swarm_config import config

logger: Final = logging.getLogger(__name__)

DEFAULT_SYMBOL: Final[str] = "WETH/USDC"
DEFAULT_SIM_PRICE_LOW: Final[float] = 90.0
DEFAULT_SIM_PRICE_HIGH: Final[float] = 110.0
LIVE_MODES: Final[frozenset[str]] = frozenset({"live", "web3", "futures"})


class MarketAdapterProtocol(Protocol):
    """Contract for market data providers."""

    async def fetch_all_tickers(self) -> Optional[dict[str, dict[str, Any]]]:
        ...


class MarketSnapshotService:
    """Fetch live market snapshots or return safe simulated fallback data."""

    __slots__ = ("_adapter", "_mode", "_primary_symbol", "_symbols", "_last_snapshot")

    def __init__(self, market_adapter: MarketAdapterProtocol, market_mode: str) -> None:
        if not isinstance(market_mode, str):
            raise ValueError("market_mode must be a string")
        if market_adapter is not None and not callable(getattr(market_adapter, "fetch_all_tickers", None)):
            raise ValueError("market_adapter must implement async fetch_all_tickers()")

        self._adapter = market_adapter
        self._mode = market_mode.strip().lower()
        self._symbols = self._configured_symbols()
        self._primary_symbol = self._symbols[0] if self._symbols else DEFAULT_SYMBOL
        self._last_snapshot: dict[str, dict[str, Any]] = {}

        logger.debug(
            "MarketSnapshotService initialized mode=%s primary_symbol=%s symbols=%s",
            self._mode,
            self._primary_symbol,
            self._symbols,
        )

    async def get_snapshot(self, session: Optional[aiohttp.ClientSession] = None) -> dict[str, dict[str, Any]]:
        """Return current market snapshot from adapter or simulated fallback."""
        del session  # kept for backward-compatible signature

        if self._mode in LIVE_MODES and self._adapter is not None:
            try:
                data = await self._adapter.fetch_all_tickers()
                sanitized = self._sanitize_tickers(data)
                if sanitized:
                    self._last_snapshot = sanitized
                    logger.debug("Fetched %d valid ticker(s) from adapter.", len(sanitized))
                    return sanitized

                logger.warning("Adapter returned no valid tickers in mode=%s.", self._mode)
            except Exception as exc:
                logger.warning("Adapter fetch failed in mode=%s: %s", self._mode, exc)

        simulated = self._get_simulated_snapshot()
        self._last_snapshot = simulated
        return simulated

    @property
    def last_snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a shallow copy of the last successful snapshot."""
        return {symbol: dict(tick) for symbol, tick in self._last_snapshot.items()}

    def _sanitize_tickers(self, tickers: Any) -> dict[str, dict[str, Any]]:
        """Return only valid ticker rows with positive finite prices."""
        if not isinstance(tickers, dict):
            return {}

        sanitized: dict[str, dict[str, Any]] = {}

        for raw_symbol, raw_tick in tickers.items():
            symbol = str(raw_symbol or "").strip()
            if not symbol or not isinstance(raw_tick, dict):
                continue

            price = self._safe_float(raw_tick.get("price"), 0.0)
            if price <= 0:
                continue

            tick = dict(raw_tick)
            tick["price"] = price
            tick.setdefault("symbol", symbol)
            tick.setdefault("timestamp", time.time())
            sanitized[symbol] = tick

        return sanitized

    def _get_simulated_snapshot(self) -> dict[str, dict[str, Any]]:
        """Generate fallback market snapshot with randomized pricing."""
        symbols = self._symbols or [self._primary_symbol]
        now = time.time()
        snapshot: dict[str, dict[str, Any]] = {}

        for symbol in symbols:
            price = random.uniform(DEFAULT_SIM_PRICE_LOW, DEFAULT_SIM_PRICE_HIGH)
            snapshot[symbol] = {
                "price": price,
                "symbol": symbol,
                "timestamp": now,
                "simulated": True,
            }

        logger.info("Simulating market snapshot for %d symbol(s), primary=%s.", len(snapshot), self._primary_symbol)
        return snapshot

    @staticmethod
    def _configured_symbols() -> list[str]:
        raw_symbols = getattr(config, "trading_symbols", "") or ""
        symbols = [item.strip() for item in str(raw_symbols).split(",") if item.strip()]
        return symbols or [DEFAULT_SYMBOL]

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        return number if math.isfinite(number) else default