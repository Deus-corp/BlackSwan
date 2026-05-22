"""LLM-driven strategic recommendation engine for the overseer system."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Final

from .interfaces import LLMGenerator
from .models import SwarmSnapshot

logger: Final = logging.getLogger(__name__)

LLM_MAX_TOKENS_OVERSEER: Final[int] = 120
LLM_TEMPERATURE_OVERSEER: Final[float] = 0.1


class LLMStrategist:
    """Requests non-critical behavioral adjustments from the LLM based on swarm state."""

    def __init__(self, llm: LLMGenerator) -> None:
        self._llm = llm

    async def suggest(self, snapshot: SwarmSnapshot) -> Dict[str, bool]:
        """Generates strategic boolean recommendations based on current snapshot."""
        prompt_payload = {
            "trade": {
                "nodes": snapshot.trade_nodes,
                "capital": round(snapshot.trade_capital, 2),
                "dq": round(snapshot.trade_dq, 4),
                "fitness": round(snapshot.trade_fitness, 4),
            },
            "security": {
                "nodes": snapshot.security_nodes,
                "blocked_ips": snapshot.blocked_ips,
            },
            "explorer": {
                "nodes": snapshot.explorer_nodes,
                "recent_findings": snapshot.recent_findings,
                "recent_vulnerability_alerts": snapshot.recent_vulnerability_alerts,
            },
            "resources": snapshot.resources,
        }

        prompt = (
            "You are BlackSwan Overseer.\n"
            "Return ONLY valid JSON with keys: reduce_risk, increase_exploration, "
            "unblock_ips, spawn_nodes, continue_explorer.\n"
            "Values must be booleans. Default all to false, except continue_explorer (true).\n"
            f"State: {json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True)}\n"
            "Answer:"
        )

        try:
            response = await asyncio.to_thread(
                self._llm.generate,
                prompt,
                max_tokens=LLM_MAX_TOKENS_OVERSEER,
                temperature=LLM_TEMPERATURE_OVERSEER,
            )
        except Exception as exc:
            logger.warning("LLM generation failed: %s", exc)
            return {}

        parsed = self._parse_json_object(response)
        if not parsed:
            return {}

        return {
            "reduce_risk": bool(parsed.get("reduce_risk", False)),
            "increase_exploration": bool(parsed.get("increase_exploration", False)),
            "unblock_ips": bool(parsed.get("unblock_ips", False)),
            "spawn_nodes": bool(parsed.get("spawn_nodes", False)),
            "continue_explorer": bool(parsed.get("continue_explorer", True)),
        }

    @staticmethod
    def _parse_json_object(response: str) -> Dict[str, Any]:
        """Sanitizes and attempts to parse LLM response as JSON."""
        if not isinstance(response, str):
            return {}

        text = response.strip()
        if not text:
            return {}

        # Strip markdown wrappers such as ```json ... ```
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE)

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}

        candidate = text[start : end + 1]

        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            # Attempt to fix common formatting issues like unquoted keys.
            repaired = re.sub(
                r'([{,]\s*)(?<!")([A-Za-z_][A-Za-z0-9_]*)(?=\s*:)',
                r'\1"\2"',
                candidate,
            )
            try:
                data = json.loads(repaired)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                logger.debug("Failed to parse LLM response as JSON")
                return {}