"""Global Pydantic models for trading strategy configuration and genome representation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategyParams(BaseModel):
    """Core bounded parameters for a trading strategy genome."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        validate_assignment=True,
    )

    max_risk_per_trade: float = Field(
        default=0.01,
        ge=0.0001,
        le=0.3,
        description="Maximum risk per trade as a capital fraction.",
    )
    phi_llm: float = Field(
        default=0.3,
        ge=0.01,
        le=1.0,
        description="LLM caution/confidence factor.",
    )
    stop_loss_ratio: float = Field(
        default=0.02,
        ge=0.001,
        le=0.2,
        description="Stop-loss ratio relative to entry.",
    )
    trailing_stop_ratio: float = Field(
        default=0.01,
        ge=0.0,
        le=0.1,
        description="Trailing stop ratio relative to high/low.",
    )
    momentum_window: int = Field(
        default=10,
        ge=2,
        le=50,
        description="Momentum calculation window in periods.",
    )
    volatility_threshold: float = Field(
        default=0.02,
        ge=0.001,
        le=0.3,
        description="Volatility activation threshold.",
    )
    trend_strength_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum trend strength required for trend-sensitive actions.",
    )

    @field_validator(
        "max_risk_per_trade",
        "phi_llm",
        "stop_loss_ratio",
        "trailing_stop_ratio",
        "volatility_threshold",
        "trend_strength_threshold",
        mode="before",
    )
    @classmethod
    def _coerce_float(cls, value: Any) -> float:
        return float(value)

    @field_validator("momentum_window", mode="before")
    @classmethod
    def _coerce_momentum_window(cls, value: Any) -> int:
        return int(round(float(value)))

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary representation."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyParams:
        """Build validated strategy params from a dictionary."""
        return cls.model_validate(data)

    @classmethod
    def defaults(cls) -> dict[str, Any]:
        """Return default strategy parameters as a dictionary."""
        return cls().to_dict()

    def merged(self, updates: dict[str, Any]) -> StrategyParams:
        """Return a validated copy with updates applied."""
        if not isinstance(updates, dict):
            raise TypeError("updates must be a dictionary")
        return self.model_copy(update=updates)