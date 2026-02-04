"""Tests for ZenBangumi config models and loader."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from zen_bangumi.config.loader import ConfigLoader
from zen_bangumi.config.models import (
    BangumiManage,
    Downloader,
    Log,
    Notification,
    Program,
    Proxy,
    RSSParser,
    ZenBangumiConfig,
)


class TestConfigModels:
    """Test individual config model creation and validation."""

    def test_program_defaults(self):
        """Test Program model with default values."""
        program = Program()
        assert program.rss_time == 900
        assert program.rename_time == 60
        assert program.webui_port == 7892

    def test_downloader_defaults(self):
        """Test Downloader model with default values."""
        downloader = Downloader()
        assert downloader.type == "qbittorrent"
        assert downloader.host_ == "172.17.0.1:8080"
        assert downloader.username_ == "admin"
        assert downloader.password_ == "adminadmin"
        assert downloader.path == "/downloads/Bangumi"
        assert downloader.ssl is False

    def test_downloader_expandvars(self):
        """Test Downloader expandvars for host, username, password."""
        os.environ["TEST_HOST"] = "localhost:8080"
        os.environ["TEST_USER"] = "testuser"
        os.environ["TEST_PASS"] = "testpass"

        downloader = Downloader(
            host="$TEST_HOST",
            username="$TEST_USER",
            password="$TEST_PASS",
        )

        assert downloader.host == "localhost:8080"
        assert downloader.username == "testuser"
        assert downloader.password == "testpass"

        del os.environ["TEST_HOST"]
        del os.environ["TEST_USER"]
        del os.environ["TEST_PASS"]

    def test_rss_parser_defaults(self):
        """Test RSSParser model with default values."""
        parser = RSSParser()
        assert parser.enable is True
        assert parser.filter == ["720", r"\d+-\d"]
        assert parser.language == "zh"

    def test_bangumi_manage_defaults(self):
        """Test BangumiManage model with default values."""
        manage = BangumiManage()
        assert manage.enable is True
        assert manage.eps_complete is False
        assert manage.rename_method == "pn"
        assert manage.group_tag is False
        assert manage.remove_bad_torrent is False

    def test_log_defaults(self):
        """Test Log model with default values."""
        log = Log()
        assert log.debug_enable is False

    def test_proxy_defaults(self):
        """Test Proxy model with default values."""
        proxy = Proxy()
        assert proxy.enable is False
        assert proxy.type == "http"
        assert proxy.host == ""
        assert proxy.port == 0

    def test_notification_defaults(self):
        """Test Notification model with default values."""
        notification = Notification()
        assert notification.enable is False
        assert notification.type == "telegram"
        assert notification.token_ == ""
        assert notification.chat_id_ == ""

    def test_notification_type_literal(self):
        """Test Notification type is limited to telegram."""
        with pytest.raises(ValueError):
            Notification(type="bark")

    def test_zen_bangumi_config_defaults(self):
        """Test ZenBangumiConfig with all default sections."""
        config = ZenBangumiConfig()
        assert isinstance(config.program, Program)
        assert isinstance(config.downloader, Downloader)
        assert isinstance(config.rss_parser, RSSParser)
        assert isinstance(config.bangumi_manage, BangumiManage)
        assert isinstance(config.log, Log)
        assert isinstance(config.proxy, Proxy)
        assert isinstance(config.notification, Notification)


class TestConfigLoader:
    """Test config loading, saving, and env override."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = ConfigLoader.__dict__.get("CONFIG_PATH")
            ConfigLoader.CONFIG_PATH = Path(tmpdir) / "config.json"
            yield Path(tmpdir)
            if original_path:
                ConfigLoader.CONFIG_PATH = original_path

    def test_load_default_config_when_missing(self, temp_config_dir):
        """Test loading default config when file doesn't exist."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"
        config = ConfigLoader.load()

        assert isinstance(config, ZenBangumiConfig)
        assert config.program.rss_time == 900
        assert config.downloader.type == "qbittorrent"

    def test_save_and_load_config(self, temp_config_dir):
        """Test saving and loading config from JSON file."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"

        original_config = ZenBangumiConfig(
            program=Program(rss_time=1200, rename_time=120, webui_port=8000)
        )
        ConfigLoader.save(original_config)

        loaded_config = ConfigLoader.load()
        assert loaded_config.program.rss_time == 1200
        assert loaded_config.program.rename_time == 120
        assert loaded_config.program.webui_port == 8000

    def test_env_override_string_field(self, temp_config_dir, monkeypatch):
        """Test environment variable override for string fields."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"

        config = ZenBangumiConfig()
        ConfigLoader.save(config)

        monkeypatch.setenv("ZEN_DOWNLOADER_HOST", "custom.host:9000")
        loaded_config = ConfigLoader.load()

        assert loaded_config.downloader.host_ == "custom.host:9000"

    def test_env_override_int_field(self, temp_config_dir, monkeypatch):
        """Test environment variable override for int fields."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"

        config = ZenBangumiConfig()
        ConfigLoader.save(config)

        monkeypatch.setenv("ZEN_PROGRAM_RSS_TIME", "1500")
        loaded_config = ConfigLoader.load()

        assert loaded_config.program.rss_time == 1500

    def test_env_override_bool_field(self, temp_config_dir, monkeypatch):
        """Test environment variable override for bool fields."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"

        config = ZenBangumiConfig()
        ConfigLoader.save(config)

        monkeypatch.setenv("ZEN_LOG_DEBUG_ENABLE", "true")
        loaded_config = ConfigLoader.load()

        assert loaded_config.log.debug_enable is True

    def test_env_override_list_field(self, temp_config_dir, monkeypatch):
        """Test environment variable override for list fields."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"

        config = ZenBangumiConfig()
        ConfigLoader.save(config)

        monkeypatch.setenv("ZEN_RSSPARSER_FILTER", "1080,720,480")
        loaded_config = ConfigLoader.load()

        assert loaded_config.rss_parser.filter == ["1080", "720", "480"]
        monkeypatch.delenv("ZEN_RSSPARSER_FILTER")

    def test_invalid_config_file_uses_defaults(self, temp_config_dir):
        """Test that invalid JSON config falls back to defaults."""
        ConfigLoader.CONFIG_PATH = temp_config_dir / "config.json"

        with open(ConfigLoader.CONFIG_PATH, "w") as f:
            f.write("{ invalid json }")

        config = ConfigLoader.load()
        assert isinstance(config, ZenBangumiConfig)
        assert config.program.rss_time == 900

    def test_config_model_dump_with_aliases(self):
        """Test that model_dump uses aliases for JSON serialization."""
        config = ZenBangumiConfig()
        dumped = config.model_dump(by_alias=True)

        assert "host" in dumped["downloader"]
        assert "username" in dumped["downloader"]
        assert "password" in dumped["downloader"]
        assert "token" in dumped["notification"]
        assert "chat_id" in dumped["notification"]

    def test_config_json_roundtrip(self, temp_config_dir):
        """Test complete JSON roundtrip with custom values."""
        config_path = temp_config_dir / "config.json"
        ConfigLoader.CONFIG_PATH = config_path

        original = ZenBangumiConfig(
            program=Program(rss_time=2000, webui_port=9000),
            downloader=Downloader(
                type="transmission",
                host="192.168.1.1:6969",
                username="user",
                password="pass",
            ),
            log=Log(debug_enable=True),
        )

        ConfigLoader.save(original)

        assert config_path.exists()
        with open(config_path, "r") as f:
            json_data = json.load(f)

        assert json_data["program"]["rss_time"] == 2000
        assert json_data["program"]["webui_port"] == 9000
        assert json_data["downloader"]["type"] == "transmission"
        assert json_data["downloader"]["host"] == "192.168.1.1:6969"
        assert json_data["log"]["debug_enable"] is True

        loaded = ConfigLoader.load()
        assert loaded.program.rss_time == 2000
        assert loaded.downloader.type == "transmission"
