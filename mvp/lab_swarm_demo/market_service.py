"""
Market service that generates simulated market ticks and publishes them to Redis.
Utilizes MarketEnvironment for simulating price changes with configured drift and volatility parameters.
"""
import redis
import time
import json
import os
import logging
import random  # Added for dummy MarketEnvironment volatility
from typing import Dict, Union, Any, Final

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Use a logger instance for better practice

# Assuming sim.engine.environment.MarketEnvironment exists and is importable
# In a real project, this would typically be part of a proper module import.
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
        def __init__(self, volatility: float, drift: float) -> None:
            """
            Initializes the dummy market environment.

            Args:
                volatility: The volatility parameter for price simulation.
                drift: The drift parameter for price simulation.
            """
            self._price: float = 100.0  # Starting price
            self.volatility: float = volatility
            self.drift: float = drift

        def step(self) -> float:
            """
            Simulates a single step in the market, applying drift and volatility to the price.

            Returns:
                The new simulated price as a float.
            """
            # Apply drift: price tends to increase/decrease by a percentage
            price_change_drift = self._price * self.drift
            
            # Apply volatility: random fluctuation around the current price
            # Using random.uniform for more direct control over the range.
            # Fluctuation is between -volatility * self._price and +volatility * self._price
            price_change_volatility = self._price * self.volatility * random.uniform(-1.0, 1.0)
            
            self._price += price_change_drift + price_change_volatility
            
            # Ensure price does not fall below a nominal minimum
            self._price = max(0.01, self._price)
            
            return self._price # For the dummy, we return just the price as a float

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
    """
    redis_client: redis.Redis
    try:
        # Initialize Redis client for publishing market data
        redis_client = redis.Redis.from_url(REDIS_URL)
        redis_client.ping() # Test connection
        logger.info("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Redis at {REDIS_URL}: {e}")
        return # Exit if Redis connection fails

    # Initialize market simulation environment with configured volatility and drift
    market_env: MarketEnvironment = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)

    logger.info(f"Market service started, publishing every {INTERVAL}s to Redis channel '{MARKET_CHANNEL}'")
    logger.info(f"Market parameters: Drift={DRIFT}, Volatility={VOLATILITY}")

    # Main loop for market tick generation and publishing
    while True:
        try:
            # Generate the next market state step. It can return either a simple price (float)
            # or a dictionary containing more detailed state information.
            raw_state: Union[float, Dict[str, Any]] = market_env.step()

            # Ensure market_state is always a dictionary (as expected by roi_dispatcher)
            # This block converts a simple float price into a dictionary if necessary.
            market_state: Dict[str, Union[float, Any]]
            if isinstance(raw_state, dict):
                # If the MarketEnvironment already returned a dict, use it directly.
                # Assuming if it's a dict, it's complete with required fields like 'price',
                # 'volatility_estimate', and 'drift'. If not, additional logic might be
                # needed here to populate missing fields from global config.
                market_state = raw_state
            else:
                # If step returned just a price (float), create the expected dictionary
                # with additional estimated parameters.
                market_state = {
                    "price": raw_state,
                    "volatility_estimate": VOLATILITY, # Assumed to be an estimate, using configured value
                    "drift": DRIFT                     # Using configured drift value
                }

            # Publish the market state as a JSON string to the "market_ticks" channel in Redis
            redis_client.publish(MARKET_CHANNEL, json.dumps(market_state))
            logger.debug(f"Published market tick: {json.dumps(market_state)}")

        except Exception as e:
            logger.error(f"Error during market tick generation or publishing: {e}", exc_info=True)
            # Log the error and continue, as a transient error shouldn't stop the entire service.

        # Pause for the specified interval before the next market tick generation
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run_market_service()