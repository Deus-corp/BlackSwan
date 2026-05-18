"""
Сервис рынка, который генерирует симулированные рыночные тики и публикует их в Redis.
Использует MarketEnvironment для симуляции изменения цен с заданными параметрами дрейфа и волатильности.
"""
import redis
import time
import json
import os
from typing import Dict, Union, Any

# Assuming sim.engine.environment.MarketEnvironment exists and is importable
from sim.engine.environment import MarketEnvironment

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
DRIFT: float = float(os.environ.get("DRIFT", 0.002))
VOLATILITY: float = float(os.environ.get("VOLATILITY", 0.01))
INTERVAL: float = float(os.environ.get("INTERVAL", 2.0))

# Initialize Redis client for publishing market data
r: redis.Redis = redis.Redis.from_url(REDIS_URL)
# Initialize market simulation environment with configured volatility and drift
market: MarketEnvironment = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)

print(f"Market service started, publishing every {INTERVAL}s to Redis channel 'market_ticks'")

# Main loop for market tick generation and publishing
while True:
    # Generate the next market state step. It can return either a simple price (float)
    # or a dictionary containing more detailed state information.
    raw_state: Union[float, Dict[str, Any]] = market.step()
    
    # Убеждаемся, что market_state — словарь (ожидается roi_dispatcher)
    # This block ensures that the published message is always a dictionary,
    # converting a simple float price into a dictionary if necessary.
    market_state: Dict[str, Union[float, Any]]
    if isinstance(raw_state, dict):
        market_state = raw_state
    else:
        # Если step вернул просто цену (float), создаём ожидаемый словарь
        # с дополнительными оценочными параметрами.
        market_state = {
            "price": raw_state,
            "volatility_estimate": VOLATILITY, # Assumed to be an estimate, using configured value
            "drift": DRIFT                     # Using configured drift value
        }
    
    # Publish the market state as a JSON string to the "market_ticks" channel in Redis
    r.publish("market_ticks", json.dumps(market_state))
    
    # Pause for the specified interval before the next market tick generation
    time.sleep(INTERVAL)