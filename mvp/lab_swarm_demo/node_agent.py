import redis
import json
import os
import time
import random
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))
NODE_ID = os.environ.get("NODE_ID", "unknown")

r = redis.Redis.from_url(REDIS_URL)
dispatcher = ROIDispatcher(config={"max_risk_per_trade": 0.05, "phi_llm": 0.15})
state = GlobalState()
event_bus = EventBus()

capital = 1000.0
state.update("economic_state", {"node_id": NODE_ID, "capital": capital})

pubsub = r.pubsub()
pubsub.subscribe("market_ticks")

print(f"Node {NODE_ID} started, capital={capital}")

for msg in pubsub.listen():
    if msg["type"] != "message":
        continue
    try:
        market_data = json.loads(msg["data"])
    except:
        continue

    # Имитация случайного отказа
    if FAILURE_PROB > 0 and random.random() < FAILURE_PROB:
        print(f"Node {NODE_ID} failed!")
        break

    capital -= BURN_RATE
    if capital <= 0:
        print(f"Node {NODE_ID} out of capital, dying.")
        break

    fraction, _ = dispatcher.evaluate(market_data, capital)
    if fraction > 0:
        ret = market_data.get("price", 100) * fraction * 0.1
        capital *= (1 + ret)
        capital -= 1.0
        state.update("economic_state", {"node_id": NODE_ID, "capital": capital})
        event_bus.publish("trades", {"node": NODE_ID, "fraction": fraction, "return": ret})

    time.sleep(0.5)