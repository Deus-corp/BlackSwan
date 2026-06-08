import argparse
import asyncio

from src.core.crdt_adapter import CRDTAdapter
from src.testing.check_controlled_retry_execution_observability import (
    _exit_code_for_result,
    check_controlled_retry_execution_observability,
    check_controlled_retry_execution_observability_from_records,
)
from src.testing.run_controlled_retry_command import (
    build_controlled_retry_command_result,
)
from tests.unit.swarms.test_run_controlled_retry_command import _rendered_command


def _controlled_result(**overrides):
    item = build_controlled_retry_command_result(_rendered_command())
    item.update(overrides)
    return item


def test_controlled_retry_execution_observability_passes_for_reject_only_result() -> None:
    result = check_controlled_retry_execution_observability_from_records(
        [_controlled_result()]
    )

    assert result["status"] == "passed"
    assert result["controlled_execution_observed"] is True
    assert result["controlled_execution_results"] == 1
    assert result["controlled_execution_rejected"] == 1
    assert result["controlled_execution_skipped"] == 0
    assert result["controlled_execution_executed"] == 0
    assert result["controlled_execution_not_implemented"] == 1
    assert result["controlled_execution_enabled"] is False
    assert "controlled_execution_allowlist_match_does_not_execute" not in result["failed_checks"]
    assert result["controlled_command_parse_valid"] == 1
    assert result["controlled_command_parse_allowlisted"] == 1
    assert result["controlled_command_parse_execution_performed"] == 0
    assert result["controlled_execution_operator_authorized"] == 0
    assert _exit_code_for_result(result) == 0


def test_controlled_retry_execution_observability_fails_when_missing() -> None:
    result = check_controlled_retry_execution_observability_from_records([])

    assert result["status"] == "failed"
    assert result["controlled_execution_observed"] is False
    assert "controlled_execution_result_exists" in result["failed_checks"]
    assert _exit_code_for_result(result) == 1


def test_controlled_retry_execution_observability_fails_when_payload_executed() -> None:
    result = check_controlled_retry_execution_observability_from_records(
        [_controlled_result(payload={"executed": True})]
    )

    assert result["status"] == "failed"
    assert "controlled_execution_payload_not_executed" in result["failed_checks"]


def test_controlled_retry_execution_observability_allows_operator_authorization_intent_without_execution() -> None:
    result = check_controlled_retry_execution_observability_from_records(
        [_controlled_result(operator_authorized=True)]
    )

    assert result["status"] == "passed"
    assert result["controlled_execution_operator_authorized"] == 1
    assert result["controlled_execution_executed"] == 0
    assert result["failed_checks"] == []


def test_controlled_retry_execution_observability_reads_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)

    async def seed() -> None:
        await crdt.add_genome(_controlled_result())

    asyncio.run(seed())

    result = check_controlled_retry_execution_observability(
        argparse.Namespace(
            db_path=db_path,
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            proposal_id="",
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert result["controlled_execution_results"] == 1
    assert result["controlled_execution_rejected"] == 1


def test_controlled_retry_execution_observability_allows_allowlist_match_without_execution() -> None:
    record = _controlled_result(allowlist_matched=True)
    record["payload"]["allowlist_matched"] = True
    record["payload"]["executed"] = False

    result = check_controlled_retry_execution_observability_from_records([record])

    assert result["status"] == "passed"
    assert result["controlled_execution_rejected"] == 1
    assert result["controlled_execution_executed"] == 0
    assert result["failed_checks"] == []


def test_controlled_retry_execution_observability_fails_when_command_parse_executed() -> None:
    record = _controlled_result()
    record["command_parse"]["execution_performed"] = True
    record["payload"]["command_parse"]["execution_performed"] = True

    result = check_controlled_retry_execution_observability_from_records([record])

    assert result["status"] == "failed"
    assert "controlled_command_parse_did_not_execute" in result["failed_checks"]


def test_controlled_retry_execution_observability_fails_when_authorized_payload_executed() -> None:
    record = _controlled_result(operator_authorized=True)
    record["payload"]["executed"] = True

    result = check_controlled_retry_execution_observability_from_records([record])

    assert result["status"] == "failed"
    assert "operator_authorization_intent_does_not_execute" in result["failed_checks"]