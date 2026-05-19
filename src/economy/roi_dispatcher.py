from typing import Tuple, Optional, Dict, Any

class ROIDispatcher:
    """
    ROI Dispatcher v2 - implements a Bayesian update for success probability
    and dynamic Kelly criterion 'phi' (fraction of capital to bet).

    It uses a Beta distribution to track success/failure history and
    combines it with a prior based on market volatility. The dispatcher
    then calculates an approved risk fraction based on a modified Kelly criterion.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the ROIDispatcher with optional configuration.

        Args:
            config: An optional dictionary containing configuration parameters.
                    Expected keys:
                    - "max_risk_per_trade": Maximum fraction of capital to risk per trade (float).
                    - "phi_llm": Base value for the dynamic phi (Kelly fraction) (float).
        """
        # Kelly criterion parameters
        self.max_risk_per_trade: float = 0.02
        self.phi_base: float = 0.25
        self.phi_k_sigma: float = 5.0  # Multiplier for volatility impact on phi

        # Bayesian tracker: Beta(alpha, beta) distribution parameters
        # alpha represents (number of successes + 1)
        self.alpha: float = 1.0
        # beta represents (number of failures + 1)
        self.beta: float = 1.0

        if config:
            self.max_risk_per_trade = config.get("max_risk_per_trade", self.max_risk_per_trade)
            # Note: "phi_llm" is used as the config key for phi_base as per original code.
            self.phi_base = config.get("phi_llm", self.phi_base)

    def _estimate_success_probability(self, volatility: float) -> float:
        """
        Estimates the probability of success using a Bayesian approach.

        Combines a volatility-based prior with a posterior derived from
        the Beta distribution (alpha, beta) reflecting historical performance.

        Args:
            volatility: The estimated market volatility.

        Returns:
            The estimated probability of success (float between 0 and 1).
        """
        # Prior estimate based on volatility
        # Formula: max(0.4, 0.55 - volatility * 2.5)
        # This creates a prior that decreases with volatility, with a floor of 0.4.
        prior: float = max(0.4, 0.55 - volatility * 2.5)

        # Posterior mean of the Beta distribution (historical performance)
        posterior: float = self.alpha / (self.alpha + self.beta)

        # Mix the prior and posterior.
        # Currently, a fixed blend: 70% prior, 30% historical posterior.
        # This weighting implicitly assumes limited historical data initially.
        return 0.7 * prior + 0.3 * posterior

    def _estimate_odds(self, volatility: float) -> float:
        """
        Estimates the odds (b in Kelly criterion, payoff ratio).
        Odds = (profit per unit risked) / (loss per unit risked).

        Args:
            volatility: The estimated market volatility.

        Returns:
            The estimated odds (b). Returns 1.0 if volatility is zero
            to prevent division by zero and imply a 1:1 risk-reward ratio.
        """
        if volatility <= 0:
            # If volatility is zero or negative, odds are set to 1.0.
            # This prevents division by zero and implies a 1:1 risk-reward ratio,
            # indicating no significant edge or predictable movement based on volatility.
            return 1.0
        # Formula: 0.02 / volatility.
        # This implies that higher volatility generally leads to lower odds (less favorable risk-reward).
        return 0.02 / volatility

    def _dynamic_phi(self, volatility: float) -> float:
        """
        Calculates a dynamic 'phi' value for the Kelly criterion.
        Phi (φ) is a fraction that scales the Kelly bet.
        It increases with volatility, up to a cap of 0.5.

        Args:
            volatility: The estimated market volatility.

        Returns:
            The dynamic phi value.
        """
        # Formula: min(0.5, self.phi_base * (1.0 + self.phi_k_sigma * volatility))
        # Phi increases from phi_base with volatility, capped at 0.5.
        return min(0.5, self.phi_base * (1.0 + self.phi_k_sigma * volatility))

    def evaluate(self, market_state: Dict[str, Any], capital: float) -> Tuple[float, float]:
        """
        Evaluates the market state and determines the approved fraction of capital to risk.

        Args:
            market_state: A dictionary containing market data.
                          Expected key: 'volatility_estimate' (float).
            capital: The current total capital available. (Note: 'capital' is not
                     directly used in the calculation of the `approved_risk_fraction`,
                     only implicitly in how `max_risk_per_trade` applies to a fraction).

        Returns:
            A tuple:
            - approved_risk_fraction: The fraction of total capital approved to risk (0.0 to max_risk_per_trade).
            - survival_score: A placeholder score, currently always 1.0.
        """
        # Get volatility estimate from market state, defaulting to 0.02 if not found.
        vol: float = market_state.get('volatility_estimate', 0.02)

        # Estimate success probability (p)
        p: float = self._estimate_success_probability(vol)
        # Estimate odds (b)
        b: float = self._estimate_odds(vol)
        # Calculate dynamic phi (φ)
        phi: float = self._dynamic_phi(vol)

        f_star: float
        if b <= 0:
            # If odds are non-positive, Kelly formula is not applicable, set f_star to 0.
            f_star = 0.0
        else:
            # Modified Kelly criterion formula: f* = p - (1-p)/b * phi
            # This calculates the optimal fraction to bet, scaled by phi in a specific way.
            f_star = p - (1.0 - p) / b * phi

        # The approved risk is capped at max_risk_per_trade and floored at 0.
        approved_risk_fraction: float = max(0.0, min(f_star, self.max_risk_per_trade))

        # Placeholder for future survival score calculation. Currently always 1.0.
        survival_score: float = 1.0
        return approved_risk_fraction, survival_score

    def update(self, success: bool) -> None:
        """
        Updates the Bayesian success/failure tracker after each trade.

        This method should be called after every trade to update the
        alpha and beta parameters of the Beta distribution, which
        in turn influences the estimated success probability.

        Args:
            success: True if the trade was successful, False otherwise.
        """
        if success:
            self.alpha += 1
        else:
            self.beta += 1