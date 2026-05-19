"""
Initializes the evolution package, exposing core components for managing
the evolutionary process within the swarm.
"""
from .engine import EvolutionEngine
from typing import List

__all__: List[str] = ["EvolutionEngine"]
