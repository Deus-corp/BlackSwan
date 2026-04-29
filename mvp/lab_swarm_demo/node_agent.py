import redis
import json
import os
import time
import random
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus
from sim.evolve_kelly import evaluate, random_params, mutate, crossover, PARAM_BOUNDS
from sim.survival_evaluator import SurvivalEvaluator

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))
NODE_ID = os.environ.get("NODE_ID", "unknown")

r = redis.Redis.from_url(REDIS_URL)

current_params = {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
dispatcher = ROIDispatcher(config=current_params)

state = GlobalState()
event_bus = EventBus()

# Survival Evaluator
survival = SurvivalEvaluator()
survival.dq = 0.02       # начальный уровень заметности
survival.liveness = 0.95 # начальная живучесть (чуть ниже 1, чтобы Expand был актуален)

capital = 1000.0
state.update("economic_state", {"node_id": NODE_ID, "capital": capital})

pubsub = r.pubsub()
pubsub.subscribe("market_ticks", "genome_updates")

step_count = 0
print(f"Node {NODE_ID} started, capital={capital}, strategy={current_params}, dq={survival.dq:.3f}, liveness={survival.liveness:.3f}")

for msg in pubsub.listen():
    if msg["type"] != "message":
        continue

    # --- Внешний геном ---
    if msg["channel"] == b"genome_updates":
        try:
            foreign_params = json.loads(msg["data"])
            current_fit = evaluate(current_params, seed=999)
            foreign_fit = evaluate(foreign_params, seed=999)
            if foreign_fit > current_fit:
                current_params = foreign_params
                dispatcher = ROIDispatcher(config=current_params)
                print(f"Node {NODE_ID} adopted foreign strategy: {current_params}")
        except:
            pass
        continue

    # --- Рыночный тик ---
    try:
        market_data = json.loads(msg["data"])
    except:
        continue

    step_count += 1

    # Имитация отказа
    if FAILURE_PROB > 0 and random.random() < FAILURE_PROB:
        print(f"Node {NODE_ID} failed!")
        break

    # Выживание: скрываемся, если нужно
    if survival.should_hide():
        capital = survival.hide(capital)
        print(f"Node {NODE_ID} hides: dq={survival.dq:.3f}, capital={capital:.2f}")

    # Выживание: расширяемся, если нужно
    if survival.should_expand() and capital >= survival.config["expand_cost"]:
        if survival.expand(capital):
            capital -= survival.config["expand_cost"]
            print(f"Node {NODE_ID} expands: liveness={survival.liveness:.3f}, capital={capital:.2f}")

    # Списание стоимости жизни
    capital -= BURN_RATE
    if capital <= 0:
        print(f"Node {NODE_ID} out of capital, dying.")
        break

    # Оценка сделки через Survival Evaluator
    expected_return = market_data.get("price", 100) * 0.1 * 0.05  # приблизительно
    _, approved = survival.evaluate_trade(capital, expected_return)

    if not approved:
        print(f"Node {NODE_ID} trade rejected (survival risk), dq={survival.dq:.3f}")
        continue

    fraction, _ = dispatcher.evaluate(market_data, capital)
    if fraction > 0:
        ret = market_data.get("price", 100) * fraction * 0.1
        capital *= (1 + ret)
        capital -= 1.0  # комиссия
        # После сделки немного увеличиваем DQ
        survival.dq = min(1.0, survival.dq + 0.001)
        state.update("economic_state", {"node_id": NODE_ID, "capital": capital})

    # --- Микро-эволюция каждые 50 шагов ---
    if step_count % 50 == 0:
        print(f"Node {NODE_ID} evolving strategy (step {step_count})...")
        local_pop = [random_params() for _ in range(5)]
        for gen_idx in range(3):
            fits = [evaluate(p, seed=step_count+gen_idx) for p in local_pop]
            best_idx = max(range(len(fits)), key=lambda i: fits[i])
            best_local = local_pop[best_idx]
            new_pop = [best_local]
            while len(new_pop) < 5:
                i1, i2 = random.sample(range(len(local_pop)), 2)
                parent = local_pop[i1] if fits[i1] > fits[i2] else local_pop[i2]
                child = crossover(parent, best_local)
                if random.random() < 0.3:
                    child = mutate(child, scale=0.1)
                new_pop.append(child)
            local_pop = new_pop
        final_fits = [evaluate(p, seed=step_count+999) for p in local_pop]
        best_final = max(zip(local_pop, final_fits), key=lambda x: x[1])[0]

        r.publish("genome_updates", json.dumps(best_final))
        print(f"Node {NODE_ID} published genome: {best_final}")

        current_fit = evaluate(current_params, seed=999)
        best_final_fit = evaluate(best_final, seed=999)
        if best_final_fit > current_fit:
            current_params = best_final
            dispatcher = ROIDispatcher(config=current_params)
            print(f"Node {NODE_ID} upgraded to own evolved strategy: {current_params}")

        state.save_genome(f"{NODE_ID}_{step_count}", best_final)

    time.sleep(0.5)