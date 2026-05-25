"""
Asynchronous Telegram Bot API notifier for system events.

Provides a robust `TelegramNotifier` class for sending asynchronous notifications
with proper session management and error handling.
"""
import logging
import os
from typing import Optional, Any, Dict, Final

import aiohttp

logger: logging.Logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Handles asynchronous message dispatching to a configured Telegram chat.

    The notifier utilizes `aiohttp.ClientSession` for efficient connection pooling.
    Configuration is prioritized from constructor arguments, falling back to
    'TELEGRAM_BOT_TOKEN' and 'TELEGRAM_CHAT_ID' environment variables.
    """

    TIMEOUT_SECONDS: Final[int] = 10

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        self._token: str = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id: str = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._session: Optional[aiohttp.ClientSession] = None
        self._enabled: bool = bool(self._token and self._chat_id)

        if not self._enabled:
            logger.warning(
                "TelegramNotifier is disabled: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID."
            )
        else:
            logger.info("TelegramNotifier initialized successfully.")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Provides an active persistent aiohttp.ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close Telegram aiohttp session if it was opened."""
        session = getattr(self, "_session", None)
        if session is not None and not session.closed:
            await session.close()
            self._session = None

    async def send(self, text: str) -> bool:
        """
        Sends a text message using the Telegram Bot API.

        Args:
            text: The message content to send (HTML formatting supported).

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        if not self._enabled:
            return False

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=self.TIMEOUT_SECONDS)
            
            async with session.post(url, json=payload, timeout=timeout) as response:
                if response.status == 200:
                    return True
                
                body = await response.text()
                logger.error(
                    "Telegram API error (status %d): %s", response.status, body
                )
                return False
        except aiohttp.ClientError as exc:
            logger.error("Telegram network/client error: %s", exc)
            return False
        except Exception as exc:
            logger.exception("Unexpected error while sending Telegram message: %s", exc)
            return False