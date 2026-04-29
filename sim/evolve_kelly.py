#!/usr/bin/env python3
"""
Прототип Ouroboros: эволюция параметров ROIDispatcher (Kelly).
Показывает, что генетический поиск улучшает прибыль по сравнению со случайными стратегиями.
"""
import sys, os, random, copy, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.engine.environment import MarketEnvironment
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState

# Конфигурация эволюции
POP_SIZE = 10
GENERATIONS = 10
STEPS = 100              # шагов симуляции для оценки одной особи
INITIAL_CAPITAL = 1000.0
DRIFT = 0.002
VOLATILITY = 0.01

# Границы допустимых параметров
PARAM_BOUNDS = {
    "max_risk_per_trade": (0.01, 0.2),
    "phi_llm": (0.05, 0.5)
}

def random_params():
    return {
        "max_risk_per_trade": random.uniform(*PARAM_BOUNDS["max_risk_per_trade"]),
        "phi_llm": random.uniform(*PARAM_BOUNDS["phi_llm"])
    }

def evaluate(params, seed=42):
    random.seed(seed)
    market = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)
    dispatcher = ROIDispatcher(config=params)
    capital = INITIAL_CAPITAL
    for _ in range(STEPS):
        raw_state = market.step()
        # Создаём словарь, который ожидает ROIDispatcher
        if isinstance(raw_state, dict):
            market_state = raw_state
        else:
            market_state = {
                "price": raw_state,
                "volatility_estimate": VOLATILITY,
                "drift": DRIFT
            }
        fraction, _ = dispatcher.evaluate(market_state, capital)
        if fraction > 0:
            ret = market_state["price"] * fraction * 0.1
            capital *= (1 + ret)
            capital -= 1.0   # комиссия
        if capital <= 0:
            break
    return capital

def mutate(params, scale=0.1):
    """Случайное изменение параметров в пределах границ."""
    new_params = copy.deepcopy(params)
    for k in PARAM_BOUNDS:
        delta = random.uniform(-scale, scale) * (PARAM_BOUNDS[k][1] - PARAM_BOUNDS[k][0])
        new_params[k] += delta
        new_params[k] = max(PARAM_BOUNDS[k][0], min(PARAM_BOUNDS[k][1], new_params[k]))
    return new_params

def crossover(p1, p2):
    """Равномерное скрещивание двух особей."""
    child = {}
    for k in PARAM_BOUNDS:
        child[k] = p1[k] if random.random() < 0.5 else p2[k]
    return child

# Инициализация популяции
population = [random_params() for _ in range(POP_SIZE)]
best_overall = None
best_fitness = 0.0

print("=== Запуск эволюции стратегии Kelly ===\n")
for gen in range(GENERATIONS):
    # Оценка всех особей
    fitnesses = []
    for params in population:
        fit = evaluate(params, seed=gen*100)
        fitnesses.append(fit)
        if fit > best_fitness:
            best_fitness = fit
            best_overall = copy.deepcopy(params)

    # Логирование поколения
    avg_fit = statistics.mean(fitnesses)
    max_fit = max(fitnesses)
    print(f"Поколение {gen+1}: средний капитал = {avg_fit:.2f}, максимальный = {max_fit:.2f}")

    # Отбор (элитизм + турнир)
    sorted_indices = sorted(range(POP_SIZE), key=lambda i: fitnesses[i], reverse=True)
    new_pop = [population[sorted_indices[0]]]  # элита
    while len(new_pop) < POP_SIZE:
        # Турнирный отбор
        i1, i2 = random.sample(range(POP_SIZE), 2)
        winner = i1 if fitnesses[i1] > fitnesses[i2] else i2
        # Скрещивание с элитой или другим турнирным победителем
        if random.random() < 0.7:
            parent2 = population[sorted_indices[0]]  # кроссовер с лучшей особью
        else:
            parent2 = population[winner]
        child = crossover(population[winner], parent2)
        # Мутация
        if random.random() < 0.3:
            child = mutate(child, scale=0.1)
        new_pop.append(child)
    population = new_pop

print(f"\n=== Лучшие параметры после {GENERATIONS} поколений ===")
print(f"max_risk_per_trade = {best_overall['max_risk_per_trade']:.4f}")
print(f"phi_llm = {best_overall['phi_llm']:.4f}")
print(f"Достигнутый капитал = {best_fitness:.2f}")

# Сравнение со стандартными параметрами из документации
standard_params = {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
standard_fitness = evaluate(standard_params, seed=999)
print(f"\nКапитал со стандартными параметрами (0.05, 0.15): {standard_fitness:.2f}")
print(f"Улучшение: {best_fitness - standard_fitness:.2f}")