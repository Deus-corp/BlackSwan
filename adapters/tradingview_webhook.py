"""
Receives signals from TradingView via webhook and saves the latest signal.
"""
import logging
from aiohttp import web
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

class TradingViewWebhook:
    """
    A class to create a webhook server that receives signals from TradingView.
    Saves the latest received signal and provides methods to start and stop the server.
    """
    def __init__(self, port: int = 8888) -> None:
        """
        Initializes TradingViewWebhook with the given port.

        :param port: The port on which the webhook server will listen.
        """
        self.port: int = port
        self.latest_signal: Optional[Dict[str, Any]] = None
        self.app: web.Application = web.Application()
        self.app.router.add_post('/tradingview', self.handle_signal)
        self._runner: Optional[web.AppRunner] = None

    async def handle_signal(self, request: web.Request) -> web.Response:
        """
        Handles incoming POST requests from TradingView on the '/tradingview' route.
        Parses the request body as JSON, saves it as `latest_signal`
        and returns a JSON response with the operation status.

        :param request: The aiohttp.web.Request object.
        :return: The aiohttp.web.Response JSON response with status "ok" or "error".
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
        Starts the webhook server on '0.0.0.0' and the specified port.
        """
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"TradingView webhook listening on port {self.port}")

    async def stop(self) -> None:
        """
        Stops the webhook server if it was started.
        """
        if self._runner:
            await self._runner.cleanup()
            logger.info(f"TradingView webhook on port {self.port} stopped.")