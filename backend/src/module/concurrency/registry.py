"""Module-level RateLimiter singletons keyed by service name (spec §9.2).

Each external service (mikan, pikpak, qbittorrent) has its own limiter.
First call with (name, config) instantiates and stashes; subsequent calls with
the same name return the existing instance (config changes require restart).

Plan 05 will wire these into the RSS pipeline and downloader calls.
"""
from __future__ import annotations

from .rate_limiter import RateLimiter

_LIMITERS: dict[str, RateLimiter] = {}


def get_rate_limiter(
    name: str,
    max_concurrent: int,
    min_interval_ms: int,
) -> RateLimiter:
    """Return the singleton limiter for `name`, creating it on first call."""
    existing = _LIMITERS.get(name)
    if existing is not None:
        return existing
    limiter = RateLimiter(max_concurrent=max_concurrent, min_interval_ms=min_interval_ms)
    _LIMITERS[name] = limiter
    return limiter


def build_mikan_limiter_from_settings() -> RateLimiter:
    """Build (or fetch) the `mikan` limiter from the current runtime settings."""
    from module.conf import settings

    return get_rate_limiter(
        "mikan",
        max_concurrent=settings.mikan.max_concurrent,
        min_interval_ms=settings.mikan.min_interval_ms,
    )
