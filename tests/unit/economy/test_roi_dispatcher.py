import pytest
from src.economy.roi_dispatcher import ROIDispatcher

@pytest.fixture
def dispatcher():
    return ROIDispatcher()

def test_initial_fraction_in_range(dispatcher):
    market_state = {"price": 1.0, "volatility_estimate": 0.02}
    fraction, survival = dispatcher.evaluate(market_state, 1000.0)
    assert 0.0 <= fraction <= dispatcher.max_risk_per_trade
    assert survival == 1.0

def test_bayesian_update_success(dispatcher):
    old_alpha, old_beta = dispatcher.alpha, dispatcher.beta
    dispatcher.update(True)
    assert dispatcher.alpha == old_alpha + 1
    assert dispatcher.beta == old_beta

def test_bayesian_update_failure(dispatcher):
    old_alpha, old_beta = dispatcher.alpha, dispatcher.beta
    dispatcher.update(False)
    assert dispatcher.alpha == old_alpha
    assert dispatcher.beta == old_beta + 1

def test_fraction_zero_when_volatility_high(dispatcher):
    market_state = {"price": 1.0, "volatility_estimate": 1e9}
    fraction, _ = dispatcher.evaluate(market_state, 1000.0)
    assert fraction == 0.0

def test_custom_config():
    dispatcher = ROIDispatcher(config={"max_risk_per_trade": 0.03, "phi_llm": 0.1})
    market_state = {"price": 1.0, "volatility_estimate": 0.02}
    fraction, _ = dispatcher.evaluate(market_state, 1000.0)
    assert 0.0 <= fraction <= 0.03