"""RssPipeline orchestration tests."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from sqlalchemy import func, select

from module.domain.models.rss import RSSItem
from module.domain.models.bangumi import Bangumi
from module.domain.models.pending_enrichment import PendingTorrentEnrichment
from module.domain.models.torrent import Torrent
from module.conf import settings
from module.mikan.parser import MikanRef
from module.services.pipeline.rss_pipeline import (
    FeedItem,
    PipelineResult,
    RssPipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(
    info_hash: str = "h1",
    homepage: str | None = "https://mikanani.me/Home/Episode/h1",
    globally_filtered: bool = False,
    global_filter_matches: tuple[str, ...] = (),
    raw_name: str = "[G] Show 01",
) -> FeedItem:
    return FeedItem(
        info_hash=info_hash,
        raw_name=raw_name,
        homepage=homepage,
        url="magnet:?xt=urn:btih:" + info_hash,
        rss_id=1,
        published_at=None,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99&subgroupid=7",
        parsed_title="Show",
        parsed_season=1,
        parsed_poster=None,
        globally_filtered=globally_filtered,
        global_filter_matches=global_filter_matches,
    )


async def _seed_rss(db_session) -> None:
    """Insert a minimal RSSItem row so FK constraints are satisfied."""
    db_session.add(
        RSSItem(id=1, name="X", url="https://mikanani.me", aggregate=False, parser="mikan")
    )
    await db_session.flush()


def _lock_registry(held: bool = False) -> MagicMock:
    registry = MagicMock()
    if held:
        registry.try_acquire = AsyncMock(return_value=None)
    else:
        lock = MagicMock()
        lock.release = MagicMock()
        registry.try_acquire = AsyncMock(return_value=lock)
    return registry


def _resolver(ref: MikanRef | None) -> MagicMock:
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=ref)
    return resolver


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_skip_when_lock_held(db_session):
    """Returns immediately with skipped_locked=True when lock is already held."""
    await _seed_rss(db_session)
    resolver = _resolver(ref=None)

    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(held=True),
        mikan_resolver=resolver,
    )
    result = await pipeline.run_for_feed(rss_id=1, items=[_item()])

    assert result.skipped_locked is True
    assert result.items_seen == 0
    resolver.resolve.assert_not_called()


@pytest.mark.integration
async def test_unresolvable_homepage_enqueues(db_session):
    """Items whose homepage cannot be resolved are enqueued as pending."""
    await _seed_rss(db_session)
    locks = _lock_registry()

    pipeline = RssPipeline(
        db_session,
        lock_registry=locks,
        mikan_resolver=_resolver(ref=None),
    )
    items = [_item(info_hash="h1"), _item(info_hash="h2")]
    result = await pipeline.run_for_feed(rss_id=1, items=items)

    assert result.items_enqueued == 2
    assert result.items_resolved == 0
    assert result.items_seen == 2
    locks.try_acquire.return_value.release.assert_called_once()


@pytest.mark.integration
async def test_no_homepage_still_attempts_resolve_then_enqueues(db_session):
    """Items with no homepage still attempt resolve; unresolved go to pending."""
    await _seed_rss(db_session)
    resolver = _resolver(ref=None)

    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=resolver,
    )
    item = _item(info_hash="h1", homepage=None)
    result = await pipeline.run_for_feed(rss_id=1, items=[item])

    assert result.items_enqueued == 1
    assert result.items_resolved == 0
    resolver.resolve.assert_called_once()


@pytest.mark.integration
async def test_resolved_item_creates_bangumi_and_torrent(db_session):
    """Successfully resolved items create a Bangumi and Torrent row."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )

    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )
    result = await pipeline.run_for_feed(rss_id=1, items=[_item()])

    assert result.items_resolved == 1
    assert result.items_enqueued == 0
    assert result.items_seen == 1
    assert result.items_failed == 0


@pytest.mark.integration
async def test_resolved_idempotent_on_existing_bangumi(db_session):
    """Two different torrents for the same (series, subgroup) reuse one Bangumi row."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )

    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    # First run: creates Series + Bangumi + Torrent(hA)
    r1 = await pipeline.run_for_feed(rss_id=1, items=[_item(info_hash="hA")])
    assert r1.items_resolved == 1

    # Second run: reuses existing Bangumi, creates Torrent(hB)
    r2 = await pipeline.run_for_feed(rss_id=1, items=[_item(info_hash="hB")])
    assert r2.items_resolved == 1

    from sqlalchemy import func, select
    from module.domain.models.bangumi import Bangumi
    from module.domain.models.torrent import Torrent

    bangumi_count = (
        await db_session.execute(select(func.count(Bangumi.id)))
    ).scalar()
    torrent_count = (
        await db_session.execute(select(func.count(Torrent.id)))
    ).scalar()

    assert bangumi_count == 1
    assert torrent_count == 2


@pytest.mark.integration
async def test_resolved_duplicate_torrent_keeps_pipeline_healthy(db_session):
    """Re-seeing the same hash for the same Bangumi should be idempotent."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )

    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    first = await pipeline.run_for_feed(rss_id=1, items=[_item(info_hash="dup-hash")])
    second = await pipeline.run_for_feed(rss_id=1, items=[_item(info_hash="dup-hash")])

    assert first.items_resolved == 1
    assert first.items_failed == 0
    assert second.items_resolved == 1
    assert second.items_failed == 0

    from sqlalchemy import func, select
    from module.domain.models.torrent import Torrent

    torrent_count = (
        await db_session.execute(select(func.count(Torrent.id)))
    ).scalar()

    assert torrent_count == 1


@pytest.mark.integration
async def test_resolved_prefers_page_mikan_ref_over_rss_link_ids(db_session):
    """When the RSS link has no bangumiId (aggregate feed) but the Mikan
    episode page returns authoritative ids, the pipeline must build a Tier 1
    (Mikan) series — not fall through to Tier 3 pending_review (review H-2)."""
    await _seed_rss(db_session)
    # rss_link has NO bangumiId / subgroupid — aggregate-style feed.
    # Mikan page gives authoritative (99, 42).
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=42,
        canonical_title="Mikan Page Title",
        poster_url="https://mikanani.me/poster.png",
    )

    item = FeedItem(
        info_hash="h1",
        raw_name="[G] Show 01",
        homepage="https://mikanani.me/Home/Episode/h1",
        url="magnet:?xt=urn:btih:h1",
        rss_id=1,
        published_at=None,
        rss_link="https://mikanani.me/RSS/MyBangumi?token=abc",  # no ids
        parsed_title="Show",
        parsed_season=1,
        parsed_poster=None,
        globally_filtered=False,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )
    result = await pipeline.run_for_feed(rss_id=1, items=[item])

    assert result.items_resolved == 1

    from sqlalchemy import select
    from module.domain.models.bangumi import Bangumi
    from module.domain.models.series import Series
    from module.domain.models.torrent import Torrent

    series = (await db_session.execute(select(Series))).scalar_one()
    # Authoritative Mikan identity — NOT pending_review.
    assert series.mikan_bangumi_id == 99
    assert series.pending_review is False
    # Page title should win over parsed title when mikan_ref is supplied.
    assert series.canonical_title == "Mikan Page Title"

    bangumi = (await db_session.execute(select(Bangumi))).scalar_one()
    assert bangumi.mikan_subgroup_id == 42

    torrent = (await db_session.execute(select(Torrent))).scalar_one()
    assert torrent.mikan_subgroup_id == 42


@pytest.mark.integration
async def test_lock_released_even_on_item_failure(db_session):
    """Lock is released even when processing fails mid-way."""
    await _seed_rss(db_session)
    lock = MagicMock()
    lock.release = MagicMock()
    locks = MagicMock()
    locks.try_acquire = AsyncMock(return_value=lock)

    resolver = MagicMock()
    resolver.resolve = AsyncMock(side_effect=RuntimeError("boom"))

    pipeline = RssPipeline(
        db_session,
        lock_registry=locks,
        mikan_resolver=resolver,
    )
    # Item has homepage so it will attempt resolve (which raises)
    result = await pipeline.run_for_feed(rss_id=1, items=[_item()])

    assert result.items_failed == 1
    assert result.items_resolved == 0
    lock.release.assert_called_once()


@pytest.mark.integration
async def test_globally_filtered_existing_bangumi_still_creates_torrent(db_session):
    """Existing subscriptions bypass the global filter during refresh."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    first = await pipeline.run_for_feed(rss_id=1, items=[_item(info_hash="h1")])
    second = await pipeline.run_for_feed(
        rss_id=1,
        items=[_item(info_hash="h2", globally_filtered=True)],
    )

    assert first.items_resolved == 1
    assert second.items_resolved == 1

    bangumi_count = (await db_session.execute(select(func.count(Bangumi.id)))).scalar()
    torrent_count = (await db_session.execute(select(func.count(Torrent.id)))).scalar()

    assert bangumi_count == 1
    assert torrent_count == 2


@pytest.mark.integration
async def test_existing_bangumi_filter_skips_matching_torrent(db_session):
    """Per-bangumi exclusion filters prevent filtered torrents entering DB."""
    await _seed_rss(db_session)
    from module.domain.models.series import Series

    series = Series(
        canonical_title="Re：从零开始的异世界生活 第二季 后半部分",
        normalized_title="re_zero_s2_part2",
        season=2,
        root_path="/downloads/ReZeroS2",
        mikan_bangumi_id=2348,
        pending_review=False,
    )
    db_session.add(series)
    await db_session.flush()

    bangumi = Bangumi(
        series_id=series.id,
        rss_id=1,
        mikan_subgroup_id=554,
        group_name="百冬练习组",
        filter="简",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=2348&subgroupid=554",
        active=True,
    )
    db_session.add(bangumi)
    await db_session.commit()

    mikan_ref = MikanRef(
        mikan_bangumi_id=2348,
        mikan_subgroup_id=554,
        canonical_title="Re：从零开始的异世界生活 第二季 后半部分",
        poster_url=None,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    result = await pipeline.run_for_feed(
        rss_id=1,
        items=[
            FeedItem(
                info_hash="simp",
                raw_name=(
                    "【百冬练习组】【Re: 从零开始的异世界的生活 S2】"
                    "[25END][1080p AVC AAC][简体]"
                ),
                homepage="https://mikanani.me/Home/Episode/simp",
                url="magnet:?xt=urn:btih:simp",
                rss_id=1,
                published_at=None,
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=2348&subgroupid=554",
                parsed_title="Re：从零开始的异世界生活 第二季 后半部分",
                parsed_season=2,
                parsed_poster=None,
                parsed_group_name="百冬练习组",
                globally_filtered=False,
            )
        ],
    )

    assert result.items_seen == 1
    assert result.items_failed == 0
    assert result.items_enqueued == 0

    torrent_count = (await db_session.execute(select(func.count(Torrent.id)))).scalar()
    assert torrent_count == 0


@pytest.mark.integration
async def test_globally_filtered_no_homepage_existing_bangumi_still_creates_torrent(db_session):
    """Existing subscriptions should bypass global filter even without homepage."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    first = await pipeline.run_for_feed(rss_id=1, items=[_item(info_hash="h1")])
    second = await pipeline.run_for_feed(
        rss_id=1,
        items=[_item(info_hash="h2", homepage=None, globally_filtered=True)],
    )

    assert first.items_resolved == 1
    assert second.items_resolved == 1

    bangumi_count = (await db_session.execute(select(func.count(Bangumi.id)))).scalar()
    torrent_count = (await db_session.execute(select(func.count(Torrent.id)))).scalar()

    assert bangumi_count == 1
    assert torrent_count == 2


@pytest.mark.integration
async def test_globally_filtered_new_item_creates_pending_review_without_torrent(db_session):
    """A resolved new item blocked by the global filter surfaces in RSS review."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    result = await pipeline.run_for_feed(
        rss_id=1,
        items=[
            _item(
                info_hash="h1",
                globally_filtered=True,
                global_filter_matches=("简",),
            )
        ],
    )

    assert result.items_seen == 1
    assert result.items_enqueued == 0
    assert result.items_failed == 0

    bangumi = (await db_session.execute(select(Bangumi))).scalar_one()
    torrent = (await db_session.execute(select(Torrent))).scalar_one()
    pending_count = (
        await db_session.execute(select(func.count(PendingTorrentEnrichment.info_hash)))
    ).scalar()

    assert bangumi.pending_review is True
    assert bangumi.global_filter_matches == "简"
    assert bangumi.filter == ",".join(settings.rss_parser.filter)
    assert torrent.bangumi_id == bangumi.id
    assert torrent.rss_id == 1
    assert torrent.name == "[G] Show 01"
    assert torrent.hash == "h1"
    assert torrent.downloaded is False
    assert pending_count == 0


@pytest.mark.integration
async def test_existing_pending_review_keeps_new_filtered_candidate(db_session):
    """A pending review row should keep later filtered candidates for preview."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    await pipeline.run_for_feed(
        rss_id=1,
        items=[
            _item(
                info_hash="h1",
                globally_filtered=True,
                global_filter_matches=("简",),
                raw_name="[G] Show 01 [简]",
            )
        ],
    )
    result = await pipeline.run_for_feed(
        rss_id=1,
        items=[
            _item(
                info_hash="h2",
                globally_filtered=True,
                global_filter_matches=("简",),
                raw_name="[G] Show 02 [简]",
            )
        ],
    )

    assert result.items_seen == 1
    assert result.items_failed == 0

    torrents = (await db_session.execute(select(Torrent))).scalars().all()
    assert [torrent.hash for torrent in torrents] == ["h1", "h2"]
    assert all(torrent.downloaded is False for torrent in torrents)


@pytest.mark.integration
async def test_resolved_item_persists_authoritative_season_rss_link(db_session):
    """Resolved Mikan items store the authoritative season RSS link on Bangumi."""
    await _seed_rss(db_session)
    mikan_ref = MikanRef(
        mikan_bangumi_id=99,
        mikan_subgroup_id=7,
        canonical_title="Show",
        poster_url=None,
    )
    item = FeedItem(
        info_hash="h1",
        raw_name="[G] Show 01",
        homepage="https://mikanani.me/Home/Episode/h1",
        url="magnet:?xt=urn:btih:h1",
        rss_id=1,
        published_at=None,
        rss_link="https://mikanani.me/RSS/MyBangumi?token=aggregate-style",
        parsed_title="Show",
        parsed_season=1,
        parsed_poster=None,
        globally_filtered=False,
    )
    pipeline = RssPipeline(
        db_session,
        lock_registry=_lock_registry(),
        mikan_resolver=_resolver(ref=mikan_ref),
    )

    result = await pipeline.run_for_feed(rss_id=1, items=[item])

    assert result.items_resolved == 1

    bangumi = (await db_session.execute(select(Bangumi))).scalar_one()
    assert bangumi.rss_link == (
        "https://mikanani.me/RSS/Bangumi?bangumiId=99&subgroupid=7"
    )
