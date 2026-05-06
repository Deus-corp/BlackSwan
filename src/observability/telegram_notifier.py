# src/observability/telegram_notifier.py
"""
Асинхронный уведомитель о событиях роя через Telegram Bot API.
"""
import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        if self.enabled:
            logger.info("Telegram notifier enabled")
        else:
            logger.warning("Telegram notifier disabled (missing token or chat_id)")

    async def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(10)) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        logger.error(f"Telegram send failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False