"""ROI dispatcher with Bayesian success tracking and capped Kelly-style sizing."""

from __future__ import annotations

import math
from typing import Any, Final


class ROIDispatcher:
    """Estimate approved risk fraction from market volatility and outcome history."""

    DEFAULT_MAX_RISK_PER_TRADE: Final[float] = 0.02
    DEFAULT_PHI_BASE: Final[float] = 0.25
    DEFAULT_PHI_K_SIGMA: Final[float] = 5.0
    DEFAULT_PHI_CAP: Final[float] = 0.5

    BETA_INITIAL_ALPHA: Final[float] = 1.0
    BETA_INITIAL_BETA: Final[float] = 1.0

    PRIOR_FLOOR: Final[float] = 0.4
    PRIOR_VOLATILITY_BASE: Final[float] = 0.55
    PRIOR_VOLATILITY_FACTOR: Final[float] = 2.5
    PRIOR_WEIGHT: Final[float] = 0.7
    POSTERIOR_WEIGHT: Final[float] = 0.3

    ODDS_NUMERATOR: Final[float] = 0.02
    DEFAULT_VOLATILITY_ESTIMATE: Final[float] = 0.02

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config if isinstance(config, dict) else {}

        self.max_risk_per_trade = self._clamp(
            self._safe_float(cfg.get("max_risk_per_trade"), self.DEFAULT_MAX_RISK_PER_TRADE),
            0.0,
            1.0,
        )
        self.phi_base = self._clamp(
            self._safe_float(cfg.get("phi_llm", cfg.get("phi_base")), self.DEFAULT_PHI_BASE),
            0.0,
            self.DEFAULT_PHI_CAP,
        )
        self.phi_k_sigma = max(
            0.0,
            self._safe_float(cfg.get("phi_k_sigma"), self.DEFAULT_PHI_K_SIGMA),
        )
        self.phi_cap = self._clamp(
            self._safe_float(cfg.get("phi_cap"), self.DEFAULT_PHI_CAP),
            0.0,
            1.0,
        )

        self.alpha = max(
            0.0,
            self._safe_float(cfg.get("alpha"), self.BETA_INITIAL_ALPHA),
        )
        self.beta = max(
            0.0,
            self._safe_float(cfg.get("beta"), self.BETA_INITIAL_BETA),
        )

    def evaluate(self, market_state: dict[str, Any], capital: float) -> tuple[float, float]:
        """
        Evaluates the market state and determines the approved risk fraction.

        Returns:
            Tuple containing (approved_risk_fraction, survival_score).
        """
        if not isinstance(market_state, dict):
            market_state = {}

        vol = max(
            0.0,
            self._safe_float(
                market_state.get("volatility_estimate", self.DEFAULT_VOLATILITY_ESTIMATE),
                self.DEFAULT_VOLATILITY_ESTIMATE,
            ),
        )

        p = self._estimate_success_probability(vol)
        b = self._estimate_odds(vol)
        phi = self._dynamic_phi(vol)

        f_star = 0.0
        if b > 0:
            f_star = p - ((1.0 - p) / b) * phi

        approved_risk_fraction = max(0.0, min(f_star, self.max_risk_per_trade))

        # Backward-compatible contract: existing callers/tests expect survival == 1.0.
        return approved_risk_fraction, 1.0

    def update(self, success: bool, weight: float = 1.0) -> None:
        """Update the Beta tracker with a weighted success/failure observation."""
        clean_weight = max(0.0, self._safe_float(weight, 1.0))
        if clean_weight == 0.0:
            return

        if bool(success):
            self.alpha += clean_weight
        else:
            self.beta += clean_weight

    def reset(self) -> None:
        """Reset the Bayesian tracker to an uninformative prior."""
        self.alpha = self.BETA_INITIAL_ALPHA
        self.beta = self.BETA_INITIAL_BETA

    def to_dict(self) -> dict[str, float]:
        """Serialize dispatcher state for diagnostics/checkpointing."""
        return {
            "max_risk_per_trade": self.max_risk_per_trade,
            "phi_base": self.phi_base,
            "phi_k_sigma": self.phi_k_sigma,
            "phi_cap": self.phi_cap,
            "alpha": self.alpha,
            "beta": self.beta,
            "posterior_success_probability": self.posterior_success_probability,
        }

    @property
    def posterior_success_probability(self) -> float:
        total = self.alpha + self.beta
        if total <= 0:
            return 0.5
        return self._clamp(self.alpha / total, 0.0, 1.0)

    def _estimate_success_probability(self, volatility: float) -> float:
        prior = max(
            self.PRIOR_FLOOR,
            self.PRIOR_VOLATILITY_BASE - volatility * self.PRIOR_VOLATILITY_FACTOR,
        )
        probability = (self.PRIOR_WEIGHT * prior) + (
            self.POSTERIOR_WEIGHT * self.posterior_success_probability
        )
        return self._clamp(probability, 0.0, 1.0)

    def _estimate_odds(self, volatility: float) -> float:
        if volatility <= 0:
            return 1.0
        return max(0.0, self.ODDS_NUMERATOR / volatility)

    def _dynamic_phi(self, volatility: float) -> float:
        raw_phi = self.phi_base * (1.0 + self.phi_k_sigma * max(0.0, volatility))
        return self._clamp(raw_phi, 0.0, self.phi_cap)

    @staticmethod
    def _kelly_fraction(*, p_success: float, odds: float) -> float:
        if odds <= 0:
            return 0.0
        p = max(0.0, min(1.0, p_success))
        q = 1.0 - p
        return p - (q / odds)

    @staticmethod
    def _survival_score(*, approved_risk_fraction: float, volatility: float, capital: float) -> float:
        capital_score = 1.0 if capital > 0 else 0.5
        volatility_penalty = min(0.5, max(0.0, volatility) * 5.0)
        risk_penalty = min(0.4, max(0.0, approved_risk_fraction) * 10.0)
        return max(0.0, min(1.0, capital_score - volatility_penalty - risk_penalty))

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        if not math.isfinite(number):
            return default

        return number

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))