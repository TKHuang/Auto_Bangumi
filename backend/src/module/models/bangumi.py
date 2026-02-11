"""Bangumi schema models (pure Pydantic/SQLModel schemas — NOT ORM tables).

The real ORM tables live in module.domain.models.bangumi.
These schemas are used for API serialization, sync-layer data containers,
and request/response validation.
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class Bangumi(SQLModel, table=False):
    model_config = {"from_attributes": True}

    id: Optional[int] = Field(default=None)
    rss_id: Optional[int] = Field(default=None, title="RSS订阅ID")
    official_title: str = Field(default="official_title", title="番剧中文名")
    year: Optional[str] = Field(default=None, title="番剧年份")
    title_raw: str = Field(default="title_raw", title="番剧原名")
    season: int = Field(default=1, title="番剧季度")
    season_raw: Optional[str] = Field(default=None, title="番剧季度原名")
    group_name: str = Field(default="Unknown", title="字幕组")
    dpi: Optional[str] = Field(default=None, title="分辨率")
    source: Optional[str] = Field(default=None, title="来源")
    subtitle: Optional[str] = Field(default=None, title="字幕")
    eps_collect: bool = Field(default=False, title="是否已收集")
    offset: int = Field(default=0, title="番剧偏移量")
    filter: str = Field(default="720,\\d+-\\d+", title="番剧过滤器")
    rss_link: str = Field(default="", title="番剧RSS链接")
    poster_link: Optional[str] = Field(default=None, title="番剧海报链接")
    added: bool = Field(default=False, title="是否已添加")
    rule_name: Optional[str] = Field(default=None, title="番剧规则名")
    save_path: Optional[str] = Field(default=None, title="番剧保存路径")
    deleted: bool = Field(default=False, title="是否已删除")
    pending_review: bool = Field(default=False, title="待审核")
    global_filter_matches: Optional[str] = Field(default=None, title="全局过滤匹配")
    torrent_count: int = Field(default=0, title="总种子数")
    completed_count: int = Field(default=0, title="已完成数")


class BangumiUpdate(SQLModel):
    model_config = {"from_attributes": True}

    rss_id: Optional[int] = Field(default=None, title="RSS订阅ID")
    official_title: str = Field(default="official_title", title="番剧中文名")
    year: Optional[str] = Field(default=None, title="番剧年份")
    title_raw: str = Field(default="title_raw", title="番剧原名")
    season: int = Field(default=1, title="番剧季度")
    season_raw: Optional[str] = Field(default=None, title="番剧季度原名")
    group_name: str = Field(default="Unknown", title="字幕组")
    dpi: Optional[str] = Field(default=None, title="分辨率")
    source: Optional[str] = Field(default=None, title="来源")
    subtitle: Optional[str] = Field(default=None, title="字幕")
    eps_collect: bool = Field(default=False, title="是否已收集")
    offset: int = Field(default=0, title="番剧偏移量")
    filter: str = Field(default="720,\\d+-\\d+", title="番剧过滤器")
    rss_link: str = Field(default="", title="番剧RSS链接")
    poster_link: Optional[str] = Field(default=None, title="番剧海报链接")
    added: bool = Field(default=False, title="是否已添加")
    rule_name: Optional[str] = Field(default=None, title="番剧规则名")
    save_path: Optional[str] = Field(default=None, title="番剧保存路径")
    deleted: bool = Field(default=False, title="是否已删除")
