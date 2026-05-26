"""Asynchronous Telegram Bot API notifier for system events."""

from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Any, Final, Optional

import aiohttp

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Async Telegram Bot API notifier with persistent session management."""

    TIMEOUT_SECONDS: Final[float] = 10.0
    MAX_MESSAGE_LENGTH: Final[int] = 4096
    DEFAULT_PARSE_MODE: Final[str] = "HTML"

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        *,
        parse_mode: str = DEFAULT_PARSE_MODE,
        disable_notification: bool = False,
        timeout_seconds: float = TIMEOUT_SECONDS,
    ) -> None:
        self._token = str(token or os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
        self._chat_id = str(chat_id or os.environ.get("TELEGRAM_CHAT_ID", "") or "").strip()
        self._parse_mode = str(parse_mode or self.DEFAULT_PARSE_MODE).strip()
        self._disable_notification = bool(disable_notification)
        self._timeout_seconds = max(1.0, float(timeout_seconds))
        self._session: aiohttp.ClientSession | None = None
        self._enabled = bool(self._token and self._chat_id)

        if not self._enabled:
            logger.info("TelegramNotifier disabled: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")
        else:
            logger.info("TelegramNotifier initialized.")

    async def __aenter__(self) -> TelegramNotifier:
        await self._get_session()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return an active persistent aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
            logger.debug("TelegramNotifier aiohttp session created.")
        return self._session

    async def close(self) -> None:
        """Close the internal HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            logger.debug("TelegramNotifier aiohttp session closed.")
        self._session = None

    async def send(self, text: str, *, parse_mode: Optional[str] = None) -> bool:
        """Send a message, splitting long content into Telegram-safe chunks."""
        if not self._enabled:
            return False

        message = str(text or "").strip()
        if not message:
            logger.debug("TelegramNotifier skipped empty message.")
            return False

        chunks = self._split_message(message)
        results: list[bool] = []

        for chunk in chunks:
            ok = await self._send_one(chunk, parse_mode=parse_mode)
            results.append(ok)
            if len(chunks) > 1:
                await asyncio.sleep(0.25)

        return all(results)

    async def send_plain(self, text: str) -> bool:
        """Send plaintext safely escaped as HTML."""
        return await self.send(html.escape(str(text or "")), parse_mode="HTML")

    async def _send_one(self, text: str, *, parse_mode: Optional[str] = None) -> bool:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": text,
            "disable_notification": self._disable_notification,
        }

        effective_parse_mode = parse_mode if parse_mode is not None else self._parse_mode
        if effective_parse_mode:
            payload["parse_mode"] = effective_parse_mode

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return True

                body = await response.text()
                logger.error("Telegram API error status=%s body=%s", response.status, body[:1000])
                return False

        except asyncio.CancelledError:
            raise
        except aiohttp.ClientError as exc:
            logger.error("Telegram network/client error: %s", exc)
            return False
        except Exception as exc:
            logger.exception("Unexpected error while sending Telegram message: %s", exc)
            return False

    @classmethod
    def _split_message(cls, text: str) -> list[str]:
        """Split message into chunks no longer than Telegram max message length."""
        if len(text) <= cls.MAX_MESSAGE_LENGTH:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            chunk = remaining[: cls.MAX_MESSAGE_LENGTH]
            split_at = max(chunk.rfind("\n"), chunk.rfind(" "))
            if split_at > cls.MAX_MESSAGE_LENGTH * 0.5:
                chunk = chunk[:split_at]

            chunks.append(chunk)
            remaining = remaining[len(chunk) :].lstrip()

        return chunks