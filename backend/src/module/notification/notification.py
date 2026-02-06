import logging

from sqlalchemy.ext.asyncio import AsyncSession

from module.conf import settings
from module.models import Notification
from module.repositories.bangumi import BangumiRepository

from .plugin import (
    BarkNotification,
    ServerChanNotification,
    TelegramNotification,
    WecomNotification,
)

logger = logging.getLogger(__name__)


def getClient(type: str):
    if type.lower() == "telegram":
        return TelegramNotification
    elif type.lower() == "server-chan":
        return ServerChanNotification
    elif type.lower() == "bark":
        return BarkNotification
    elif type.lower() == "wecom":
        return WecomNotification
    else:
        return None


class PostNotification:
    def __init__(self):
        Notifier = getClient(settings.notification.type)
        self.notifier = Notifier(
            token=settings.notification.token, chat_id=settings.notification.chat_id
        )

    @staticmethod
    async def _get_poster(session: AsyncSession, notify: Notification):
        bangumi_repo = BangumiRepository(session)
        poster_path = await bangumi_repo.match_poster(notify.official_title)
        notify.poster_path = poster_path

    async def send_msg(self, session: AsyncSession, notify: Notification) -> bool:
        await self._get_poster(session, notify)
        try:
            self.notifier.post_msg(notify)
            logger.debug(f"Send notification: {notify.official_title}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
            return False

    def __enter__(self):
        self.notifier.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.notifier.__exit__(exc_type, exc_val, exc_tb)
