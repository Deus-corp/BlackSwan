"""
strategy_schema.py — Глобальные Pydantic-модели для параметров стратегии и genome.
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional
# Removed unused import 'json'

class StrategyParams(BaseModel):
    """Основные параметры торговой стратегии (genome)."""
    max_risk_per_trade: float = Field(default=0.01, ge=0.0001, le=0.3)
    phi_llm: float = Field(default=0.3, ge=0.01, le=1.0)
    # новые поля
    stop_loss_ratio: float = Field(default=0.02, ge=0.001, le=0.2)
    trailing_stop_ratio: float = Field(default=0.01, ge=0.0, le=0.1)
    momentum_window: int = Field(default=10, ge=2, le=50)
    volatility_threshold: float = Field(default=0.02, ge=0.001, le=0.3)

    class Config:
        extra = "forbid"

    def to_dict(self) -> Dict[str, float]:
        """
        Преобразует текущие параметры стратегии в словарь.
        """
        return self.model_dump()