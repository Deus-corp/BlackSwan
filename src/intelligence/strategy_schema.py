"""
strategy_schema.py — Global Pydantic models for trading strategy configuration and genome representation.
"""
from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class StrategyParams(BaseModel):
    """
    Core parameters for a trading strategy (genome).

    Attributes:
        max_risk_per_trade: Maximum risk allowed per trade as a fraction of total capital.
        phi_llm: Confidence/caution coefficient for LLM, affecting position sizing or signal frequency.
        stop_loss_ratio: Price ratio defining the stop-loss level relative to the entry price.
        trailing_stop_ratio: Percentage ratio for trailing stop distance from the local high/low.
        momentum_window: Number of time periods (candles) used for momentum calculation.
        volatility_threshold: Threshold value for volatility-based filtering or activation.
    """

    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True
    )

    max_risk_per_trade: float = Field(
        default=0.01, 
        ge=0.0001, 
        le=0.3,
        description="Maximum risk per trade (0.0001 - 0.3)."
    )
    phi_llm: float = Field(
        default=0.3, 
        ge=0.01, 
        le=1.0,
        description="LLM caution/confidence factor (0.01 - 1.0)."
    )
    stop_loss_ratio: float = Field(
        default=0.02, 
        ge=0.001, 
        le=0.2,
        description="Stop-loss ratio relative to entry (0.001 - 0.2)."
    )
    trailing_stop_ratio: float = Field(
        default=0.01, 
        ge=0.0, 
        le=0.1,
        description="Trailing stop ratio relative to high/low (0.0 - 0.1)."
    )
    momentum_window: int = Field(
        default=10, 
        ge=2, 
        le=50,
        description="Momentum calculation window in periods (2 - 50)."
    )
    volatility_threshold: float = Field(
        default=0.02, 
        ge=0.001, 
        le=0.3,
        description="Volatility activation threshold (0.001 - 0.3)."
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the strategy parameters instance into a plain dictionary.

        Returns:
            A dictionary representation of the strategy parameters.
        """
        return self.model_dump()