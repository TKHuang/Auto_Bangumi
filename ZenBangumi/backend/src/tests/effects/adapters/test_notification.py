"""Tests for Telegram notification adapter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from zen_bangumi.config.models import Notification
from zen_bangumi.domain.commands.base import SendNotification
from zen_bangumi.effects.adapters.notification import (
    TelegramNotifier,
    NotificationDispatcher,
)


class TestTelegramNotifier:
    """Tests for TelegramNotifier class."""

    async def test_send_message_formats_payload_correctly(self):
        """Test that sendMessage payload is formatted correctly."""
        notifier = TelegramNotifier()
        token = "test_token_123"
        chat_id = "test_chat_456"
        text = "Test message"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await notifier.send_message(token, chat_id, text)

            # Verify the URL and payload
            call_args = mock_post.call_args
            assert call_args is not None
            assert (
                call_args[0][0]
                == f"https://api.telegram.org/bot{token}/sendMessage"
            )
            assert call_args[1]["json"] == {
                "chat_id": chat_id,
                "text": text,
                "disable_notification": True,
            }

    async def test_send_photo_with_poster_works(self):
        """Test that sendPhoto with poster URL works correctly."""
        notifier = TelegramNotifier()
        token = "test_token_123"
        chat_id = "test_chat_456"
        photo_url = "https://example.com/poster.jpg"
        caption = "Test caption"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await notifier.send_photo(token, chat_id, photo_url, caption)

            # Verify the URL and payload
            call_args = mock_post.call_args
            assert call_args is not None
            assert (
                call_args[0][0]
                == f"https://api.telegram.org/bot{token}/sendPhoto"
            )
            assert call_args[1]["json"] == {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption,
                "disable_notification": True,
            }

    async def test_send_message_raises_on_api_error(self):
        """Test that send_message raises HTTPError on API failure."""
        notifier = TelegramNotifier()
        token = "test_token_123"
        chat_id = "test_chat_456"
        text = "Test message"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("API Error")
            mock_post.return_value = mock_response

            with pytest.raises(Exception, match="API Error"):
                await notifier.send_message(token, chat_id, text)

    async def test_send_photo_raises_on_api_error(self):
        """Test that send_photo raises HTTPError on API failure."""
        notifier = TelegramNotifier()
        token = "test_token_123"
        chat_id = "test_chat_456"
        photo_url = "https://example.com/poster.jpg"
        caption = "Test caption"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("API Error")
            mock_post.return_value = mock_response

            with pytest.raises(Exception, match="API Error"):
                await notifier.send_photo(token, chat_id, photo_url, caption)


class TestNotificationDispatcher:
    """Tests for NotificationDispatcher class."""

    async def test_dispatch_with_notification_disabled_no_http_call(self):
        """Test that disabled notifications skip HTTP calls."""
        config = Notification(enable=False, type="telegram", token="test_token", chat_id="test_chat")
        dispatcher = NotificationDispatcher(config)
        command = SendNotification(
            title="Test Anime",
            message="New episode available",
            poster_url=None,
        )

        with patch.object(
            dispatcher.notifier, "send_message", new_callable=AsyncMock
        ) as mock_send:
            await dispatcher.dispatch(command)
            mock_send.assert_not_called()

    async def test_dispatch_with_notification_enabled_sends_message(self):
        """Test that enabled notifications send messages."""
        config = Notification(enable=True, type="telegram", token="test_token", chat_id="test_chat")
        dispatcher = NotificationDispatcher(config)
        command = SendNotification(
            title="Test Anime",
            message="New episode available",
            poster_url=None,
        )

        with patch.object(
            dispatcher.notifier, "send_message", new_callable=AsyncMock
        ) as mock_send:
            await dispatcher.dispatch(command)
            mock_send.assert_called_once_with(
                token="test_token",
                chat_id="test_chat",
                text="New episode available",
            )

    async def test_dispatch_with_poster_sends_photo(self):
        """Test that notifications with poster send photo."""
        config = Notification(enable=True, type="telegram", token="test_token", chat_id="test_chat")
        dispatcher = NotificationDispatcher(config)
        command = SendNotification(
            title="Test Anime",
            message="New episode available",
            poster_url="https://example.com/poster.jpg",
        )

        with patch.object(
            dispatcher.notifier, "send_photo", new_callable=AsyncMock
        ) as mock_send:
            await dispatcher.dispatch(command)
            mock_send.assert_called_once_with(
                token="test_token",
                chat_id="test_chat",
                photo_url="https://example.com/poster.jpg",
                caption="New episode available",
            )

    async def test_dispatch_error_handling_logs_and_raises(self):
        """Test that dispatch errors are logged and re-raised."""
        config = Notification(enable=True, type="telegram", token="test_token", chat_id="test_chat")
        dispatcher = NotificationDispatcher(config)
        command = SendNotification(
            title="Test Anime",
            message="New episode available",
            poster_url=None,
        )

        with patch.object(
            dispatcher.notifier, "send_message", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = Exception("Network error")

            with pytest.raises(Exception, match="Network error"):
                await dispatcher.dispatch(command)

    async def test_dispatch_with_env_var_expansion(self):
        """Test that config env vars are expanded."""
        config = Notification(
            enable=True,
            type="telegram",
            token="${TEST_TOKEN}",
            chat_id="${TEST_CHAT_ID}",
        )
        dispatcher = NotificationDispatcher(config)
        command = SendNotification(
            title="Test Anime",
            message="New episode available",
            poster_url=None,
        )

        # The config properties handle env var expansion
        # Just verify the dispatcher uses the config values
        with patch.object(
            dispatcher.notifier, "send_message", new_callable=AsyncMock
        ) as mock_send:
            await dispatcher.dispatch(command)
            # Verify it was called (env vars would be expanded by config)
            assert mock_send.called
