from pathlib import Path


def test_runtime_directive_experience_loop_doc_exists_and_mentions_chain() -> None:
    path = Path("docs/runtime_directive_experience_loop.md")

    assert path.exists()

    text = path.read_text(encoding="utf-8")

    assert "Directive" in text
    assert "DirectiveResult" in text
    assert "EvidenceRecord" in text
    assert "MemoryRecord" in text
    assert "REDUCE_RISK" in text
    assert "src.testing.seed_directive" in text
    assert "src.testing.publish_directive_evidence" in text
    assert "src.testing.evidence_memory_bridge" in text
    assert "runtime-reduce-risk-1" in text
    assert "simulation_replay_scenario" in text
    assert "src.testing.publish_replay_scenarios" in text
    assert "simulation_replay_pending" in text
    assert "OBSERVE target=simulation" in text
    assert "advisory-only" in text