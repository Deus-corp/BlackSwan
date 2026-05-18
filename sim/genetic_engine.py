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
- Quality-Diversity (QD) archive integration for novelty bonus

Designed to be dropped into the current project and used as:

    engine = GeneticEngine(pop_size=10)
    engine.initialize()
    engine.evolve_generation()

If you want custom fitness logic, pass `fitness_fn`.
"""

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Any


# =========================
# DATA MODEL
# =========================


@dataclass(slots=True)
class Genome:
    """
    Represents a single individual in the genetic algorithm.

    Attributes:
        params: A dictionary of parameters defining the genome's traits.
        fitness: The evaluated fitness score of the genome.
        age: The number of generations this genome has survived.
        niche: A string indicating the genome's role or characteristic (e.g., "exploration").
        species_id: Identifier for the species this genome belongs to.
        parents: A tuple of identifiers (or None) for the parent genomes.
        lineage: A list of strings tracing the genome's evolutionary path.
        mutation_count: Number of mutations applied to this genome.
        eval_count: Number of times this genome's fitness has been evaluated.
    """

    params: Dict[str, float]
    fitness: float = 0.0
    age: int = 0
    niche: str = "exploration"
    species_id: int = -1
    parents: Tuple[Optional[Any], Optional[Any]] = (None, None)  # Using Any for id(), which is volatile.
    lineage: List[str] = field(default_factory=list)
    mutation_count: int = 0
    eval_count: int = 0

    def copy(self) -> Genome:
        """Creates a deep copy of the genome."""
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
    """
    Represents a group of similar genomes (a species).

    Attributes:
        species_id: Unique identifier for the species.
        representative: A Genome chosen to represent the species' characteristics.
        members: A list of indices of genomes belonging to this species in the population.
        best_fitness: The highest fitness achieved by any member of this species.
        stagnation: Number of generations without improvement in `best_fitness`.
    """

    species_id: int
    representative: Genome
    members: List[int] = field(default_factory=list)
    best_fitness: float = float("-inf")
    stagnation: int = 0


# =========================
# ENGINE
# =========================


class GeneticEngine:
    """
    A genetic algorithm engine designed for BlackSwan, incorporating speciation
    and Quality-Diversity principles.

    Manages a population of genomes, evolves them through selection, crossover,
    and mutation, and maintains species diversity.

    Attributes:
        pop_size: The target size of the population.
        base_mutation_rate: The base probability of a parameter mutating.
        mutation_rate: The current adaptive mutation rate.
        elite_size: Number of top-performing genomes to carry over directly.
        tournament_size: Number of genomes to select from for tournament selection.
        species_threshold: Maximum parameter distance for genomes to be in the same species.
        max_species: Maximum number of species to allow.
        novelty_weight: Weight given to novelty score in fitness calculation (currently unused in favor of QD_bonus_weight).
        qd_bonus_weight: Weight of the novelty bonus from the QD archive in total fitness.
        qd_archive: A dictionary mapping descriptor tuples to the best Genome found for that descriptor.
        fitness_fn: Callable to evaluate a genome's parameters, or a default one.
        population: The current list of genomes.
        species: A dictionary of active species.
        _species_seq: Counter for assigning new species IDs.
        _fitness_cache: Cache for fitness evaluations to avoid recomputing.
        _last_best_fitness: The best fitness achieved in the previous generation.
        _stagnation: Number of generations since overall best fitness improved.
        generation: The current generation number.
        champion: A tuple of the best genome's parameters and its fitness.
    """

    def __init__(
        self,
        pop_size: int = 50,
        fitness_fn: Optional[Callable[[Dict[str, float]], float]] = None,
        mutation_rate: float = 0.25,
        elite_size: int = 2,
        tournament_size: int = 3,
        species_threshold: float = 0.25,
        max_species: int = 16,
        novelty_weight: float = 0.0,  # Legacy, QD archive takes precedence
        qd_bonus_weight: float = 0.3,
        seed: Optional[int] = None,
    ):
        if pop_size < 2:
            raise ValueError("pop_size must be >= 2")
        if elite_size < 0:
            raise ValueError("elite_size must be >= 0")
        if tournament_size < 2:
            raise ValueError("tournament_size must be >= 2")
        if not (0.0 <= mutation_rate <= 1.0):
            raise ValueError("mutation_rate must be between 0.0 and 1.0")
        if not (0.0 <= qd_bonus_weight <= 1.0):
            raise ValueError("qd_bonus_weight must be between 0.0 and 1.0")

        # Quality-Diversity archive (10x10 grid)
        self.qd_archive: Dict[Tuple[int, int], Genome] = {}
        self.qd_bonus_weight: float = qd_bonus_weight  # weight of novelty in final fitness

        self.pop_size: int = pop_size
        self.base_mutation_rate: float = float(mutation_rate)
        self.mutation_rate: float = float(mutation_rate)  # Current adaptive rate
        self.elite_size: int = min(elite_size, pop_size)
        self.tournament_size: int = min(tournament_size, pop_size)
        self.species_threshold: float = float(species_threshold)
        self.max_species: int = max_species
        self.novelty_weight: float = float(novelty_weight)  # Kept for _tournament_pick and _ranked_population but QD is dominant

        self._rng: random.Random = random.Random(seed)

        self.fitness_fn: Callable[[Dict[str, float]], float] = fitness_fn or self._default_fitness
        self.population: List[Genome] = []
        self.species: Dict[int, Species] = {}
        self._species_seq: int = 0  # Counter for species IDs
        self._fitness_cache: Dict[str, float] = {}
        self._last_best_fitness: float = float("-inf")
        self._stagnation: int = 0  # Global stagnation counter
        self.generation: int = 0
        self.champion: Tuple[Dict[str, float], float] = ({}, float("-inf"))

    # =========================
    # INITIALIZATION
    # =========================

    def initialize(self, seed_population: Optional[Iterable[Dict[str, float]]] = None) -> None:
        """
        Initializes the population, optionally with a seed population.
        Fills up to `pop_size` with random genomes if needed.
        """
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
        """
        A default fitness function if none is provided.
        Rewards parameters closer to 0.5 and penalizes spread.
        """
        if not params:
            return 0.0
        # Ensure values are floats before processing
        vals: List[float] = [float(v) for v in params.values()]
        # Check for division by zero if params is empty, though checked above
        if not vals:
            return 0.0
        center: float = sum(1.0 - abs(v - 0.5) * 2.0 for v in vals) / len(vals)
        spread: float = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        return max(0.0, center - 0.15 * spread)

    @staticmethod
    def _hash_params(params: Dict[str, float]) -> str:
        """Generates a consistent hash for a set of parameters."""
        # Sort items for consistent hashing across runs/platforms
        items = sorted((str(k), round(float(v), 10)) for k, v in params.items())
        raw = repr(items).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _fitness(self, params: Dict[str, float]) -> float:
        """
        Calculates fitness, utilizing a cache to avoid re-evaluating identical parameter sets.
        Handles NaN fitness values.
        """
        key: str = self._hash_params(params)
        cached: Optional[float] = self._fitness_cache.get(key)
        if cached is not None:
            return cached
        value: float = float(self.fitness_fn(params))
        if value != value:  # Check for NaN (NaN is not equal to itself)
            value = float("-inf")
        self._fitness_cache[key] = value
        return value

    def evaluate_population(self) -> None:
        """
        Evaluates the fitness of all genomes in the current population.
        Applies a novelty bonus based on the Quality-Diversity archive.
        """
        for genome in self.population:
            # Calculate base fitness
            base_fitness: float = self._fitness(genome.params)
            # Calculate novelty bonus from QD-archive
            novelty: float = self.novelty_bonus(genome)
            # Combine base fitness with novelty bonus
            genome.fitness = base_fitness + self.qd_bonus_weight * novelty
            genome.eval_count += 1
            # Update the QD-archive with the current genome
            self._update_archive(genome)

        # After evaluating all genomes, rebuild species based on updated population
        self._rebuild_species()
        self._assign_species_ids()
        self._update_champion()

    # =========================
    # SPECIES
    # =========================

    def _distance(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        """
        Calculates the Euclidean distance between two parameter dictionaries.
        Missing keys are treated as having a value of 0.0.
        """
        keys: set[str] = set(a) | set(b)
        if not keys:
            return 0.0
        total: float = 0.0
        for k in keys:
            va: float = float(a.get(k, 0.0))
            vb: float = float(b.get(k, 0.0))
            total += (va - vb) ** 2
        return math.sqrt(total / len(keys))

    def _rebuild_species(self) -> None:
        """
        Re-assigns all genomes to species based on their parameter distance
        to existing species representatives. Creates new species if needed.
        Handles `max_species` by potentially merging or removing species, though not explicitly implemented yet.
        """
        self.species = {}
        self._species_seq = 0  # Reset species ID counter
        if not self.population:
            return

        # Assign genomes to species
        for idx, genome in enumerate(self.population):
            assigned = False
            for species_obj in self.species.values():
                if self._distance(genome.params, species_obj.representative.params) <= self.species_threshold:
                    species_obj.members.append(idx)
                    assigned = True
                    break
            if not assigned:
                # Create a new species for this genome
                sid = self._species_seq
                self._species_seq += 1
                self.species[sid] = Species(
                    species_id=sid,
                    representative=genome.copy(),  # Representative is a copy of the first member
                    members=[idx],
                )
        # TODO: Implement handling for self.max_species, e.g., merging smallest species or culling.

    def _assign_species_ids(self) -> None:
        """Updates the `species_id` attribute for each genome in the population."""
        for sid, species_obj in self.species.items():
            for idx in species_obj.members:
                # Ensure index is valid before access
                if 0 <= idx < len(self.population):
                    self.population[idx].species_id = sid

    def species_count(self) -> int:
        """Returns the number of active species."""
        return len(self.species)

    def diversity(self) -> float:
        """
        Calculates the diversity of the population based on unique parameter hashes.
        Returns a value between 0.0 and 1.0.
        """
        if len(self.population) <= 1:
            return 0.0
        signatures: set[str] = {self._hash_params(g.params) for g in self.population}
        return len(signatures) / len(self.population)

    def novelty_score(self, genome: Genome) -> float:
        """
        Calculates a novelty score for a genome based on its distance to its k-nearest neighbors.
        (Currently only used with `novelty_weight` if > 0, otherwise QD bonus takes over).
        """
        if not self.population or len(self.population) == 1:
            return 0.0
        # Calculate distances to all other genomes
        dists: List[float] = [self._distance(genome.params, other.params) for other in self.population if other is not genome]
        if not dists:
            return 0.0
        # Average distance to the 5 nearest neighbors
        k = min(5, len(dists))
        if k == 0:
            return 0.0
        return sum(sorted(dists)[:k]) / k

    # =========================
    # SELECTION
    # =========================

    def _tournament_pick(self) -> Genome:
        """
        Selects a genome using tournament selection from the entire population.
        Considers both fitness and novelty (if `novelty_weight` > 0).
        """
        if not self.population:
            raise RuntimeError("Population is empty, cannot pick from tournament.")
        k_val = min(self.tournament_size, len(self.population))
        contestants: List[Genome] = self._rng.sample(self.population, k=k_val)
        contestants.sort(
            key=lambda g: g.fitness + self.novelty_weight * self.novelty_score(g),
            reverse=True,
        )
        return contestants[0]

    def _ranked_population(self) -> List[Genome]:
        """
        Returns the population sorted by combined fitness (fitness + novelty_weight * novelty_score).
        """
        return sorted(
            self.population,
            key=lambda g: g.fitness + self.novelty_weight * self.novelty_score(g),
            reverse=True,
        )

    # =========================
    # REPRODUCTION
    # =========================

    def crossover(self, a: Genome, b: Genome) -> Genome:
        """
        Performs crossover between two parent genomes to create a child.
        Combines parameters and applies blend crossover (BLX-alpha) for some parameters.
        """
        keys: list[str] = sorted(set(a.params) | set(b.params))
        child_params: Dict[str, float] = {}
        for k in keys:
            va: float = float(a.params.get(k, 0.5))
            vb: float = float(b.params.get(k, 0.5))

            val: float
            if self._rng.random() < 0.5:
                val = va
            else:
                val = vb

            # Apply blend crossover with 35% probability
            if self._rng.random() < 0.35:
                alpha: float = self._rng.random()  # Random factor between 0 and 1
                val = alpha * va + (1.0 - alpha) * vb
            child_params[k] = self._clamp(val)

        child = Genome(
            params=child_params,
            fitness=0.0,
            age=0,
            niche=a.niche if self._rng.random() < 0.5 else b.niche,
            parents=(None, None),  # Using None as id() is volatile. Could use unique IDs if implemented.
            lineage=(a.lineage[-5:] + b.lineage[-5:] + ["child"])[-12:],
        )
        return child

    def mutate(self, genome: Genome) -> Genome:
        """
        Applies mutations to a genome's parameters.
        Uses an adaptive mutation rate and applies Gaussian perturbation.
        """
        mutated: Genome = genome.copy()
        rate: float = self._adaptive_mutation_rate()
        keys: List[str] = list(mutated.params.keys())

        for k in keys:
            if self._rng.random() < rate:
                old_val: float = mutated.params[k]
                sigma: float = 0.08 + 0.25 * rate  # Adaptive sigma for Gaussian mutation
                factor: float = math.exp(self._rng.gauss(0.0, sigma))
                if self._rng.random() < 0.5:  # Apply inverse factor 50% of the time
                    factor = 1.0 / factor
                mutated.params[k] = self._clamp(old_val * factor)
                mutated.mutation_count += 1

        # Occasionally add a direct uniform perturbation
        if keys and self._rng.random() < rate * 0.35:
            k_choice: str = self._rng.choice(keys)
            mutated.params[k_choice] = self._clamp(mutated.params[k_choice] + self._rng.uniform(-0.15, 0.15))
            mutated.mutation_count += 1

        mutated.age = 0
        mutated.fitness = 0.0
        mutated.eval_count = 0
        mutated.lineage.append("mut")
        mutated.lineage = mutated.lineage[-12:]  # Keep lineage history limited
        return mutated

    def _adaptive_mutation_rate(self) -> float:
        """
        Calculates an adaptive mutation rate based on population diversity and stagnation.
        Higher stagnation or lower diversity leads to higher mutation rates.
        """
        div: float = self.diversity()
        stagnation_boost: float = min(0.25, self._stagnation * 0.02)  # Max 0.25 boost
        diversity_boost: float = 0.0 if div >= 0.6 else (0.25 - 0.25 * div)  # Boost if diversity is low
        rate: float = self.base_mutation_rate + stagnation_boost + diversity_boost
        return max(0.02, min(0.8, rate))  # Clamp rate between 0.02 and 0.8

    # =========================
    # SURVIVOR SELECTION
    # =========================

    def evolve_generation(self) -> None:
        """
        Evolves the population to the next generation.
        Includes elite preservation, QD archive integration, crossover, and mutation.
        """
        if not self.population:
            raise RuntimeError("Population is empty; call initialize() first.")

        # Increment age for all genomes
        for genome in self.population:
            genome.age += 1

        self.evaluate_population()  # Re-evaluate with latest population and QD archive
        ranked: List[Genome] = self._ranked_population()
        next_population: List[Genome] = []

        # 1. Preserve elites from the current population
        next_population.extend([g.copy() for g in ranked[: self.elite_size]])

        # 2. Add high-performing genomes from the QD archive to introduce diversity and novelty
        # These are added *after* the main elites and will count towards pop_size.
        qd_archive_genomes = sorted(self.qd_archive.values(), key=lambda g: g.fitness, reverse=True)
        for genome_from_qd in qd_archive_genomes:
            if len(next_population) >= self.pop_size:
                break
            # Ensure QD archive genomes are distinct from elites already copied
            # This check is basic (param hash), a more robust check might be needed
            if all(self._hash_params(genome_from_qd.params) != self._hash_params(g.params) for g in next_population):
                next_population.append(genome_from_qd.copy())

        # 3. Fill the rest of the population with children from crossover and mutation
        while len(next_population) < self.pop_size:
            parent_a: Genome = self._species_aware_pick()
            parent_b: Genome = self._species_aware_pick()
            child: Genome = self.crossover(parent_a, parent_b)
            child = self.mutate(child)
            next_population.append(child)

        self.population = next_population[: self.pop_size]  # Ensure population size is maintained
        self._rebuild_species()
        self.evaluate_population()  # Final evaluation for the new generation
        self.generation += 1
        self._update_stagnation()
        self._update_champion()

    def _species_aware_pick(self) -> Genome:
        """
        Selects a parent genome, prioritizing species with more members
        and then using a tournament within that species.
        """
        if not self.species:
            return self._tournament_pick()  # Fallback to general tournament

        species_items: List[Species] = list(self.species.values())
        # Weights for species selection: proportional to number of members
        # Use max(1, ...) to ensure species with 0 members (shouldn't happen post _rebuild_species) still have a chance.
        sizes: List[int] = [max(1, len(s.members)) for s in species_items]
        chosen_species: Species = self._rng.choices(species_items, weights=sizes, k=1)[0]

        # Select a contestant from the chosen species using a mini-tournament
        indices_in_species: List[int] = chosen_species.members
        if not indices_in_species:
            return self._tournament_pick() # Fallback if species somehow has no members

        # Filter population to only members of chosen species
        species_population: List[Genome] = [self.population[i] for i in indices_in_species if 0 <= i < len(self.population)]
        if not species_population:
            return self._tournament_pick() # Fallback if species members are invalid

        k_val = max(1, min(self.tournament_size, len(species_population)))
        contestants: List[Genome] = self._rng.sample(species_population, k=k_val)
        contestants.sort(
            key=lambda g: g.fitness + self.novelty_weight * self.novelty_score(g),
            reverse=True,
        )
        return contestants[0]

    def _update_stagnation(self) -> None:
        """
        Updates the global stagnation counter and individual species' stagnation.
        Resets counters if a new overall best fitness is found.
        """
        best_now: float = max((g.fitness for g in self.population), default=float("-inf"))
        if best_now > self._last_best_fitness + 1e-12:  # Add tolerance for float comparison
            self._last_best_fitness = best_now
            self._stagnation = 0
            for species_obj in self.species.values():
                species_obj.stagnation = 0  # Reset species stagnation
                species_obj.best_fitness = max(species_obj.best_fitness, best_now)
        else:
            self._stagnation += 1
            for species_obj in self.species.values():
                species_obj.stagnation += 1

    def _update_champion(self) -> None:
        """Updates the stored champion genome based on the current population."""
        if not self.population:
            self.champion = ({}, float("-inf"))
            return
        best: Genome = max(self.population, key=lambda g: g.fitness)
        self.champion = (dict(best.params), float(best.fitness))

    # =========================
    # CONTROLS
    # =========================

    def set_mutation_rate(self, rate: float) -> None:
        """Sets the base mutation rate, clamping it between 0.0 and 1.0."""
        self.base_mutation_rate = max(0.0, min(1.0, float(rate)))
        self.mutation_rate = self.base_mutation_rate  # Also update current rate

    def set_fitness_fn(self, fn: Callable[[Dict[str, float]], float]) -> None:
        """
        Sets a custom fitness function. Clears the fitness cache and re-evaluates the population.
        """
        self.fitness_fn = fn
        self._fitness_cache.clear()
        self.evaluate_population()

    # =========================
    # COMPATIBILITY HELPERS
    # =========================

    def best(self, top_n: int = 1) -> List[Dict[str, float]]:
        """
        Returns the parameters of the top N best genomes.
        (Legacy method, `get_best` is preferred for full Genome objects).
        """
        ranked: List[Genome] = self._ranked_population()[:top_n]
        return [dict(g.params) for g in ranked]

    def add_genome(self, genome: Genome) -> None:
        """
        Safely adds a genome to the population. If the population exceeds `pop_size`,
        the oldest genome (first in list) is removed.
        """
        self.population.append(genome)
        if len(self.population) > self.pop_size:
            # Simple removal of the "oldest" by list position, assumes chronological add
            self.population.pop(0)

    def get_best(self, top_n: int = 1) -> List[Genome]:
        """Returns the top N best Genome objects (copies)."""
        return [g.copy() for g in self._ranked_population()[:top_n]]

    def get_champion(self) -> Tuple[Dict[str, float], float]:
        """Returns the parameters and fitness of the overall champion genome."""
        return self.champion

    def export_population(self) -> List[Dict[str, float]]:
        """Exports the parameters of all genomes in the current population."""
        return [dict(g.params) for g in self.population]

    # =========================
    # INTERNALS
    # =========================

    def _random_params(self) -> Dict[str, float]:
        """
        Generates a dictionary of random parameters within predefined ranges.
        These parameters are used for initial population generation.
        """
        # Ensure all parameters needed by _compute_descriptor are present here
        # and have reasonable ranges to map correctly to the QD grid.
        return {
            "max_risk_per_trade": self._clamp(self._rng.uniform(0.01, 0.15)),
            "phi_llm": self._clamp(self._rng.uniform(0.05, 0.35)),
            "exploration_rate": self._clamp(self._rng.uniform(0.05, 0.5)),
            "confidence_floor": self._clamp(self._rng.uniform(0.01, 0.25)),
            "trailing_stop_ratio": self._clamp(self._rng.uniform(0.005, 0.05)),  # Added for QD descriptor
            "momentum_window": self._clamp(self._rng.uniform(5.0, 60.0), low=5.0, high=60.0), # Added for QD descriptor
        }

    @staticmethod
    def _clamp(x: float, low: float = 0.0001, high: float = 1.0) -> float:
        """Clamps a float value within a specified range [low, high]. Handles NaN."""
        if x != x:  # Check for NaN
            return low
        return max(low, min(high, float(x)))

    def _compute_descriptor(self, genome: Genome) -> Tuple[int, int]:
        """
        Computes a 2D descriptor (row, col) for the Quality-Diversity archive
        based on specific parameters of the genome.
        The descriptor maps continuous parameter ranges to a 10x10 grid.
        """
        params = genome.params

        # Retrieve parameters with sensible defaults if they are missing
        max_risk_per_trade = params.get("max_risk_per_trade", 0.05)
        phi_llm = params.get("phi_llm", 0.15)
        trailing_stop_ratio = params.get("trailing_stop_ratio", 0.01)
        momentum_window = params.get("momentum_window", 10.0)

        # Calculate "risk" and "aggressiveness" composite features
        # Min/Max values are derived from _random_params ranges:
        # max_risk_per_trade: [0.01, 0.15]
        # phi_llm: [0.05, 0.35]
        # trailing_stop_ratio: [0.005, 0.05]
        # momentum_window: [5.0, 60.0]

        # Feature 1: "risk"
        # Range: min_risk = 0.01 * 0.05 = 0.0005, max_risk = 0.15 * 0.35 = 0.0525
        risk = max_risk_per_trade * phi_llm
        risk_min, risk_max = 0.0005, 0.0525
        # Normalize and map to 0-9 for the row
        row = int((risk - risk_min) / (risk_max - risk_min) * 9.999) # Scale to 0-9.999
        row = min(9, max(0, row))

        # Feature 2: "aggressiveness"
        # Range: min_agg = 0.005 + 5.0/100.0 = 0.055, max_agg = 0.05 + 60.0/100.0 = 0.65
        aggressiveness = trailing_stop_ratio + momentum_window / 100.0
        agg_min, agg_max = 0.055, 0.65
        # Normalize and map to 0-9 for the column
        col = int((aggressiveness - agg_min) / (agg_max - agg_min) * 9.999) # Scale to 0-9.999
        col = min(9, max(0, col))

        return (row, col)

    def _update_archive(self, genome: Genome) -> None:
        """
        Updates the Quality-Diversity (QD) archive. If a cell is empty or the
        new genome has higher fitness than the current occupant, it replaces it.
        """
        row, col = self._compute_descriptor(genome)
        key: Tuple[int, int] = (row, col)
        # Store a copy to prevent modification of archive genome when original is mutated
        if key not in self.qd_archive or genome.fitness > self.qd_archive[key].fitness:
            self.qd_archive[key] = genome.copy()

    def novelty_bonus(self, genome: Genome) -> float:
        """
        Returns a novelty bonus for the genome.
        Returns 1.0 if its descriptor cell in the QD archive is empty,
        0.3 if it's occupied (encouraging exploration of new cells).
        """
        row, col = self._compute_descriptor(genome)
        key: Tuple[int, int] = (row, col)
        if key not in self.qd_archive:
            return 1.0  # High bonus for exploring a new cell
        return 0.3  # Smaller bonus for improving an existing cell