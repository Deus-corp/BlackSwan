#!/usr/bin/env python3
"""Generic genetic/evolution engine for BlackSwan autonomous swarms.

This engine is intentionally domain-neutral. Trading parameters are supported as
one default search space, but the engine can evolve any numeric parameter genome
for any swarm: security, explorer, improver, memory, simulation, or trade.

Features:
- Genome dataclass with stable id, lineage, species, age, niche metadata.
- Fitness cache to avoid repeated evaluations.
- Speciation by normalized parameter distance.
- Adaptive mutation based on stagnation and diversity.
- Tournament selection with elitism.
- Quality-Diversity archive for novelty preservation.
- Backward-compatible API used by current trade swarm:
  - initialize()
  - evolve_generation()
  - champion
  - add_genome()
  - get_best()
  - export_population()
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Optional


NumericParams = dict[str, float]
FitnessFn = Callable[[NumericParams], float]


DEFAULT_PARAM_SPACE: dict[str, tuple[float, float]] = {
    # Generic autonomy knobs.
    "risk_tolerance": (0.01, 0.30),
    "exploration_rate": (0.01, 0.70),
    "confidence_floor": (0.01, 0.50),
    "memory_weight": (0.01, 1.00),
    "coordination_weight": (0.01, 1.00),
    "self_improvement_rate": (0.001, 0.25),
    # Backward-compatible trade knobs.
    "max_risk_per_trade": (0.01, 0.15),
    "phi_llm": (0.05, 0.35),
    "trailing_stop_ratio": (0.005, 0.05),
    "momentum_window": (5.0, 60.0),
}


@dataclass(slots=True)
class Genome:
    """A candidate strategy/configuration in an evolutionary population."""

    params: NumericParams
    fitness: float = 0.0
    age: int = 0
    niche: str = "exploration"
    species_id: int = -1
    parents: tuple[Optional[str], Optional[str]] = (None, None)
    lineage: list[str] = field(default_factory=list)
    mutation_count: int = 0
    eval_count: int = 0
    genome_id: str = ""
    created_at: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.params = _normalize_params(self.params)
        self.fitness = _safe_float(self.fitness, 0.0)
        self.age = max(0, int(self.age))
        self.niche = str(self.niche or "exploration").strip() or "exploration"
        self.species_id = int(self.species_id)
        self.lineage = [str(item) for item in self.lineage if str(item)]
        self.mutation_count = max(0, int(self.mutation_count))
        self.eval_count = max(0, int(self.eval_count))
        self.created_at = _safe_float(self.created_at, time.time())
        self.meta = dict(self.meta or {})

        if not self.genome_id:
            self.genome_id = self.compute_id(self.params, created_at=self.created_at)

    def copy(self) -> Genome:
        """Return a detached copy of the genome."""
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
            genome_id=self.genome_id,
            created_at=self.created_at,
            meta=dict(self.meta),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize genome to a JSON-friendly dictionary."""
        return {
            "params": dict(self.params),
            "fitness": self.fitness,
            "age": self.age,
            "niche": self.niche,
            "species_id": self.species_id,
            "parents": list(self.parents),
            "lineage": list(self.lineage),
            "mutation_count": self.mutation_count,
            "eval_count": self.eval_count,
            "genome_id": self.genome_id,
            "created_at": self.created_at,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Genome:
        """Deserialize a genome from a mapping."""
        parents_raw = data.get("parents", (None, None))
        parents: tuple[Optional[str], Optional[str]]
        if isinstance(parents_raw, Sequence) and not isinstance(parents_raw, (str, bytes, bytearray)):
            first = str(parents_raw[0]) if len(parents_raw) > 0 and parents_raw[0] is not None else None
            second = str(parents_raw[1]) if len(parents_raw) > 1 and parents_raw[1] is not None else None
            parents = (first, second)
        else:
            parents = (None, None)

        return cls(
            params=dict(data.get("params", {})),
            fitness=_safe_float(data.get("fitness"), 0.0),
            age=int(data.get("age", 0) or 0),
            niche=str(data.get("niche", "exploration")),
            species_id=int(data.get("species_id", -1) or -1),
            parents=parents,
            lineage=[str(item) for item in data.get("lineage", []) or []],
            mutation_count=int(data.get("mutation_count", 0) or 0),
            eval_count=int(data.get("eval_count", 0) or 0),
            genome_id=str(data.get("genome_id", "") or ""),
            created_at=_safe_float(data.get("created_at"), time.time()),
            meta=dict(data.get("meta", {}) or {}),
        )

    @staticmethod
    def compute_id(params: Mapping[str, Any], *, created_at: float | None = None) -> str:
        """Compute stable-ish genome id from params and optional creation timestamp."""
        payload = {
            "params": _normalize_params(params),
            "created_at": round(float(created_at if created_at is not None else 0.0), 6),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class Species:
    """Group of similar genomes."""

    species_id: int
    representative: Genome
    members: list[int] = field(default_factory=list)
    best_fitness: float = float("-inf")
    stagnation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "species_id": self.species_id,
            "representative": self.representative.to_dict(),
            "members": list(self.members),
            "best_fitness": self.best_fitness,
            "stagnation": self.stagnation,
        }


class GeneticEngine:
    """Domain-neutral genetic algorithm engine for autonomous swarm evolution."""

    def __init__(
        self,
        pop_size: int = 50,
        fitness_fn: Optional[FitnessFn] = None,
        mutation_rate: float = 0.25,
        elite_size: int = 2,
        tournament_size: int = 3,
        species_threshold: float = 0.25,
        max_species: int = 16,
        novelty_weight: float = 0.0,
        qd_bonus_weight: float = 0.3,
        seed: Optional[int] = None,
        param_space: Optional[Mapping[str, tuple[float, float]]] = None,
        niche: str = "exploration",
        qd_grid_size: int = 10,
    ) -> None:
        if pop_size < 2:
            raise ValueError("pop_size must be >= 2")
        if elite_size < 0:
            raise ValueError("elite_size must be >= 0")
        if tournament_size < 2:
            raise ValueError("tournament_size must be >= 2")
        if max_species < 1:
            raise ValueError("max_species must be >= 1")
        if qd_grid_size < 2:
            raise ValueError("qd_grid_size must be >= 2")

        self.pop_size = int(pop_size)
        self.base_mutation_rate = self._clamp_rate(mutation_rate)
        self.mutation_rate = self.base_mutation_rate
        self.elite_size = min(int(elite_size), self.pop_size)
        self.tournament_size = min(int(tournament_size), self.pop_size)
        self.species_threshold = max(0.0, float(species_threshold))
        self.max_species = int(max_species)
        self.novelty_weight = max(0.0, float(novelty_weight))
        self.qd_bonus_weight = self._clamp_rate(qd_bonus_weight)
        self.qd_grid_size = int(qd_grid_size)
        self.default_niche = str(niche or "exploration")

        self.param_space = self._normalize_param_space(param_space or DEFAULT_PARAM_SPACE)
        self._rng = random.Random(seed)

        self.fitness_fn: FitnessFn = fitness_fn or self._default_fitness
        self.population: list[Genome] = []
        self.species: dict[int, Species] = {}
        self.qd_archive: dict[tuple[int, int], Genome] = {}

        self._species_seq = 0
        self._fitness_cache: dict[str, float] = {}
        self._last_best_fitness = float("-inf")
        self._stagnation = 0
        self.generation = 0
        self.champion: tuple[NumericParams, float] = ({}, float("-inf"))

    def initialize(self, seed_population: Optional[Iterable[Mapping[str, Any]]] = None) -> None:
        """Initialize population from optional seed genomes/params and random fill."""
        self.population = []

        if seed_population is not None:
            for item in seed_population:
                if isinstance(item, Genome):
                    genome = item.copy()
                    genome.lineage = (genome.lineage + ["seed"])[:12]
                elif isinstance(item, Mapping) and "params" in item:
                    genome = Genome.from_dict(item)
                    genome.lineage = (genome.lineage + ["seed"])[:12]
                else:
                    genome = Genome(params=dict(item), niche=self.default_niche, lineage=["seed"])

                self.population.append(self._bounded_genome(genome))

                if len(self.population) >= self.pop_size:
                    break

        while len(self.population) < self.pop_size:
            self.population.append(
                Genome(
                    params=self._random_params(),
                    niche=self.default_niche,
                    lineage=["random"],
                )
            )

        self._fitness_cache.clear()
        self._rebuild_species()
        self.evaluate_population()

    def evaluate_population(self) -> None:
        """Evaluate all genomes, update QD archive, species, and champion."""
        for genome in self.population:
            base_fitness = self._fitness(genome.params)
            novelty = self.novelty_bonus(genome)
            genome.fitness = _finite_or(base_fitness + self.qd_bonus_weight * novelty, float("-inf"))
            genome.eval_count += 1
            self._update_archive(genome)

        self._rebuild_species()
        self._assign_species_ids()
        self._update_champion()

    def evolve_generation(self) -> None:
        """Evolve population by elitism, QD injection, selection, crossover, and mutation."""
        if not self.population:
            raise RuntimeError("Population is empty; call initialize() first")

        for genome in self.population:
            genome.age += 1

        self.evaluate_population()

        ranked = self._ranked_population()
        next_population: list[Genome] = [g.copy() for g in ranked[: self.elite_size]]
        seen_hashes = {self._hash_params(g.params) for g in next_population}

        for archive_genome in self._ranked_archive():
            if len(next_population) >= self.pop_size:
                break

            signature = self._hash_params(archive_genome.params)
            if signature not in seen_hashes:
                next_population.append(archive_genome.copy())
                seen_hashes.add(signature)

        while len(next_population) < self.pop_size:
            parent_a = self._species_aware_pick()
            parent_b = self._species_aware_pick()
            child = self.crossover(parent_a, parent_b)
            child = self.mutate(child)
            next_population.append(child)

        self.population = next_population[: self.pop_size]
        self.generation += 1

        self._rebuild_species()
        self.evaluate_population()
        self._update_stagnation()
        self.mutation_rate = self._adaptive_mutation_rate()
        self._update_champion()

    def crossover(self, a: Genome, b: Genome) -> Genome:
        """Create child genome by uniform/blend crossover."""
        keys = sorted(set(a.params) | set(b.params) | set(self.param_space))
        child_params: NumericParams = {}

        for key in keys:
            low, high = self._bounds_for(key)
            default = (low + high) / 2.0
            va = _safe_float(a.params.get(key), default)
            vb = _safe_float(b.params.get(key), default)

            value = va if self._rng.random() < 0.5 else vb

            if self._rng.random() < 0.35:
                alpha = self._rng.random()
                value = alpha * va + (1.0 - alpha) * vb

            child_params[key] = self._clamp_param(key, value)

        parent_a_id = a.genome_id or self._hash_params(a.params)[:16]
        parent_b_id = b.genome_id or self._hash_params(b.params)[:16]

        return Genome(
            params=child_params,
            fitness=0.0,
            age=0,
            niche=a.niche if self._rng.random() < 0.5 else b.niche,
            parents=(parent_a_id, parent_b_id),
            lineage=(a.lineage[-4:] + b.lineage[-4:] + ["child"])[-12:],
            meta={"generation": self.generation + 1},
        )

    def mutate(self, genome: Genome) -> Genome:
        """Return mutated copy of genome."""
        mutated = genome.copy()
        rate = self._adaptive_mutation_rate()
        keys = list(mutated.params.keys()) or list(self.param_space.keys())

        for key in keys:
            if key not in mutated.params:
                low, high = self._bounds_for(key)
                mutated.params[key] = self._rng.uniform(low, high)

            if self._rng.random() < rate:
                old_value = _safe_float(mutated.params[key], 0.0)
                low, high = self._bounds_for(key)
                span = max(1e-12, high - low)

                if self._rng.random() < 0.7:
                    sigma = span * (0.04 + 0.25 * rate)
                    new_value = old_value + self._rng.gauss(0.0, sigma)
                else:
                    factor = math.exp(self._rng.gauss(0.0, 0.08 + 0.25 * rate))
                    if self._rng.random() < 0.5:
                        factor = 1.0 / factor
                    new_value = old_value * factor

                mutated.params[key] = self._clamp_param(key, new_value)
                mutated.mutation_count += 1

        if keys and self._rng.random() < rate * 0.35:
            key = self._rng.choice(keys)
            low, high = self._bounds_for(key)
            span = high - low
            mutated.params[key] = self._clamp_param(
                key,
                _safe_float(mutated.params[key], (low + high) / 2.0) + self._rng.uniform(-0.15, 0.15) * span,
            )
            mutated.mutation_count += 1

        mutated.age = 0
        mutated.fitness = 0.0
        mutated.eval_count = 0
        mutated.species_id = -1
        mutated.genome_id = Genome.compute_id(mutated.params, created_at=time.time())
        mutated.created_at = time.time()
        mutated.lineage = (mutated.lineage + ["mut"])[-12:]
        return mutated

    def add_genome(self, genome: Genome | Mapping[str, Any]) -> None:
        """Add external genome, preserving population size."""
        if isinstance(genome, Genome):
            candidate = genome.copy()
        elif isinstance(genome, Mapping) and "params" in genome:
            candidate = Genome.from_dict(genome)
        elif isinstance(genome, Mapping):
            candidate = Genome(params=dict(genome), niche=self.default_niche, lineage=["import"])
        else:
            raise TypeError("genome must be Genome or mapping")

        candidate = self._bounded_genome(candidate)
        self.population.append(candidate)

        if len(self.population) > self.pop_size:
            self.population = self._ranked_population()[: self.pop_size]

        self._rebuild_species()
        self.evaluate_population()

    def best(self, top_n: int = 1) -> list[NumericParams]:
        """Legacy helper returning params of top N genomes."""
        return [dict(g.params) for g in self._ranked_population()[: max(0, int(top_n))]]

    def get_best(self, top_n: int = 1) -> list[Genome]:
        """Return copies of top N genomes."""
        return [g.copy() for g in self._ranked_population()[: max(0, int(top_n))]]

    def get_champion(self) -> tuple[NumericParams, float]:
        """Return champion as (params, fitness)."""
        return dict(self.champion[0]), float(self.champion[1])

    def export_population(self) -> list[NumericParams]:
        """Legacy helper returning params only."""
        return [dict(g.params) for g in self.population]

    def export_genomes(self) -> list[dict[str, Any]]:
        """Export full genome metadata."""
        return [g.to_dict() for g in self.population]

    def import_genomes(self, genomes: Iterable[Genome | Mapping[str, Any]]) -> None:
        """Replace population with provided genomes and evaluate."""
        imported: list[Genome] = []

        for item in genomes:
            if isinstance(item, Genome):
                imported.append(self._bounded_genome(item.copy()))
            elif isinstance(item, Mapping) and "params" in item:
                imported.append(self._bounded_genome(Genome.from_dict(item)))
            elif isinstance(item, Mapping):
                imported.append(self._bounded_genome(Genome(params=dict(item), lineage=["import"])))

            if len(imported) >= self.pop_size:
                break

        self.population = imported
        while len(self.population) < self.pop_size:
            self.population.append(Genome(params=self._random_params(), niche=self.default_niche, lineage=["random"]))

        self._fitness_cache.clear()
        self.evaluate_population()

    def set_mutation_rate(self, rate: float) -> None:
        """Set base mutation rate."""
        self.base_mutation_rate = self._clamp_rate(rate)
        self.mutation_rate = self.base_mutation_rate

    def set_fitness_fn(self, fn: FitnessFn) -> None:
        """Set custom fitness function and re-evaluate population if initialized."""
        if not callable(fn):
            raise TypeError("fitness function must be callable")

        self.fitness_fn = fn
        self._fitness_cache.clear()

        if self.population:
            self.evaluate_population()

    def species_count(self) -> int:
        """Return active species count."""
        return len(self.species)

    def diversity(self) -> float:
        """Return unique-genome diversity in [0, 1]."""
        if len(self.population) <= 1:
            return 0.0

        signatures = {self._hash_params(g.params) for g in self.population}
        return len(signatures) / len(self.population)

    def novelty_score(self, genome: Genome) -> float:
        """Return average distance to nearest neighbors."""
        if len(self.population) <= 1:
            return 0.0

        distances = [
            self._distance(genome.params, other.params)
            for other in self.population
            if other is not genome
        ]
        if not distances:
            return 0.0

        k = min(5, len(distances))
        return sum(sorted(distances)[:k]) / k

    def novelty_bonus(self, genome: Genome) -> float:
        """Return QD archive novelty bonus."""
        key = self._compute_descriptor(genome)

        if key not in self.qd_archive:
            return 1.0

        occupant = self.qd_archive[key]
        distance = self._distance(genome.params, occupant.params)
        return max(0.05, min(0.3, distance + 0.05))

    def summary(self) -> dict[str, Any]:
        """Return serializable engine summary."""
        champion_params, champion_fitness = self.get_champion()
        return {
            "generation": self.generation,
            "population_size": len(self.population),
            "species_count": self.species_count(),
            "diversity": self.diversity(),
            "mutation_rate": self.mutation_rate,
            "stagnation": self._stagnation,
            "qd_archive_size": len(self.qd_archive),
            "champion_fitness": champion_fitness,
            "champion_params": champion_params,
        }

    def _default_fitness(self, params: NumericParams) -> float:
        """Domain-neutral default fitness that rewards balanced, finite params."""
        if not params:
            return 0.0

        normalized_values = []
        for key, value in params.items():
            low, high = self._bounds_for(key)
            span = max(1e-12, high - low)
            normalized_values.append((_safe_float(value, low) - low) / span)

        if not normalized_values:
            return 0.0

        center_score = sum(1.0 - abs(value - 0.5) * 2.0 for value in normalized_values) / len(normalized_values)
        spread = max(normalized_values) - min(normalized_values) if len(normalized_values) > 1 else 0.0
        return max(0.0, center_score - 0.15 * spread)

    def _fitness(self, params: NumericParams) -> float:
        key = self._hash_params(params)
        if key in self._fitness_cache:
            return self._fitness_cache[key]

        try:
            value = float(self.fitness_fn(dict(params)))
        except Exception:
            value = float("-inf")

        value = _finite_or(value, float("-inf"))
        self._fitness_cache[key] = value
        return value

    def _ranked_population(self) -> list[Genome]:
        return sorted(
            self.population,
            key=lambda genome: genome.fitness + self.novelty_weight * self.novelty_score(genome),
            reverse=True,
        )

    def _ranked_archive(self) -> list[Genome]:
        return sorted(self.qd_archive.values(), key=lambda genome: genome.fitness, reverse=True)

    def _tournament_pick(self) -> Genome:
        if not self.population:
            raise RuntimeError("Population is empty")

        k = min(self.tournament_size, len(self.population))
        contestants = self._rng.sample(self.population, k=k)
        return max(
            contestants,
            key=lambda genome: genome.fitness + self.novelty_weight * self.novelty_score(genome),
        )

    def _species_aware_pick(self) -> Genome:
        if not self.species:
            return self._tournament_pick()

        species_items = [species for species in self.species.values() if species.members]
        if not species_items:
            return self._tournament_pick()

        weights = [max(1, len(species.members)) for species in species_items]
        chosen = self._rng.choices(species_items, weights=weights, k=1)[0]

        species_population = [
            self.population[index]
            for index in chosen.members
            if 0 <= index < len(self.population)
        ]

        if not species_population:
            return self._tournament_pick()

        k = min(self.tournament_size, len(species_population))
        contestants = self._rng.sample(species_population, k=k)
        return max(
            contestants,
            key=lambda genome: genome.fitness + self.novelty_weight * self.novelty_score(genome),
        )

    def _rebuild_species(self) -> None:
        self.species = {}
        self._species_seq = 0

        for index, genome in enumerate(self.population):
            assigned_species_id = self._find_species_for(genome)

            if assigned_species_id is None and len(self.species) >= self.max_species:
                assigned_species_id = self._closest_species_id(genome)

            if assigned_species_id is None:
                assigned_species_id = self._species_seq
                self._species_seq += 1
                self.species[assigned_species_id] = Species(
                    species_id=assigned_species_id,
                    representative=genome.copy(),
                    members=[],
                    best_fitness=float("-inf"),
                    stagnation=0,
                )

            species_obj = self.species[assigned_species_id]
            species_obj.members.append(index)

            if genome.fitness > species_obj.best_fitness:
                species_obj.best_fitness = genome.fitness
                species_obj.representative = genome.copy()
                species_obj.stagnation = 0

        self._assign_species_ids()

    def _find_species_for(self, genome: Genome) -> Optional[int]:
        for species_id, species_obj in self.species.items():
            if self._distance(genome.params, species_obj.representative.params) <= self.species_threshold:
                return species_id
        return None

    def _closest_species_id(self, genome: Genome) -> Optional[int]:
        if not self.species:
            return None

        return min(
            self.species,
            key=lambda species_id: self._distance(
                genome.params,
                self.species[species_id].representative.params,
            ),
        )

    def _assign_species_ids(self) -> None:
        for species_id, species_obj in self.species.items():
            for index in species_obj.members:
                if 0 <= index < len(self.population):
                    self.population[index].species_id = species_id

    def _update_stagnation(self) -> None:
        best_now = max((genome.fitness for genome in self.population), default=float("-inf"))

        if best_now > self._last_best_fitness + 1e-12:
            self._last_best_fitness = best_now
            self._stagnation = 0
            for species_obj in self.species.values():
                species_obj.stagnation = 0
        else:
            self._stagnation += 1
            for species_obj in self.species.values():
                species_obj.stagnation += 1

    def _update_champion(self) -> None:
        if not self.population:
            self.champion = ({}, float("-inf"))
            return

        best = max(self.population, key=lambda genome: genome.fitness)
        self.champion = (dict(best.params), float(best.fitness))

    def _adaptive_mutation_rate(self) -> float:
        diversity = self.diversity()
        stagnation_boost = min(0.25, self._stagnation * 0.02)
        diversity_boost = 0.0 if diversity >= 0.6 else (0.25 - 0.25 * diversity)
        return max(0.02, min(0.8, self.base_mutation_rate + stagnation_boost + diversity_boost))

    def _distance(self, a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
        keys = set(a) | set(b) | set(self.param_space)
        if not keys:
            return 0.0

        total = 0.0

        for key in keys:
            low, high = self._bounds_for(key)
            span = max(1e-12, high - low)
            va = (_safe_float(a.get(key), (low + high) / 2.0) - low) / span
            vb = (_safe_float(b.get(key), (low + high) / 2.0) - low) / span
            total += (va - vb) ** 2

        return math.sqrt(total / len(keys))

    def _random_params(self) -> NumericParams:
        return {
            key: self._rng.uniform(low, high)
            for key, (low, high) in self.param_space.items()
        }

    def _bounded_genome(self, genome: Genome) -> Genome:
        bounded = genome.copy()
        bounded.params = {
            key: self._clamp_param(key, value)
            for key, value in bounded.params.items()
        }

        for key, (low, high) in self.param_space.items():
            if key not in bounded.params:
                bounded.params[key] = self._rng.uniform(low, high)

        return bounded

    def _compute_descriptor(self, genome: Genome) -> tuple[int, int]:
        """Compute QD cell from generic risk/aggression-like descriptors."""
        params = genome.params

        risk_source = (
            params.get("risk_tolerance")
            if "risk_tolerance" in params
            else params.get("max_risk_per_trade", 0.05)
        )
        exploration_source = params.get("exploration_rate", params.get("phi_llm", 0.15))
        coordination_source = params.get("coordination_weight", params.get("memory_weight", 0.5))
        improvement_source = params.get("self_improvement_rate", params.get("trailing_stop_ratio", 0.01))

        risk = self._normalize_value("risk_tolerance", risk_source)
        exploration = self._normalize_value("exploration_rate", exploration_source)
        coordination = self._normalize_value("coordination_weight", coordination_source)
        improvement = self._normalize_value("self_improvement_rate", improvement_source)

        row_value = 0.65 * risk + 0.35 * exploration
        col_value = 0.50 * coordination + 0.50 * improvement

        return (
            self._grid_index(row_value),
            self._grid_index(col_value),
        )

    def _update_archive(self, genome: Genome) -> None:
        key = self._compute_descriptor(genome)
        current = self.qd_archive.get(key)

        if current is None or genome.fitness > current.fitness:
            self.qd_archive[key] = genome.copy()

    def _normalize_value(self, key: str, value: Any) -> float:
        low, high = self._bounds_for(key)
        span = max(1e-12, high - low)
        normalized = (_safe_float(value, (low + high) / 2.0) - low) / span
        return max(0.0, min(1.0, normalized))

    def _grid_index(self, value: float) -> int:
        return max(0, min(self.qd_grid_size - 1, int(value * self.qd_grid_size)))

    def _bounds_for(self, key: str) -> tuple[float, float]:
        bounds = self.param_space.get(key)
        if bounds is None:
            return 0.0, 1.0
        return bounds

    def _clamp_param(self, key: str, value: Any) -> float:
        low, high = self._bounds_for(key)
        return max(low, min(high, _safe_float(value, low)))

    @staticmethod
    def _normalize_param_space(param_space: Mapping[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
        normalized: dict[str, tuple[float, float]] = {}

        for key, bounds in param_space.items():
            if not isinstance(bounds, Sequence) or len(bounds) != 2:
                raise ValueError(f"Invalid bounds for {key!r}: expected (low, high)")

            low = _safe_float(bounds[0], 0.0)
            high = _safe_float(bounds[1], 1.0)

            if not math.isfinite(low) or not math.isfinite(high):
                raise ValueError(f"Invalid finite bounds for {key!r}")
            if high <= low:
                raise ValueError(f"Upper bound must be > lower bound for {key!r}")

            normalized[str(key)] = (low, high)

        if not normalized:
            raise ValueError("param_space cannot be empty")

        return normalized

    @staticmethod
    def _hash_params(params: Mapping[str, Any]) -> str:
        raw = json.dumps(_normalize_params(params), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _clamp(x: float, low: float = 0.0001, high: float = 1.0) -> float:
        """Legacy static clamp helper."""
        value = _safe_float(x, low)
        return max(low, min(high, value))

    @staticmethod
    def _clamp_rate(rate: float) -> float:
        return max(0.0, min(1.0, _safe_float(rate, 0.0)))


def _normalize_params(params: Mapping[str, Any]) -> NumericParams:
    normalized: NumericParams = {}

    for key, value in dict(params or {}).items():
        number = _safe_float(value, 0.0)
        normalized[str(key)] = number

    return normalized


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    return number if math.isfinite(number) else default


def _finite_or(value: float, default: float) -> float:
    return value if math.isfinite(value) else default