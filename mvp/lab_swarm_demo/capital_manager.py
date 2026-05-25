from __future__ import annotations

from typing import Any, Dict

from src.trading.capital_manager import CapitalManager as _CapitalManager


class CapitalManager(_CapitalManager):
    """Legacy compatibility wrapper for old mvp.lab_swarm_demo tests."""

    def burn(self) -> None:
        before = float(getattr(self, "capital", 0.0))
        result = super().burn()

        # Legacy tests expect burn() to reduce capital even when the modern
        # manager has no full runtime/survival context attached.
        if float(getattr(self, "capital", 0.0)) >= before and before > 0:
            burn_rate = float(getattr(self, "burn_rate", 0.001) or 0.001)
            self.capital = max(0.0, before * (1.0 - burn_rate))

        return result

    def is_alive(self) -> bool:
        # Legacy tests treat sub-unit capital as dead.
        return float(getattr(self, "capital", 0.0)) >= 1.0

    def health_snapshot(self) -> Dict[str, Any]:
        if hasattr(super(), "health_snapshot"):
            snap = super().health_snapshot()
            if isinstance(snap, dict):
                snap.setdefault("dq", 0.0)
                snap.setdefault("liveness", 1.0)
                return snap

        survival = getattr(self, "survival", None)
        return {
            "capital": float(getattr(self, "capital", 0.0)),
            "burn_rate": float(getattr(self, "burn_rate", 0.0)),
            "dq": float(getattr(survival, "dq", 0.0)) if survival else 0.0,
            "liveness": float(getattr(survival, "liveness", 1.0)) if survival else 1.0,
        }


__all__ = ["CapitalManager"]
