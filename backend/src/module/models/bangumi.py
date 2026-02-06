from typing import Optional

from sqlmodel import Field, SQLModel

from module.domain.value_objects import (
    BangumiParsingError,
    Episode,
    Notification,
    SeasonInfo,
)


class Bangumi(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    rss_id: Optional[int] = Field(default=None, foreign_key="rssitem.id", alias="rss_id", title="RSS订阅ID")
    official_title: str = Field(
        default="official_title", alias="official_title", title="番剧中文名"
    )
    year: Optional[str] = Field(alias="year", title="番剧年份")
    title_raw: str = Field(default="title_raw", alias="title_raw", title="番剧原名")
    season: int = Field(default=1, alias="season", title="番剧季度")
    season_raw: Optional[str] = Field(alias="season_raw", title="番剧季度原名")
    group_name: str = Field(default="Unknown", alias="group_name", title="字幕组")
    dpi: Optional[str] = Field(alias="dpi", title="分辨率")
    source: Optional[str] = Field(alias="source", title="来源")
    subtitle: Optional[str] = Field(alias="subtitle", title="字幕")
    eps_collect: bool = Field(default=False, alias="eps_collect", title="是否已收集")
    offset: int = Field(default=0, alias="offset", title="番剧偏移量")
    filter: str = Field(default="720,\\d+-\\d+", alias="filter", title="番剧过滤器")
    rss_link: str = Field(default="", alias="rss_link", title="番剧RSS链接")
    poster_link: Optional[str] = Field(alias="poster_link", title="番剧海报链接")
    added: bool = Field(default=False, alias="added", title="是否已添加")
    rule_name: Optional[str] = Field(alias="rule_name", title="番剧规则名")
    save_path: Optional[str] = Field(alias="save_path", title="番剧保存路径")
    deleted: bool = Field(False, alias="deleted", title="是否已删除")
    pending_review: bool = Field(default=False, alias="pending_review", title="待审核")
    global_filter_matches: Optional[str] = Field(default=None, alias="global_filter_matches", title="全局过滤匹配")


class BangumiUpdate(SQLModel):
    rss_id: Optional[int] = Field(default=None, alias="rss_id", title="RSS订阅ID")
    official_title: str = Field(
        default="official_title", alias="official_title", title="番剧中文名"
    )
    year: Optional[str] = Field(alias="year", title="番剧年份")
    title_raw: str = Field(default="title_raw", alias="title_raw", title="番剧原名")
    season: int = Field(default=1, alias="season", title="番剧季度")
    season_raw: Optional[str] = Field(alias="season_raw", title="番剧季度原名")
    group_name: str = Field(default="Unknown", alias="group_name", title="字幕组")
    dpi: Optional[str] = Field(alias="dpi", title="分辨率")
    source: Optional[str] = Field(alias="source", title="来源")
    subtitle: Optional[str] = Field(alias="subtitle", title="字幕")
    eps_collect: bool = Field(default=False, alias="eps_collect", title="是否已收集")
    offset: int = Field(default=0, alias="offset", title="番剧偏移量")
    filter: str = Field(default="720,\\d+-\\d+", alias="filter", title="番剧过滤器")
    rss_link: str = Field(default="", alias="rss_link", title="番剧RSS链接")
    poster_link: Optional[str] = Field(alias="poster_link", title="番剧海报链接")
    added: bool = Field(default=False, alias="added", title="是否已添加")
    rule_name: Optional[str] = Field(alias="rule_name", title="番剧规则名")
    save_path: Optional[str] = Field(alias="save_path", title="番剧保存路径")
    deleted: bool = Field(False, alias="deleted", title="是否已删除")
