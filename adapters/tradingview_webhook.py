# adapters/tradingview_webhook.py
"""
Приём сигналов от TradingView через webhook и сохранение последнего сигнала.
"""
import logging
from aiohttp import web

logger = logging.getLogger(__name__)

class TradingViewWebhook:
    def __init__(self, port: int = 8888):
        self.port = port
        self.latest_signal = None
        self.app = web.Application()
        self.app.router.add_post('/tradingview', self.handle_signal)
        self._runner = None

    async def handle_signal(self, request):
        try:
            data = await request.json()
            self.latest_signal = data
            logger.info(f"Received TradingView signal: {data}")
            return web.json_response({"status": "ok"})
        except Exception as e:
            logger.error(f"Failed to parse TradingView signal: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=400)

    async def start(self):
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"TradingView webhook listening on port {self.port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()