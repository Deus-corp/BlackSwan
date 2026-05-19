# src/observability/telegram_notifier.py
"""
Асинхронный уведомитель о событиях роя через Telegram Bot API.

Этот модуль предоставляет класс `TelegramNotifier` для отправки
уведомлений в Telegram асинхронно.
"""
import os
import logging
from typing import Optional, Any, Dict

import aiohttp

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Класс для отправки асинхронных уведомлений в Telegram.

    Использует `aiohttp` для взаимодействия с Telegram Bot API.
    Настройки токена бота и ID чата могут быть заданы при инициализации
    или получены из переменных окружения (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).

    Args:
        token (Optional[str]): Токен Telegram бота. Если не указан,
                                   используется переменная окружения TELEGRAM_BOT_TOKEN.
        chat_id (Optional[str]): ID чата или канала Telegram. Если не указан,
                                     используется переменная окружения TELEGRAM_CHAT_ID.
    """
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        """
        Инициализирует уведомитель Telegram.
        """
        self.token: str = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id: str = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled: bool = bool(self.token and self.chat_id)
        
        # Aiohttp ClientSession should be reused for performance.
        # It's better to manage its lifecycle explicitly.
        self._session: Optional[aiohttp.ClientSession] = None

        if self.enabled:
            logger.info("Telegram notifier enabled and ready.")
        else:
            logger.warning("Telegram notifier disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables).")

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Возвращает или создает `aiohttp.ClientSession`.

        Returns:
            aiohttp.ClientSession: Активная HTTP-сессия.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """
        Закрывает `aiohttp.ClientSession`, если она была открыта.
        Рекомендуется вызывать при завершении работы приложения для корректного
        освобождения ресурсов.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Telegram notifier aiohttp session closed.")
        self._session = None # Clear the session reference

    async def send(self, text: str) -> bool:
        """
        Отправляет текстовое сообщение в Telegram.

        Сообщение будет отправлено только если уведомитель включен (self.enabled).
        Использует 'HTML' режим парсинга для форматирования текста.

        Args:
            text (str): Текст сообщения для отправки.

        Returns:
            bool: True, если сообщение было успешно отправлено (HTTP 200),
                  иначе False.
        """
        if not self.enabled:
            logger.debug("Telegram notifier is disabled, skipping message send.")
            return False

        url: str = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    logger.debug("Telegram message sent successfully.")
                    return True
                else:
                    response_text = await resp.text()
                    logger.error(f"Telegram send failed with status {resp.status}. Response: {response_text}")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"Telegram send client error: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected exceptions
            logger.error(f"Telegram send unexpected error: {e}", exc_info=True)
            return False
