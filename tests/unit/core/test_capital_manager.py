import pytest
from mvp.lab_swarm_demo.capital_manager import CapitalManager

def test_burn_reduces_capital():
    mgr = CapitalManager(capital=1000.0)
    mgr.burn()
    assert mgr.capital < 1000.0

def test_is_alive():
    mgr = CapitalManager(capital=0.5)
    mgr.burn()
    assert mgr.is_alive() is False

def test_health_snapshot():
    mgr = CapitalManager(capital=500.0)
    snap = mgr.health_snapshot()
    assert snap["capital"] == 500.0
    assert "dq" in snap
    assert "liveness" in snap

def test_apply_dq_delta():
    # Мок survival
    class FakeSurvival:
        def __init__(self):
            self.dq = 0.0
            self.liveness = 1.0
    surv = FakeSurvival()
    mgr = CapitalManager(capital=1000.0)
    mgr.set_survival(surv)
    mgr.apply_dq_delta(0.001)
    assert surv.dq == 0.001