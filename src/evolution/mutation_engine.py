"""
MutationEngine — LLM-мутации, хранение истории и метрик.
"""
import json
import time
from typing import Dict, List, Optional
from loguru import logger
from src.intelligence.strategy_schema import StrategyParams


class MutationRecord:
    def __init__(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
        self.timestamp = time.time()
        self.old_params = old_params.copy()
        self.new_params = new_params.copy()
        self.context = context


class MutationEngine:
    def __init__(self, llm_client, node_id: str = "swarm", nonce_manager=None):
        self.llm = llm_client
        self.history: List[MutationRecord] = []
        self.total_mutations = 0
        self.node_id = node_id                # ← сохраняем идентификатор
        self.nonce_manager = nonce_manager

    def mutate(self, params: Dict[str, float], context: str, external_context: str = "") -> Dict[str, float]:
        """
        Выполняет LLM-мутацию параметров.
        context: базовая информация (volatility, dq, capital)
        external_context: дополнительные данные (новости, сигналы, OrderBook)
        """
        full_context = context
        if external_context:
            full_context += "\nAdditional market data:\n" + external_context

        prompt = f"""You are an expert trading strategy optimizer for the Kelly criterion.

Current market context:
{full_context}

Current strategy parameters:
{json.dumps(params, indent=2)}

Suggest a small, conservative adjustment. Return ONLY valid JSON like:
{{"max_risk_per_trade": 0.02, "phi_llm": 0.4, "stop_loss_ratio": 0.03, "trailing_stop_ratio": 0.01, "momentum_window": 14, "volatility_threshold": 0.025}}
"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.generate(prompt, max_tokens=300, temperature=0.35)
                try:
                    new_params = StrategyParams.model_validate_json(response).to_dict()
                    self._record(params, new_params, full_context)
                    logger.info(f"LLM mutation successful: {params} → {new_params}")
                    return new_params
                except Exception:
                    import re
                    match = re.search(r'\{.*\}', response, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        new_params = StrategyParams(**data).to_dict()
                        self._record(params, new_params, full_context)
                        logger.info(f"LLM mutation (fallback) successful: {params} → {new_params}")
                        return new_params
            except Exception as e:
                logger.warning(f"LLM mutation attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.3 * (attempt + 1))
        return params

    def _record(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
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
            except Exception as e:
                logger.error(f"Failed to save mutation to DB: {e}")

    def get_stats(self) -> Dict:
        """Возвращает статистику мутаций."""
        return {
            "total_mutations": self.total_mutations,
            "last_mutation": self.history[-1].__dict__ if self.history else None,
        }