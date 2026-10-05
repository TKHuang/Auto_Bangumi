"""Effective display fields of a Bangumi.

A Bangumi row reads its title, season, year and poster through its Series.
The save path is ``path_override`` when set, else ``<series.root_path>/Season N``.
These functions also accept the flat ``module.models.Bangumi`` DTO, which
carries the same fields directly (``official_title``, ``season``, ...).

Plain functions on purpose: callers must still load ``Bangumi.series``.
"""

from pathlib import PurePosixPath
from typing import Any, Optional


def effective_title(data: Any, default: Optional[str] = "") -> Optional[str]:
    series = getattr(data, "series", None)
    if series is not None:
        return series.canonical_title or ""
    return getattr(data, "official_title", default) or default


def effective_season(data: Any) -> int:
    series = getattr(data, "series", None)
    if series is not None:
        return series.season if series.season is not None else 1
    return getattr(data, "season", 1) or 1


def effective_year(data: Any) -> Optional[int]:
    series = getattr(data, "series", None)
    if series is not None:
        return series.year
    return getattr(data, "year", None)


def effective_poster(data: Any) -> Optional[str]:
    series = getattr(data, "series", None)
    if series is not None:
        return series.poster_url
    return getattr(data, "poster_link", None)


def effective_save_path(data: Any) -> Optional[str]:
    path_override = getattr(data, "path_override", None)
    if path_override:
        return path_override
    series = getattr(data, "series", None)
    if series is not None:
        # Series.root_path is NOT NULL and never empty (identity_resolver).
        return str(PurePosixPath(series.root_path) / f"Season {effective_season(data)}")
    return getattr(data, "save_path", None)
