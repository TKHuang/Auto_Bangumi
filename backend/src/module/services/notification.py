"""Notification service with support for multiple providers.

Providers: Telegram, ServerChan, Bark, WeCom
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class NotificationProvider:
    """Base class for notification providers."""

    token: str
    chat_id: str | None

    def __init__(self, token: str, chat_id: str | None = None) -> None:
        self.token = token
        self.chat_id = chat_id

    def send(self, title: str, message: str) -> bool:
        """Send notification. Returns True if successful."""
        raise NotImplementedError


class TelegramNotification(NotificationProvider):
    """Telegram notification provider."""

    photo_url: str
    message_url: str

    def __init__(self, token: str, chat_id: str | None = None) -> None:
        super().__init__(token, chat_id)
        self.photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        self.message_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def send(self, title: str, message: str) -> bool:
        """Send message to Telegram."""
        import requests

        text = f"{title}\n{message}"
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_notification": True,
        }
        try:
            resp = requests.post(self.message_url, data=data, timeout=5)
            logger.debug(f"Telegram notification: {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send Telegram notification: {e}")
            return False


class ServerChanNotification(NotificationProvider):
    """ServerChan (Server酱) notification provider."""

    notification_url: str

    def __init__(self, token: str, chat_id: str | None = None) -> None:
        super().__init__(token, chat_id)
        self.notification_url = f"https://sctapi.ftqq.com/{token}.send"

    def send(self, title: str, message: str) -> bool:
        """Send message to ServerChan."""
        import requests

        data = {
            "title": title,
            "desp": message,
        }
        try:
            resp = requests.post(self.notification_url, data=data, timeout=5)
            logger.debug(f"ServerChan notification: {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send ServerChan notification: {e}")
            return False


class BarkNotification(NotificationProvider):
    """Bark notification provider."""

    notification_url: str

    def __init__(self, token: str, chat_id: str | None = None) -> None:
        super().__init__(token, chat_id)
        self.notification_url = "https://api.day.app/push"

    def send(self, title: str, message: str) -> bool:
        """Send message to Bark."""
        import requests

        data = {
            "title": title,
            "body": message,
            "device_key": self.token,
        }
        try:
            resp = requests.post(self.notification_url, data=data, timeout=5)
            logger.debug(f"Bark notification: {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send Bark notification: {e}")
            return False


class WecomNotification(NotificationProvider):
    """WeCom (企业微信) notification provider."""

    notification_url: str

    def __init__(self, token: str, chat_id: str | None = None) -> None:
        super().__init__(token, chat_id)
        # chat_id is used as the webhook URL for WeCom
        self.notification_url = chat_id or ""

    def send(self, title: str, message: str) -> bool:
        """Send message to WeCom."""
        import requests

        # Format title with prefix
        formatted_title = "【番剧更新】" + title
        msg = f"{title}\n{message}"

        data = {
            "key": self.token,
            "type": "news",
            "title": formatted_title,
            "msg": msg,
        }
        try:
            resp = requests.post(self.notification_url, data=data, timeout=5)
            logger.debug(f"WeCom notification: {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send WeCom notification: {e}")
            return False


def get_provider(provider_type: str, token: str, chat_id: str | None = None) -> NotificationProvider | None:
    """Get notification provider by type."""
    provider_type = provider_type.lower()
    if provider_type == "telegram":
        return TelegramNotification(token, chat_id)
    elif provider_type == "server-chan":
        return ServerChanNotification(token, chat_id)
    elif provider_type == "bark":
        return BarkNotification(token, chat_id)
    elif provider_type == "wecom":
        return WecomNotification(token, chat_id)
    else:
        logger.warning(f"Unknown notification provider: {provider_type}")
        return None


async def send_notification(title: str, message: str, config: "Config") -> bool:
    """Send notification using configured provider.

    Args:
        title: Notification title
        message: Notification message
        config: Configuration object with notification settings

    Returns:
        True if notification sent successfully, False otherwise
    """
    if not config.notification.enable:
        logger.debug("Notifications disabled")
        return False

    provider = get_provider(
        config.notification.type,
        config.notification.token,
        config.notification.chat_id,
    )

    if not provider:
        logger.warning(f"Failed to create notification provider: {config.notification.type}")
        return False

    return provider.send(title, message)
