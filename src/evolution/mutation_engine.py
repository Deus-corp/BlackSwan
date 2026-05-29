"""MutationEngine manages LLM-driven strategy parameter mutations.

The engine asks an LLM for bounded JSON parameter updates, robustly extracts JSON
from noisy responses, falls back to random bounded mutations, and records mutation
history/events without requiring nonce-manager-specific persistence hooks.
"""

from __future__ import annotations

import copy
import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from loguru import logger

try:
    from src.swarms.trade.domain.mutation_metrics import note_llm_mutation
except ImportError:
    logger.warning("Could not import note_llm_mutation; mutation metrics disabled.")

    def note_llm_mutation() -> None:
        return None


@dataclass(slots=True)
class MutationRecord:
    """Single strategy parameter mutation record."""

    old_params: dict[str, float]
    new_params: dict[str, float]
    context: str
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MutationEngine:
    """Generate bounded strategy mutations using an LLM with safe random fallback."""

    STRATEGY_KEYS: tuple[str, ...] = (
        "max_risk_per_trade",
        "phi_llm",
        "stop_loss_ratio",
        "trailing_stop_ratio",
        "momentum_window",
        "volatility_threshold",
    )

    PARAM_BOUNDS: dict[str, tuple[float, float]] = {
        "max_risk_per_trade": (0.001, 0.2),
        "phi_llm": (0.001, 1.0),
        "stop_loss_ratio": (0.001, 0.5),
        "trailing_stop_ratio": (0.001, 0.5),
        "momentum_window": (2.0, 100.0),
        "volatility_threshold": (0.001, 1.0),
    }

    DEFAULT_PARAMS: dict[str, float] = {
        "max_risk_per_trade": 0.02,
        "phi_llm": 0.25,
        "stop_loss_ratio": 0.03,
        "trailing_stop_ratio": 0.01,
        "momentum_window": 14.0,
        "volatility_threshold": 0.025,
    }

    MAX_HISTORY = 1_000
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_SECONDS = 0.3

    def __init__(
        self,
        llm_client: Any,
        node_id: str = "swarm",
        nonce_manager: Any = None,
        event_store: Any = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_history: int = MAX_HISTORY,
    ) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.llm = llm_client
        self.history: list[MutationRecord] = []
        self.total_mutations = 0
        self.node_id = clean_node_id
        self.nonce_manager = nonce_manager
        self.event_store = event_store
        self.max_retries = max(1, int(max_retries))
        self.max_history = max(1, int(max_history))

    def mutate(
        self,
        params: dict[str, float],
        context: str,
        external_context: str = "",
    ) -> dict[str, float]:
        """Generate a new bounded strategy parameter set."""
        current_params = self._normalize_params(params)
        full_context = self._build_context(context, external_context)
        prompt = self._build_prompt(current_params, full_context)

        for attempt in range(self.max_retries):
            try:
                response = self._call_llm(prompt)
                logger.debug("LLM raw mutation response: {}", response)

                json_candidate = self._extract_json(response)
                if not json_candidate:
                    raise ValueError("No valid JSON object found in LLM response.")

                raw_params = json.loads(json_candidate)
                if not isinstance(raw_params, dict):
                    raise ValueError("LLM JSON response is not an object.")

                new_params = self._normalize_params(raw_params, fallback=current_params)
                self._record(current_params, new_params, full_context, source="llm")
                note_llm_mutation()

                if new_params == current_params:
                    logger.info("LLM suggested no parameter change.")
                else:
                    logger.info("LLM mutation successful: {} -> {}", current_params, new_params)

                return new_params

            except json.JSONDecodeError as exc:
                logger.warning(
                    "LLM mutation JSON parse failed ({}/{}): {}",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )
            except Exception as exc:
                logger.warning(
                    "LLM mutation attempt failed ({}/{}): {}",
                    attempt + 1,
                    self.max_retries,
                    exc,
                    exc_info=True,
                )

            if attempt < self.max_retries - 1:
                time.sleep(self.DEFAULT_BACKOFF_SECONDS * (attempt + 1))

        logger.warning("All LLM mutation attempts failed; applying random fallback mutation.")
        fallback_params = self._random_mutation(current_params)
        self._record(current_params, fallback_params, full_context, source="random_fallback")
        note_llm_mutation()
        return fallback_params

    def _call_llm(self, prompt: str) -> str:
        if self.llm is None or not hasattr(self.llm, "generate"):
            raise RuntimeError("llm_client must provide a generate(prompt, ...) method")

        response = self.llm.generate(prompt, max_tokens=300, temperature=0.25)
        return str(response or "")

    def _build_prompt(self, params: dict[str, float], context: str) -> str:
        return f"""You are a JSON generator. Output ONLY a valid JSON object.
No explanations, no markdown, no comments, no <think> tags.

Adjust the following strategy parameters based on the market context.
The JSON object must contain exactly these keys:
{", ".join(json.dumps(key) for key in self.STRATEGY_KEYS)}

Current market context:
{context}

Current strategy parameters:
{json.dumps(params, indent=2, sort_keys=True)}

Valid output example:
{{"max_risk_per_trade": 0.02, "phi_llm": 0.4, "stop_loss_ratio": 0.03, "trailing_stop_ratio": 0.01, "momentum_window": 14, "volatility_threshold": 0.025}}

Now generate only the adjusted JSON object:
"""

    @staticmethod
    def _build_context(context: str, external_context: str = "") -> str:
        parts = [str(context or "").strip()]
        external = str(external_context or "").strip()
        if external:
            parts.append("Additional market data:")
            parts.append(external)
        return "\n".join(part for part in parts if part)

    def _normalize_params(
        self,
        raw_params: dict[str, Any],
        *,
        fallback: Optional[dict[str, float]] = None,
    ) -> dict[str, float]:
        if not isinstance(raw_params, dict):
            raw_params = {}

        fallback_params = fallback or self.DEFAULT_PARAMS
        normalized: dict[str, float] = {}

        for key in self.STRATEGY_KEYS:
            value = raw_params.get(key, fallback_params.get(key, self.DEFAULT_PARAMS[key]))
            normalized[key] = self._normalize_value(key, value, fallback_params.get(key))

        return normalized

    def _normalize_value(self, key: str, value: Any, fallback: Optional[float] = None) -> float:
        low, high = self.PARAM_BOUNDS[key]
        default = self.DEFAULT_PARAMS[key] if fallback is None else fallback

        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float(default)

        number = max(low, min(high, number))

        if key == "momentum_window":
            return float(int(round(number)))

        return round(number, 4)

    def _random_mutation(self, params: dict[str, float]) -> dict[str, float]:
        mutated = dict(params)

        for key in self.STRATEGY_KEYS:
            low, high = self.PARAM_BOUNDS[key]
            current = mutated.get(key, self.DEFAULT_PARAMS[key])

            if key == "momentum_window":
                delta = random.choice([-5, -3, -2, -1, 1, 2, 3, 5])
                mutated[key] = self._normalize_value(key, current + delta)
                continue

            factor = random.uniform(0.85, 1.15)
            jitter = random.uniform(-0.01, 0.01)
            candidate = current * factor + jitter
            mutated[key] = self._normalize_value(key, candidate)

            if mutated[key] < low or mutated[key] > high:
                mutated[key] = self._normalize_value(key, random.uniform(low, high))

        return mutated

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract the first valid JSON object from a noisy LLM response."""
        if not text:
            return None

        clean_text = self._strip_noise(str(text))

        fenced_json = self._extract_fenced_json(clean_text)
        if fenced_json is not None:
            return fenced_json

        return self._extract_balanced_json_object(clean_text)

    @staticmethod
    def _strip_noise(text: str) -> str:
        text = re.sub(
            r"<\s*think\s*>.*?(?:<\s*/\s*think\s*>|$)",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    @staticmethod
    def _extract_fenced_json(text: str) -> Optional[str]:
        for pattern in (
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
        ):
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if not match:
                continue

            candidate = match.group(1).strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

        return None

    @staticmethod
    def _extract_balanced_json_object(text: str) -> Optional[str]:
        starts = [index for index, char in enumerate(text) if char == "{"]

        for start in starts:
            depth = 0
            in_string = False
            escape = False

            for index in range(start, len(text)):
                char = text[index]

                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                    continue

                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : index + 1].strip()
                        try:
                            json.loads(candidate)
                            return candidate
                        except json.JSONDecodeError:
                            break

        return None

    def _record(
        self,
        old_params: dict[str, float],
        new_params: dict[str, float],
        context: str,
        *,
        source: str,
    ) -> None:
        record = MutationRecord(
            old_params=copy.deepcopy(old_params),
            new_params=copy.deepcopy(new_params),
            context=str(context or ""),
            source=source,
        )

        self.history.append(record)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

        self.total_mutations += 1

        self._persist_to_mutation_store(record)
        self._persist_to_event_store(record)

    def _persist_to_mutation_store(self, record: MutationRecord) -> None:
        if self.nonce_manager is None:
            return

        save_mutation = getattr(self.nonce_manager, "save_mutation", None)
        if not callable(save_mutation):
            logger.debug(
                "Mutation store for node {} has no save_mutation(); skipping external mutation persistence.",
                self.node_id,
            )
            return

        try:
            save_mutation(
                node_id=self.node_id,
                old_params=record.old_params,
                new_params=record.new_params,
                context=record.context,
                source=record.source,
                timestamp=record.timestamp,
            )
        except TypeError:
            try:
                save_mutation(
                    node_id=self.node_id,
                    old_params=record.old_params,
                    new_params=record.new_params,
                    context=record.context,
                )
            except Exception as exc:
                logger.warning("Failed to save mutation to mutation store: {}", exc)
        except Exception as exc:
            logger.warning("Failed to save mutation to mutation store: {}", exc)

    def _persist_to_event_store(self, record: MutationRecord) -> None:
        if self.event_store is None:
            return

        append = getattr(self.event_store, "append", None)
        if not callable(append):
            return

        try:
            from src.core.events import Event

            append(
                Event.create(
                    node_id=self.node_id,
                    event_type="llm_mutation",
                    payload={
                        "old_params": record.old_params,
                        "new_params": record.new_params,
                        "context": record.context,
                        "source": record.source,
                        "timestamp": record.timestamp,
                    },
                    parent_id=None,
                )
            )
        except Exception as exc:
            logger.warning("Failed to write mutation event: {}", exc)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_mutations": self.total_mutations,
            "history_size": len(self.history),
            "last_mutation": self.history[-1].to_dict() if self.history else None,
        }