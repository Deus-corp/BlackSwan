"""TradingView webhook server for receiving and storing latest trading signals."""

from __future__ import annotations

import hmac
import logging
import os
import time
from typing import Any, Optional

from aiohttp import web
from aiohttp.web import AppRunner, Application, Request, Response, TCPSite

logger = logging.getLogger(__name__)


class TradingViewWebhook:
    """Small aiohttp server that receives TradingView JSON webhook signals."""

    DEFAULT_MAX_BODY_BYTES = 64 * 1024

    def __init__(
        self,
        port: int = 8888,
        host: str = "0.0.0.0",
        *,
        secret: str | None = None,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    ) -> None:
        self.port = int(port)
        self.host = str(host or "0.0.0.0").strip() or "0.0.0.0"
        self.secret = secret if secret is not None else os.environ.get("TRADINGVIEW_WEBHOOK_SECRET", "")
        self.max_body_bytes = max(1024, int(max_body_bytes))

        self.latest_signal: Optional[dict[str, Any]] = None
        self.signal_count = 0
        self.last_error: Optional[str] = None

        self.app: Application = Application(client_max_size=self.max_body_bytes)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_post("/tradingview", self.handle_signal)

        self._runner: Optional[AppRunner] = None
        self._site: Optional[TCPSite] = None

    async def handle_health(self, _request: Request) -> Response:
        """Return webhook health and last-signal metadata."""
        return web.json_response(
            {
                "status": "ok",
                "signal_count": self.signal_count,
                "has_latest_signal": self.latest_signal is not None,
                "last_error": self.last_error,
            }
        )

    async def handle_signal(self, request: Request) -> Response:
        """Handle incoming TradingView POST JSON payload."""
        try:
            if self.secret and not self._authorized(request):
                self.last_error = "unauthorized"
                logger.warning("Rejected TradingView signal: unauthorized.")
                return web.json_response({"status": "error", "message": "unauthorized"}, status=401)

            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("payload must be a JSON object")

            signal = self._normalize_signal(data)
            self.latest_signal = signal
            self.signal_count += 1
            self.last_error = None

            logger.info(
                "Processed TradingView signal action=%s symbol=%s count=%d",
                signal.get("action"),
                signal.get("symbol"),
                self.signal_count,
            )
            return web.json_response({"status": "ok", "signal_count": self.signal_count})

        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("Failed to process TradingView signal: %s", exc)
            return web.json_response({"status": "error", "message": str(exc)}, status=400)

    async def start(self) -> None:
        """Start webhook server."""
        if self._runner is not None:
            logger.warning("TradingView webhook server is already running.")
            return

        self._runner = AppRunner(self.app)
        await self._runner.setup()

        self._site = TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info("TradingView webhook listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop webhook server and cleanup aiohttp resources."""
        if self._site is not None:
            await self._site.stop()
            self._site = None

        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

        logger.info("TradingView webhook on %s:%d stopped.", self.host, self.port)

    def pop_latest_signal(self) -> Optional[dict[str, Any]]:
        """Return and clear latest signal."""
        signal = self.latest_signal
        self.latest_signal = None
        return signal

    def _authorized(self, request: Request) -> bool:
        expected = str(self.secret or "")
        if not expected:
            return True

        provided = (
            request.headers.get("X-TradingView-Secret")
            or request.headers.get("X-Webhook-Secret")
            or request.query.get("secret")
            or ""
        )
        return hmac.compare_digest(str(provided), expected)

    @staticmethod
    def _normalize_signal(data: dict[str, Any]) -> dict[str, Any]:
        signal = dict(data)
        signal.setdefault("received_at", time.time())

        if "action" in signal:
            signal["action"] = str(signal["action"]).strip().lower()
        elif "side" in signal:
            signal["action"] = str(signal["side"]).strip().lower()

        if "symbol" in signal:
            signal["symbol"] = str(signal["symbol"]).strip().upper()

        return signal