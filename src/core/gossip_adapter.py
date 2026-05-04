"""
Адаптер промышленного gossip-слоя (HMAC, backoff, replay protection).
Заменяет старую gossip_loop и peer_score без правки node_agent.py.
"""
import asyncio
import os
import time
import uuid
from typing import Dict, Optional, Any
import aiohttp
from aiohttp import web

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

    def __init__(self, crdt_adapter: CRDTAdapter):
        self.crdt_adapter = crdt_adapter
        self.node = GossipNode(CFG, policy=DeltaPolicy(min_fitness=0.0))
        self._known_versions: Dict[str, Dict[str, int]] = {}
        self._running = False
        self.reputation_manager = None
        
    def set_reputation_manager(self, rep_man):
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

    def pull_genomes(self) -> list:
        """
        Возвращает список геномов, полученных от пиров.
        Вызывается из node_agent.py в главном цикле.
        """
        # Получаем свежие геномы из CRDT (все, кроме тех, что уже есть?)
        # Для простоты: возвращаем пустой список, т.к. integrate будет 
        # забирать геномы напрямую из crdt_adapter.get_top().
        return []

    async def gossip_round(self) -> None:
        """
        Один раунд gossip: выбирает пира и обменивается геномами.
        Вызывается периодически (раз в 50 шагов) из node_agent.py.
        """
        if not CFG.peers:
            return
        # Создаём сессию и делаем sync_once с одним пиром
        async with aiohttp.ClientSession() as session:
            # Выбираем первого пира (или случайного)
            peer = CFG.peers[0]  # можно улучшить до случайного
            try:
                # Формируем конверт с нашей дельтой
                our_versions = await self.crdt_adapter.get_versions()
                our_delta = await self.crdt_adapter.get_delta(
                    self._known_versions.get(peer, {})
                )
                envelope = GossipEnvelope(
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
                        data = await resp.json()
                        remote_delta = data.get("delta", {})
                        if remote_delta:
                            await self.crdt_adapter.merge(remote_delta)
                        # Обновляем известные версии пира
                        self._known_versions[peer] = data.get("versions", {})
            except Exception:
                pass  # пир недоступен – идём дальше

    # ----- Health endpoint -----
    async def _handle_health(self, request):
        return web.json_response({"status": "ok"})

    async def start(self) -> None:
        """Запускает HTTP-сервер и gossip-цикл (заменяет run_server + gossip_loop)."""
        app = self.node.build_app()
        # Добавляем маршрут для проверки работоспособности
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/metrics", self._handle_metrics)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, CFG.bind_host, CFG.port)
        await site.start()
        self._running = True

        # Запускаем фоновый gossip-цикл
        asyncio.create_task(self._gossip_loop())

    async def _gossip_loop(self) -> None:
        while self._running:
            await self.gossip_round()
            await asyncio.sleep(CFG.gossip_interval_s)

    async def stop(self) -> None:
        self._running = False
        # handle_metrics
    async def _handle_metrics(self, request):
        from src.observability.metrics import collect_metrics, prometheus_format
        metrics = collect_metrics()
        body = prometheus_format(metrics)
        return web.Response(text=body, content_type="text/plain; charset=utf-8")