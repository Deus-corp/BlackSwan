"""
Receives signals from TradingView via webhook and stores the latest signal.
"""
import logging
from typing import Any, Optional, Dict, Final

from aiohttp import web
from aiohttp.web import Request, Response, Application, AppRunner, TCPSite

logger: logging.Logger = logging.getLogger(__name__)


class TradingViewWebhook:
    """
    A server that receives signals from TradingView via POST requests.

    Maintains state of the most recent signal received and provides a lifecycle
    interface for the underlying aiohttp application.
    """

    def __init__(self, port: int = 8888, host: str = "0.0.0.0") -> None:
        """
        Initializes the TradingViewWebhook server instance.

        :param port: The network port to bind to.
        :param host: The host interface to bind to.
        """
        self.port: int = port
        self.host: str = host
        self.latest_signal: Optional[Dict[str, Any]] = None

        self.app: Application = Application()
        self.app.router.add_post("/tradingview", self.handle_signal)
        self._runner: Optional[AppRunner] = None

    async def handle_signal(self, request: Request) -> Response:
        """
        Handles incoming POST requests containing JSON payloads from TradingView.

        :param request: The incoming aiohttp request.
        :return: A JSON response indicating success or failure.
        """
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Payload must be a JSON object")

            self.latest_signal = data
            logger.info("Successfully processed TradingView signal.")
            return web.json_response({"status": "ok"})

        except (ValueError, Exception) as e:
            logger.error("Failed to process TradingView signal: %s", e)
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=400
            )

    async def start(self) -> None:
        """
        Starts the webhook server, setting up the runner and TCP site.
        """
        if self._runner is not None:
            logger.warning("Webhook server is already running.")
            return

        self._runner = AppRunner(self.app)
        await self._runner.setup()
        site: TCPSite = TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info("TradingView webhook listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """
        Gracefully stops the webhook server and cleans up resources.
        """
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            logger.info("TradingView webhook on port %d stopped.", self.port)