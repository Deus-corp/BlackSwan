"""
Приём сигналов от TradingView через webhook и сохранение последнего сигнала.
"""
import logging
from aiohttp import web
from typing import Any, Optional, Dict 

logger = logging.getLogger(__name__)

class TradingViewWebhook:
    """
    Класс для создания webhook-сервера, который принимает сигналы от TradingView.
    Сохраняет последний полученный сигнал и предоставляет методы для запуска и остановки сервера.
    """
    def __init__(self, port: int = 8888):
        """
        Инициализирует TradingViewWebhook с заданным портом.

        :param port: Порт, на котором будет слушать webhook-сервер.
        """
        self.port: int = port
        self.latest_signal: Optional[Dict[str, Any]] = None 
        self.app = web.Application()
        self.app.router.add_post('/tradingview', self.handle_signal)
        self._runner: Optional[web.AppRunner] = None 

    async def handle_signal(self, request: web.Request) -> web.Response:
        """
        Обрабатывает входящие POST-запросы от TradingView на маршруте '/tradingview'.
        Парсит тело запроса как JSON, сохраняет его как `latest_signal`
        и возвращает JSON-ответ со статусом операции.

        :param request: Объект запроса aiohttp.web.Request.
        :return: JSON-ответ aiohttp.web.Response со статусом "ok" или "error".
        """
        try:
            data: Dict[str, Any] = await request.json()
            self.latest_signal = data
            logger.info(f"Received TradingView signal: {data}")
            return web.json_response({"status": "ok"})
        except Exception as e:
            logger.error(f"Failed to parse TradingView signal: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=400)

    async def start(self) -> None:
        """
        Запускает webhook-сервер на '0.0.0.0' и указанном порту.
        """
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"TradingView webhook listening on port {self.port}")

    async def stop(self) -> None:
        """
        Останавливает webhook-сервер, если он был запущен.
        """
        if self._runner:
            await self._runner.cleanup()
            logger.info(f"TradingView webhook on port {self.port} stopped.")