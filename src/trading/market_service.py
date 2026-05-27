"""Market service that generates simulated market ticks and optionally publishes them to Redis."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import signal
import time
from typing import Any, Final, Optional, TypedDict

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None  # type: ignore[assignment]

from src.simulation import MarketEnvironment

logger: Final[logging.Logger] = logging.getLogger(__name__)


class MarketTick(TypedDict):
    """Single market data tick."""

    price: float
    volatility_estimate: float
    drift: float
    symbol: str
    timestamp: float

DEFAULT_REDIS_URL: Final[str] = "redis://localhost:6379"
DEFAULT_MARKET_CHANNEL: Final[str] = "market_ticks"
DEFAULT_SYMBOL: Final[str] = "WETH/USDC"
DEFAULT_DRIFT: Final[float] = 0.002
DEFAULT_VOLATILITY: Final[float] = 0.01
DEFAULT_INTERVAL: Final[float] = 2.0


def run_market_service(
    *,
    redis_url: Optional[str] = None,
    channel: Optional[str] = None,
    symbol: Optional[str] = None,
    drift: Optional[float] = None,
    volatility: Optional[float] = None,
    interval: Optional[float] = None,
    max_ticks: Optional[int] = None,
    publish: bool = True,
) -> None:
    """Run the market simulation publisher loop."""
    settings = _settings(
        redis_url=redis_url,
        channel=channel,
        symbol=symbol,
        drift=drift,
        volatility=volatility,
        interval=interval,
        max_ticks=max_ticks,
        publish=publish,
    )

    redis_client = None
    if settings["publish"]:
        redis_client = _connect_redis(settings["redis_url"])
        if redis_client is None:
            logger.warning("Redis unavailable; market ticks will be logged but not published.")

    market_env = MarketEnvironment(
        volatility=settings["volatility"],
        drift=settings["drift"],
    )

    shutdown_requested = False

    def _handle_signal(signum: int, _frame: Any) -> None:
        nonlocal shutdown_requested
        logger.info("Received signal %s, stopping market service.", signum)
        shutdown_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info(
        "Starting market service symbol=%s interval=%.3fs channel=%s publish=%s max_ticks=%s",
        settings["symbol"],
        settings["interval"],
        settings["channel"],
        bool(redis_client),
        settings["max_ticks"],
    )

    tick_count = 0

    while not shutdown_requested:
        if settings["max_ticks"] is not None and tick_count >= settings["max_ticks"]:
            break

        try:
            tick = _build_tick(
                raw_state=market_env.step(),
                symbol=settings["symbol"],
                volatility=settings["volatility"],
                drift=settings["drift"],
            )

            if redis_client is not None:
                redis_client.publish(settings["channel"], json.dumps(tick, ensure_ascii=False, separators=(",", ":")))

            logger.debug("Published market tick: %s", tick)
            tick_count += 1

        except Exception:
            logger.exception("Market service simulation cycle failed.")

        time.sleep(settings["interval"])

    logger.info("Market service stopped after %d tick(s).", tick_count)


def _settings(
    *,
    redis_url: Optional[str],
    channel: Optional[str],
    symbol: Optional[str],
    drift: Optional[float],
    volatility: Optional[float],
    interval: Optional[float],
    max_ticks: Optional[int],
    publish: bool,
) -> dict[str, Any]:
    resolved_drift = _safe_float(drift if drift is not None else os.getenv("DRIFT"), DEFAULT_DRIFT)
    resolved_volatility = _safe_float(volatility if volatility is not None else os.getenv("VOLATILITY"), DEFAULT_VOLATILITY)
    resolved_interval = _safe_float(interval if interval is not None else os.getenv("INTERVAL"), DEFAULT_INTERVAL)

    if resolved_volatility < 0:
        raise ValueError("volatility must be non-negative")
    if resolved_interval <= 0:
        raise ValueError("interval must be positive")

    if max_ticks is None:
        env_max_ticks = os.getenv("MAX_TICKS", "")
        resolved_max_ticks = int(env_max_ticks) if env_max_ticks.strip() else None
    else:
        resolved_max_ticks = int(max_ticks)

    if resolved_max_ticks is not None and resolved_max_ticks < 0:
        raise ValueError("max_ticks must be non-negative or None")

    return {
        "redis_url": str(redis_url or os.getenv("REDIS_URL", DEFAULT_REDIS_URL)).strip(),
        "channel": str(channel or os.getenv("MARKET_CHANNEL", DEFAULT_MARKET_CHANNEL)).strip(),
        "symbol": str(symbol or os.getenv("MARKET_SYMBOL", DEFAULT_SYMBOL)).strip() or DEFAULT_SYMBOL,
        "drift": resolved_drift,
        "volatility": resolved_volatility,
        "interval": resolved_interval,
        "max_ticks": resolved_max_ticks,
        "publish": bool(publish),
    }


def _connect_redis(redis_url: str) -> Any | None:
    if redis is None:
        logger.warning("redis package is not installed.")
        return None

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        logger.info("Connected to Redis at %s", redis_url)
        return client
    except Exception as exc:
        logger.warning("Redis connection failed at %s: %s", redis_url, exc)
        return None


def _build_tick(*, raw_state: Any, symbol: str, volatility: float, drift: float) -> MarketTick:
    if isinstance(raw_state, dict):
        price = _safe_float(raw_state.get("price"), 0.0)
        vol = _safe_float(raw_state.get("volatility_estimate", raw_state.get("volatility")), volatility)
        raw_drift = _safe_float(raw_state.get("drift"), drift)
    else:
        price = _safe_float(raw_state, 0.0)
        vol = volatility
        raw_drift = drift

    if price <= 0:
        price = 0.01

    return {
        "price": price,
        "volatility_estimate": max(0.0, vol),
        "drift": raw_drift,
        "symbol": symbol,
        "timestamp": time.time(),
    }


def _safe_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BlackSwan simulated market tick publisher.")
    parser.add_argument("--redis-url", default=None)
    parser.add_argument("--channel", default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--drift", type=float, default=None)
    parser.add_argument("--volatility", type=float, default=None)
    parser.add_argument("--interval", type=float, default=None)
    parser.add_argument("--max-ticks", type=int, default=None)
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    run_market_service(
        redis_url=args.redis_url,
        channel=args.channel,
        symbol=args.symbol,
        drift=args.drift,
        volatility=args.volatility,
        interval=args.interval,
        max_ticks=args.max_ticks,
        publish=not args.no_publish,
    )


if __name__ == "__main__":
    main()