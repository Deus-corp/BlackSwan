from typing import Tuple, Optional, Dict, Any, Final

class ROIDispatcher:
    """
    ROI Dispatcher v2 - implements a Bayesian update for success probability
    and dynamic Kelly criterion 'phi' (fraction of capital to bet).

    It uses a Beta distribution to track success/failure history and
    combines it with a prior based on market volatility. The dispatcher
    then calculates an approved risk fraction based on a modified Kelly criterion.

    This class encapsulates the logic for determining an appropriate risk fraction
    for a given market state, learning from past trade outcomes.
    """

    # --- Configuration Defaults and Constants ---
    # Kelly criterion parameters
    DEFAULT_MAX_RISK_PER_TRADE: Final[float] = 0.02
    DEFAULT_PHI_BASE: Final[float] = 0.25
    PHI_K_SIGMA_MULTIPLIER: Final[float] = 5.0
    PHI_CAP: Final[float] = 0.5

    # Bayesian tracker: Beta(alpha, beta) distribution parameters
    # alpha represents (number of successes + 1)
    # beta represents (number of failures + 1)
    BETA_INITIAL_ALPHA: Final[float] = 1.0
    BETA_INITIAL_BETA: Final[float] = 1.0

    # Success Probability Estimation Constants
    PRIOR_FLOOR: Final[float] = 0.4
    PRIOR_VOLATILITY_BASE: Final[float] = 0.55
    PRIOR_VOLATILITY_FACTOR: Final[float] = 2.5
    PRIOR_WEIGHT: Final[float] = 0.7
    POSTERIOR_WEIGHT: Final[float] = 0.3

    # Odds Estimation Constants
    # This constant represents a baseline expected return or edge,
    # inversely proportional to volatility.
    ODDS_NUMERATOR: Final[float] = 0.02
    DEFAULT_VOLATILITY_ESTIMATE: Final[float] = 0.02 # Used if market_state lacks volatility

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initializes the ROIDispatcher with optional configuration.

        Args:
            config: An optional dictionary containing configuration parameters.
                    Expected keys:
                    - "max_risk_per_trade": Maximum fraction of capital to risk per trade (float).
                                            Defaults to `DEFAULT_MAX_RISK_PER_TRADE`.
                    - "phi_llm": Base value for the dynamic phi (Kelly fraction) (float).
                                 Note: This key maps to `self.phi_base` due to historical naming.
                                 Defaults to `DEFAULT_PHI_BASE`.
        """
        # Kelly criterion parameters
        self.max_risk_per_trade: float = self.DEFAULT_MAX_RISK_PER_TRADE
        self.phi_base: float = self.DEFAULT_PHI_BASE
        self.phi_k_sigma: float = self.PHI_K_SIGMA_MULTIPLIER

        # Bayesian tracker: Beta(alpha, beta) distribution parameters
        self.alpha: float = self.BETA_INITIAL_ALPHA
        self.beta: float = self.BETA_INITIAL_BETA

        if config:
            self.max_risk_per_trade = config.get("max_risk_per_trade", self.max_risk_per_trade)
            # "phi_llm" is used as the config key for phi_base as per original code's convention.
            self.phi_base = config.get("phi_llm", self.phi_base)

    def _estimate_success_probability(self, volatility: float) -> float:
        """
        Estimates the probability of success using a Bayesian approach.

        Combines a volatility-based prior with a posterior derived from
        the Beta distribution (alpha, beta) reflecting historical performance.

        The prior assumes that higher volatility generally implies a lower
        inherent success probability, with a floor to prevent overly pessimistic estimates.
        The posterior reflects the accumulated historical success/failure ratio.
        These are blended with fixed weights.

        Args:
            volatility: The estimated market volatility (non-negative).

        Returns:
            The estimated probability of success (float between 0 and 1).
        """
        # Prior estimate based on volatility
        # Formula: max(PRIOR_FLOOR, PRIOR_VOLATILITY_BASE - volatility * PRIOR_VOLATILITY_FACTOR)
        prior: float = max(self.PRIOR_FLOOR, self.PRIOR_VOLATILITY_BASE - volatility * self.PRIOR_VOLATILITY_FACTOR)

        # Posterior mean of the Beta distribution (historical performance)
        # Avoid division by zero, though initial alpha/beta should prevent this.
        sum_alpha_beta = self.alpha + self.beta
        if sum_alpha_beta <= 0:
            posterior = 0.5 # Default to neutral if no valid history
        else:
            posterior: float = self.alpha / sum_alpha_beta

        # Mix the prior and posterior with fixed weights.
        # This weighting implicitly assumes that the prior holds more sway, particularly
        # when historical data (alpha, beta) might be limited initially.
        return self.PRIOR_WEIGHT * prior + self.POSTERIOR_WEIGHT * posterior

    def _estimate_odds(self, volatility: float) -> float:
        """
        Estimates the odds (b in Kelly criterion, payoff ratio).
        Odds = (expected profit per unit risked) / (expected loss per unit risked).

        The odds are inversely related to volatility, implying that higher market
        volatility might lead to a less favorable risk-reward profile or
        that a fixed 'edge' (represented by `ODDS_NUMERATOR`) is harder to achieve
        with increased market choppiness.

        Args:
            volatility: The estimated market volatility (non-negative).

        Returns:
            The estimated odds (b). Returns 1.0 if volatility is zero or negative
            to prevent division by zero and imply a 1:1 risk-reward ratio,
            indicating no significant edge or predictable movement based on volatility.
        """
        if volatility <= 0:
            return 1.0  # Safe default: 1:1 risk-reward ratio if volatility is non-positive.
        # Formula: ODDS_NUMERATOR / volatility
        return self.ODDS_NUMERATOR / volatility

    def _dynamic_phi(self, volatility: float) -> float:
        """
        Calculates a dynamic 'phi' value for the Kelly criterion.
        Phi (φ) is a fraction that scales the Kelly bet, typically used to reduce
        the aggressiveness of the full Kelly bet.
        It increases with volatility, up to a defined cap, making the strategy
        more aggressive (closer to full Kelly) in more volatile conditions,
        but always constrained.

        Args:
            volatility: The estimated market volatility (non-negative).

        Returns:
            The dynamic phi value (float between `phi_base` and `PHI_CAP`).
        """
        # Formula: min(PHI_CAP, self.phi_base * (1.0 + self.phi_k_sigma * volatility))
        # Phi increases from phi_base with volatility, capped at PHI_CAP.
        return min(self.PHI_CAP, self.phi_base * (1.0 + self.phi_k_sigma * volatility))

    def evaluate(self, market_state: Dict[str, Any], capital: float) -> Tuple[float, float]:
        """
        Evaluates the market state and determines the approved fraction of capital to risk.

        This method calculates the optimal Kelly fraction (`f_star`) based on
        estimated success probability, odds, and a dynamic scaling factor.
        The final approved risk fraction is constrained by `max_risk_per_trade`
        and floored at zero.

        Args:
            market_state: A dictionary containing market data.
                          Expected key: 'volatility_estimate' (float, non-negative).
                          If not found, `DEFAULT_VOLATILITY_ESTIMATE` is used.
            capital: The current total capital available.
                     Note: 'capital' is not directly used in the calculation of the
                     `approved_risk_fraction` itself, as the output is a fraction.
                     It would be used downstream to calculate the absolute risk amount.

        Returns:
            A tuple:
            - approved_risk_fraction: The fraction of total capital approved to risk (0.0 to `max_risk_per_trade`).
            - survival_score: A placeholder score, currently always 1.0, intended for future risk management metrics.
        """
        # Get volatility estimate from market state, defaulting if not found.
        # Ensure volatility is non-negative for calculations.
        vol: float = max(0.0, float(market_state.get('volatility_estimate', self.DEFAULT_VOLATILITY_ESTIMATE)))

        # Estimate success probability (p)
        p: float = self._estimate_success_probability(vol)
        # Estimate odds (b)
        b: float = self._estimate_odds(vol)
        # Calculate dynamic phi (φ)
        phi: float = self._dynamic_phi(vol)

        f_star: float
        if b <= 0:
            # If odds are non-positive, Kelly formula is not applicable or implies infinite loss potential.
            # Setting f_star to 0.0 prevents taking any risk.
            f_star = 0.0
        else:
            # Modified Kelly criterion formula: f* = p - (1-p)/b * phi
            # This calculates the optimal fraction to bet, scaled by phi to adjust aggressiveness.
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
        alpha and beta parameters of the Beta distribution. These parameters
        reflect the accumulated historical performance and influence the
        estimated success probability in subsequent `evaluate` calls.

        Args:
            success: True if the trade was successful (profitable), False otherwise (loss or breakeven).
        """
        if success:
            self.alpha += 1
        else:
            self.beta += 1