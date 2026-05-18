"""
Market service that generates simulated market ticks and publishes them to Redis.
Utilizes MarketEnvironment for simulating price changes with configured drift and volatility parameters.
"""
import redis
import time
import json
import os
import logging
from typing import Dict, Union, Any

# Assuming sim.engine.environment.MarketEnvironment exists and is importable
# In a real project, this would typically be part of a proper module import.
try:
    from sim.engine.environment import MarketEnvironment
except ImportError:
    logging.error("Could not import MarketEnvironment. Please ensure 'sim' package is installed and accessible.")
    # Define a dummy class or exit if MarketEnvironment is critical and missing
    class MarketEnvironment:
        def __init__(self, volatility: float, drift: float):
            logging.warning("Using dummy MarketEnvironment due to import error. Prices will be fixed.")
            self._price = 100.0
            self.volatility = volatility
            self.drift = drift
        def step(self) -> float:
            # Simulate a very simple price movement or just return current price
            self._price += self.drift * self._price
            return self._price

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration from environment variables
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
DRIFT: float = float(os.environ.get("DRIFT", "0.002"))
VOLATILITY: float = float(os.environ.get("VOLATILITY", "0.01"))
INTERVAL: float = float(os.environ.get("INTERVAL", "2.0"))
MARKET_CHANNEL: str = "market_ticks"

def run_market_service() -> None:
    """
    Initializes the market simulation and Redis publisher, then continuously
    generates and publishes market ticks.
    """
    try:
        # Initialize Redis client for publishing market data
        r: redis.Redis = redis.Redis.from_url(REDIS_URL)
        r.ping() # Test connection
        logging.info("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e:
        logging.error(f"Could not connect to Redis at {REDIS_URL}: {e}")
        return # Exit if Redis connection fails

    # Initialize market simulation environment with configured volatility and drift
    market: MarketEnvironment = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)

    logging.info(f"Market service started, publishing every {INTERVAL}s to Redis channel '{MARKET_CHANNEL}'")
    logging.info(f"Market parameters: Drift={DRIFT}, Volatility={VOLATILITY}")

    # Main loop for market tick generation and publishing
    while True:
        try:
            # Generate the next market state step. It can return either a simple price (float)
            # or a dictionary containing more detailed state information.
            raw_state: Union[float, Dict[str, Any]] = market.step()

            # Ensure market_state is always a dictionary (as expected by roi_dispatcher)
            # This block converts a simple float price into a dictionary if necessary.
            market_state: Dict[str, Union[float, Any]]
            if isinstance(raw_state, dict):
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
            r.publish(MARKET_CHANNEL, json.dumps(market_state))
            logging.debug(f"Published market tick: {json.dumps(market_state)}")

        except Exception as e:
            logging.error(f"Error during market tick generation or publishing: {e}", exc_info=True)
            # Depending on desired resilience, might want to continue or break here.
            # For a market service, it might be better to log and continue.

        # Pause for the specified interval before the next market tick generation
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run_market_service()