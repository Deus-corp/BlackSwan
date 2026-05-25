from typing import Dict, Any, Final, Tuple

class ROIDispatcher:
    """
    ROI Dispatcher v2 - implements a Bayesian update for success probability
    and dynamic Kelly criterion 'phi' (fraction of capital to bet).

    It uses a Beta distribution to track success/failure history and
    combines it with a prior based on market volatility. The dispatcher
    then calculates an approved risk fraction based on a modified Kelly criterion.
    """

    # Kelly criterion parameters
    DEFAULT_MAX_RISK_PER_TRADE: Final[float] = 0.02
    DEFAULT_PHI_BASE: Final[float] = 0.25
    PHI_K_SIGMA_MULTIPLIER: Final[float] = 5.0
    PHI_CAP: Final[float] = 0.5

    # Bayesian tracker: Beta(alpha, beta) distribution parameters
    BETA_INITIAL_ALPHA: Final[float] = 1.0
    BETA_INITIAL_BETA: Final[float] = 1.0

    # Success Probability Estimation Constants
    PRIOR_FLOOR: Final[float] = 0.4
    PRIOR_VOLATILITY_BASE: Final[float] = 0.55
    PRIOR_VOLATILITY_FACTOR: Final[float] = 2.5
    PRIOR_WEIGHT: Final[float] = 0.7
    POSTERIOR_WEIGHT: Final[float] = 0.3

    # Odds Estimation Constants
    ODDS_NUMERATOR: Final[float] = 0.02
    DEFAULT_VOLATILITY_ESTIMATE: Final[float] = 0.02

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        """
        Initializes the ROIDispatcher with optional configuration.

        Args:
            config: Dictionary containing 'max_risk_per_trade' or 'phi_llm'.
        """
        self.max_risk_per_trade: float = self.DEFAULT_MAX_RISK_PER_TRADE
        self.phi_base: float = self.DEFAULT_PHI_BASE
        self.phi_k_sigma: float = self.PHI_K_SIGMA_MULTIPLIER

        self.alpha: float = self.BETA_INITIAL_ALPHA
        self.beta: float = self.BETA_INITIAL_BETA

        if config:
            self.max_risk_per_trade = config.get("max_risk_per_trade", self.max_risk_per_trade)
            self.phi_base = config.get("phi_llm", self.phi_base)

    def _estimate_success_probability(self, volatility: float) -> float:
        """Estimates the probability of success using a Bayesian approach."""
        prior: float = max(self.PRIOR_FLOOR, self.PRIOR_VOLATILITY_BASE - volatility * self.PRIOR_VOLATILITY_FACTOR)

        sum_alpha_beta: float = self.alpha + self.beta
        posterior: float = (self.alpha / sum_alpha_beta) if sum_alpha_beta > 0 else 0.5

        return (self.PRIOR_WEIGHT * prior) + (self.POSTERIOR_WEIGHT * posterior)

    def _estimate_odds(self, volatility: float) -> float:
        """Estimates the odds (b) for the Kelly criterion."""
        if volatility <= 0:
            return 1.0
        return self.ODDS_NUMERATOR / volatility

    def _dynamic_phi(self, volatility: float) -> float:
        """Calculates dynamic 'phi' (Kelly scaling factor) based on volatility."""
        return min(self.PHI_CAP, self.phi_base * (1.0 + self.phi_k_sigma * volatility))

    def evaluate(self, market_state: Dict[str, Any], capital: float) -> Tuple[float, float]:
        """
        Evaluates the market state and determines the approved risk fraction.

        Returns:
            Tuple containing (approved_risk_fraction, survival_score).
        """
        vol: float = max(0.0, float(market_state.get('volatility_estimate', self.DEFAULT_VOLATILITY_ESTIMATE)))

        p: float = self._estimate_success_probability(vol)
        b: float = self._estimate_odds(vol)
        phi: float = self._dynamic_phi(vol)

        f_star: float = 0.0
        if b > 0:
            f_star = p - ((1.0 - p) / b) * phi

        approved_risk_fraction: float = max(0.0, min(f_star, self.max_risk_per_trade))
        return approved_risk_fraction, 1.0

    def update(self, success: bool) -> None:
        """Updates the Bayesian success/failure tracker."""
        if success:
            self.alpha += 1.0
        else:
            self.beta += 1.0