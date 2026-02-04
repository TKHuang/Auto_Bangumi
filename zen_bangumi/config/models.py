"""Pydantic v2 config models for ZenBangumi with JSON persistence and env var override."""

from os.path import expandvars
from typing import Literal

from pydantic import BaseModel, Field


class Program(BaseModel):
    """Program configuration."""

    rss_time: int = Field(900, description="RSS check interval in seconds")
    rename_time: int = Field(60, description="Rename check interval in seconds")
    webui_port: int = Field(7892, description="WebUI port")


class Downloader(BaseModel):
    """Downloader configuration."""

    type: str = Field("qbittorrent", description="Downloader type")
    host_: str = Field("172.17.0.1:8080", alias="host", description="Downloader host")
    username_: str = Field("admin", alias="username", description="Downloader username")
    password_: str = Field(
        "adminadmin", alias="password", description="Downloader password"
    )
    path: str = Field("/downloads/Bangumi", description="Downloader path")
    ssl: bool = Field(False, description="Use SSL for downloader connection")

    @property
    def host(self) -> str:
        """Get host with env var expansion."""
        return expandvars(self.host_)

    @property
    def username(self) -> str:
        """Get username with env var expansion."""
        return expandvars(self.username_)

    @property
    def password(self) -> str:
        """Get password with env var expansion."""
        return expandvars(self.password_)


class RSSParser(BaseModel):
    """RSS parser configuration."""

    enable: bool = Field(True, description="Enable RSS parser")
    filter: list[str] = Field(["720", r"\d+-\d"], description="Filter patterns")
    language: str = Field("zh", description="Language for parsing")


class BangumiManage(BaseModel):
    """Bangumi management configuration."""

    enable: bool = Field(True, description="Enable bangumi management")
    eps_complete: bool = Field(
        False, description="Enable episode completion (from source only)"
    )
    rename_method: str = Field("pn", description="Rename method")
    group_tag: bool = Field(False, description="Include group tag in rename")
    remove_bad_torrent: bool = Field(False, description="Remove bad torrents")


class Log(BaseModel):
    """Logging configuration."""

    debug_enable: bool = Field(False, description="Enable debug logging")


class Proxy(BaseModel):
    """Proxy configuration."""

    enable: bool = Field(False, description="Enable proxy")
    type: str = Field("http", description="Proxy type (http/socks5)")
    host: str = Field("", description="Proxy host")
    port: int = Field(0, description="Proxy port")
    username_: str = Field("", alias="username", description="Proxy username")
    password_: str = Field("", alias="password", description="Proxy password")

    @property
    def username(self) -> str:
        """Get username with env var expansion."""
        return expandvars(self.username_)

    @property
    def password(self) -> str:
        """Get password with env var expansion."""
        return expandvars(self.password_)


class Notification(BaseModel):
    """Notification configuration."""

    enable: bool = Field(False, description="Enable notifications")
    type: Literal["telegram"] = Field("telegram", description="Notification type")
    token_: str = Field("", alias="token", description="Telegram bot token")
    chat_id_: str = Field("", alias="chat_id", description="Telegram chat ID")

    @property
    def token(self) -> str:
        """Get token with env var expansion."""
        return expandvars(self.token_)

    @property
    def chat_id(self) -> str:
        """Get chat_id with env var expansion."""
        return expandvars(self.chat_id_)


class ZenBangumiConfig(BaseModel):
    """Top-level ZenBangumi configuration."""

    program: Program = Field(default_factory=Program)
    downloader: Downloader = Field(default_factory=Downloader)
    rss_parser: RSSParser = Field(default_factory=RSSParser)
    bangumi_manage: BangumiManage = Field(default_factory=BangumiManage)
    log: Log = Field(default_factory=Log)
    proxy: Proxy = Field(default_factory=Proxy)
    notification: Notification = Field(default_factory=Notification)

    def model_dump_json_safe(self, **kwargs) -> dict:
        """Dump model to dict with aliases for JSON serialization."""
        return self.model_dump(by_alias=True, **kwargs)
