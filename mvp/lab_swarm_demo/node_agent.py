import redis
import json
import os
import time
import random
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus
from sim.genetic_engine import GeneticEngine
from sim.survival_evaluator import SurvivalEvaluator

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))
NODE_ID = os.environ.get("NODE_ID", "unknown")

r = redis.Redis.from_url(REDIS_URL)

# Инициализация GeneticEngine
engine = GeneticEngine(pop_size=10)
engine.initialize()

# Загружаем лучший геном из GlobalState (L2-память), если он там есть
state = GlobalState()
best_genomes = state.get_best_genomes(top_n=1)
current_params = None
if best_genomes:
    # Берём последний сохранённый геном
    last_key = list(best_genomes.keys())[-1]
    current_params = best_genomes[last_key]
    print(f"Node {NODE_ID} loaded genome from L2: {current_params}")
else:
    current_params = {"max_risk_per_trade": 0.05, "phi_llm": 0.15}

dispatcher = ROIDispatcher(config=current_params)
survival = SurvivalEvaluator()
survival.dq = 0.02
survival.liveness = 1.0

capital = 1000.0
state.update("economic_state", {"node_id": NODE_ID, "capital": capital})

pubsub = r.pubsub()
pubsub.subscribe("market_ticks", "genome_updates")

step_count = 0
last_champion_fitness = 0.0
# Метрики Ouroboros
v_s = 0   # скорость улучшения (количество успешных мутаций)
v_h = 0   # скорость деградации (количество ухудшений или откатов)
print(f"Node {NODE_ID} started, capital={capital}, strategy={current_params}, dq={survival.dq:.3f}, liveness={survival.liveness:.3f}")

for msg in pubsub.listen():
    if msg["type"] != "message":
        continue

    # --- Приём внешнего генома ---
    if msg["channel"] == b"genome_updates":
        try:
            foreign_params = json.loads(msg["data"])
            # Добавляем как "иммигранта" в популяцию GeneticEngine
            engine.population.append(foreign_params)
            # Ограничиваем размер популяции
            if len(engine.population) > engine.pop_size:
                engine.population.pop(0)
            print(f"Node {NODE_ID} added foreign genome to population")
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

    # Survival logic
    if survival.should_hide():
        capital = survival.hide(capital)
        print(f"Node {NODE_ID} hides: dq={survival.dq:.3f}, capital={capital:.2f}")

    if survival.should_expand() and capital >= survival.config["expand_cost"]:
        if survival.expand(capital):
            capital -= survival.config["expand_cost"]
            print(f"Node {NODE_ID} expands: liveness={survival.liveness:.3f}, capital={capital:.2f}")

    capital -= BURN_RATE
    if capital <= 0:
        print(f"Node {NODE_ID} out of capital, dying.")
        break

    expected_return = market_data.get("price", 100) * 0.1 * 0.05
    _, approved = survival.evaluate_trade(capital, expected_return)

    if not approved:
        print(f"Node {NODE_ID} trade rejected (survival risk), dq={survival.dq:.3f}")
        continue

    fraction, _ = dispatcher.evaluate(market_data, capital)
    if fraction > 0:
        ret = market_data.get("price", 100) * fraction * 0.1
        capital *= (1 + ret)
        capital -= 1.0
        survival.dq = min(1.0, survival.dq + 0.001)
        state.update("economic_state", {"node_id": NODE_ID, "capital": capital})

    # --- Эволюция каждые 50 шагов ---
    if step_count % 50 == 0:
        print(f"Node {NODE_ID} evolving generation (step {step_count}), V_s={v_s}, V_h={v_h}, ratio={v_s/(v_h+1):.2f}")
        engine.evolve_generation()
        # Обновляем метрики V_s и V_h
        if engine.champion[1] > last_champion_fitness:
            v_s += 1
        elif engine.champion[1] < last_champion_fitness:
            v_h += 1
        last_champion_fitness = engine.champion[1]

        # Публикуем текущего чемпиона, если он улучшился
        if engine.champion[1] > 0:
            r.publish("genome_updates", json.dumps(engine.champion[0]))
            print(f"Node {NODE_ID} published champion genome: {engine.champion[0]}")

        # Сохраняем чемпиона в L2 GlobalState
        state.save_genome(f"{NODE_ID}_gen{engine.generation}", engine.champion[0])

        # Если текущие параметры хуже чемпиона, перенимаем их
        current_fit = engine._fitness(current_params)
        if engine.champion[1] > current_fit:
            current_params = engine.champion[0]
            dispatcher = ROIDispatcher(config=current_params)
            print(f"Node {NODE_ID} upgraded to champion strategy: {current_params}")

    time.sleep(0.5)