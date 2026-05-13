"""
MutationEngine — LLM-мутации, хранение истории и метрик.
Исправлено: теперь параметры из ответа LLM применяются напрямую,
без принудительной замены на дефолтные значения.
"""
import json
import re
import time
from typing import Dict, List, Optional
from loguru import logger
from src.core.events import Event


class MutationRecord:
    def __init__(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
        self.timestamp = time.time()
        self.old_params = old_params.copy()
        self.new_params = new_params.copy()
        self.context = context


class MutationEngine:
    # ожидаемые ключи стратегии (без жёстких привязок)
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
        self.event_store = event_store   # опционально для хранения мутаций в событийной БД

    def mutate(self, params: Dict[str, float], context: str, external_context: str = "") -> Dict[str, float]:
        """
        Выполняет LLM-мутацию параметров и возвращает **реально изменённые** значения.
        Если LLM возвращает кривой JSON, используется старый параметр.
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
                # Извлекаем JSON из ответа (может быть обёрнут в markdown)
                json_candidate = self._extract_json(response)
                if not json_candidate:
                    raise ValueError("No JSON found in LLM response")

                # Парсим без строгой схемы, затем нормализуем
                raw_params = json.loads(json_candidate)

                # Собираем новые параметры: берём значения из ответа, недостающие – старые
                new_params = {}
                for key in self.STRATEGY_KEYS:
                    if key in raw_params and isinstance(raw_params[key], (int, float)):
                        # лёгкая валидация диапазона (0.001 – 1.0 для ratios, 2 – 100 для window)
                        if key == "momentum_window":
                            new_params[key] = max(2, min(100, int(raw_params[key])))
                        else:
                            new_params[key] = round(max(0.001, min(1.0, float(raw_params[key]))), 4)
                    else:
                        # если ключ отсутствует или неправильный – сохраняем старый
                        new_params[key] = params.get(key, 0.1)

                # Если всё идентично старому (LLM предложила запрещённые линии), логируем и возвращаем старое
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

        # Если все попытки провалились, оставляем старые параметры
        logger.error("All LLM mutation attempts failed, returning original parameters")
        return params

    def _extract_json(self, text: str) -> Optional[str]:
        """
        Ищет JSON-объект в тексте, обёрнутый в ```json ... ``` или просто { ... }.
        """
        # Попытка найти ```json ... ```
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        # Попытка найти просто { ... }
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _record(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
        record = MutationRecord(old_params, new_params, context)
        self.history.append(record)
        self.total_mutations += 1

        # Сохраняем в nonce БД, если доступен nonce_manager
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

        # Дополнительно пишем в event_store, чтобы дашборд видел мутации даже без nonce
        if self.event_store:
            try:
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