"""Trade node evolution helper functions."""

from __future__ import annotations

import math
import random
from typing import Any, Dict

from src.evolution import Genome


def node_niche(node: Any) -> str:
    """Return current evolutionary niche for a trade node."""
    current_params = getattr(node, "current_params", {}) or {}
    risk = float(current_params.get("max_risk_per_trade", 0.05)) if isinstance(current_params, dict) else 0.05
    phi = float(current_params.get("phi_llm", 0.4)) if isinstance(current_params, dict) else 0.4

    if risk >= 0.08 or phi >= 0.6:
        return "exploration"
    if risk <= 0.025:
        return "preservation"
    return "balanced"


def accept_genome(node: Any, genome: Dict[str, Any]) -> bool:
    """Return True if an incoming genome is acceptable for the node."""
    if not isinstance(genome, dict):
        return False

    params = genome.get("params", genome)
    if not isinstance(params, dict):
        return False

    score = float(genome.get("fitness", genome.get("score", 0.0)) or 0.0)
    local = float(getattr(node, "best_fitness", 0.0) or 0.0)

    if score >= local:
        return True

    # Keep a small exploration chance for diversity.
    diversity = population_diversity(node)
    exploration_chance = min(0.2, max(0.02, diversity * 0.1))
    return random.random() < exploration_chance


def make_genome(node: Any, params: Dict[str, float], fitness: float) -> Dict[str, Any]:
    """Build serializable genome dictionary from params and fitness."""
    return {
        "node_id": getattr(node, "node_id", "unknown"),
        "niche": node_niche(node),
        "params": dict(params or {}),
        "fitness": float(fitness),
        "generation": int(getattr(node, "generation", 0) or 0),
    }


def dict_to_genome(node: Any, data: Dict[str, Any], niche: str = "exploration") -> Genome:
    """Convert dictionary payload to Genome."""
    params = data.get("params", data)
    if not isinstance(params, dict):
        params = {}

    fitness = float(data.get("fitness", data.get("score", 0.0)) or 0.0)
    age = int(data.get("age", data.get("generation", getattr(node, "generation", 0))) or 0)

    return Genome(
        params=dict(params),
        fitness=fitness,
        age=age,
        niche=str(data.get("niche", niche) or niche),
    )


def local_score(node: Any, genome: Genome) -> float:
    """Score genome against current trade-node state."""
    if not isinstance(genome, Genome):
        return 0.0

    params = getattr(genome, "params", {}) or {}
    score = float(getattr(genome, "fitness", 0.0) or 0.0)

    volatility = current_volatility(node)
    risk = float(params.get("max_risk_per_trade", 0.05) or 0.05)

    if volatility > 0.05 and risk > 0.08:
        score -= 0.1
    if volatility < 0.02 and risk < 0.02:
        score -= 0.03

    return max(0.0, min(1.0, score))


def population_diversity(node: Any) -> float:
    """Return approximate diversity of known population."""
    population = getattr(node, "population", []) or []
    if len(population) < 2:
        return 0.0

    signatures: set[str] = set()
    for genome in population:
        params = getattr(genome, "params", None)
        if not isinstance(params, dict):
            continue
        signature = "|".join(f"{key}:{round(float(value), 4)}" for key, value in sorted(params.items()) if _is_number(value))
        if signature:
            signatures.add(signature)

    return len(signatures) / max(1, len(population))


def population_niche_counts(node: Any) -> Dict[str, int]:
    """Count population by niche."""
    counts: Dict[str, int] = {}
    for genome in getattr(node, "population", []) or []:
        niche = str(getattr(genome, "niche", "unknown") or "unknown")
        counts[niche] = counts.get(niche, 0) + 1
    return counts


def current_volatility(node: Any) -> float:
    """Return current volatility from node params/state."""
    current_params = getattr(node, "current_params", {}) or {}
    if isinstance(current_params, dict):
        value = current_params.get("volatility_threshold")
        if value is not None:
            return _safe_float(value, 0.0)
    return _safe_float(getattr(node, "last_volatility", 0.0), 0.0)


def recombine(node: Any, g1: Dict[str, Any], g2: Dict[str, Any]) -> Dict[str, Any]:
    """Recombine two parameter dictionaries."""
    del node  # reserved for future context-aware recombination

    out: Dict[str, Any] = {}
    keys = set(g1 or {}).union(g2 or {})
    for key in keys:
        v1 = (g1 or {}).get(key)
        v2 = (g2 or {}).get(key)

        if _is_number(v1) and _is_number(v2):
            out[key] = (float(v1) + float(v2)) / 2.0
        else:
            out[key] = v1 if random.random() < 0.5 else v2

    return out


def seed_from_memory(node: Any) -> None:
    """Seed evolution engine from memory if a compatible method exists."""
    memory = getattr(node, "semantic_memory", None)
    engine = getattr(node, "evolution_engine", None)

    if memory is None or engine is None:
        return

    seed_method = getattr(engine, "seed_from_memory", None)
    if callable(seed_method):
        seed_method(memory)


def _is_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def _safe_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


__all__ = [
    "accept_genome",
    "current_volatility",
    "dict_to_genome",
    "local_score",
    "make_genome",
    "node_niche",
    "population_diversity",
    "population_niche_counts",
    "recombine",
    "seed_from_memory",
]