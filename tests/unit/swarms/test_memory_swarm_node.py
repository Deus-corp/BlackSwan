import pytest

from src.swarms.memory.node import MemorySwarmNode


class DummyCRDT:
    def __init__(self) -> None:
        self.payloads = []

    async def add_genome(self, payload):
        self.payloads.append(payload)


@pytest.mark.asyncio
async def test_memory_swarm_node_publishes_real_memory_metrics() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    await node.remember_event("hello memory", topic="test")
    await node.publish_heartbeat()

    assert node.crdt.payloads

    payload = node.crdt.payloads[-1]

    assert payload["type"] == "swarm_heartbeat"
    assert payload["swarm"] == "memory"
    assert payload["node_id"] == "memory-test"

    metrics = payload["metrics"]

    assert metrics["total_records"] == 1
    assert metrics["records_ingested"] == 1
    assert metrics["by_kind"]["event"] == 1
    assert metrics["by_scope"]["own"] == 1
    assert metrics["verified_records"] == 1
    assert metrics["episodic_records"] == 1

@pytest.mark.asyncio
async def test_memory_swarm_node_ingests_external_record_through_quarantine() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "event",
            "scope": "shared",
            "topic": "external",
            "payload": {"message": "external memory", "tags": ["external"]},
            "source": {
                "originNodeId": "trusted-node",
                "swarm": "trade",
                "parents": [],
            },
            "confidence": 0.9,
        }
    )

    assert accepted is True
    assert node.records_ingested == 1
    assert node.records_rejected == 0

    stats = await node.memory.stats()
    assert stats.total_records == 1
    assert stats.by_scope["shared"] == 1
    assert stats.by_kind["event"] == 1


@pytest.mark.asyncio
async def test_memory_swarm_node_rejects_low_confidence_record() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "event",
            "scope": "shared",
            "topic": "external",
            "payload": {"message": "low confidence"},
            "source": {
                "originNodeId": "trusted-node",
                "swarm": "trade",
                "parents": [],
            },
            "confidence": 0.1,
        }
    )

    assert accepted is False
    assert node.records_ingested == 0
    assert node.records_rejected == 1

    stats = await node.memory.stats()
    assert stats.total_records == 0

@pytest.mark.asyncio
async def test_memory_swarm_node_annotates_ingested_record_with_recognition() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "event",
            "scope": "shared",
            "topic": "recognition",
            "payload": {"message": "test_green milestone validated", "tags": ["test"]},
            "source": {
                "originNodeId": "simulation-1",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
            "verified": True,
        }
    )

    assert accepted is True
    assert node.records_recognized == 1
    assert node.recognition_counts

    records = await node.memory.recall(
        {
            "kind": "event",
            "scope": "shared",
            "text": "recognition",
        }
    )

    assert len(records) == 1

    record = records[0]
    recognition = record.payload["recognition"]

    assert recognition["label"] in node.recognition_counts
    assert "recognition:" + recognition["label"] in record.payload["tags"]
    assert record.source["recognition_label"] == recognition["label"]


@pytest.mark.asyncio
async def test_memory_swarm_node_recognizes_duplicate_ingestion() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    raw = {
        "kind": "event",
        "scope": "shared",
        "topic": "duplicate",
        "payload": {"message": "same simulation memory event"},
        "source": {
            "originNodeId": "simulation-1",
            "swarm": "simulation",
            "parents": [],
        },
        "confidence": 0.95,
    }

    first = await node.ingest_record({**raw, "id": "dup-1"})
    second = await node.ingest_record({**raw, "id": "dup-2"})

    assert first is True
    assert second is True
    assert node.records_recognized == 2
    assert node.recognition_counts.get("duplicate", 0) >= 1

    records = await node.memory.recall(
        {
            "kind": "event",
            "scope": "shared",
            "text": "same simulation memory event",
        }
    )

    assert len(records) == 2

@pytest.mark.asyncio
async def test_memory_swarm_node_adds_recognition_policy_hints() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "fact",
            "scope": "shared",
            "topic": "milestone",
            "payload": {"message": "test_green milestone validated"},
            "source": {
                "originNodeId": "simulation-1",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
            "verified": True,
        }
    )

    assert accepted is True
    assert node.recognition_action_counts.get("store", 0) == 1
    assert node.recognition_action_counts.get("gold_candidate", 0) == 1

    records = await node.memory.recall(
        {
            "kind": "fact",
            "scope": "shared",
            "text": "milestone",
        }
    )

    assert len(records) == 1

    record = records[0]
    policy = record.payload["recognition_policy"]

    assert "store" in policy["actions"]
    assert "gold_candidate" in policy["actions"]
    assert "action:gold_candidate" in record.payload["tags"]
    assert record.source["recognition_policy_severity"] == "info"


@pytest.mark.asyncio
async def test_memory_swarm_node_marks_dangerous_memory_policy_hints() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "event",
            "scope": "shared",
            "topic": "security",
            "payload": {"message": "private_key leak detected"},
            "source": {
                "originNodeId": "security-1",
                "swarm": "security",
                "parents": [],
            },
            "confidence": 0.95,
        }
    )

    assert accepted is True
    assert node.recognition_counts.get("dangerous", 0) == 1
    assert node.recognition_action_counts.get("alert", 0) == 1
    assert node.recognition_action_counts.get("review", 0) == 1
    assert node.recognition_action_counts.get("quarantine_candidate", 0) == 1

    records = await node.memory.recall(
        {
            "kind": "event",
            "scope": "shared",
            "text": "private_key",
        }
    )

    assert len(records) == 1

    record = records[0]
    policy = record.payload["recognition_policy"]

    assert policy["severity"] == "critical"
    assert "alert" in policy["actions"]
    assert "review" in policy["actions"]
    assert "action:alert" in record.payload["tags"]
    assert "risk:high" in record.payload["tags"]

@pytest.mark.asyncio
async def test_memory_swarm_node_heartbeat_reports_gold_candidates() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "fact",
            "scope": "shared",
            "topic": "milestone",
            "payload": {"message": "test_green milestone validated"},
            "source": {
                "originNodeId": "simulation-1",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
            "verified": True,
        }
    )

    assert accepted is True

    await node.publish_heartbeat()

    payload = node.crdt.payloads[-1]
    metrics = payload["metrics"]

    assert metrics["gold_candidates"] == 1
    assert metrics["recognition_action_counts"]["gold_candidate"] == 1

@pytest.mark.asyncio
async def test_memory_swarm_node_exports_gold_samples(tmp_path) -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "fact",
            "scope": "shared",
            "topic": "milestone",
            "payload": {"message": "test_green milestone validated"},
            "source": {
                "originNodeId": "simulation-1",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
            "verified": True,
        }
    )

    assert accepted is True

    output_path = tmp_path / "gold_samples.jsonl"
    exported_path = await node.export_gold_samples(output_path)

    assert exported_path == output_path
    assert output_path.exists()

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "test_green milestone validated" in lines[0]

def test_memory_swarm_node_cli_parser_export_gold() -> None:
    from src.swarms.memory.node import build_parser

    parser = build_parser()
    args = parser.parse_args(["export-gold", "--output", "artifacts/memory/gold.jsonl"])

    assert args.command == "export-gold"
    assert args.output == "artifacts/memory/gold.jsonl"

def test_memory_swarm_node_cli_parser_export_gold_no_scan_shared() -> None:
    from src.swarms.memory.node import build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "export-gold",
            "--output",
            "artifacts/memory/gold.jsonl",
            "--no-scan-shared",
        ]
    )

    assert args.command == "export-gold"
    assert args.output == "artifacts/memory/gold.jsonl"
    assert args.no_scan_shared is True

@pytest.mark.asyncio
async def test_memory_swarm_node_heartbeat_includes_memory_summary() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "fact",
            "scope": "shared",
            "topic": "milestone",
            "payload": {"message": "test_green milestone validated"},
            "source": {
                "originNodeId": "simulation-1",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
            "verified": True,
        }
    )

    assert accepted is True

    await node.publish_heartbeat()

    metrics = node.crdt.payloads[-1]["metrics"]
    summary = metrics["memory_summary"]

    assert summary["total_records"] == 1
    assert summary["gold_candidates"] == 1
    assert summary["recognition_counts"]["valuable"] == 1
    assert summary["recognition_action_counts"]["gold_candidate"] == 1
    assert metrics["gold_candidates"] == 1

@pytest.mark.asyncio
async def test_memory_swarm_node_heartbeat_reports_replay_execution_evidence_summary(monkeypatch) -> None:
    from src.memory.summary import MemorySummary
    import src.swarms.memory.node as memory_node_module

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    def fake_build_memory_summary(*args, **kwargs):
        return MemorySummary(
            total_records=1,
            runtime_evidence_records=1,
            replay_execution_evidence_records=1,
            replay_execution_evidence_passed=1,
            replay_execution_evidence_failed=0,
        )

    monkeypatch.setattr(memory_node_module, "build_memory_summary", fake_build_memory_summary)

    await node.publish_heartbeat()

    metrics = node.crdt.payloads[-1]["metrics"]
    summary = metrics["memory_summary"]

    assert summary["runtime_evidence_records"] == 1
    assert summary["replay_execution_evidence_records"] == 1
    assert summary["replay_execution_evidence_passed"] == 1
    assert summary["replay_execution_evidence_failed"] == 0