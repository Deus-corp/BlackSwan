import redis
import time
import json
import os
from sim.engine.environment import MarketEnvironment

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DRIFT = float(os.environ.get("DRIFT", 0.002))
VOLATILITY = float(os.environ.get("VOLATILITY", 0.01))
INTERVAL = float(os.environ.get("INTERVAL", 2.0))

r = redis.Redis.from_url(REDIS_URL)
market = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)

print(f"Market service started, publishing every {INTERVAL}s")
while True:
    market_state = market.step()
    r.publish("market_ticks", json.dumps(market_state))
    time.sleep(INTERVAL)