from pathlib import Path

from src.swarms.explorer.node import ExplorerNode


class _FakeCRDT:
    def __init__(self) -> None:
        self.state = {}
        self.records = []

    async def add_genome(self, record):
        self.records.append(record)
        gid = record.get("gid") if isinstance(record, dict) else None
        if gid:
            self.state[gid] = record
        return record

    def close(self) -> None:
        return None


def test_explorer_node_ingests_source_adapter_target_metadata(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-source-aware-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    accepted = node._ingest_direct_targets(
        [
            {
                "url": "https://export.arxiv.org/api/query?search_query=all%3Aagents",
                "source_adapter": "arxiv",
                "source_kind": "arxiv_api_query",
                "discovery_method": "arxiv_api_search",
                "score": 0.9,
                "exploration_run_id": "run-1",
            },
            {
                "url": "https://github.com/search?q=agents&type=repositories",
                "source_adapter": "github",
                "source_kind": "github_repository_search",
                "discovery_method": "github_search",
                "score": 0.8,
                "exploration_run_id": "run-1",
            },
        ],
        event_gid="seed-1",
        source_gids=["seed-1"],
        provenance={"exploration_run_id": "run-1"},
    )

    assert len(accepted) == 2

    arxiv_context = node._target_context_by_url[
        "https://export.arxiv.org/api/query?search_query=all%3Aagents"
    ]
    github_context = node._target_context_by_url[
        "https://github.com/search?q=agents&type=repositories"
    ]

    assert arxiv_context["source_adapter"] == "arxiv"
    assert arxiv_context["source_kind"] == "arxiv_api_query"
    assert arxiv_context["discovery_method"] == "arxiv_api_search"
    assert arxiv_context["score"] == 0.9
    assert arxiv_context["exploration_run_id"] == "run-1"

    assert github_context["source_adapter"] == "github"
    assert github_context["score"] == 0.8


def test_explorer_node_source_aware_scheduler_prioritizes_adapters(
    tmp_path: Path,
) -> None:
    node = ExplorerNode(
        node_id="exp-node-source-priority-test",
        memory_db=tmp_path / "explorer_node.sqlite3",
    )
    node.batch_limit = 4
    node.max_targets_per_domain_per_tick = 2

    node._target_context_by_url = {
        "https://docs.example/sitemap.xml": {
            "source_adapter": "sitemap",
            "score": 0.85,
        },
        "https://export.arxiv.org/api/query?search_query=all%3Aagents": {
            "source_adapter": "arxiv",
            "score": 0.9,
        },
        "https://github.com/search?q=agents&type=repositories": {
            "source_adapter": "github",
            "score": 0.8,
        },
        "https://duckduckgo.com/html?q=agents": {
            "source_adapter": "search",
            "score": 0.65,
        },
    }

    selected = node._select_domain_aware_targets(
        [
            "https://duckduckgo.com/html?q=agents",
            "https://github.com/search?q=agents&type=repositories",
            "https://docs.example/sitemap.xml",
            "https://export.arxiv.org/api/query?search_query=all%3Aagents",
        ]
    )

    assert selected == [
        "https://duckduckgo.com/html?q=agents",
        "https://github.com/search?q=agents&type=repositories",
        "https://docs.example/sitemap.xml",
        "https://export.arxiv.org/api/query?search_query=all%3Aagents",
    ]

    # Each domain contributes once; selected counters preserve adapter visibility.
    assert node._source_adapter_targets_selected["search"] == 1
    assert node._source_adapter_targets_selected["github"] == 1
    assert node._source_adapter_targets_selected["sitemap"] == 1
    assert node._source_adapter_targets_selected["arxiv"] == 1