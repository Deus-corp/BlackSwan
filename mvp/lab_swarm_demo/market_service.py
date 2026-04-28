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
    raw_state = market.step()
    # Убеждаемся, что market_state — словарь (ожидается roi_dispatcher)
    if isinstance(raw_state, dict):
        market_state = raw_state
    else:
        # Если step вернул просто цену, создаём ожидаемый словарь
        market_state = {
            "price": raw_state,
            "volatility_estimate": VOLATILITY,
            "drift": DRIFT
        }
    r.publish("market_ticks", json.dumps(market_state))
    time.sleep(INTERVAL)