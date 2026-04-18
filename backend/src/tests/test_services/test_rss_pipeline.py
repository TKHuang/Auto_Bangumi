"""RssPipeline orchestration tests."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.domain.models.rss import RSSItem
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
) -> FeedItem:
    return FeedItem(
        info_hash=info_hash,
        raw_name="[G] Show 01",
        homepage=homepage,
        url="magnet:?xt=urn:btih:" + info_hash,
        rss_id=1,
        published_at=None,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99&subgroupid=7",
        parsed_title="Show",
        parsed_season=1,
        parsed_poster=None,
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
async def test_no_homepage_enqueues_without_resolver_call(db_session):
    """Items with no homepage skip the resolver and go directly to pending."""
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
    resolver.resolve.assert_not_called()


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
