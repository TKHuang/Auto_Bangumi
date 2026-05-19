"""Bangumi schema models (pure Pydantic/SQLModel schemas — NOT ORM tables).

The real ORM tables live in module.domain.models.bangumi.
These schemas are used for API serialization, sync-layer data containers,
and request/response validation.

When model_validate() is called on an ORM Bangumi (which has a .series
relationship), the model_validator below extracts the nested fields so that
the flat API surface (official_title, season, year, save_path, poster_link)
is always populated correctly even though the shims are gone from the ORM.
"""

from pathlib import PurePosixPath
from typing import Any, Optional

from pydantic import model_validator
from sqlmodel import Field, SQLModel


def _orm_bangumi_to_flat(obj: Any) -> dict:
    """Extract flat API fields from an ORM Bangumi + its Series relationship.

    Returns a plain dict that Pydantic can then validate normally.
    Only called when `obj` is not already a plain dict (i.e. it is an ORM
    object coming in via ``model_validate(orm_obj)``).
    """
    series = getattr(obj, "series", None)

    # --- identity / series-side fields ---
    canonical_title: str = ""
    year_val: Optional[str] = None
    season_val: int = 1
    poster_val: Optional[str] = None
    save_path_val: Optional[str] = None

    if series is not None:
        canonical_title = series.canonical_title or ""
        year_val = str(series.year) if series.year is not None else None
        season_val = series.season if series.season is not None else 1
        poster_val = series.poster_url

    path_override = getattr(obj, "path_override", None)
    if path_override:
        save_path_val = path_override
    elif series is not None and series.root_path:
        save_path_val = str(PurePosixPath(series.root_path) / f"Season {season_val}")

    return {
        # ORM direct columns
        "id": getattr(obj, "id", None),
        "rss_id": getattr(obj, "rss_id", None),
        "group_name": getattr(obj, "group_name", "Unknown"),
        "dpi": getattr(obj, "dpi", None),
        "source": getattr(obj, "source", None),
        "subtitle": getattr(obj, "subtitle", None),
        "eps_collect": getattr(obj, "eps_collect", False),
        "offset": getattr(obj, "offset", 0),
        "filter": getattr(obj, "filter", "720,\\d+-\\d+"),
        "rss_link": getattr(obj, "rss_link", ""),
        "added": getattr(obj, "added", False),
        "rule_name": getattr(obj, "rule_name", None),
        "deleted": getattr(obj, "deleted", False),
        "pending_review": getattr(obj, "pending_review", False),
        "global_filter_matches": getattr(obj, "global_filter_matches", None),
        # Pydantic-only fields (not on ORM) kept at defaults
        "title_raw": getattr(obj, "title_raw", ""),
        "season_raw": getattr(obj, "season_raw", None),
        # Computed from series
        "official_title": canonical_title,
        "year": year_val,
        "season": season_val,
        "poster_link": poster_val,
        "save_path": save_path_val,
    }


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
    # None = downloader state not yet fetched (UI shows loading); int = real count.
    # Never default to 0 from a stale DB read — that would silently hide a
    # downloader outage and make missing/errored torrents look completed.
    completed_count: Optional[int] = Field(default=None, title="已完成数")

    @model_validator(mode="before")
    @classmethod
    def _flatten_orm(cls, v: Any) -> Any:
        """When validating an ORM Bangumi, extract series-side fields into a flat dict.

        Detects ORM Bangumi objects by checking the actual ORM class identity rather
        than duck-typing, so MagicMock objects in tests are not affected.
        """
        if isinstance(v, dict):
            return v
        # Lazy import to avoid circular imports; only triggers on actual ORM objects.
        try:
            from module.domain.models.bangumi import Bangumi as OrmBangumi
            if isinstance(v, OrmBangumi):
                return _orm_bangumi_to_flat(v)
        except ImportError:
            pass
        return v


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
