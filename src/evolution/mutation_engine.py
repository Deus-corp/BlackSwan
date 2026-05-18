"""
MutationEngine manages LLM-driven parameter mutations, recording historical data and metrics.

It includes robust JSON parsing for LLM responses and falls back to random mutations
if LLM parsing fails after several attempts, ensuring continuous evolution.
"""
import json
import re
import time
import random
from typing import Dict, List, Optional, Any
from loguru import logger

# Import for mutation metrics - kept here to preserve original functionality,
# though a more decoupled approach might use dependency injection or a callback.
# Ensure this import path is correct for your project structure.
try:
    from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation
except ImportError:
    logger.warning("Could not import 'note_llm_mutation'. Mutation metrics will not be recorded.")
    def note_llm_mutation() -> None:
        """Placeholder for mutation metrics function if actual import fails."""
        pass


class MutationRecord:
    """
    Represents a single record of a strategy parameter mutation.

    Attributes:
        timestamp (float): Unix timestamp of when the mutation occurred.
        old_params (Dict[str, float]): The strategy parameters before mutation.
        new_params (Dict[str, float]): The strategy parameters after mutation.
        context (str): The market context used for the mutation.
    """
    def __init__(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str) -> None:
        self.timestamp: float = time.time()
        self.old_params: Dict[str, float] = old_params.copy()
        self.new_params: Dict[str, float] = new_params.copy()
        self.context: str = context


class MutationEngine:
    """
    Orchestrates the mutation of trading strategy parameters using an LLM.

    It provides a robust mechanism to generate new parameters based on market context,
    handles LLM response parsing, implements fallback random mutations, and records
    all changes.
    """

    STRATEGY_KEYS: List[str] = [
        "max_risk_per_trade", "phi_llm", "stop_loss_ratio",
        "trailing_stop_ratio", "momentum_window", "volatility_threshold"
    ]

    def __init__(self, llm_client: Any, node_id: str = "swarm", nonce_manager: Any = None, event_store: Any = None) -> None:
        """
        Initializes the MutationEngine.

        Args:
            llm_client: An object with a `generate` method that takes a prompt
                        and returns an LLM response string.
            node_id (str): Identifier for the current node, used for recording mutations.
            nonce_manager (Any, optional): An object to save mutation nonces/records.
                                           Must have a `save_mutation` method.
            event_store (Any, optional): An object to append mutation events.
                                         Must have an `append` method and expect
                                         `Event.create` objects.
        """
        self.llm = llm_client
        self.history: List[MutationRecord] = []
        self.total_mutations: int = 0
        self.node_id: str = node_id
        self.nonce_manager = nonce_manager
        self.event_store = event_store

    def mutate(self, params: Dict[str, float], context: str, external_context: str = "") -> Dict[str, float]:
        """
        Generates a new set of strategy parameters based on current context using an LLM.

        If LLM generation or parsing fails after multiple retries, it falls back
        to random mutations.

        Args:
            params (Dict[str, float]): The current strategy parameters.
            context (str): The primary market context.
            external_context (str): Additional market data to append to the context.

        Returns:
            Dict[str, float]: The new, mutated strategy parameters.
        """
        full_context: str = context
        if external_context:
            full_context += "\nAdditional market data:\n" + external_context

        prompt: str = f"""You are a JSON generator. Output ONLY a valid JSON object. No explanations, no markdown, no <think> tags.

Adjust the following strategy parameters based on the market context. The JSON must contain exactly these keys:
"max_risk_per_trade", "phi_llm", "stop_loss_ratio", "trailing_stop_ratio", "momentum_window", "volatility_threshold".

Current market context:
{full_context}

Current strategy parameters:
{json.dumps(params, indent=2)}

Example of valid output:
{{"max_risk_per_trade": 0.02, "phi_llm": 0.4, "stop_loss_ratio": 0.03, "trailing_stop_ratio": 0.01, "momentum_window": 14, "volatility_threshold": 0.025}}

Now generate your adjusted JSON:
"""

        max_retries: int = 3
        for attempt in range(max_retries):
            try:
                response: str = self.llm.generate(prompt, max_tokens=300, temperature=0.25)
                logger.debug(f"LLM FULL raw response: {response}")

                json_candidate: Optional[str] = self._extract_json(response)
                if not json_candidate:
                    raise ValueError("No valid JSON found in LLM response after extraction attempts.")

                raw_params: Dict[str, Any] = json.loads(json_candidate)
                new_params: Dict[str, float] = {}

                for key in self.STRATEGY_KEYS:
                    if key in raw_params and isinstance(raw_params[key], (int, float)):
                        if key == "momentum_window":
                            # Ensure momentum_window is an integer within a reasonable range
                            new_params[key] = float(max(2, min(100, int(raw_params[key]))))
                        else:
                            # Clamp float parameters to a common range and round
                            new_params[key] = round(max(0.001, min(1.0, float(raw_params[key]))), 4)
                    else:
                        # Fallback to current parameter value if LLM output is invalid or missing for a key
                        logger.warning(f"LLM output for key '{key}' was invalid or missing. Using current value: {params.get(key, 0.1)}")
                        new_params[key] = params.get(key, 0.1) # Default to 0.1 if key also missing in current params

                if new_params == params:
                    logger.info("LLM suggested no real change in parameters, keeping current values.")
                else:
                    logger.info(f"LLM mutation successful: {params} → {new_params}")

                self._record(params, new_params, full_context)
                note_llm_mutation() # Record global LLM mutation metric
                return new_params

            except json.JSONDecodeError as e:
                logger.warning(f"LLM JSON parsing failed (attempt {attempt+1}/{max_retries}): {e}")
            except ValueError as e:
                logger.warning(f"LLM response content error (attempt {attempt+1}/{max_retries}): {e}")
            except Exception as e:
                logger.exception(f"An unexpected error occurred during LLM mutation attempt {attempt+1}/{max_retries}: {e}")

            if attempt < max_retries - 1:
                time.sleep(0.3 * (attempt + 1)) # Exponential backoff

        # Fallback: Apply random mutations if all LLM attempts fail
        logger.warning("All LLM mutation attempts failed. Applying random mutation as a fallback.")
        new_params_fallback: Dict[str, float] = {}
        for key in self.STRATEGY_KEYS:
            if key == "momentum_window":
                new_params_fallback[key] = float(random.randint(2, 50))
            else:
                new_params_fallback[key] = round(random.uniform(0.001, 0.3), 4)

        self._record(params, new_params_fallback, full_context)
        note_llm_mutation() # Record global LLM mutation metric even for fallback
        return new_params_fallback

    def _extract_json(self, text: str) -> Optional[str]:
        """
        Extracts a JSON string from a given text, prioritizing various formats.

        Args:
            text (str): The input text, potentially containing JSON.

        Returns:
            Optional[str]: The extracted JSON string if found and valid, otherwise None.
        """
        # 1. Remove everything between <think> and </think> (case-insensitive, greedy)
        #    Also handles unclosed <think> tags.
        text = re.sub(r'<\s*think\s*>.*?(?:<\s*/\s*think\s*>|$)', '', text, flags=re.DOTALL | re.IGNORECASE)

        # 2. Remove any remaining XML-like tags (e.g., <tool_code>, <function_call>)
        text = re.sub(r'<[^>]+>', '', text)

        # 3. Search for JSON within ```json ... ``` blocks
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # 4. Search for JSON within generic ``` ... ``` blocks
        match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # 5. Iteratively search for the first valid JSON object starting with '{' and ending with '}'
        #    This is the most aggressive fallback.
        candidates = re.finditer(r'\{.*?\}', text, re.DOTALL)
        for m in candidates:
            candidate = m.group(0)
            try:
                json.loads(candidate) # Validate if it's actual JSON
                return candidate
            except json.JSONDecodeError:
                continue # Not valid JSON, try next candidate

        logger.debug("No valid JSON pattern found in text after all extraction attempts.")
        return None

    def _record(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str) -> None:
        """
        Records the mutation in history and optionally persists it to external systems.

        Args:
            old_params (Dict[str, float]): The parameters before mutation.
            new_params (Dict[str, float]): The parameters after mutation.
            context (str): The context used for the mutation.
        """
        record = MutationRecord(old_params, new_params, context)
        self.history.append(record)
        self.total_mutations += 1

        if self.nonce_manager:
            try:
                self.nonce_manager.save_mutation(
                    node_id=self.node_id,
                    old_params=old_params,
                    new_params=new_params,
                    context=context
                )
                logger.debug(f"Mutation saved to nonce_manager for node {self.node_id}.")
            except Exception as e:
                logger.error(f"Failed to save mutation to nonce_manager: {e}")

        if self.event_store:
            try:
                # Import Event here to avoid circular dependency or if it's not always needed
                # If Event is frequently used, consider moving its import to the top
                from src.core.events import Event
                self.event_store.append(Event.create(
                    node_id=self.node_id,
                    event_type="llm_mutation",
                    payload={
                        "old_params": old_params,
                        "new_params": new_params,
                        "context": context
                    },
                    parent_id=None # Assuming mutations are root events or parent_id is optional
                ))
                logger.debug(f"Mutation event written to event_store for node {self.node_id}.")
            except ImportError:
                logger.error("Could not import 'src.core.events.Event'. Event not stored.")
            except Exception as e:
                logger.error(f"Failed to write mutation to event_store: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Retrieves statistics about the mutation engine's operations.

        Returns:
            Dict[str, Any]: A dictionary containing total mutations and details
                            of the last mutation, if any.
        """
        return {
            "total_mutations": self.total_mutations,
            "last_mutation": self.history[-1].__dict__ if self.history else None,
        }