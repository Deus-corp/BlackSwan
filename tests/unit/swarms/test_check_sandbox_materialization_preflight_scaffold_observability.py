from tests.unit.swarms.test_check_sandbox_request_envelope_scaffold_observability import (
    _envelope_record,
    _matrix_record,
    _preflight_record,
    _valid_scaffold_record,
)
from src.testing.build_real_execution_sandbox_materialization_preflight_scaffold import (
    build_real_execution_sandbox_materialization_preflight_scaffold_record,
)
from src.testing.check_sandbox_materialization_preflight_scaffold_observability import (
    _exit_code_for_result,
    _format_result,
    check_sandbox_materialization_preflight_scaffold_observability_from_records,
)


def _materialization_record(**overrides):
    item = build_real_execution_sandbox_materialization_preflight_scaffold_record(
        _envelope_record()
    )
    item.update(overrides)
    item["payload"] = {
        **dict(item.get("payload") or {}),
        **{
            key: value
            for key, value in overrides.items()
            if key != "payload"
        },
    }
    return item


def test_check_sandbox_materialization_preflight_scaffold_observability_passes_for_fail_closed_materialization() -> None:
    result = (
        check_sandbox_materialization_preflight_scaffold_observability_from_records(
            [
                _matrix_record(),
                _valid_scaffold_record(),
                _preflight_record(),
                _envelope_record(),
                _materialization_record(),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "passed"
    assert result["failed_checks"] == []
    assert result["sandbox_materialization_preflight_scaffold_observed"] is True
    assert result["sandbox_materialization_preflight_scaffold_records"] == 1
    assert (
        result["sandbox_materialization_preflight_scaffold_linkage_complete"]
        is True
    )
    assert result["sandbox_materialization_preflight_scaffold_orphans"] == 0
    assert result["sandbox_materialization_preflight_scaffold_blocked"] == 1
    assert result["sandbox_materialization_preflight_scaffold_fail_closed"] == 1
    assert result["sandbox_materialization_preflight_scaffold_deny_by_default"] == 1
    assert result["sandbox_materialization_preflight_scaffold_preflight_enabled"] == 0
    assert result["sandbox_materialization_preflight_scaffold_preflight_passed"] == 0
    assert (
        result[
            "sandbox_materialization_preflight_scaffold_envelope_generation_enabled"
        ]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_envelope_materialized"]
        == 0
    )
    assert result["sandbox_materialization_preflight_scaffold_envelope_executable"] == 0
    assert (
        result["sandbox_materialization_preflight_scaffold_workspace_creation_enabled"]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_input_materialization_enabled"]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_command_rendering_enabled"]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_sandbox_execution_enabled"]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_result_generation_enabled"]
        == 0
    )
    assert result["sandbox_materialization_preflight_scaffold_execution_performed"] == 0
    assert result["sandbox_materialization_preflight_scaffold_subprocess_invoked"] == 0
    assert result["sandbox_materialization_preflight_scaffold_real_execution_enabled"] == 0
    assert (
        result[
            "sandbox_materialization_preflight_scaffold_external_side_effects_performed"
        ]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_production_paths_mutated"]
        == 0
    )
    assert (
        result["sandbox_materialization_preflight_scaffold_production_secrets_accessed"]
        == 0
    )
    assert (
        result["brief_key_metrics"][
            "security_real_execution_sandbox_materialization_preflight_scaffolds"
        ]
        == 1
    )
    assert "Sandbox materialization preflight scaffold observed" in result[
        "brief_summary"
    ]


def test_check_sandbox_materialization_preflight_scaffold_observability_fails_when_preflight_enabled() -> None:
    result = (
        check_sandbox_materialization_preflight_scaffold_observability_from_records(
            [
                _matrix_record(),
                _valid_scaffold_record(),
                _preflight_record(),
                _envelope_record(),
                _materialization_record(
                    sandbox_materialization_preflight_enabled=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_materialization_preflight_scaffold_does_not_enable_preflight"
        in result["failed_checks"]
    )


def test_check_sandbox_materialization_preflight_scaffold_observability_fails_when_preflight_passed() -> None:
    result = (
        check_sandbox_materialization_preflight_scaffold_observability_from_records(
            [
                _matrix_record(),
                _valid_scaffold_record(),
                _preflight_record(),
                _envelope_record(),
                _materialization_record(
                    sandbox_materialization_preflight_passed=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_materialization_preflight_scaffold_does_not_pass_preflight"
        in result["failed_checks"]
    )


def test_check_sandbox_materialization_preflight_scaffold_observability_fails_when_materializes_inputs() -> None:
    result = (
        check_sandbox_materialization_preflight_scaffold_observability_from_records(
            [
                _matrix_record(),
                _valid_scaffold_record(),
                _preflight_record(),
                _envelope_record(),
                _materialization_record(
                    sandbox_input_materialization_enabled=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_materialization_preflight_scaffold_does_not_materialize_inputs"
        in result["failed_checks"]
    )


def test_check_sandbox_materialization_preflight_scaffold_observability_fails_when_executes() -> None:
    result = (
        check_sandbox_materialization_preflight_scaffold_observability_from_records(
            [
                _matrix_record(),
                _valid_scaffold_record(),
                _preflight_record(),
                _envelope_record(),
                _materialization_record(
                    sandbox_execution_enabled=True,
                    execution_performed=True,
                    subprocess_invoked=True,
                ),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    assert result["status"] == "failed"
    assert (
        "sandbox_materialization_preflight_scaffold_does_not_enable_sandbox_execution"
        in result["failed_checks"]
    )
    assert "sandbox_materialization_preflight_scaffold_does_not_execute" in result[
        "failed_checks"
    ]
    assert (
        "sandbox_materialization_preflight_scaffold_does_not_invoke_subprocess"
        in result["failed_checks"]
    )


def test_check_sandbox_materialization_preflight_scaffold_observability_format_and_exit_code() -> None:
    result = (
        check_sandbox_materialization_preflight_scaffold_observability_from_records(
            [
                _matrix_record(),
                _valid_scaffold_record(),
                _preflight_record(),
                _envelope_record(),
                _materialization_record(),
            ],
            proposal_id="proposal-1",
            rendered_command_id="rendered-1",
        )
    )

    text = _format_result(result)

    assert _exit_code_for_result(result) == 0
    assert (
        "Sandbox materialization preflight scaffold observability: status=passed"
        in text
    )
    assert "observed=true" in text
    assert "preflight_enabled=0" in text
    assert "preflight_passed=0" in text
    assert "input_materialization_enabled=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "real_execution_enabled=0" in text