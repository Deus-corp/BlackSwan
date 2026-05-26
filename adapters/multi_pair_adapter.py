"""Unified multi-symbol adapter manager for spot, futures, web3, and simulation modes."""

from __future__ import annotations

import inspect
import logging
import math
import os
from typing import Any, Optional

from adapters.futures_adapter import FuturesAdapter
from adapters.live_market import BinanceTestnetAdapter
from adapters.web3_testnet import Web3TestnetAdapter

logger = logging.getLogger(__name__)

DEFAULT_PRICE_SCALE = 10_000.0
LIVE_MODES = {"live", "futures", "web3"}
VALID_ACCOUNTS = {"spot", "futures"}


class MultiPairAdapter:
    """Manage multiple child market adapters behind a unified interface."""

    AdapterType = BinanceTestnetAdapter | FuturesAdapter | Web3TestnetAdapter

    def __init__(
        self,
        symbols: list[str],
        market_mode: str = "sim",
        crdt_adapter: Optional[Any] = None,
        *,
        hedge_enabled: Optional[bool] = None,
        price_scale: Optional[float] = None,
    ) -> None:
        self.symbols = self._normalize_symbols(symbols)
        self.market_mode = str(market_mode or "sim").strip().lower()
        self.hedge_enabled = self._env_bool("HEDGE_ENABLED", False) if hedge_enabled is None else bool(hedge_enabled)
        self.price_scale = self._positive_float(
            price_scale if price_scale is not None else os.environ.get("PRICE_SCALE"),
            DEFAULT_PRICE_SCALE,
        )
        self.adapters: dict[str, MultiPairAdapter.AdapterType] = {}

        self._build_adapters(crdt_adapter=crdt_adapter)

        if not self.adapters:
            logger.warning("No adapters initialized for symbols=%s market_mode=%s", self.symbols, self.market_mode)

    def get_adapter(self, symbol: str, account: str = "spot") -> Optional[AdapterType]:
        """Return child adapter for symbol/account."""
        clean_symbol = self._clean_symbol(symbol)
        clean_account = str(account or "spot").strip().lower()

        if clean_account not in VALID_ACCOUNTS:
            logger.warning("Unknown adapter account type requested: %s", account)
            return None

        return self.adapters.get(self._key(clean_symbol, clean_account))

    async def ainit(self) -> None:
        """Initialize all child adapters that expose ainit()."""
        seen: set[int] = set()

        for key, adapter in self.adapters.items():
            if adapter is None or id(adapter) in seen:
                continue
            seen.add(id(adapter))

            ainit = getattr(adapter, "ainit", None)
            if not callable(ainit):
                continue

            try:
                await self._maybe_await(ainit())
                logger.info("Initialized adapter '%s' (%s).", key, type(adapter).__name__)
            except Exception as exc:
                logger.warning("Failed to initialize adapter '%s': %s", key, exc)

    async def fetch_all_tickers(self) -> dict[str, dict[str, Any]]:
        """Fetch ticker information for all primary adapters."""
        results: dict[str, dict[str, Any]] = {}

        for key, adapter in self.adapters.items():
            symbol, account = self._parse_key(key)

            # Prefer one public quote per symbol. Spot/web3 are primary; futures is primary only in futures-only mode.
            if account == "futures" and self._key(symbol, "spot") in self.adapters:
                continue

            ticker = await self._fetch_ticker_from_adapter(key, adapter)
            if ticker is None:
                continue

            ticker.setdefault("symbol", symbol)
            ticker["account"] = account
            ticker["adapter_key"] = key

            if self._should_scale_prices():
                ticker = self._scaled_ticker(ticker)

            results[symbol] = ticker

        return results

    async def close(self) -> None:
        """Close all child adapters that expose close()."""
        seen: set[int] = set()

        for key, adapter in self.adapters.items():
            if adapter is None or id(adapter) in seen:
                continue
            seen.add(id(adapter))

            close = getattr(adapter, "close", None)
            if not callable(close):
                continue

            try:
                await self._maybe_await(close())
                logger.info("Closed adapter '%s' (%s).", key, type(adapter).__name__)
            except Exception as exc:
                logger.warning("Failed to close adapter '%s': %s", key, exc)

    def _build_adapters(self, *, crdt_adapter: Optional[Any]) -> None:
        mode = self.market_mode

        for symbol in self.symbols:
            if mode == "live":
                self.adapters[self._key(symbol, "spot")] = BinanceTestnetAdapter(symbol=symbol)

            elif mode == "futures":
                self.adapters[self._key(symbol, "futures")] = FuturesAdapter(symbol=symbol)
                if self.hedge_enabled:
                    self.adapters[self._key(symbol, "spot")] = BinanceTestnetAdapter(symbol=symbol)

            elif mode == "web3":
                if crdt_adapter is None:
                    logger.debug("crdt_adapter is None for web3 adapter symbol=%s.", symbol)
                self.adapters[self._key(symbol, "spot")] = Web3TestnetAdapter(symbol=symbol, crdt_adapter=crdt_adapter)

            elif mode == "sim":
                # Keep current behavior: use spot adapter as simulated/live-feed base.
                self.adapters[self._key(symbol, "spot")] = BinanceTestnetAdapter(symbol=symbol)

            else:
                logger.warning("Unsupported market_mode=%r; falling back to sim adapter for %s.", mode, symbol)
                self.adapters[self._key(symbol, "spot")] = BinanceTestnetAdapter(symbol=symbol)

    async def _fetch_ticker_from_adapter(self, key: str, adapter: AdapterType) -> Optional[dict[str, Any]]:
        try:
            get_ticker = getattr(adapter, "get_ticker", None)
            if callable(get_ticker):
                ticker = await self._maybe_await(get_ticker())
            else:
                fetch_all = getattr(adapter, "fetch_all_tickers", None)
                if not callable(fetch_all):
                    logger.debug("Adapter '%s' has no get_ticker/fetch_all_tickers.", key)
                    return None

                symbol, _ = self._parse_key(key)
                all_tickers = await self._maybe_await(fetch_all())
                ticker = all_tickers.get(symbol) if isinstance(all_tickers, dict) else None

            if not isinstance(ticker, dict):
                logger.debug("No ticker data returned for adapter '%s'.", key)
                return None

            price = self._safe_float(ticker.get("price", ticker.get("ask", ticker.get("bid"))), 0.0)
            if price <= 0:
                logger.debug("Adapter '%s' returned invalid price: %r", key, ticker)
                return None

            normalized = dict(ticker)
            normalized["price"] = price
            return normalized

        except Exception:
            logger.exception("Failed to fetch ticker for adapter '%s'.", key)
            return None

    def _should_scale_prices(self) -> bool:
        return self.market_mode != "sim" and self.price_scale not in {0.0, 1.0}

    def _scaled_ticker(self, ticker: dict[str, Any]) -> dict[str, Any]:
        scaled = dict(ticker)

        for field in ("price", "bid", "ask"):
            if field not in scaled:
                continue

            value = self._safe_float(scaled.get(field), float("nan"))
            if math.isfinite(value):
                scaled[field] = value / self.price_scale

        scaled["price_scale"] = self.price_scale
        return scaled

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @classmethod
    def _normalize_symbols(cls, symbols: list[str]) -> list[str]:
        if not symbols:
            return ["BTC/USDT"]

        normalized = []
        seen = set()

        for symbol in symbols:
            clean = cls._clean_symbol(symbol)
            if clean and clean not in seen:
                normalized.append(clean)
                seen.add(clean)

        return normalized or ["BTC/USDT"]

    @staticmethod
    def _clean_symbol(symbol: str) -> str:
        return str(symbol or "").strip().upper()

    @classmethod
    def _key(cls, symbol: str, account: str) -> str:
        return f"{cls._clean_symbol(symbol)}_{str(account or 'spot').strip().lower()}"

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        symbol, _, account = str(key).rpartition("_")
        return symbol, account or "spot"

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}

    @classmethod
    def _positive_float(cls, value: Any, default: float) -> float:
        number = cls._safe_float(value, default)
        if not math.isfinite(number) or number <= 0:
            return default
        return number

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default