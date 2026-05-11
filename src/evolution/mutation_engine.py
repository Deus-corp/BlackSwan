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
    def __init__(self, llm_client):
        self.llm = llm_client
        self.history: List[MutationRecord] = []
        self.total_mutations = 0

    def mutate(self, params: Dict[str, float], context: str) -> Dict[str, float]:
        """
        Выполняет LLM-мутацию параметров. Возвращает новые параметры (или старые при ошибке).
        """
        prompt = f"""You are an expert trading strategy optimizer for the Kelly criterion.

Current market context:
{context}

Current strategy parameters:
{json.dumps(params, indent=2)}

Suggest a small, conservative adjustment. Return ONLY valid JSON like:
{{"max_risk_per_trade": 0.02, "phi_llm": 0.4}}"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.generate(prompt, max_tokens=200, temperature=0.35)
                # Пытаемся спарсить через Pydantic
                try:
                    new_params = StrategyParams.model_validate_json(response).to_dict()
                    self._record(params, new_params, context)
                    logger.info(f"LLM mutation successful: {params} → {new_params}")
                    return new_params
                except Exception:
                    # Fallback: ищем JSON вручную
                    import re
                    match = re.search(r'\{.*\}', response, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        new_params = StrategyParams(**data).to_dict()
                        self._record(params, new_params, context)
                        logger.info(f"LLM mutation (fallback) successful: {params} → {new_params}")
                        return new_params
            except Exception as e:
                logger.warning(f"LLM mutation attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.3 * (attempt + 1))
        return params  # fallback

    def _record(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
        record = MutationRecord(old_params, new_params, context)
        self.history.append(record)
        self.total_mutations += 1
        # Опционально можно сохранять в БД
        logger.debug(f"Mutation recorded, total: {self.total_mutations}")

    def get_stats(self) -> Dict:
        """Возвращает статистику мутаций."""
        return {
            "total_mutations": self.total_mutations,
            "last_mutation": self.history[-1].__dict__ if self.history else None,
        }