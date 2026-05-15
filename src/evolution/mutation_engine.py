"""
MutationEngine — LLM-мутации, хранение истории и метрик.
Исправлено: улучшенный поиск JSON в ответах локальной LLM,
fallback-случайные мутации при ошибках парсинга.
"""
import json
import re
import time
import random
from typing import Dict, List, Optional
from loguru import logger


class MutationRecord:
    def __init__(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
        self.timestamp = time.time()
        self.old_params = old_params.copy()
        self.new_params = new_params.copy()
        self.context = context


class MutationEngine:
    STRATEGY_KEYS = [
        "max_risk_per_trade", "phi_llm", "stop_loss_ratio",
        "trailing_stop_ratio", "momentum_window", "volatility_threshold"
    ]

    def __init__(self, llm_client, node_id: str = "swarm", nonce_manager=None, event_store=None):
        self.llm = llm_client
        self.history: List[MutationRecord] = []
        self.total_mutations = 0
        self.node_id = node_id
        self.nonce_manager = nonce_manager
        self.event_store = event_store

    def mutate(self, params: Dict[str, float], context: str, external_context: str = "") -> Dict[str, float]:
        full_context = context
        if external_context:
            full_context += "\nAdditional market data:\n" + external_context

        prompt = f"""You are a trading strategy optimizer. Adjust the following parameters conservatively based on the current market context. Return ONLY a JSON object with the updated values.

Current market context:
{full_context}

Current strategy parameters:
{json.dumps(params, indent=2)}

Return a JSON like:
{{"max_risk_per_trade": 0.02, "phi_llm": 0.4, "stop_loss_ratio": 0.03, "trailing_stop_ratio": 0.01, "momentum_window": 14, "volatility_threshold": 0.025}}

Do not include any other text, explanations, or markdown formatting.
"""
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.generate(prompt, max_tokens=300, temperature=0.35)
                # Ищем JSON с максимальной жадностью
                json_candidate = self._extract_json(response)
                if not json_candidate:
                    raise ValueError("No JSON found in LLM response")

                raw_params = json.loads(json_candidate)
                new_params = {}
                for key in self.STRATEGY_KEYS:
                    if key in raw_params and isinstance(raw_params[key], (int, float)):
                        if key == "momentum_window":
                            new_params[key] = max(2, min(100, int(raw_params[key])))
                        else:
                            new_params[key] = round(max(0.001, min(1.0, float(raw_params[key]))), 4)
                    else:
                        new_params[key] = params.get(key, 0.1)

                if new_params == params:
                    logger.info("LLM suggested no real change, keeping current params")
                else:
                    logger.info(f"LLM mutation successful: {params} → {new_params}")
                self._record(params, new_params, full_context)
                return new_params

            except Exception as e:
                logger.warning(f"LLM mutation attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.3 * (attempt + 1))

        # Fallback: случайные мутации, чтобы не стоять на месте
        logger.warning("All LLM attempts failed, applying random mutation")
        new_params = {}
        for key in self.STRATEGY_KEYS:
            if key == "momentum_window":
                new_params[key] = random.randint(2, 50)
            else:
                new_params[key] = round(random.uniform(0.001, 0.3), 4)
        self._record(params, new_params, full_context)
        return new_params

    def _extract_json(self, text: str) -> Optional[str]:
        import re
        # 1. Ищем ```json ... ```
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # 2. Ищем просто ``` ... ```
        match = re.search(r'```\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        # 3. Удаляем все XML-теги
        cleaned = re.sub(r'<[^>]+>', '', text)

        # 4. Перебираем все подстроки, начинающиеся с { и заканчивающиеся }
        candidates = re.finditer(r'\{.*?\}', cleaned, re.DOTALL)
        for m in candidates:
            candidate = m.group(0)
            try:
                json.loads(candidate)
                return candidate
            except:
                continue
        return None

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

        if self.event_store:
            try:
                from src.core.events import Event
                self.event_store.append(Event.create(
                    node_id=self.node_id,
                    event_type="llm_mutation",
                    payload={
                        "old_params": old_params,
                        "new_params": new_params,
                        "context": context
                    },
                    parent_id=None
                ))
            except Exception as e:
                logger.error(f"Failed to write mutation to event_store: {e}")

    def get_stats(self) -> Dict:
        return {
            "total_mutations": self.total_mutations,
            "last_mutation": self.history[-1].__dict__ if self.history else None,
        }