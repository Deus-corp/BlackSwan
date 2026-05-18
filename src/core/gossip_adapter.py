"""
Адаптер промышленного gossip-слоя (HMAC, backoff, replay protection).
Заменяет старую gossip_loop и peer_score без правки node_agent.py.
"""
import asyncio
import os
import time
import uuid
import traceback # Added for error logging in _handle_metrics
from typing import Dict, Optional, Any, List # Added List
import aiohttp
from aiohttp import web

import logging
logger = logging.getLogger(__name__)

from src.core.gossip_layer import (
    GossipConfig,
    GossipNode,
    DeltaPolicy,
    GossipEnvelope,
)
from src.core.crdt_adapter import CRDTAdapter  # наш новый CRDT

# Конфигурация из окружения
CFG = GossipConfig(
    node_id=os.environ.get("NODE_ID", str(uuid.uuid4())),
    port=int(os.environ.get("PORT", "8000")),
    peers_csv=os.environ.get("PEERS", ""),
    shared_secret=os.environ.get("GOSSIP_SECRET", "blackswan-dev-secret"),
    gossip_interval_s=float(os.environ.get("GOSSIP_INTERVAL", "1.5")),
)

class SafeGossipAdapter:
    """
    Заменяет:
      - pubsub + r.publish(...) для геномов
      - старую gossip_loop + peer_score
    на защищённый GossipNode.
    """

    node: GossipNode
    _known_versions: Dict[str, Dict[str, int]]
    _running: bool
    reputation_manager: Optional[Any] # Type can be more specific if ReputationManager class is available

    def __init__(self, crdt_adapter: CRDTAdapter):
        self.crdt_adapter = crdt_adapter
        self.node = GossipNode(CFG, policy=DeltaPolicy(min_fitness=0.0))
        self._known_versions: Dict[str, Dict[str, int]] = {}
        self._running = False
        self.reputation_manager = None
        
    def set_reputation_manager(self, rep_man: Any) -> None: # Added type hint for rep_man and return
        """
        Устанавливает менеджер репутации для адаптера.
        :param rep_man: Объект менеджера репутации (тип Any, если конкретный класс недоступен).
        """
        self.reputation_manager = rep_man

    # ----- Методы, которые дёргает node_agent.py -----

    def set_champion(self, genome: Dict[str, Any]) -> None:
        """
        Сохраняет чемпиона в CRDT и публикует через gossip.
        Вызывается из node_agent.py при появлении нового чемпиона.
        """
        # Сохраняем геном локально (асинхронно, но node_agent.py не ждёт)
        asyncio.create_task(self.crdt_adapter.add_genome(genome))
        # Публикация произойдёт автоматически на следующем цикле gossip
        # благодаря тому, что новый геном уже в CRDT.

    def pull_genomes(self) -> List[Dict[str, Any]]: # More specific return type hint
        """
        Возвращает список геномов, полученных от пиров.
        Вызывается из node_agent.py в главном цикле.
        """
        # Получаем свежие геномы из CRDT (все, кроме тех, что уже есть?)
        # Для простоты: возвращаем пустой список, т.к. integrate будет 
        # забирать геномы напрямую из crdt_adapter.get_top().
        return []

    async def gossip_round(self) -> None: # Added return type hint
        """
        Один раунд gossip: выбирает пира и обменивается геномами.
        Вызывается периодически (раз в 50 шагов) из node_agent.py.
        """
        if not CFG.peers:
            return
        # Создаём сессию и делаем sync_once с одним пиром
        async with aiohttp.ClientSession() as session:
            # Выбираем первого пира (или случайного)
            peer: str = CFG.peers[0]  # можно улучшить до случайного
            try:
                # Формируем конверт с нашей дельтой
                our_versions: Dict[str, int] = await self.crdt_adapter.get_versions()
                our_delta: Dict[str, Any] = await self.crdt_adapter.get_delta(
                    self._known_versions.get(peer, {})
                )
                envelope: GossipEnvelope = GossipEnvelope(
                    sender=CFG.node_id,
                    ts=time.time(),
                    nonce=uuid.uuid4().hex,
                    versions=our_versions,
                    delta=our_delta,
                )
                envelope.sign(CFG.secret_bytes)

                async with session.post(
                    f"http://{peer}/gossip",
                    json=envelope.to_dict(),
                    timeout=CFG.request_timeout_s
                ) as resp:
                    if resp.status == 200:
                        data: Dict[str, Any] = await resp.json()
                        remote_delta: Dict[str, Any] = data.get("delta", {})
                        if remote_delta:
                            await self.crdt_adapter.merge(remote_delta)
                        # Обновляем известные версии пира
                        self._known_versions[peer] = data.get("versions", {})
            except Exception as e: # Catch specific exception if possible, or log more details
                logger.warning(f"Gossip round with peer {peer} failed: {e}") # Log the specific error
                pass  # пир недоступен – идём дальше

    # ----- Health endpoint -----
    async def _handle_health(self, request: web.Request) -> web.Response: # Added type hints
        """
        Обработчик HTTP-запроса для проверки состояния здоровья ноды.
        Возвращает JSON-ответ со статусом "ok".
        """
        return web.json_response({"status": "ok"})

    async def start(self) -> None: # Added return type hint
        """Запускает HTTP-сервер и gossip-цикл (заменяет run_server + gossip_loop)."""
        app: web.Application = self.node.build_app()
        # Добавляем маршрут для проверки работоспособности
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_metrics)
        runner: web.AppRunner = web.AppRunner(app)
        await runner.setup()
        site: web.TCPSite = web.TCPSite(runner, CFG.bind_host, CFG.port)
        await site.start()
        self._running = True

        # Запускаем фоновый gossip-цикл
        asyncio.create_task(self._gossip_loop())

    async def _gossip_loop(self) -> None: # Added return type hint
        """
        Фоновый цикл для периодического выполнения gossip-раундов.
        Продолжает работу, пока адаптер запущен (`_running` is True).
        """
        while self._running:
            await self.gossip_round()
            await asyncio.sleep(CFG.gossip_interval_s)

    async def stop(self) -> None: # Added return type hint
        """
        Останавливает фоновый gossip-цикл, устанавливая флаг `_running` в False.
        """
        self._running = False
        # handle_metrics
    async def _handle_metrics(self, request: web.Request) -> web.Response: # Added type hints
        """
        Обработчик HTTP-запроса для выдачи метрик в формате Prometheus.
        """
        try:
            from src.observability.metrics import collect_metrics, prometheus_format
            metrics = collect_metrics()
            body: str = prometheus_format(metrics)
            return web.Response(text=body, content_type="text/plain", charset="utf-8")
        except Exception as e:
            # import traceback # Already imported at the top
            logger.error(f"Metrics endpoint failed: {traceback.format_exc()}")
            return web.Response(text=f"Error: {e}", status=500, content_type="text/plain")