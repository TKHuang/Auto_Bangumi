"""Tests for notification service."""

import pytest
from unittest.mock import MagicMock, patch, Mock

from module.services.notification import (
    TelegramNotification,
    ServerChanNotification,
    BarkNotification,
    WecomNotification,
    get_provider,
    send_notification,
)


class TestTelegramNotification:
    """Tests for Telegram notification provider."""

    def test_init(self):
        """Test Telegram provider initialization."""
        provider = TelegramNotification(token="test_token", chat_id="123456")
        assert provider.token == "test_token"
        assert provider.chat_id == "123456"
        assert "test_token" in provider.photo_url
        assert "test_token" in provider.message_url

    def test_send_success(self):
        """Test successful message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            provider = TelegramNotification(token="test_token", chat_id="123456")
            result = provider.send("Test Title", "Test Message")

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["data"]["chat_id"] == "123456"
            assert "Test Title" in call_args[1]["data"]["text"]
            assert "Test Message" in call_args[1]["data"]["text"]

    def test_send_failure(self):
        """Test failed message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_post.return_value = mock_response

            provider = TelegramNotification(token="test_token", chat_id="123456")
            result = provider.send("Test Title", "Test Message")

            assert result is False

    def test_send_exception(self):
        """Test exception handling."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            provider = TelegramNotification(token="test_token", chat_id="123456")
            result = provider.send("Test Title", "Test Message")

            assert result is False


class TestServerChanNotification:
    """Tests for ServerChan notification provider."""

    def test_init(self):
        """Test ServerChan provider initialization."""
        provider = ServerChanNotification(token="test_token")
        assert provider.token == "test_token"
        assert "test_token" in provider.notification_url
        assert "sctapi.ftqq.com" in provider.notification_url

    def test_send_success(self):
        """Test successful message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            provider = ServerChanNotification(token="test_token")
            result = provider.send("Test Title", "Test Message")

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["data"]["title"] == "Test Title"
            assert call_args[1]["data"]["desp"] == "Test Message"

    def test_send_failure(self):
        """Test failed message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_post.return_value = mock_response

            provider = ServerChanNotification(token="test_token")
            result = provider.send("Test Title", "Test Message")

            assert result is False

    def test_send_exception(self):
        """Test exception handling."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            provider = ServerChanNotification(token="test_token")
            result = provider.send("Test Title", "Test Message")

            assert result is False


class TestBarkNotification:
    """Tests for Bark notification provider."""

    def test_init(self):
        """Test Bark provider initialization."""
        provider = BarkNotification(token="test_token")
        assert provider.token == "test_token"
        assert provider.notification_url == "https://api.day.app/push"

    def test_send_success(self):
        """Test successful message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            provider = BarkNotification(token="test_token")
            result = provider.send("Test Title", "Test Message")

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["data"]["title"] == "Test Title"
            assert call_args[1]["data"]["body"] == "Test Message"
            assert call_args[1]["data"]["device_key"] == "test_token"

    def test_send_failure(self):
        """Test failed message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_post.return_value = mock_response

            provider = BarkNotification(token="test_token")
            result = provider.send("Test Title", "Test Message")

            assert result is False

    def test_send_exception(self):
        """Test exception handling."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            provider = BarkNotification(token="test_token")
            result = provider.send("Test Title", "Test Message")

            assert result is False


class TestWecomNotification:
    """Tests for WeCom notification provider."""

    def test_init(self):
        """Test WeCom provider initialization."""
        provider = WecomNotification(token="test_token", chat_id="https://webhook.url")
        assert provider.token == "test_token"
        assert provider.notification_url == "https://webhook.url"

    def test_init_no_chat_id(self):
        """Test WeCom provider initialization without chat_id."""
        provider = WecomNotification(token="test_token")
        assert provider.token == "test_token"
        assert provider.notification_url == ""

    def test_send_success(self):
        """Test successful message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            provider = WecomNotification(token="test_token", chat_id="https://webhook.url")
            result = provider.send("Test Title", "Test Message")

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["data"]["key"] == "test_token"
            assert call_args[1]["data"]["type"] == "news"
            assert "【番剧更新】" in call_args[1]["data"]["title"]
            assert "Test Title" in call_args[1]["data"]["title"]

    def test_send_failure(self):
        """Test failed message send."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_post.return_value = mock_response

            provider = WecomNotification(token="test_token", chat_id="https://webhook.url")
            result = provider.send("Test Title", "Test Message")

            assert result is False

    def test_send_exception(self):
        """Test exception handling."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")

            provider = WecomNotification(token="test_token", chat_id="https://webhook.url")
            result = provider.send("Test Title", "Test Message")

            assert result is False


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_telegram_provider(self):
        """Test getting Telegram provider."""
        provider = get_provider("telegram", "token", "chat_id")
        assert isinstance(provider, TelegramNotification)

    def test_get_telegram_provider_case_insensitive(self):
        """Test case-insensitive provider lookup."""
        provider = get_provider("TELEGRAM", "token", "chat_id")
        assert isinstance(provider, TelegramNotification)

    def test_get_server_chan_provider(self):
        """Test getting ServerChan provider."""
        provider = get_provider("server-chan", "token")
        assert isinstance(provider, ServerChanNotification)

    def test_get_bark_provider(self):
        """Test getting Bark provider."""
        provider = get_provider("bark", "token")
        assert isinstance(provider, BarkNotification)

    def test_get_wecom_provider(self):
        """Test getting WeCom provider."""
        provider = get_provider("wecom", "token", "chat_id")
        assert isinstance(provider, WecomNotification)

    def test_get_unknown_provider(self):
        """Test getting unknown provider."""
        provider = get_provider("unknown", "token")
        assert provider is None


class TestSendNotification:
    """Tests for send_notification async function."""

    @pytest.mark.asyncio
    async def test_send_notification_disabled(self):
        """Test sending notification when disabled."""
        config = MagicMock()
        config.notification.enable = False

        result = await send_notification("Title", "Message", config)
        assert result is False

    @pytest.mark.asyncio
    @patch("module.services.notification.get_provider")
    async def test_send_notification_success(self, mock_get_provider):
        """Test successful notification send."""
        mock_provider = MagicMock()
        mock_provider.send.return_value = True
        mock_get_provider.return_value = mock_provider

        config = MagicMock()
        config.notification.enable = True
        config.notification.type = "telegram"
        config.notification.token = "token"
        config.notification.chat_id = "chat_id"

        result = await send_notification("Title", "Message", config)
        assert result is True
        mock_provider.send.assert_called_once_with("Title", "Message")

    @pytest.mark.asyncio
    @patch("module.services.notification.get_provider")
    async def test_send_notification_failure(self, mock_get_provider):
        """Test failed notification send."""
        mock_provider = MagicMock()
        mock_provider.send.return_value = False
        mock_get_provider.return_value = mock_provider

        config = MagicMock()
        config.notification.enable = True
        config.notification.type = "telegram"
        config.notification.token = "token"
        config.notification.chat_id = "chat_id"

        result = await send_notification("Title", "Message", config)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_unknown_provider(self):
        """Test sending notification with unknown provider."""
        config = MagicMock()
        config.notification.enable = True
        config.notification.type = "unknown"
        config.notification.token = "token"
        config.notification.chat_id = "chat_id"

        result = await send_notification("Title", "Message", config)
        assert result is False

    @pytest.mark.asyncio
    @patch("module.services.notification.get_provider")
    async def test_send_notification_with_all_providers(self, mock_get_provider):
        """Test sending notification with different providers."""
        for provider_type in ["telegram", "server-chan", "bark", "wecom"]:
            mock_provider = MagicMock()
            mock_provider.send.return_value = True
            mock_get_provider.return_value = mock_provider

            config = MagicMock()
            config.notification.enable = True
            config.notification.type = provider_type
            config.notification.token = "token"
            config.notification.chat_id = "chat_id"

            result = await send_notification("Title", "Message", config)
            assert result is True
