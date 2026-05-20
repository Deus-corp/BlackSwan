"""LLM strategist for soft overseer suggestions."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Protocol

from src.swarms.overseer.interfaces import LLMGenerator
from src.swarms.overseer.models import SwarmSnapshot

logger = logging.getLogger(__name__)

LLM_MAX_TOKENS_OVERSEER = 120
LLM_TEMPERATURE_OVERSEER = 0.1


class StrategistClient(Protocol):
    def generate(self, prompt: str, *, max_tokens: int, temperature: float) -> str:
        ...


class LLMStrategist:
    """Requests only non-critical recommendations from the LLM."""

    def __init__(self, llm: LLMGenerator) -> None:
        self._llm = llm

    async def suggest(self, snapshot: SwarmSnapshot) -> Dict[str, bool]:
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
            "Return ONLY valid JSON with boolean fields:\n"
            "reduce_risk, increase_exploration, unblock_ips, spawn_nodes, continue_explorer.\n"
            "Do not enforce safety policy; that is handled elsewhere.\n"
            "All omitted fields default to false, except continue_explorer defaults to true.\n"
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

        expected = [
            "reduce_risk",
            "increase_exploration",
            "unblock_ips",
            "spawn_nodes",
            "continue_explorer",
        ]
        return {
            key: parsed.get(key, False) if isinstance(parsed.get(key, False), bool) else False
            for key in expected
        }

    @staticmethod
    def _parse_json_object(response: str) -> Dict[str, Any]:
        if not isinstance(response, str):
            return {}

        text = response.strip()
        if not text:
            return {}

        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}

        candidate = text[start : end + 1]

        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            # Best-effort repair for bare keys.
            repaired = re.sub(
                r'([{,]\s*)(?<!")([A-Za-z_][A-Za-z0-9_]*)(?=\s*:)',
                r'\1"\2"',
                candidate,
            )
            try:
                parsed = json.loads(repaired)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}