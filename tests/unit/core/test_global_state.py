import pytest
from src.core.global_state import GlobalState

def test_initial_state_has_required_sections():
    gs = GlobalState()
    state = gs.state
    assert "knowledge_graph" in state
    assert "economic_state" in state
    assert "infrastructure_state" in state
    assert "security_state" in state
    assert "component_status" in state

def test_update_modifies_state():
    gs = GlobalState()
    gs.update("economic_state", {"treasury_balance": {"USDC": 100.0}})
    assert gs.state["economic_state"]["treasury_balance"]["USDC"] == 100.0

def test_snapshot_returns_consistent_cid():
    gs = GlobalState()
    cid1 = gs.snapshot()
    # без изменений CID должен остаться тем же
    cid2 = gs.snapshot()
    assert cid1 == cid2
    # после изменения CID меняется
    gs.update("security_state", {"active_threat_level": "medium"})
    cid3 = gs.snapshot()
    assert cid1 != cid3

def test_verify_invariants_empty_state():
    gs = GlobalState()
    violations = gs.verify_invariants()
    assert len(violations) == 0

def test_verify_invariants_missing_section():
    gs = GlobalState()
    del gs.state["economic_state"]
    violations = gs.verify_invariants()
    assert "Missing section: economic_state" in violations