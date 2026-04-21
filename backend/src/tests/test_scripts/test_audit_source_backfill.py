"""Tests for scripts/audit_source_backfill.py."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

# Make scripts/ importable
BACKEND_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.audit_source_backfill import (  # noqa: E402
    audit_bangumi_source_coverage,
    classify_bangumi_source,
    execute_source_backfill,
    filter_bangumi_rows,
)

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent


_grp_counter = 0


def _grp() -> str:
    global _grp_counter
    _grp_counter += 1
    return f"AUDITGRP{_grp_counter}"


async def _seed_bangumi(
    db_session,
    *,
    title: str,
    season: int,
    rss_link: str,
    active: bool = True,
) -> Bangumi:
    series = Series(
        canonical_title=title,
        normalized_title=title.lower(),
        season=season,
        root_path=f"/downloads/{title}",
    )
    db_session.add(series)
    await db_session.flush()

    bangumi = Bangumi(
        series_id=series.id,
        group_name=_grp(),
        rss_link=rss_link,
        active=active,
        pending_review=False,
        deleted=False,
    )
    db_session.add(bangumi)
    await db_session.flush()
    await db_session.refresh(bangumi)
    return bangumi


@pytest.mark.integration
async def test_classify_bangumi_source_separates_season_specific_and_legacy(db_session):
    season_specific = await _seed_bangumi(
        db_session,
        title="Safe Show",
        season=1,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=100&subgroupid=7",
    )
    legacy = await _seed_bangumi(
        db_session,
        title="Legacy Show",
        season=1,
        rss_link="https://mikanani.me/RSS/MyBangumi?token=abc",
    )

    safe, legacy_rows = classify_bangumi_source([season_specific, legacy])

    assert [b.id for b in safe] == [season_specific.id]
    assert [b.id for b in legacy_rows] == [legacy.id]


@pytest.mark.integration
async def test_audit_bangumi_source_coverage_reports_missing_hashes(db_session):
    bangumi = await _seed_bangumi(
        db_session,
        title="Audit Show",
        season=1,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=200&subgroupid=9",
    )
    db_session.add(
        Torrent(
            bangumi_id=bangumi.id,
            rss_id=None,
            name="Episode 01",
            url="u1",
            hash="hash-01",
            downloaded=True,
        )
    )
    await db_session.flush()

    source_torrents = [
        SimpleNamespace(name="Episode 01", hash="hash-01"),
        SimpleNamespace(name="Episode 02", hash="hash-02"),
        SimpleNamespace(name="Episode 03", hash="hash-03"),
    ]

    with patch(
        "scripts.audit_source_backfill.fetch_source_torrents",
        new=AsyncMock(return_value=source_torrents),
    ):
        result = await audit_bangumi_source_coverage(db_session, bangumi)

    assert result["bangumi_id"] == bangumi.id
    assert result["source_count"] == 3
    assert result["existing_count"] == 1
    assert result["missing_hashes"] == ["hash-02", "hash-03"]


@pytest.mark.integration
async def test_execute_source_backfill_only_runs_for_missing_safe_rows(db_session):
    safe_missing = await _seed_bangumi(
        db_session,
        title="Safe Missing",
        season=1,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=300&subgroupid=5",
    )
    safe_complete = await _seed_bangumi(
        db_session,
        title="Safe Complete",
        season=1,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=301&subgroupid=5",
    )
    legacy = await _seed_bangumi(
        db_session,
        title="Legacy",
        season=1,
        rss_link="https://mikanani.me/RSS/MyBangumi?token=legacy",
    )

    with patch(
        "scripts.audit_source_backfill.audit_bangumi_source_coverage",
        new=AsyncMock(
            side_effect=[
                {
                    "bangumi_id": safe_missing.id,
                    "missing_hashes": ["h1", "h2"],
                    "source_count": 2,
                    "existing_count": 0,
                },
                {
                    "bangumi_id": safe_complete.id,
                    "missing_hashes": [],
                    "source_count": 2,
                    "existing_count": 2,
                },
            ]
        ),
    ), patch(
        "scripts.audit_source_backfill.create_downloader",
        return_value=object(),
    ), patch(
        "scripts.audit_source_backfill.RSSEngine.download_bangumi",
        new=AsyncMock(return_value={"status": True, "count": 2}),
    ) as mock_backfill:
        report = await execute_source_backfill(
            db_session,
            [safe_missing, safe_complete, legacy],
            execute=True,
        )

    assert report["safe_total"] == 2
    assert report["legacy_total"] == 1
    assert report["executed"] == 1
    mock_backfill.assert_awaited_once()
    assert mock_backfill.await_args.args[2] == safe_missing.id


@pytest.mark.integration
async def test_filter_bangumi_rows_by_requested_ids(db_session):
    first = await _seed_bangumi(
        db_session,
        title="Filter One",
        season=1,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=401&subgroupid=1",
    )
    second = await _seed_bangumi(
        db_session,
        title="Filter Two",
        season=1,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=402&subgroupid=1",
    )

    filtered = filter_bangumi_rows([first, second], {second.id})

    assert [b.id for b in filtered] == [second.id]
