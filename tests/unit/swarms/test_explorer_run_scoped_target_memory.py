from pathlib import Path

from src.swarms.explorer.node import ExplorerNode


def test_explorer_node_allows_same_url_in_new_exploration_run(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-run-scoped-memory-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )

    first = node._ingest_direct_targets(
        [
            {
                "url": "https://example.com/resource",
                "source_adapter": "search",
                "score": 0.5,
                "exploration_run_id": "run-1",
            }
        ],
        event_gid="seed-run-1",
        source_gids=["seed-run-1"],
        provenance={"exploration_run_id": "run-1"},
    )

    second = node._ingest_direct_targets(
        [
            {
                "url": "https://example.com/resource",
                "source_adapter": "search",
                "score": 0.5,
                "exploration_run_id": "run-2",
            }
        ],
        event_gid="seed-run-2",
        source_gids=["seed-run-2"],
        provenance={"exploration_run_id": "run-2"},
    )

    duplicate_same_run = node._ingest_direct_targets(
        [
            {
                "url": "https://example.com/resource",
                "source_adapter": "search",
                "score": 0.5,
                "exploration_run_id": "run-2",
            }
        ],
        event_gid="seed-run-2b",
        source_gids=["seed-run-2b"],
        provenance={"exploration_run_id": "run-2"},
    )

    assert first == ["https://example.com/resource"]
    assert second == ["https://example.com/resource"]
    assert duplicate_same_run == []