"""Mikan episode-page parser (spec §8.1).

Extracts (mikan_bangumi_id, mikan_subgroup_id) plus canonical_title and
poster_url from a fetched episode page. Uses three-tier fallback:

  Tier A: subscribe button data attributes (data-bangumiid + data-subtitlegroupid)
  Tier B: /Home/Bangumi/{id}#{sub} anchor
  Tier C: RSS URL ?bangumiId=&subgroupid=

Returns None if no tier matches (treat as non_mikan or parse_failed upstream).

Also provides `extract_mikan_ids_from_rss`, a lightweight utility that parses
(mikan_bangumi_id, mikan_subgroup_id) directly from a Mikan RSS URL without
fetching the page, used by the bangumi creation pipeline.
"""
from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MikanRef:
    mikan_bangumi_id: int
    mikan_subgroup_id: int
    canonical_title: Optional[str] = None
    poster_url: Optional[str] = None


# Matches Mikan RSS URLs of the form:
#   https://mikanani.me/RSS/Bangumi?bangumiId=3437&subgroupid=583
# The subgroupid parameter is optional.
_MIKAN_RSS_RE = re.compile(
    r"mikan(?:ani|ime)?\.(?:me|tv)/RSS/Bangumi\?bangumiId=(\d+)"
    r"(?:&subgroupid=(\d+))?",
    re.IGNORECASE,
)


def extract_mikan_ids_from_rss(
    rss_link: Optional[str],
) -> tuple[Optional[int], Optional[int]]:
    """Return (mikan_bangumi_id, mikan_subgroup_id) extracted from *rss_link*.

    Returns (None, None) when the link is empty or is not a Mikan RSS URL.
    """
    if not rss_link:
        return None, None
    match = _MIKAN_RSS_RE.search(rss_link)
    if not match:
        return None, None
    bangumi_id = int(match.group(1))
    subgroup_id = int(match.group(2)) if match.group(2) is not None else None
    return bangumi_id, subgroup_id


_TIER_A = re.compile(
    r'data-bangumiid="(\d+)"\s+data-subtitlegroupid="(\d+)"',
)
_TIER_B = re.compile(r'/Home/Bangumi/(\d+)#(\d+)')
_TIER_C = re.compile(r'bangumiId=(\d+)&subgroupid=(\d+)')
_TITLE = re.compile(
    r'<(?:div|p)[^>]*class="[^"]*bangumi-title[^"]*"[^>]*>\s*'
    r'<a[^>]*>([^<]+)</a>'
)
_POSTER = re.compile(
    r'class="[^"]*bangumi-poster[^"]*"[^>]*style="[^"]*'
    r'background-image:\s*url\(\s*[\'"]?([^\'")]+)'
)


def _find_ids(html: str) -> Optional[tuple[int, int]]:
    for pattern in (_TIER_A, _TIER_B, _TIER_C):
        m = pattern.search(html)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def parse_mikan_page(html: str) -> Optional[MikanRef]:
    """Parse a Mikan episode page. Returns None if no (bangumi_id, subgroup_id)
    can be extracted via any of the three tiers."""
    if not html:
        return None

    ids = _find_ids(html)
    if ids is None:
        return None
    bid, sid = ids

    title_match = _TITLE.search(html)
    title = (
        html_module.unescape(title_match.group(1)).strip()
        if title_match
        else None
    )

    poster_match = _POSTER.search(html)
    poster = poster_match.group(1) if poster_match else None

    return MikanRef(
        mikan_bangumi_id=bid,
        mikan_subgroup_id=sid,
        canonical_title=title,
        poster_url=poster,
    )


# Canonical bangumi-page URL helpers
# ----------------------------------
# The fragment form `/Home/Bangumi/<bangumi>#<subgroup>` is what Mikan's own
# UI links to, so it doubles as a human-clickable key: operators paste it
# into the WebUI resolve form, the URL then short-circuits future episodes
# that land on the same page.

_DEFAULT_MIKAN_BASE_URL = "https://mikanani.me"

# Accepts a full URL, a schema-less host, or a pure path — anything that
# contains `/Home/Bangumi/<id>#<sub>` is valid. Subgroup is required: without
# it a Mikan page cannot be disambiguated between fansub groups (spec §6.4).
_CANONICAL_BANGUMI_URL_RE = re.compile(
    r"/Home/Bangumi/(\d+)#(\d+)\b",
)


def build_canonical_bangumi_url(
    bangumi_id: int,
    subgroup_id: int,
    *,
    base_url: str = _DEFAULT_MIKAN_BASE_URL,
) -> str:
    """Return the canonical `/Home/Bangumi/<id>#<sub>` URL for a bangumi.

    Matches the form the Mikan UI itself renders in <a class="bangumi-title">
    anchors, so the result is safe to store and then click through directly
    from the WebUI resolution page.
    """
    if bangumi_id <= 0 or subgroup_id <= 0:
        raise ValueError("bangumi_id and subgroup_id must both be positive")
    return f"{base_url.rstrip('/')}/Home/Bangumi/{bangumi_id}#{subgroup_id}"


def build_season_rss_url(
    bangumi_id: int,
    subgroup_id: int,
    *,
    base_url: str = _DEFAULT_MIKAN_BASE_URL,
) -> str:
    """Return the season-specific Mikan RSS URL for a bangumi/subgroup pair."""
    if bangumi_id <= 0 or subgroup_id <= 0:
        raise ValueError("bangumi_id and subgroup_id must both be positive")
    return (
        f"{base_url.rstrip('/')}/RSS/Bangumi"
        f"?bangumiId={bangumi_id}&subgroupid={subgroup_id}"
    )


def parse_canonical_bangumi_url(url: Optional[str]) -> Optional[tuple[int, int]]:
    """Parse an operator-supplied bangumi-page URL back into ids.

    Returns (bangumi_id, subgroup_id) if the string contains a recognisable
    ``/Home/Bangumi/<id>#<sub>`` fragment; returns None otherwise. URLs
    missing the subgroup fragment are rejected on purpose — without a
    subgroup the identity is ambiguous.
    """
    if not url:
        return None
    stripped = url.strip()
    if not stripped:
        return None
    match = _CANONICAL_BANGUMI_URL_RE.search(stripped)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
