"""Controlled retry execution adapter contract.

This module defines the execution adapter interface before any real execution
adapter is introduced. The only supported adapter is `mock`, and it never
invokes subprocesses.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

class UnsupportedControlledRetryExecutionAdapter(ValueError):
    """Raised when a controlled retry execution adapter is not supported."""

class ControlledRetryExecutionAdapter(Protocol):
    """Protocol for future controlled retry execution adapters."""

    name: str
    mode: str

    def run(
        self,
        controlled_result: Mapping[str, Any],
        *,
        timeout_profile: str = "standard",
    ) -> dict[str, Any]:
        """Return an execution-shaped adapter result."""


class MockControlledRetryExecutionAdapter:
    """Mock adapter that never invokes subprocesses."""

    name = "mock"
    mode = "mock"

    def run(
        self,
        controlled_result: Mapping[str, Any],
        *,
        timeout_profile: str = "standard",
    ) -> dict[str, Any]:
        rendered_command_id = str(
            controlled_result.get("rendered_command_id") or ""
        ).strip()
        controlled_execution_result_id = str(
            controlled_result.get("controlled_execution_result_id") or ""
        ).strip()

        return {
            "type": "controlled_retry_execution_adapter_result",
            "adapter": self.name,
            "mode": self.mode,
            "status": "mock_executed",
            "reason": "mock_execution_completed",
            "controlled_execution_result_id": controlled_execution_result_id,
            "rendered_command_id": rendered_command_id,
            "timeout_profile": timeout_profile,
            "subprocess_invoked": False,
            "real_execution_enabled": False,
            "exit_code": 0,
            "stdout": "mock controlled retry execution",
            "stderr": "",
            "payload": {
                "executed": False,
                "mock_executed": True,
                "subprocess_invoked": False,
                "real_execution_enabled": False,
                "adapter": self.name,
                "mode": self.mode,
                "timeout_profile": timeout_profile,
            },
        }


class UnsupportedRealControlledRetryExecutionAdapter:
    """Placeholder for a future real adapter.

    This adapter is intentionally not runnable. It documents that real execution
    requires a separate explicit implementation PR.
    """

    name = "real"
    mode = "real"
    supported = False
    real_execution_supported = False
    subprocess_supported = False

    def run(
        self,
        controlled_result: Mapping[str, Any],
        *,
        timeout_profile: str = "standard",
    ) -> dict[str, Any]:
        raise UnsupportedControlledRetryExecutionAdapter(
            "controlled retry real execution adapter is not supported"
        )


def get_controlled_retry_execution_adapter(
    adapter: str,
) -> ControlledRetryExecutionAdapter:
    """Return a controlled retry execution adapter by name."""
    clean_adapter = str(adapter or "").strip().lower()

    if clean_adapter == "mock":
        return MockControlledRetryExecutionAdapter()

    if clean_adapter == "real":
        raise UnsupportedControlledRetryExecutionAdapter(
            "controlled retry real execution adapter is not supported"
        )

    raise UnsupportedControlledRetryExecutionAdapter(
        f"unsupported controlled retry execution adapter: {adapter}"
    )


def describe_controlled_retry_execution_adapter_contract() -> dict[str, Any]:
    """Return a machine-readable adapter contract summary."""
    return {
        "type": "controlled_retry_execution_adapter_contract",
        "schema_version": "controlled-retry-execution-adapter/v1",
        "supported_adapters": ["mock"],
        "unsupported_adapters": ["real"],
        "placeholder_adapters": ["real"],
        "real_execution_supported": False,
        "subprocess_supported": False,
        "required_invariants": {
            "payload_executed": False,
            "subprocess_invoked": False,
            "real_execution_enabled": False,
        },
        "adapter_result_fields": [
            "adapter",
            "mode",
            "status",
            "reason",
            "controlled_execution_result_id",
            "rendered_command_id",
            "timeout_profile",
            "subprocess_invoked",
            "real_execution_enabled",
            "exit_code",
            "stdout",
            "stderr",
            "payload",
        ],
        "real_adapter_contract": {
            "name": "real",
            "mode": "real",
            "supported": False,
            "runnable": False,
            "requires_explicit_pr": True,
            "failure_reason": "controlled_retry_real_execution_adapter_not_supported",
        },
    }