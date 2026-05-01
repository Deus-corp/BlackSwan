import pytest
from src.security.reputation_manager import ReputationManager

def test_initial_score():
    rep = ReputationManager()
    assert rep.get_score("node1") == 1.0

def test_penalty_for_inflated_fitness():
    rep = ReputationManager()
    rep.update("node1", claimed_fitness=0.9, actual_fitness=0.1)
    assert rep.get_score("node1") < 1.0

def test_bonus_for_honest_claim():
    rep = ReputationManager()
    rep.update("node1", claimed_fitness=0.5, actual_fitness=0.5)
    assert rep.get_score("node1") > 1.0

def test_is_trusted_threshold():
    rep = ReputationManager()
    rep.scores["node1"] = 0.3
    assert rep.is_trusted("node1")
    rep.scores["node1"] = 0.29
    assert not rep.is_trusted("node1")