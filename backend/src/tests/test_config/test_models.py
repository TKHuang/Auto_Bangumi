import json
import os
import tempfile
from pathlib import Path

import pytest

from module.conf.models import (
    BangumiManage,
    Config,
    Downloader,
    ExperimentalOpenAI,
    Log,
    Notification,
    Program,
    Proxy,
    RSSParser,
)


class TestProgram:
    def test_program_defaults(self):
        program = Program()
        assert program.rss_time == 900
        assert program.rename_time == 60
        assert program.webui_port == 7892

    def test_program_custom_values(self):
        program = Program(rss_time=1800, rename_time=120, webui_port=8080)
        assert program.rss_time == 1800
        assert program.rename_time == 120
        assert program.webui_port == 8080


class TestDownloader:
    def test_downloader_defaults(self):
        downloader = Downloader()
        assert downloader.type == "qbittorrent"
        assert downloader.host_ == "172.17.0.1:8080"
        assert downloader.username_ == "admin"
        assert downloader.password_ == "adminadmin"
        assert downloader.path == "/downloads/Bangumi"
        assert downloader.ssl is False

    def test_downloader_alias_serialization(self):
        downloader = Downloader()
        data = downloader.model_dump(by_alias=True)
        assert "host" in data
        assert "username" in data
        assert "password" in data
        assert data["host"] == "172.17.0.1:8080"

    def test_downloader_expandvars_host(self):
        os.environ["TEST_HOST"] = "192.168.1.1:9090"
        downloader = Downloader()
        downloader.host_ = "$TEST_HOST"
        assert downloader.host == "192.168.1.1:9090"
        del os.environ["TEST_HOST"]

    def test_downloader_expandvars_username(self):
        os.environ["TEST_USER"] = "testuser"
        downloader = Downloader()
        downloader.username_ = "$TEST_USER"
        assert downloader.username == "testuser"
        del os.environ["TEST_USER"]

    def test_downloader_expandvars_password(self):
        os.environ["TEST_PASS"] = "testpass123"
        downloader = Downloader()
        downloader.password_ = "$TEST_PASS"
        assert downloader.password == "testpass123"
        del os.environ["TEST_PASS"]


class TestRSSParser:
    def test_rss_parser_defaults(self):
        parser = RSSParser()
        assert parser.enable is True
        assert parser.filter == ["720", r"\d+-\d"]
        assert parser.language == "zh"

    def test_rss_parser_custom_filter(self):
        parser = RSSParser(filter=["1080", "2160"])
        assert parser.filter == ["1080", "2160"]


class TestBangumiManage:
    def test_bangumi_manage_defaults(self):
        manage = BangumiManage()
        assert manage.enable is True
        assert manage.eps_complete is False
        assert manage.eps_complete_from_source is True
        assert manage.rename_method == "pn"
        assert manage.group_tag is False
        assert manage.remove_bad_torrent is False


class TestLog:
    def test_log_defaults(self):
        log = Log()
        assert log.debug_enable is False

    def test_log_debug_enabled(self):
        log = Log(debug_enable=True)
        assert log.debug_enable is True


class TestProxy:
    def test_proxy_defaults(self):
        proxy = Proxy()
        assert proxy.enable is False
        assert proxy.type == "http"
        assert proxy.host == ""
        assert proxy.port == 0
        assert proxy.username_ == ""
        assert proxy.password_ == ""

    def test_proxy_expandvars_username(self):
        os.environ["PROXY_USER"] = "proxyuser"
        proxy = Proxy()
        proxy.username_ = "$PROXY_USER"
        assert proxy.username == "proxyuser"
        del os.environ["PROXY_USER"]

    def test_proxy_expandvars_password(self):
        os.environ["PROXY_PASS"] = "proxypass"
        proxy = Proxy()
        proxy.password_ = "$PROXY_PASS"
        assert proxy.password == "proxypass"
        del os.environ["PROXY_PASS"]


class TestNotification:
    def test_notification_defaults(self):
        notif = Notification()
        assert notif.enable is False
        assert notif.type == "telegram"
        assert notif.token_ == ""
        assert notif.chat_id_ == ""

    def test_notification_expandvars_token(self):
        os.environ["NOTIF_TOKEN"] = "token123"
        notif = Notification()
        notif.token_ = "$NOTIF_TOKEN"
        assert notif.token == "token123"
        del os.environ["NOTIF_TOKEN"]

    def test_notification_expandvars_chat_id(self):
        os.environ["NOTIF_CHAT"] = "12345"
        notif = Notification()
        notif.chat_id_ = "$NOTIF_CHAT"
        assert notif.chat_id == "12345"
        del os.environ["NOTIF_CHAT"]


class TestExperimentalOpenAI:
    def test_openai_defaults(self):
        openai = ExperimentalOpenAI()
        assert openai.enable is False
        assert openai.api_key == ""
        assert openai.api_base == "https://api.openai.com/v1"
        assert openai.api_type == "openai"
        assert openai.api_version == "2023-05-15"
        assert openai.model == "gpt-3.5-turbo"
        assert openai.deployment_id == ""

    def test_openai_api_base_validation(self):
        openai = ExperimentalOpenAI(api_base="https://api.openai.com/")
        assert openai.api_base == "https://api.openai.com/v1"

    def test_openai_azure_config(self):
        openai = ExperimentalOpenAI(
            enable=True,
            api_type="azure",
            api_version="2024-02-15",
            deployment_id="my-deployment",
        )
        assert openai.api_type == "azure"
        assert openai.deployment_id == "my-deployment"


class TestConfig:
    def test_config_defaults(self):
        config = Config()
        assert isinstance(config.program, Program)
        assert isinstance(config.downloader, Downloader)
        assert isinstance(config.rss_parser, RSSParser)
        assert isinstance(config.bangumi_manage, BangumiManage)
        assert isinstance(config.log, Log)
        assert isinstance(config.proxy, Proxy)
        assert isinstance(config.notification, Notification)
        assert isinstance(config.experimental_openai, ExperimentalOpenAI)

    def test_config_model_dump_by_alias(self):
        config = Config()
        data = config.model_dump(by_alias=True)
        assert "program" in data
        assert "downloader" in data
        assert data["downloader"]["host"] == "172.17.0.1:8080"
        assert data["downloader"]["username"] == "admin"
        assert data["downloader"]["password"] == "adminadmin"

    def test_config_from_json(self):
        json_data = {
            "program": {"rss_time": 1200, "rename_time": 90, "webui_port": 8000},
            "downloader": {
                "type": "qbittorrent",
                "host": "localhost:8080",
                "username": "user",
                "password": "pass",
                "path": "/downloads",
                "ssl": True,
            },
            "rss_parser": {"enable": False, "filter": ["1080"], "language": "en"},
            "bangumi_manage": {
                "enable": True,
                "eps_complete": True,
                "eps_complete_from_source": False,
                "rename_method": "normal",
                "group_tag": True,
                "remove_bad_torrent": True,
            },
            "log": {"debug_enable": True},
            "proxy": {
                "enable": True,
                "type": "socks5",
                "host": "proxy.example.com",
                "port": 1080,
                "username": "proxyuser",
                "password": "proxypass",
            },
            "notification": {
                "enable": True,
                "type": "telegram",
                "token": "token123",
                "chat_id": "12345",
            },
            "experimental_openai": {
                "enable": True,
                "api_key": "sk-123",
                "api_base": "https://api.openai.com/v1",
                "api_type": "openai",
                "api_version": "2023-05-15",
                "model": "gpt-3.5-turbo",
                "deployment_id": "",
            },
        }
        config = Config.model_validate(json_data)
        assert config.program.rss_time == 1200
        assert config.program.rename_time == 90
        assert config.downloader.type == "qbittorrent"
        assert config.downloader.host_ == "localhost:8080"
        assert config.rss_parser.enable is False
        assert config.log.debug_enable is True

    def test_config_json_roundtrip(self):
        config = Config(
            program=Program(rss_time=1500, rename_time=100),
            downloader=Downloader(type="pikpak"),
        )
        data = config.model_dump(by_alias=True)
        json_str = json.dumps(data)
        loaded_data = json.loads(json_str)
        config2 = Config.model_validate(loaded_data)
        assert config2.program.rss_time == 1500
        assert config2.program.rename_time == 100
        assert config2.downloader.type == "pikpak"

    def test_config_partial_override(self):
        base_config = Config()
        override_data = {
            "program": {"rss_time": 2000},
            "downloader": {"type": "transmission"},
        }
        base_dict = base_config.model_dump(by_alias=True)
        base_dict["program"].update(override_data["program"])
        base_dict["downloader"].update(override_data["downloader"])
        config = Config.model_validate(base_dict)
        assert config.program.rss_time == 2000
        assert config.downloader.type == "transmission"
        assert config.downloader.host_ == "172.17.0.1:8080"


@pytest.mark.integration
class TestConfigLoading:
    def test_config_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_data = {
                "program": {"rss_time": 900, "rename_time": 60, "webui_port": 7892},
                "downloader": {
                    "type": "qbittorrent",
                    "host": "172.17.0.1:8080",
                    "username": "admin",
                    "password": "adminadmin",
                    "path": "/downloads/Bangumi",
                    "ssl": False,
                },
                "rss_parser": {"enable": True, "filter": ["720"], "language": "zh"},
                "bangumi_manage": {
                    "enable": True,
                    "eps_complete": False,
                    "eps_complete_from_source": True,
                    "rename_method": "pn",
                    "group_tag": False,
                    "remove_bad_torrent": False,
                },
                "log": {"debug_enable": False},
                "proxy": {
                    "enable": False,
                    "type": "http",
                    "host": "",
                    "port": 0,
                    "username": "",
                    "password": "",
                },
                "notification": {
                    "enable": False,
                    "type": "telegram",
                    "token": "",
                    "chat_id": "",
                },
                "experimental_openai": {
                    "enable": False,
                    "api_key": "",
                    "api_base": "https://api.openai.com/v1",
                    "api_type": "openai",
                    "api_version": "2023-05-15",
                    "model": "gpt-3.5-turbo",
                    "deployment_id": "",
                },
            }
            with open(config_file, "w") as f:
                json.dump(config_data, f)

            with open(config_file, "r") as f:
                loaded_data = json.load(f)
            config = Config.model_validate(loaded_data)
            assert config.program.rss_time == 900
            assert config.downloader.type == "qbittorrent"
