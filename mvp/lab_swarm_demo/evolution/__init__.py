"""
Initializes the evolution package, exposing core components.
"""
from .engine import EvolutionEngine
from typing import List

__all__: List[str] = ["EvolutionEngine"]