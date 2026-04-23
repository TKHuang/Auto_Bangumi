from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import module.services.downloader.factory as factory


def _pikpak_config():
    return SimpleNamespace(
        downloader=SimpleNamespace(
            type="pikpak",
            username="demo@example.com",
            password="secret",
        )
    )


class TestCreateDownloader:
    def test_pikpak_returns_fresh_instance_per_call(self, monkeypatch):
        if hasattr(factory, "_pikpak_instance"):
            monkeypatch.setattr(factory, "_pikpak_instance", None)

        config = _pikpak_config()
        session_a = object()
        session_b = object()
        downloader_a = MagicMock(name="downloader_a")
        downloader_b = MagicMock(name="downloader_b")

        with patch("module.services.downloader.pikpak.PikPakDownloader") as mock_cls:
            mock_cls.side_effect = [downloader_a, downloader_b]

            result_a = factory.create_downloader(config, session=session_a)
            result_b = factory.create_downloader(config, session=session_b)

        assert result_a is downloader_a
        assert result_b is downloader_b
        assert result_a is not result_b
        assert mock_cls.call_count == 2
        mock_cls.assert_any_call(
            username="demo@example.com",
            password="secret",
            session=session_a,
        )
        mock_cls.assert_any_call(
            username="demo@example.com",
            password="secret",
            session=session_b,
        )
