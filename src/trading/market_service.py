"""
Market service that generates simulated market ticks and publishes them to Redis.
Utilizes MarketEnvironment for simulating price changes with configured drift and volatility parameters.
"""
import json
import logging
import os
import random
import time
from typing import Any, Dict, Final, Optional, TypedDict, Union

import redis

# Configure logging
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger: Final[logging.Logger] = logging.getLogger(__name__)


class MarketTick(TypedDict):
    """Represents a single market data tick to be published."""
    price: float
    volatility_estimate: float
    drift: float


try:
    from sim.engine.environment import MarketEnvironment
    logger.info("Successfully imported MarketEnvironment from 'sim.engine.environment'.")
except ImportError:
    logger.warning("Could not import MarketEnvironment. Using internal fallback implementation.")

    class MarketEnvironment:
        """Internal fallback MarketEnvironment for price simulation."""
        __slots__ = ('_price', 'volatility', 'drift')

        def __init__(self, volatility: float, drift: float) -> None:
            if volatility < 0:
                raise ValueError("volatility must be non-negative.")
            self._price: float = 100.0
            self.volatility: float = float(volatility)
            self.drift: float = float(drift)

        def step(self) -> float:
            """Calculates next price step based on drift and random volatility."""
            price_change = self._price * (self.drift + self.volatility * random.uniform(-1.0, 1.0))
            self._price = max(0.01, self._price + price_change)
            return self._price


# Configuration
REDIS_URL: Final[str] = os.environ.get("REDIS_URL", "redis://localhost:6379")
DRIFT: Final[float] = float(os.environ.get("DRIFT", "0.002"))
VOLATILITY: Final[float] = float(os.environ.get("VOLATILITY", "0.01"))
INTERVAL: Final[float] = float(os.environ.get("INTERVAL", "2.0"))
MARKET_CHANNEL: Final[str] = "market_ticks"


def run_market_service() -> None:
    """Initializes environment and publisher, running the main simulation loop."""
    if INTERVAL <= 0:
        raise ValueError("INTERVAL must be a positive number.")

    try:
        redis_client: redis.Redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info(f"Connected to Redis at {REDIS_URL}")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        return

    market_env = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)

    logger.info(f"Starting service: {INTERVAL}s interval, channel '{MARKET_CHANNEL}'")

    while True:
        try:
            raw_state = market_env.step()
            
            if isinstance(raw_state, dict):
                tick: MarketTick = {
                    "price": float(raw_state.get("price", 0.0)),
                    "volatility_estimate": float(raw_state.get("volatility_estimate", VOLATILITY)),
                    "drift": float(raw_state.get("drift", DRIFT)),
                }
            else:
                tick = {
                    "price": float(raw_state),
                    "volatility_estimate": VOLATILITY,
                    "drift": DRIFT
                }

            redis_client.publish(MARKET_CHANNEL, json.dumps(tick))
            logger.debug(f"Published tick: {tick}")

        except Exception as e:
            logger.error(f"Simulation cycle error: {e}", exc_info=True)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    run_market_service()