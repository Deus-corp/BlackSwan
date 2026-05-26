"""Binance spot testnet adapter for market data, balances, and guarded order placement."""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, time, timezone
from typing import Any, Optional

try:
    import ccxt.async_support as ccxt
except ImportError:  # pragma: no cover - optional dependency
    ccxt = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class BinanceTestnetAdapter:
    """Async Binance spot testnet adapter using CCXT."""

    DEFAULT_SYMBOL = "BTC/USDT"

    def __init__(self, symbol: str = DEFAULT_SYMBOL) -> None:
        self.symbol = self._clean_symbol(symbol)
        self.api_key = str(os.environ.get("BINANCE_TESTNET_API_KEY", "") or "").strip()
        self.api_secret = str(os.environ.get("BINANCE_TESTNET_API_SECRET", "") or "").strip()
        self.market_open_time = self._parse_market_time(os.environ.get("MARKET_OPEN", "00:00"), time(0, 0))
        self.market_close_time = self._parse_market_time(os.environ.get("MARKET_CLOSE", "23:59"), time(23, 59))

        if ccxt is None:
            self.exchange = None
            logger.warning("ccxt is not installed. BinanceTestnetAdapter is disabled.")
            return

        if not self.api_key or not self.api_secret:
            logger.warning("Binance testnet API credentials are missing. Adapter may be read-only/disabled.")

        self.exchange = ccxt.binance(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )

        set_sandbox_mode = getattr(self.exchange, "set_sandbox_mode", None)
        if callable(set_sandbox_mode):
            set_sandbox_mode(True)

    async def ainit(self) -> None:
        """Load exchange markets and verify connectivity."""
        if self.exchange is None:
            return

        try:
            await self.exchange.load_markets()
            logger.info("Binance spot testnet connected. symbol=%s", self.symbol)
        except Exception as exc:
            logger.error("Connection failed for Binance spot testnet: %s", exc)

    async def close(self) -> None:
        """Close CCXT exchange session."""
        exchange = getattr(self, "exchange", None)
        if exchange is not None:
            try:
                await exchange.close()
                logger.info("Binance spot testnet adapter closed.")
            except Exception as exc:
                logger.warning("Failed to close Binance spot testnet adapter: %s", exc)

    def _is_market_open(self) -> bool:
        """Return True when current UTC time is inside configured market window."""
        now = datetime.now(timezone.utc).time()

        if self.market_open_time <= self.market_close_time:
            return self.market_open_time <= now <= self.market_close_time

        return now >= self.market_open_time or now <= self.market_close_time

    async def fetch_all_tickers(self) -> dict[str, dict[str, Any]]:
        """Fetch ticker snapshot in the format expected by market services."""
        ticker = await self.get_ticker()
        return {self.symbol: ticker} if ticker else {}

    async def get_ticker(self) -> Optional[dict[str, Any]]:
        """Fetch ticker data if market window is open."""
        if self.exchange is None:
            return None

        if not self._is_market_open():
            logger.debug("Market window closed for symbol=%s.", self.symbol)
            return None

        try:
            ticker = await self.exchange.fetch_ticker(self.symbol)
            price = self._safe_float(ticker.get("last"), 0.0)
            bid = self._safe_float(ticker.get("bid"), 0.0)
            ask = self._safe_float(ticker.get("ask"), 0.0)

            if price <= 0:
                price = bid or ask
            if price <= 0:
                return None

            return {
                "price": price,
                "bid": bid,
                "ask": ask,
                "symbol": self.symbol,
                "timestamp": int(ticker.get("timestamp") or datetime.now(timezone.utc).timestamp() * 1000),
            }

        except Exception as exc:
            logger.error("Failed to fetch ticker for %s: %s", self.symbol, exc)
            return None

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> dict[str, Any]:
        """Place a market or limit order on Binance spot testnet."""
        if self.exchange is None:
            return self._error("exchange_unavailable")

        clean_side = str(side or "").strip().lower()
        if clean_side not in {"buy", "sell"}:
            return self._error("invalid_order_side")

        safe_amount = self._positive_float(amount)
        if safe_amount is None:
            return self._error("amount_must_be_positive")

        safe_price = None if price is None else self._positive_float(price)
        if price is not None and safe_price is None:
            return self._error("price_must_be_positive")

        try:
            if safe_price is not None:
                order = await self.exchange.create_limit_order(self.symbol, clean_side, safe_amount, safe_price)
                logger.info("Placed Binance LIMIT order: %s %.8f %s @ %.8f", clean_side.upper(), safe_amount, self.symbol, safe_price)
            else:
                order = await self.exchange.create_market_order(self.symbol, clean_side, safe_amount)
                logger.info("Placed Binance MARKET order: %s %.8f %s", clean_side.upper(), safe_amount, self.symbol)

            if isinstance(order, dict):
                order.setdefault("success", True)
                order.setdefault("status", "filled")
                order.setdefault("error", None)
                return order

            return {"success": True, "status": "filled", "result": order, "error": None}

        except Exception as exc:
            logger.error("Order placement failed side=%s symbol=%s amount=%s price=%s: %s", clean_side, self.symbol, safe_amount, safe_price, exc)
            return self._error(str(exc))

    async def fetch_balance(self) -> dict[str, float]:
        """Fetch free account balances."""
        if self.exchange is None:
            return {}

        try:
            balance = await self.exchange.fetch_balance()
            free = balance.get("free", {}) if isinstance(balance, dict) else {}
            if not isinstance(free, dict):
                return {}

            return {
                str(currency): self._safe_float(value, 0.0)
                for currency, value in free.items()
            }
        except Exception as exc:
            logger.error("Balance fetch failed: %s", exc)
            return {}

    def switch_symbol(self, new_symbol: str) -> None:
        """Update active trading pair."""
        self.symbol = self._clean_symbol(new_symbol)
        logger.info("Switched Binance spot symbol to %s", self.symbol)

    @staticmethod
    def _parse_market_time(value: str | None, default: time) -> time:
        raw = str(value or "").strip()
        try:
            return datetime.strptime(raw, "%H:%M").time()
        except ValueError:
            logger.warning("Invalid market time %r. Using default %s.", value, default.strftime("%H:%M"))
            return default

    @classmethod
    def _clean_symbol(cls, symbol: str) -> str:
        clean = str(symbol or "").strip().upper()
        return clean or cls.DEFAULT_SYMBOL

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @classmethod
    def _positive_float(cls, value: Any) -> Optional[float]:
        number = cls._safe_float(value, float("nan"))
        if not math.isfinite(number) or number <= 0:
            return None
        return number

    @staticmethod
    def _error(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "error",
            "error": str(error),
        }