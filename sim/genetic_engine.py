from __future__ import annotations

"""
GeneticEngine for BlackSwan.

Features:
- Genome dataclass with lineage/species/age metadata
- fitness cache to avoid repeated evaluation
- speciation by param-distance threshold
- adaptive mutation based on stagnation/diversity
- tournament selection + elitism
- compatibility helpers for legacy code paths

Designed to be dropped into the current project and used as:

    engine = GeneticEngine(pop_size=10)
    engine.initialize()
    engine.evolve_generation()

If you want custom fitness logic, pass `fitness_fn`.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import hashlib
import math
import random


# =========================
# DATA MODEL
# =========================

@dataclass(slots=True)
class Genome:
    params: Dict[str, float]
    fitness: float = 0.0
    age: int = 0
    niche: str = "exploration"
    species_id: int = -1
    parents: Tuple[Optional[int], Optional[int]] = (None, None)
    lineage: List[str] = field(default_factory=list)
    mutation_count: int = 0
    eval_count: int = 0

    def copy(self) -> "Genome":
        return Genome(
            params=dict(self.params),
            fitness=self.fitness,
            age=self.age,
            niche=self.niche,
            species_id=self.species_id,
            parents=self.parents,
            lineage=list(self.lineage),
            mutation_count=self.mutation_count,
            eval_count=self.eval_count,
        )


@dataclass(slots=True)
class Species:
    species_id: int
    representative: Genome
    members: List[int] = field(default_factory=list)
    best_fitness: float = float("-inf")
    stagnation: int = 0


# =========================
# ENGINE
# =========================

class GeneticEngine:
    def __init__(
        self,
        pop_size: int = 50,
        fitness_fn: Optional[Callable[[Dict[str, float]], float]] = None,
        mutation_rate: float = 0.25,
        elite_size: int = 2,
        tournament_size: int = 3,
        species_threshold: float = 0.25,
        max_species: int = 16,
        novelty_weight: float = 0.0,
        seed: Optional[int] = None,
    ):
        if pop_size < 2:
            raise ValueError("pop_size must be >= 2")
        if elite_size < 0:
            raise ValueError("elite_size must be >= 0")
        if tournament_size < 2:
            raise ValueError("tournament_size must be >= 2")
        
            # Quality-Diversity archive (10x10 grid)
        self.qd_archive = {}
        self.qd_bonus_weight = 0.3   # вес новизны в итоговой оценке

        self.pop_size = pop_size
        self.base_mutation_rate = float(mutation_rate)
        self.mutation_rate = float(mutation_rate)
        self.elite_size = min(elite_size, pop_size)
        self.tournament_size = min(tournament_size, pop_size)
        self.species_threshold = float(species_threshold)
        self.max_species = max_species
        self.novelty_weight = float(novelty_weight)
        self._rng = random.Random(seed)

        self.fitness_fn = fitness_fn or self._default_fitness
        self.population: List[Genome] = []
        self.species: Dict[int, Species] = {}
        self._species_seq = 0
        self._fitness_cache: Dict[str, float] = {}
        self._last_best_fitness = float("-inf")
        self._stagnation = 0
        self.generation = 0
        self.champion: Tuple[Dict[str, float], float] = ({}, float("-inf"))

    # =========================
    # INITIALIZATION
    # =========================

    def initialize(self, seed_population: Optional[Iterable[Dict[str, float]]] = None) -> None:
        self.population = []
        if seed_population is not None:
            for params in seed_population:
                self.population.append(Genome(params=dict(params), lineage=["seed"]))

        while len(self.population) < self.pop_size:
            self.population.append(Genome(params=self._random_params(), lineage=["random"]))

        self._rebuild_species()
        self.evaluate_population()
        self._update_champion()

    # =========================
    # FITNESS
    # =========================

    def _default_fitness(self, params: Dict[str, float]) -> float:
        if not params:
            return 0.0
        vals = [float(v) for v in params.values()]
        center = sum(1.0 - abs(v - 0.5) * 2.0 for v in vals) / len(vals)
        spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        return max(0.0, center - 0.15 * spread)

    @staticmethod
    def _hash_params(params: Dict[str, float]) -> str:
        items = sorted((str(k), round(float(v), 10)) for k, v in params.items())
        raw = repr(items).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _fitness(self, params: Dict[str, float]) -> float:
        key = self._hash_params(params)
        cached = self._fitness_cache.get(key)
        if cached is not None:
            return cached
        value = float(self.fitness_fn(params))
        if value != value:  # NaN
            value = float("-inf")
        self._fitness_cache[key] = value
        return value

    def evaluate_population(self) -> None:
        for genome in self.population:
            # базовый фитнес
            base_fitness = self._fitness(genome.params)
            # бонус за новизну (Quality-Diversity)
            novelty = self.novelty_bonus(genome)
            genome.fitness = base_fitness + self.qd_bonus_weight * novelty
            genome.eval_count += 1
            # обновляем QD-архив
            self._update_archive(genome)
        self._rebuild_species()
        self._assign_species_ids()
        self._update_champion()

    # =========================
    # SPECIES
    # =========================

    def _distance(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        keys = set(a) | set(b)
        if not keys:
            return 0.0
        total = 0.0
        for k in keys:
            va = float(a.get(k, 0.0))
            vb = float(b.get(k, 0.0))
            total += (va - vb) ** 2
        return math.sqrt(total / len(keys))

    def _rebuild_species(self) -> None:
        self.species = {}
        self._species_seq = 0
        if not self.population:
            return

        for idx, genome in enumerate(self.population):
            assigned = False
            for species in self.species.values():
                if self._distance(genome.params, species.representative.params) <= self.species_threshold:
                    species.members.append(idx)
                    assigned = True
                    break
            if not assigned:
                sid = self._species_seq
                self._species_seq += 1
                self.species[sid] = Species(
                    species_id=sid,
                    representative=genome.copy(),
                    members=[idx],
                )

    def _assign_species_ids(self) -> None:
        for sid, species in self.species.items():
            for idx in species.members:
                self.population[idx].species_id = sid

    def species_count(self) -> int:
        return len(self.species)

    def diversity(self) -> float:
        if len(self.population) <= 1:
            return 0.0
        signatures = {self._hash_params(g.params) for g in self.population}
        return len(signatures) / len(self.population)

    def novelty_score(self, genome: Genome) -> float:
        if not self.population:
            return 0.0
        dists = [self._distance(genome.params, other.params) for other in self.population if other is not genome]
        if not dists:
            return 0.0
        return sum(sorted(dists)[: min(5, len(dists))]) / min(5, len(dists))

    # =========================
    # SELECTION
    # =========================

    def _tournament_pick(self) -> Genome:
        contestants = self._rng.sample(self.population, k=min(self.tournament_size, len(self.population)))
        contestants.sort(
            key=lambda g: g.fitness + self.novelty_weight * self.novelty_score(g),
            reverse=True,
        )
        return contestants[0]

    def _ranked_population(self) -> List[Genome]:
        return sorted(
            self.population,
            key=lambda g: g.fitness + self.novelty_weight * self.novelty_score(g),
            reverse=True,
        )

    # =========================
    # REPRODUCTION
    # =========================

    def crossover(self, a: Genome, b: Genome) -> Genome:
        keys = sorted(set(a.params) | set(b.params))
        child_params: Dict[str, float] = {}
        for k in keys:
            va = float(a.params.get(k, 0.5))
            vb = float(b.params.get(k, 0.5))
            if self._rng.random() < 0.5:
                val = va
            else:
                val = vb
            if self._rng.random() < 0.35:
                alpha = self._rng.random()
                val = alpha * va + (1.0 - alpha) * vb
            child_params[k] = self._clamp(val)

        child = Genome(
            params=child_params,
            fitness=0.0,
            age=0,
            niche=a.niche if self._rng.random() < 0.5 else b.niche,
            parents=(id(a), id(b)),
            lineage=(a.lineage[-5:] + b.lineage[-5:] + ["child"])[-12:],
        )
        return child

    def mutate(self, genome: Genome) -> Genome:
        mutated = genome.copy()
        rate = self._adaptive_mutation_rate()
        keys = list(mutated.params.keys())
        for k in keys:
            if self._rng.random() < rate:
                old = mutated.params[k]
                sigma = 0.08 + 0.25 * rate
                factor = math.exp(self._rng.gauss(0.0, sigma))
                if self._rng.random() < 0.5:
                    factor = 1.0 / factor
                mutated.params[k] = self._clamp(old * factor)
                mutated.mutation_count += 1

        if keys and self._rng.random() < rate * 0.35:
            k = self._rng.choice(keys)
            mutated.params[k] = self._clamp(mutated.params[k] + self._rng.uniform(-0.15, 0.15))
            mutated.mutation_count += 1

        mutated.age = 0
        mutated.fitness = 0.0
        mutated.eval_count = 0
        mutated.lineage.append("mut")
        mutated.lineage = mutated.lineage[-12:]
        return mutated

    def _adaptive_mutation_rate(self) -> float:
        div = self.diversity()
        stagnation_boost = min(0.25, self._stagnation * 0.02)
        diversity_boost = 0.0 if div >= 0.6 else (0.25 - 0.25 * div)
        rate = self.base_mutation_rate + stagnation_boost + diversity_boost
        return max(0.02, min(0.8, rate))

    # =========================
    # SURVIVOR SELECTION
    # =========================

    def evolve_generation(self) -> None:
        if not self.population:
            raise RuntimeError("population is empty; call initialize() first")

        for genome in self.population:
            genome.age += 1

        self.evaluate_population()
        ranked = self._ranked_population()
        elites = [g.copy() for g in ranked[: self.elite_size]]
        next_population: List[Genome] = elites

        # Добавляем в элиту по одному лучшему геному из каждой ячейки QD-архива
        for genome in self.qd_archive.values():
            if len(next_population) < self.pop_size:
                next_population.append(genome.copy())

        while len(next_population) < self.pop_size:
            parent_a = self._species_aware_pick()
            parent_b = self._species_aware_pick()
            child = self.crossover(parent_a, parent_b)
            child = self.mutate(child)
            next_population.append(child)

        self.population = next_population[: self.pop_size]
        self._rebuild_species()
        self.evaluate_population()
        self.generation += 1
        self._update_stagnation()
        self._update_champion()

    def _species_aware_pick(self) -> Genome:
        if not self.species:
            return self._tournament_pick()

        species_items = list(self.species.values())
        sizes = [max(1, len(s.members)) for s in species_items]
        chosen_species = self._rng.choices(species_items, weights=sizes, k=1)[0]
        indices = chosen_species.members or list(range(len(self.population)))
        contestants = [self.population[i] for i in indices]
        contestants.sort(
            key=lambda g: g.fitness + self.novelty_weight * self.novelty_score(g),
            reverse=True,
        )
        top_k = contestants[: max(1, min(self.tournament_size, len(contestants)))]
        return self._rng.choice(top_k)

    def _update_stagnation(self) -> None:
        best_now = max((g.fitness for g in self.population), default=float("-inf"))
        if best_now > self._last_best_fitness + 1e-12:
            self._last_best_fitness = best_now
            self._stagnation = 0
            for species in self.species.values():
                species.stagnation = 0
                species.best_fitness = max(species.best_fitness, best_now)
        else:
            self._stagnation += 1
            for species in self.species.values():
                species.stagnation += 1

    def _update_champion(self) -> None:
        if not self.population:
            self.champion = ({}, float("-inf"))
            return
        best = max(self.population, key=lambda g: g.fitness)
        self.champion = (dict(best.params), float(best.fitness))

    # =========================
    # CONTROLS
    # =========================

    def set_mutation_rate(self, rate: float) -> None:
        self.base_mutation_rate = max(0.0, min(1.0, float(rate)))
        self.mutation_rate = self.base_mutation_rate

    def set_fitness_fn(self, fn: Callable[[Dict[str, float]], float]) -> None:
        self.fitness_fn = fn
        self._fitness_cache.clear()
        self.evaluate_population()

    # =========================
    # COMPATIBILITY HELPERS
    # =========================

    def best(self, top_n: int = 1) -> List[Dict[str, float]]:
        ranked = self._ranked_population()[:top_n]
        return [dict(g.params) for g in ranked]
    
    def add_genome(self, genome: Genome) -> None:
        """Безопасно добавляет геном в популяцию (инкапсуляция)."""
        self.population.append(genome)
        if len(self.population) > self.pop_size:
            self.population.pop(0)

    def get_best(self, top_n: int = 1) -> List[Genome]:
        return [g.copy() for g in self._ranked_population()[:top_n]]

    def get_champion(self) -> Tuple[Dict[str, float], float]:
        return self.champion

    def export_population(self) -> List[Dict[str, float]]:
        return [dict(g.params) for g in self.population]

    # =========================
    # INTERNALS
    # =========================

    def _random_params(self) -> Dict[str, float]:
        return {
            "max_risk_per_trade": self._clamp(self._rng.uniform(0.01, 0.15)),
            "phi_llm": self._clamp(self._rng.uniform(0.05, 0.35)),
            "exploration_rate": self._clamp(self._rng.uniform(0.05, 0.5)),
            "confidence_floor": self._clamp(self._rng.uniform(0.01, 0.25)),
        }

    @staticmethod
    def _clamp(x: float, low: float = 0.0001, high: float = 1.0) -> float:
        if x != x:  # NaN
            return low
        return max(low, min(high, float(x)))
    
    def _compute_descriptor(self, genome: Genome) -> tuple:
        """Возвращает (row, col) для QD-архива на основе параметров."""
        params = genome.params
        risk = params.get("max_risk_per_trade", 0.05) * params.get("phi_llm", 0.15)
        aggressiveness = params.get("trailing_stop_ratio", 0.01) + params.get("momentum_window", 10) / 100.0
        # Нормируем в 0..9
        row = min(9, max(0, int(risk * 50)))          # risk ~0..0.5 → row 0..9
        col = min(9, max(0, int(aggressiveness * 5)))  # aggressiveness ~0..2 → col 0..9
        return (row, col)

    def _update_archive(self, genome: Genome):
        """Обновляет QD-архив. Если ячейка пуста или фитнес выше – сохраняет геном."""
        row, col = self._compute_descriptor(genome)
        key = (row, col)
        if key not in self.qd_archive or genome.fitness > self.qd_archive[key].fitness:
            self.qd_archive[key] = genome

    def novelty_bonus(self, genome: Genome) -> float:
        """Возвращает бонус за новизну (1.0 если ячейка пуста, 0.3 если занята)."""
        row, col = self._compute_descriptor(genome)
        key = (row, col)
        if key not in self.qd_archive:
            return 1.0
        return 0.3