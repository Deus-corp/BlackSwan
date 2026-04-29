import redis
import json
import os
import time
import random
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus

# Для эволюции импортируем функции из прототипа Ouroboros
from sim.evolve_kelly import evaluate, random_params, mutate, crossover, PARAM_BOUNDS

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))
NODE_ID = os.environ.get("NODE_ID", "unknown")

r = redis.Redis.from_url(REDIS_URL)

# Текущие параметры стратегии (можно инициализировать случайно или стандартно)
current_params = {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
dispatcher = ROIDispatcher(config=current_params)

state = GlobalState()
event_bus = EventBus()

capital = 1000.0
state.update("economic_state", {"node_id": NODE_ID, "capital": capital})

# Подписываемся на оба топика
pubsub = r.pubsub()
pubsub.subscribe("market_ticks", "genome_updates")

step_count = 0
print(f"Node {NODE_ID} started, capital={capital}, strategy={current_params}")

for msg in pubsub.listen():
    if msg["type"] != "message":
        continue

    # ─── Обработка внешнего генома ───
    if msg["channel"] == b"genome_updates":
        try:
            foreign_params = json.loads(msg["data"])
            # Проверяем, лучше ли он нашего
            current_fit = evaluate(current_params, seed=999)
            foreign_fit = evaluate(foreign_params, seed=999)
            if foreign_fit > current_fit:
                current_params = foreign_params
                dispatcher = ROIDispatcher(config=current_params)
                print(f"Node {NODE_ID} adopted foreign strategy: {current_params}")
        except Exception:
            pass
        continue

    # ─── Рыночный тик ───
    try:
        market_data = json.loads(msg["data"])
    except:
        continue

    step_count += 1

    # Имитация случайного отказа
    if FAILURE_PROB > 0 and random.random() < FAILURE_PROB:
        print(f"Node {NODE_ID} failed!")
        break

    capital -= BURN_RATE
    if capital <= 0:
        print(f"Node {NODE_ID} out of capital, dying.")
        break

    # Торговое решение
    fraction, _ = dispatcher.evaluate(market_data, capital)
    if fraction > 0:
        ret = market_data.get("price", 100) * fraction * 0.1
        capital *= (1 + ret)
        capital -= 1.0  # комиссия
        state.update("economic_state", {"node_id": NODE_ID, "capital": capital})
        # event_bus.publish("trades", ...) - пока отключено

    # ─── Микро-эволюция каждые 50 шагов ───
    if step_count % 50 == 0:
        print(f"Node {NODE_ID} evolving strategy (step {step_count})...")
        # Маленькая популяция, 3 поколения
        local_pop = [random_params() for _ in range(5)]
        for gen_idx in range(3):
            fits = [evaluate(p, seed=step_count+gen_idx) for p in local_pop]
            # Элитизм: сохраняем лучшего
            best_idx = max(range(len(fits)), key=lambda i: fits[i])
            best_local = local_pop[best_idx]
            new_pop = [best_local]
            while len(new_pop) < 5:
                # Турнирный отбор
                i1, i2 = random.sample(range(len(local_pop)), 2)
                parent = local_pop[i1] if fits[i1] > fits[i2] else local_pop[i2]
                # Скрещивание с лучшим
                child = crossover(parent, best_local)
                if random.random() < 0.3:
                    child = mutate(child, scale=0.1)
                new_pop.append(child)
            local_pop = new_pop
        # Лучший после микро-эволюции
        final_fits = [evaluate(p, seed=step_count+999) for p in local_pop]
        best_final = max(zip(local_pop, final_fits), key=lambda x: x[1])[0]

        # Публикуем в Redis
        r.publish("genome_updates", json.dumps(best_final))
        print(f"Node {NODE_ID} published genome: {best_final}")

        # Если он лучше текущего – применяем
        current_fit = evaluate(current_params, seed=999)
        best_final_fit = evaluate(best_final, seed=999)
        if best_final_fit > current_fit:
            current_params = best_final
            dispatcher = ROIDispatcher(config=current_params)
            print(f"Node {NODE_ID} upgraded to own evolved strategy: {current_params}")

        # Сохраняем лучший геном в глобальное состояние
        state.save_genome(f"{NODE_ID}_{step_count}", best_final)

    time.sleep(0.5)