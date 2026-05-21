"""
Market service that generates simulated market ticks and publishes them to Redis.
Utilizes MarketEnvironment for simulating price changes with configured drift and volatility parameters.
"""
import redis
import time
import json
import os
import logging
import random
from typing import Dict, Union, Any, Final, TypedDict, Optional

# Configure logging
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger: Final[logging.Logger] = logging.getLogger(__name__)


class MarketTick(TypedDict):
    """
    Represents a single market data tick to be published.

    Attributes:
        price: The current simulated price of the asset.
        volatility_estimate: An estimate of the market's volatility.
        drift: The current drift parameter of the market.
    """
    price: float
    volatility_estimate: float
    drift: float


try:
    from sim.engine.environment import MarketEnvironment
    logger.info("Successfully imported MarketEnvironment from 'sim.engine.environment'.")
except ImportError:
    logger.error("Could not import MarketEnvironment from 'sim.engine.environment'. "
                 "Please ensure 'sim' package is installed and accessible.")
    logger.warning("Using dummy MarketEnvironment due to import error. Prices will have basic simulation.")
    
    class MarketEnvironment:
        """
        A dummy MarketEnvironment class used when the actual 'sim' package cannot be imported.
        Simulates basic price movements with drift and volatility.
        """
        __slots__ = ('_price', 'volatility', 'drift')

        def __init__(self, volatility: float, drift: float) -> None:
            """
            Initializes the dummy market environment.

            Args:
                volatility: The volatility parameter for price simulation. Must be non-negative.
                drift: The drift parameter for price simulation.

            Raises:
                ValueError: If volatility is negative.
            """
            if not isinstance(volatility, (int, float)) or volatility < 0:
                raise ValueError("volatility must be a non-negative number.")
            if not isinstance(drift, (int, float)):
                raise ValueError("drift must be a number.")
            self._price: float = 100.0
            self.volatility: float = float(volatility)
            self.drift: float = float(drift)

        def step(self) -> float:
            """
            Simulates a single step in the market, applying drift and volatility to the price.

            Returns:
                The new simulated price as a float.
            """
            price_change_drift = self._price * self.drift
            price_change_volatility = self._price * self.volatility * random.uniform(-1.0, 1.0)
            self._price += price_change_drift + price_change_volatility
            self._price = max(0.01, self._price)
            return self._price


# Configuration from environment variables
REDIS_URL: Final[str] = os.environ.get("REDIS_URL", "redis://localhost:6379")
DRIFT: Final[float] = float(os.environ.get("DRIFT", "0.002"))
VOLATILITY: Final[float] = float(os.environ.get("VOLATILITY", "0.01"))
INTERVAL: Final[float] = float(os.environ.get("INTERVAL", "2.0"))
MARKET_CHANNEL: Final[str] = "market_ticks"


def run_market_service() -> None:
    """
    Initializes the market simulation and Redis publisher, then continuously
    generates and publishes market ticks.

    The service connects to Redis, simulates market price changes using a
    MarketEnvironment (either real or dummy), and publishes the resulting
    market state (price, volatility_estimate, drift) as JSON to a Redis channel
    at a specified interval.

    Raises:
        ValueError: If INTERVAL is not a positive number.
    """
    if not isinstance(INTERVAL, (int, float)) or INTERVAL <= 0:
        raise ValueError("INTERVAL must be a positive number.")

    redis_client: Optional[redis.Redis] = None
    try:
        redis_client = redis.Redis.from_url(REDIS_URL)
        redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Redis at {REDIS_URL}: {e}")
        return

    market_env: MarketEnvironment = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)

    logger.info(f"Market service started, publishing every {INTERVAL}s to Redis channel '{MARKET_CHANNEL}'")
    logger.info(f"Market parameters: Drift={DRIFT}, Volatility={VOLATILITY}")

    while True:
        try:
            raw_state: Union[float, Dict[str, Any]] = market_env.step()
            market_tick_data: MarketTick

            if isinstance(raw_state, dict):
                price_from_dict = raw_state.get("price")
                if not isinstance(price_from_dict, (int, float)):
                    logger.warning(
                        f"MarketEnvironment returned a dict but 'price' key is missing or non-numeric: "
                        f"{price_from_dict}. Using 0.0 as fallback."
                    )
                    price_val = 0.0
                else:
                    price_val = float(price_from_dict)

                market_tick_data = {
                    "price": price_val,
                    "volatility_estimate": raw_state.get("volatility_estimate", VOLATILITY),
                    "drift": raw_state.get("drift", DRIFT),
                }
            else:
                market_tick_data = {
                    "price": raw_state,
                    "volatility_estimate": VOLATILITY,
                    "drift": DRIFT
                }

            if redis_client:
                redis_client.publish(MARKET_CHANNEL, json.dumps(market_tick_data))
                logger.debug(f"Published market tick: {json.dumps(market_tick_data)}")

        except Exception as e:
            logger.error(f"Error during market tick generation or publishing: {e}", exc_info=True)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    run_market_service()