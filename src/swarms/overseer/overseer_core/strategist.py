"""LLM-driven strategic recommendation engine for the overseer system.

The strategist is intentionally advisory.

It can suggest:
- reduce_risk
- increase_exploration
- unblock_ips
- spawn_nodes
- continue_explorer
- run_improver_once
- pause_improver

The deterministic PolicyEngine remains the safety gate. LLM output cannot
override hard safety rules.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Mapping
from typing import Any, Dict, Final

from src.swarms.overseer.overseer_core.interfaces import LLMGenerator
from src.swarms.overseer.overseer_core.models import SwarmSnapshot

logger: Final = logging.getLogger(__name__)

LLM_MAX_TOKENS_OVERSEER: Final[int] = 200
LLM_TEMPERATURE_OVERSEER: Final[float] = 0.1

ALLOWED_KEYS: Final[set[str]] = {
    "reduce_risk",
    "increase_exploration",
    "unblock_ips",
    "spawn_nodes",
    "continue_explorer",
    "run_improver_once",
    "pause_improver",
}

DEFAULT_SUGGESTIONS: Final[dict[str, bool]] = {
    "reduce_risk": False,
    "increase_exploration": False,
    "unblock_ips": False,
    "spawn_nodes": False,
    "continue_explorer": True,
    "run_improver_once": False,
    "pause_improver": False,
}

MAX_LLM_RESPONSE_CHARS: Final[int] = 8000


class LLMStrategist:
    """Requests non-critical behavioral adjustments from the LLM.

    This class does not execute anything. It only returns normalized boolean
    suggestions for PolicyEngine.merge().
    """

    def __init__(self, llm: LLMGenerator) -> None:
        self._llm = llm

    async def suggest(self, snapshot: SwarmSnapshot) -> Dict[str, bool]:
        """Generate advisory strategic boolean recommendations."""
        prompt = self._build_prompt(snapshot)

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
            logger.debug("LLM strategist returned no parseable JSON.")
            return {}

        normalized = self._normalize_suggestions(parsed)

        logger.debug("LLM strategist suggestions: %s", normalized)

        return normalized

    def _build_prompt(self, snapshot: SwarmSnapshot) -> str:
        """Build compact JSON-constrained prompt."""
        payload = {
            "trade": {
                "nodes": snapshot.trade_nodes,
                "capital": round(snapshot.trade_capital, 2),
                "dq": round(snapshot.trade_dq, 4),
                "fitness": round(snapshot.trade_fitness, 4),
                "stale_nodes": list(snapshot.stale_trade_nodes),
            },
            "security": {
                "nodes": snapshot.security_nodes,
                "blocked_ips": snapshot.blocked_ips,
                "stale_nodes": list(snapshot.stale_security_nodes),
            },
            "explorer": {
                "nodes": snapshot.explorer_nodes,
                "recent_findings": snapshot.recent_findings,
                "recent_vulnerability_alerts": snapshot.recent_vulnerability_alerts,
                "stale_nodes": list(snapshot.stale_explorer_nodes),
            },
            "improver": {
                "nodes": snapshot.improver_nodes,
                "files_processed": snapshot.improver_files_processed,
                "files_improved": snapshot.improver_files_improved,
                "files_quarantined": snapshot.improver_files_quarantined,
                "files_failed": snapshot.improver_files_failed,
                "last_cycle_duration_seconds": round(
                    snapshot.improver_last_cycle_duration_seconds,
                    2,
                ),
                "last_error_count": snapshot.improver_last_error_count,
                "stale_nodes": list(snapshot.stale_improver_nodes),
                "advisory_only": True,
            },
            "resources": snapshot.resources,
            "safety_note": {
                "improver_commands_are_advisory_only": True,
                "do_not_enable_run_improver_once_when_pause_improver_is_true": True,
            },
        }

        schema = {
            "reduce_risk": "boolean",
            "increase_exploration": "boolean",
            "unblock_ips": "boolean",
            "spawn_nodes": "boolean",
            "continue_explorer": "boolean",
            "run_improver_once": "boolean",
            "pause_improver": "boolean",
        }

        defaults = DEFAULT_SUGGESTIONS

        return (
            "You are BlackSwan Overseer strategist.\n"
            "Return ONLY one valid JSON object. No markdown. No prose.\n"
            "The JSON object MUST contain exactly these boolean keys:\n"
            f"{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
            "Defaults if uncertain:\n"
            f"{json.dumps(defaults, ensure_ascii=False, sort_keys=True)}\n"
            "Do not include explanations. Do not include nested objects.\n"
            "You are advisory only; hard safety rules are enforced elsewhere.\n"
            "Improver flags are advisory-only and must not be treated as direct execution.\n"
            "Current swarm state:\n"
            f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"
            "JSON:"
        )

    @classmethod
    def _normalize_suggestions(cls, data: Mapping[str, Any]) -> Dict[str, bool]:
        """Allowlist and cast parsed LLM output."""
        normalized: Dict[str, bool] = {}

        for key in ALLOWED_KEYS:
            default = DEFAULT_SUGGESTIONS[key]
            normalized[key] = cls._to_bool(data.get(key), default=default)

        # Hard internal sanity: pause wins over run at strategist-normalization level too.
        if normalized.get("pause_improver"):
            normalized["run_improver_once"] = False

        return normalized

    @staticmethod
    def _to_bool(value: Any, *, default: bool) -> bool:
        """Convert loose model output to bool safely."""
        if isinstance(value, bool):
            return value

        if value is None:
            return default

        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            cleaned = value.strip().lower()

            if cleaned in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
                return True

            if cleaned in {"0", "false", "no", "n", "off", "disable", "disabled"}:
                return False

        return default

    @staticmethod
    def _parse_json_object(response: Any) -> Dict[str, Any]:
        """Extract and parse one JSON object from an LLM response."""
        if not isinstance(response, str):
            return {}

        text = response.strip()

        if not text:
            return {}

        if len(text) > MAX_LLM_RESPONSE_CHARS:
            text = text[:MAX_LLM_RESPONSE_CHARS]

        text = LLMStrategist._strip_markdown_fence(text)

        candidate = LLMStrategist._extract_first_json_object(text)
        if not candidate:
            return {}

        parsed = LLMStrategist._json_loads_object(candidate)
        if parsed:
            return parsed

        repaired = LLMStrategist._repair_common_json_issues(candidate)
        if repaired != candidate:
            return LLMStrategist._json_loads_object(repaired)

        return {}

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        """Remove common ```json wrappers."""
        stripped = text.strip()

        if stripped.startswith("```"):
            stripped = re.sub(
                r"^```(?:json|JSON)?\s*",
                "",
                stripped,
                flags=re.IGNORECASE,
            )
            stripped = re.sub(
                r"\s*```$",
                "",
                stripped,
                flags=re.IGNORECASE,
            )

        return stripped.strip()

    @staticmethod
    def _extract_first_json_object(text: str) -> str:
        """Extract first balanced JSON object from text."""
        start = text.find("{")
        if start == -1:
            return ""

        depth = 0
        in_string = False
        escape = False

        for idx in range(start, len(text)):
            char = text[idx]

            if escape:
                escape = False
                continue

            if char == "\\":
                escape = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]

        return ""

    @staticmethod
    def _json_loads_object(candidate: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return {}

        return dict(parsed) if isinstance(parsed, Mapping) else {}

    @staticmethod
    def _repair_common_json_issues(candidate: str) -> str:
        """Repair conservative common JSON issues from small models/API wrappers."""
        repaired = candidate.strip()

        repaired = re.sub(
            r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)',
            r'\1"\2"\3',
            repaired,
        )

        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        repaired = re.sub(r"\bNone\b", "null", repaired)

        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        return repaired