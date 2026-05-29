"""Async Binance futures adapter built on CCXT."""

from __future__ import annotations

import logging
import math
import os
import time
from typing import Any, Optional

try:
    import ccxt.async_support as ccxt
except ImportError:  # pragma: no cover - optional dependency
    ccxt = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class FuturesAdapter:
    """Adapter for Binance futures/testnet through CCXT async support."""

    LEVERAGE_ADJUST_COOLDOWN: int = 300
    DEFAULT_SYMBOL = "BTC/USDT"

    def __init__(self, symbol: str = DEFAULT_SYMBOL) -> None:
        self.symbol = str(symbol or self.DEFAULT_SYMBOL).strip() or self.DEFAULT_SYMBOL
        self.api_key = str(os.environ.get("BINANCE_TESTNET_API_KEY", "") or "").strip()
        self.api_secret = str(os.environ.get("BINANCE_TESTNET_API_SECRET", "") or "").strip()

        self.leverage = self._env_int("FUTURES_LEVERAGE", 2, minimum=1)
        self.stop_loss_percent = self._env_float("STOP_LOSS_PERCENT", 2.0, minimum=0.0)
        self.max_leverage = self._env_int("MAX_LEVERAGE", 5, minimum=1)
        self.min_leverage = self._env_int("MIN_LEVERAGE", 1, minimum=1)

        if self.min_leverage > self.max_leverage:
            self.min_leverage, self.max_leverage = self.max_leverage, self.min_leverage

        self.leverage = max(self.min_leverage, min(self.max_leverage, self.leverage))
        self._last_leverage_adjust_timestamp = 0.0

        if ccxt is None:
            self.exchange = None
            logger.warning("ccxt is not installed. FuturesAdapter is disabled.")
            return

        if not self.api_key or not self.api_secret:
            logger.warning("Binance testnet API credentials are missing. FuturesAdapter may be read-only/disabled.")

        self.exchange = ccxt.binance(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )

        set_sandbox_mode = getattr(self.exchange, "set_sandbox_mode", None)
        if callable(set_sandbox_mode):
            set_sandbox_mode(True)

    async def ainit(self) -> None:
        """Initialize exchange state after construction."""
        if self.exchange is None:
            return

        try:
            await self.exchange.load_markets()
        except Exception as exc:
            logger.warning("Could not load futures markets: %s", exc)

        try:
            await self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info("Futures adapter ready: symbol=%s leverage=%sx", self.symbol, self.leverage)
        except Exception as exc:
            logger.warning("Could not set initial leverage for %s: %s", self.symbol, exc)

    async def close(self) -> None:
        """Close the CCXT exchange session."""
        exchange = getattr(self, "exchange", None)
        if exchange is not None:
            try:
                await exchange.close()
                logger.info("Futures adapter CCXT session closed.")
            except Exception as exc:
                logger.warning("Failed to close futures exchange session: %s", exc)

    async def fetch_all_tickers(self) -> dict[str, dict[str, Any]]:
        """Fetch ticker snapshot in the shape expected by market services."""
        ticker = await self.get_ticker()
        return {self.symbol: ticker} if ticker else {}

    async def get_ticker(self) -> Optional[dict[str, Any]]:
        """Return ticker with last price for configured symbol."""
        if self.exchange is None:
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
                "timestamp": int(ticker.get("timestamp") or time.time() * 1000),
            }
        except Exception as exc:
            logger.error("Futures ticker fetch failed for %s: %s", self.symbol, exc)
            return None

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> dict[str, Any]:
        """Place a futures market or limit order."""
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
                logger.info("Futures LIMIT order placed: %s %.8f %s @ %.8f", clean_side.upper(), safe_amount, self.symbol, safe_price)
            else:
                order = await self.exchange.create_market_order(self.symbol, clean_side, safe_amount)
                logger.info("Futures MARKET order placed: %s %.8f %s", clean_side.upper(), safe_amount, self.symbol)

            if isinstance(order, dict):
                order.setdefault("success", True)
                order.setdefault("status", "filled")
                order.setdefault("error", None)
                return order

            return {"success": True, "status": "filled", "result": order, "error": None}

        except Exception as exc:
            logger.error(
                "Futures order failed symbol=%s side=%s amount=%s price=%s: %s",
                self.symbol,
                clean_side,
                safe_amount,
                safe_price,
                exc,
            )
            return self._error(str(exc))

    async def close_position(self, symbol: Optional[str] = None) -> dict[str, Any]:
        """Close current open position for a symbol with a market order."""
        if self.exchange is None:
            return self._error("exchange_unavailable")

        sym = str(symbol or self.symbol).strip() or self.symbol

        try:
            positions = await self.exchange.fetch_positions([sym])
            if not isinstance(positions, list):
                return self._error("invalid_positions_response")

            open_positions = [
                position
                for position in positions
                if self._safe_float(position.get("contracts"), 0.0) != 0.0
            ]

            if not open_positions:
                logger.info("No open position found for %s.", sym)
                return {"success": True, "status": "skipped", "info": "No open position", "error": None}

            position = open_positions[0]
            amount = abs(self._safe_float(position.get("contracts"), 0.0))
            if amount <= 0:
                return {"success": True, "status": "skipped", "info": "No open position", "error": None}

            side = "sell" if str(position.get("side", "")).lower() == "long" else "buy"
            logger.info("Closing %s position amount=%.8f symbol=%s", position.get("side"), amount, sym)
            return await self.place_order(side, amount)

        except Exception as exc:
            logger.error("Close position failed for %s: %s", sym, exc)
            return self._error(str(exc))

    async def fetch_balance(self) -> dict[str, float]:
        """Return available balances by currency."""
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
            logger.error("Futures balance fetch failed: %s", exc)
            return {}

    def check_stop_loss(self, entry_price: float, current_price: float, side: str) -> bool:
        """Return True when stop-loss threshold is breached."""
        clean_side = str(side or "").strip().lower()
        if clean_side not in {"long", "short"}:
            logger.error("Invalid position side for stop-loss check: %s", side)
            return False

        entry = self._positive_float(entry_price)
        current = self._positive_float(current_price)
        if entry is None or current is None:
            logger.warning("Invalid prices for stop-loss check: entry=%r current=%r", entry_price, current_price)
            return False

        if clean_side == "long":
            loss_percent = (entry - current) / entry * 100.0
        else:
            loss_percent = (current - entry) / entry * 100.0

        return loss_percent >= self.stop_loss_percent

    async def adjust_leverage(self, volatility: float) -> None:
        """Adjust leverage based on volatility with cooldown."""
        if self.exchange is None:
            return

        current_time = time.monotonic()
        elapsed = current_time - self._last_leverage_adjust_timestamp

        if elapsed < self.LEVERAGE_ADJUST_COOLDOWN:
            logger.debug("Leverage adjustment on cooldown: %.1fs remaining.", self.LEVERAGE_ADJUST_COOLDOWN - elapsed)
            return

        vol = max(0.0, self._safe_float(volatility, 0.0))
        target_leverage: Optional[int] = None

        if vol < 0.01:
            target_leverage = min(self.max_leverage, self.leverage + 1)
        elif vol > 0.05:
            target_leverage = max(self.min_leverage, self.leverage - 1)

        if target_leverage is None or target_leverage == self.leverage:
            return

        try:
            await self.exchange.set_leverage(target_leverage, self.symbol)
            self.leverage = target_leverage
            self._last_leverage_adjust_timestamp = current_time
            logger.info("Leverage adjusted to %sx for %s", target_leverage, self.symbol)
        except Exception as exc:
            logger.error("Failed to adjust leverage for %s: %s", self.symbol, exc)

    @staticmethod
    def _error(error: str) -> dict[str, Any]:
        return {"success": False, "status": "error", "error": str(error)}

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

    @classmethod
    def _env_float(cls, name: str, default: float, *, minimum: float | None = None) -> float:
        value = cls._safe_float(os.environ.get(name), default)
        if minimum is not None:
            value = max(minimum, value)
        return value

    @classmethod
    def _env_int(cls, name: str, default: int, *, minimum: int | None = None) -> int:
        try:
            value = int(os.environ.get(name, str(default)))
        except (TypeError, ValueError):
            value = default
        if minimum is not None:
            value = max(minimum, value)
        return value