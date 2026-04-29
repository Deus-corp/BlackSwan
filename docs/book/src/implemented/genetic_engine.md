#!/usr/bin/env python3
"""
Genetic Engine с Champion/Challenger для эволюции стратегий.
Совместим с существующим ROIDispatcher и симулятором.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random, copy, statistics
from typing import List, Dict, Tuple
from sim.evolve_kelly import evaluate, random_params, mutate, crossover, PARAM_BOUNDS

class GeneticEngine:
    def __init__(self, pop_size=10, elite_fraction=0.25, mutation_rate=0.3, crossover_rate=0.7):
        self.pop_size = pop_size
        self.elite_fraction = elite_fraction
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.population: List[Dict] = []
        self.champion: Tuple[Dict, float] = ({}, 0.0)  # (params, fitness)
        self.challenger: Tuple[Dict, float] = ({}, 0.0)
        self.generation = 0

    def initialize(self):
        self.population = [random_params() for _ in range(self.pop_size)]
        # Первый champion – лучший в начальной популяции
        self._evaluate_population()
        best = max(enumerate(self.population), key=lambda x: self._fitness(x[1]))
        self.champion = (copy.deepcopy(best[1]), self._fitness(best[1]))
        self.challenger = ({}, 0.0)

    def _fitness(self, params: Dict) -> float:
        """Оценка особи через симуляцию (можно заменить на исторические данные)"""
        return evaluate(params, seed=self.generation*100)

    def _evaluate_population(self) -> List[float]:
        return [self._fitness(p) for p in self.population]

    def evolve_generation(self):
        """Одна итерация эволюции: отбор, скрещивание, мутация, Champion/Challenger."""
        fitnesses = self._evaluate_population()

        # Отбор (элитизм + турнир)
        sorted_indices = sorted(range(self.pop_size), key=lambda i: fitnesses[i], reverse=True)
        elite_count = max(1, int(self.pop_size * self.elite_fraction))
        new_pop = [copy.deepcopy(self.population[i]) for i in sorted_indices[:elite_count]]

        while len(new_pop) < self.pop_size:
            # Турнир
            i1, i2 = random.sample(range(self.pop_size), 2)
            winner = i1 if fitnesses[i1] > fitnesses[i2] else i2
            # Скрещивание с элитой или другим победителем
            if random.random() < self.crossover_rate:
                parent2 = self.population[sorted_indices[0]]  # кроссовер с лучшей особью
            else:
                parent2 = self.population[winner]
            child = crossover(self.population[winner], parent2)
            # Мутация
            if random.random() < self.mutation_rate:
                child = mutate(child, scale=0.1)
            new_pop.append(child)

        self.population = new_pop
        self.generation += 1

        # Обновляем challenger
        best_idx = max(range(self.pop_size), key=lambda i: self._fitness(self.population[i]))
        best_params = copy.deepcopy(self.population[best_idx])
        best_fitness = self._fitness(best_params)
        if best_params != self.champion[0]:  # не тот же самый
            self.challenger = (best_params, best_fitness)

        # Champion/Challenger проверка
        if self.challenger[1] > self.champion[1]:
            self.champion = copy.deepcopy(self.challenger)
            self.challenger = ({}, 0.0)
            print(f"[Gen {self.generation}] New champion: fitness={self.champion[1]:.2f}")
        else:
            # Challenger не прошёл, остаётся старый champion
            self.challenger = ({}, 0.0)

    def run(self, generations=10):
        self.initialize()
        print(f"Initial champion fitness: {self.champion[1]:.2f}")
        for _ in range(generations):
            self.evolve_generation()
        return self.champion

# Демонстрация
if __name__ == "__main__":
    engine = GeneticEngine(pop_size=10)
    best_params, best_fit = engine.run(generations=10)
    print(f"\nFinal champion: params={best_params}, fitness={best_fit:.2f}")