"""Telegram notification adapter for ZenBangumi."""

import logging
from typing import Optional

import httpx

from zen_bangumi.config.models import Notification
from zen_bangumi.domain.commands.base import SendNotification

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends notifications via Telegram Bot API."""

    async def send_message(self, token: str, chat_id: str, text: str) -> None:
        """
        Send a text message to Telegram chat.

        Args:
            token: Telegram bot token
            chat_id: Target chat ID
            text: Message text

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_notification": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()

    async def send_photo(
        self, token: str, chat_id: str, photo_url: str, caption: str
    ) -> None:
        """
        Send a photo with caption to Telegram chat.

        Args:
            token: Telegram bot token
            chat_id: Target chat ID
            photo_url: URL of the photo to send
            caption: Photo caption

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "disable_notification": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()


class NotificationDispatcher:
    """Dispatches SendNotification commands to appropriate notifier."""

    def __init__(self, config: Notification):
        """
        Initialize dispatcher with notification config.

        Args:
            config: Notification configuration from ZenBangumiConfig
        """
        self.config = config
        self.notifier = TelegramNotifier()

    async def dispatch(self, command: SendNotification) -> None:
        """
        Dispatch a notification command.

        If notifications are disabled in config, returns immediately without
        making any HTTP calls.

        Args:
            command: SendNotification command to dispatch

        Raises:
            httpx.HTTPError: If API request fails (only if enabled)
        """
        if not self.config.enable:
            logger.debug("Notifications disabled, skipping dispatch")
            return

        try:
            if command.poster_url:
                await self.notifier.send_photo(
                    token=self.config.token,
                    chat_id=self.config.chat_id,
                    photo_url=command.poster_url,
                    caption=command.message,
                )
            else:
                await self.notifier.send_message(
                    token=self.config.token,
                    chat_id=self.config.chat_id,
                    text=command.message,
                )
            logger.debug(f"Notification sent: {command.title}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            raise
