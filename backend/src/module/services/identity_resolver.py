"""IdentityResolver — three-tier series identity lookup (spec §6.4).

Tier 1 (mikan): MikanRef.mikan_bangumi_id → Series.mikan_bangumi_id
  - Hit  → return existing
  - Miss → create new Series from MikanRef data

Tier 2 (fallback): (normalized_title, season, cour_part) → Series
  - Hit  → return existing (used when no MikanRef is available)

Tier 3 (pending_review): no match in tiers 1/2
  - Create new Series with pending_review=True
  - If a Mikan-sourced series exists with the same fallback key, surface it
    as a cross-source merge candidate (caller / UI decides whether to merge)

`raw_title_for_root` is the human-readable title used to derive the
Series.canonical_title and root_path when creating a new row. Normally this
is `MikanRef.canonical_title` when Mikan resolved, else the torrent's raw
title (best guess).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from module.conf import settings
from module.domain.models.series import Series
from module.mikan.parser import MikanRef
from module.repositories.series import SeriesRepository


@dataclass
class ResolvedIdentity:
    series: Series
    tier: str  # "mikan" | "fallback" | "pending_review"
    newly_created: bool
    merge_candidates: list[int] = field(default_factory=list)


_ILLEGAL_PATH_CHARS = re.compile(r'[\\/:*?"<>|]+')


def _safe_path_component(title: str) -> str:
    """Strip characters that would confuse file systems (PikPak + Win + POSIX).

    Mirrors the sanitation applied in the legacy save_path pipeline (see
    commit f327af6c). Replaces runs of illegal chars with a single space.
    """
    cleaned = _ILLEGAL_PATH_CHARS.sub(" ", title).strip()
    return cleaned or "untitled"


def _derive_root_path(title: str) -> str:
    base = settings.downloader.path.rstrip("/\\")
    return os.path.join(base, _safe_path_component(title))


class IdentityResolver:
    def __init__(self, series_repo: SeriesRepository):
        self._repo = series_repo

    async def resolve(
        self,
        mikan_ref: Optional[MikanRef],
        normalized_title: str,
        season: int,
        cour_part: Optional[str],
        raw_title_for_root: str,
    ) -> ResolvedIdentity:
        # Tier 1: Mikan authoritative
        if mikan_ref is not None:
            hit = await self._repo.get_by_mikan_id(mikan_ref.mikan_bangumi_id)
            if hit is not None:
                return ResolvedIdentity(series=hit, tier="mikan", newly_created=False)

            title = mikan_ref.canonical_title or raw_title_for_root
            created = await self._repo.create({
                "mikan_bangumi_id": mikan_ref.mikan_bangumi_id,
                "canonical_title": title,
                "normalized_title": normalized_title,
                "season": season,
                "cour_part": cour_part,
                "poster_url": mikan_ref.poster_url,
                "root_path": _derive_root_path(title),
                "pending_review": False,
            })
            return ResolvedIdentity(series=created, tier="mikan", newly_created=True)

        # Tier 2: fallback key — only non-Mikan sourced series qualify
        hit = await self._repo.get_by_fallback(normalized_title, season, cour_part)
        if hit is not None and hit.mikan_bangumi_id is None:
            return ResolvedIdentity(series=hit, tier="fallback", newly_created=False)

        # Tier 3: pending review. With the partial fallback constraint scoped
        # to mikan_bangumi_id IS NULL (migration 0006), inserting a new
        # non-Mikan series is safe even when an existing Mikan series shares
        # the same (normalized_title, season, cour_part). The Mikan row is
        # surfaced as a merge candidate; user / UI confirms the merge.
        candidates = await self._repo.find_possible_cross_source_merge(
            normalized_title, season, cour_part,
        )
        created = await self._repo.create({
            "canonical_title": raw_title_for_root,
            "normalized_title": normalized_title,
            "season": season,
            "cour_part": cour_part,
            "root_path": _derive_root_path(raw_title_for_root),
            "pending_review": True,
        })
        return ResolvedIdentity(
            series=created,
            tier="pending_review",
            newly_created=True,
            merge_candidates=[c.id for c in candidates],
        )
