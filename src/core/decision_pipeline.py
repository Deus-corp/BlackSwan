from typing import Dict, Any
from .global_state import GlobalState
from .event_bus import EventBus

class DecisionPipeline:
    """
    Заглушка универсального конвейера принятия решений.
    В MVP реализует только этапы Proposal → Validation (заглушка) → Execution (заглушка).
    """

    def __init__(self, state: GlobalState, event_bus: EventBus):
        self.state: GlobalState = state
        self.event_bus: EventBus = event_bus

    async def process(self, proposal: Dict[str, Any]) -> bool:
        """
        Обрабатывает предложенный объект через пайплайн принятия решений.
        Включает этапы оценки и выполнения.
        Возвращает True, если предложение было успешно обработано и выполнено, иначе False.
        """
        # 1. Proposal уже передан
        # 2. Evaluation
        if not self._evaluate(proposal):
            await self.event_bus.publish("execution", {"proposal": proposal, "status": "rejected"}, "decision_pipeline")
            return False
        # 3. Execution (заглушка)
        self.state.update("execution_state", {"last_proposal": proposal["id"]})
        await self.event_bus.publish("execution", {"proposal": proposal, "status": "executed"}, "decision_pipeline")
        return True

    def _evaluate(self, proposal: Dict[str, Any]) -> bool:
        """
        Оценивает предложение на основе заданных правил.
        В данной заглушке, предложения, помеченные как "dangerous", отклоняются.
        """
        # Простая проверка: все предложения, кроме помеченных как опасные, принимаются
        if proposal.get("dangerous"):
            return False
        return True