"""
strategy_schema.py — Глобальные Pydantic-модели для параметров стратегии и genome.
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional
import json

class StrategyParams(BaseModel):
    """Основные параметры торговой стратегии (genome)."""
    max_risk_per_trade: float = Field(default=0.01, ge=0.0001, le=0.3)
    phi_llm: float = Field(default=0.3, ge=0.01, le=1.0)
    # можно расширять
    take_profit_ratio: float = Field(default=2.0, ge=1.0, le=5.0)
    min_confidence: float = Field(default=0.6, ge=0.3, le=0.95)
    curiosity_weight: float = Field(default=0.15, ge=0.0, le=0.4)

    class Config:
        extra = "forbid"

    def to_dict(self) -> Dict[str, float]:
        return self.model_dump()