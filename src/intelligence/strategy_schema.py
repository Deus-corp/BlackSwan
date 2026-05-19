"""
strategy_schema.py — Глобальные Pydantic-модели для параметров стратегии и genome.
"""
from pydantic import BaseModel, Field, ConfigDict # Import ConfigDict for Pydantic v2
from typing import Dict, Union

class StrategyParams(BaseModel):
    """
    Основные параметры торговой стратегии (genome).

    Атрибуты:
        max_risk_per_trade: Максимальный риск на сделку, как доля от капитала.
        phi_llm: Коэффициент осторожности/доверия LLM, влияющий на размер позиции или частоту сделок.
        stop_loss_ratio: Соотношение стоп-лосса к цене входа.
        trailing_stop_ratio: Соотношение трейлинг-стопа к максимальной цене.
        momentum_window: Окно для расчета моментума (количество свечей/периодов).
        volatility_threshold: Порог волатильности для активации определенных условий стратегии.
    """
    # Pydantic v2 model configuration. 'extra='forbid'' prevents additional fields not defined in the schema.
    model_config = ConfigDict(extra='forbid')

    max_risk_per_trade: float = Field(default=0.01, ge=0.0001, le=0.3,
                                      description="Максимальный риск на сделку, как доля от капитала (0.0001-0.3).")
    phi_llm: float = Field(default=0.3, ge=0.01, le=1.0,
                           description="Коэффициент осторожности/доверия LLM (0.01-1.0).")
    stop_loss_ratio: float = Field(default=0.02, ge=0.001, le=0.2,
                                   description="Соотношение стоп-лосса к цене входа (0.001-0.2).")
    trailing_stop_ratio: float = Field(default=0.01, ge=0.0, le=0.1,
                                     description="Соотношение трейлинг-стопа к максимальной цене (0.0-0.1).")
    momentum_window: int = Field(default=10, ge=2, le=50,
                                 description="Окно для расчета моментума (2-50 периодов).")
    volatility_threshold: float = Field(default=0.02, ge=0.001, le=0.3,
                                       description="Порог волатильности (0.001-0.3).")

    def to_dict(self) -> Dict[str, Union[float, int]]:
        """
        Преобразует текущие параметры стратегии в словарь.

        Returns:
            Словарь, представляющий параметры стратегии.
        """
        # model_dump() is the Pydantic v2 method for converting a model to a dictionary.
        return self.model_dump()
