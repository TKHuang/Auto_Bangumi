"""enrichment_retry scheduled job tests."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from module.mikan.parser import MikanRef
from module.scheduler.jobs.enrichment_retry import drain_pending


async def _seed_rss(db_session):
    from module.domain.models.rss import RSSItem
    # URL encodes Mikan identity so resolve_series_for_rss can derive ids.
    db_session.add(
        RSSItem(
            id=1,
            name="X",
            url="https://mikanani.me/RSS/Bangumi?bangumiId=99&subgroupid=7",
            aggregate=False,
            parser="mikan",
        )
    )
    await db_session.flush()


@pytest.mark.integration
async def test_drain_with_empty_queue_is_noop(db_session):
    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    summary = await drain_pending(db_session, mikan_resolver=resolver)

    assert summary == {"attempted": 0, "resolved": 0, "still_pending": 0}
    resolver.resolve.assert_not_called()


@pytest.mark.integration
async def test_drain_calls_resolver_per_pending_item(db_session):
    await _seed_rss(db_session)
    from module.services.pending_enrichment import PendingEnrichmentService
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h1", raw_name="x", homepage="u1",
                      url="m1", rss_id=1, published_at=None)
    await svc.enqueue(info_hash="h2", raw_name="y", homepage="u2",
                      url="m2", rss_id=1, published_at=None)
    await db_session.commit()

    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=None)

    summary = await drain_pending(db_session, mikan_resolver=resolver)

    assert summary["attempted"] == 2
    assert summary["resolved"] == 0
    assert summary["still_pending"] == 2
    assert resolver.resolve.await_count == 2


@pytest.mark.integration
async def test_drain_records_error_on_resolver_exception(db_session):
    await _seed_rss(db_session)
    from module.services.pending_enrichment import PendingEnrichmentService
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h1", raw_name="x", homepage="u",
                      url="m", rss_id=1, published_at=None)
    await db_session.commit()

    resolver = MagicMock()
    resolver.resolve = AsyncMock(side_effect=ConnectionError("503"))

    summary = await drain_pending(db_session, mikan_resolver=resolver)
    assert summary["still_pending"] == 1
    pending = await svc.list_pending()
    assert pending[0].attempt_count == 1
    assert "ConnectionError" in pending[0].last_error or "503" in pending[0].last_error


@pytest.mark.integration
async def test_drain_resolved_creates_bangumi_and_removes_row(db_session):
    """Resolved items create Series + Bangumi + Torrent and drop the pending row."""
    await _seed_rss(db_session)
    from module.services.pending_enrichment import PendingEnrichmentService

    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="h", raw_name="[G] Show 01", homepage="https://mikanani.me/Home/Episode/h",
        url="magnet:?xt=urn:btih:h", rss_id=1, published_at=None,
    )
    await db_session.commit()

    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=MikanRef(
        mikan_bangumi_id=99, mikan_subgroup_id=7,
        canonical_title="Show", poster_url=None,
    ))

    summary = await drain_pending(db_session, mikan_resolver=resolver)

    assert summary["resolved"] == 1
    assert summary["still_pending"] == 0
    # Pending row was deleted on success.
    assert await svc.list_pending() == []

    # Exactly one Bangumi + one Torrent were created.
    from module.domain.models.bangumi import Bangumi
    from module.domain.models.torrent import Torrent
    bangumi_count = (await db_session.execute(select(func.count(Bangumi.id)))).scalar()
    torrent_count = (await db_session.execute(select(func.count(Torrent.id)))).scalar()
    assert bangumi_count == 1
    assert torrent_count == 1


@pytest.mark.integration
async def test_drain_resolved_reuses_existing_bangumi(db_session):
    """Two pending rows for same (series, subgroup) share one Bangumi row."""
    await _seed_rss(db_session)
    from module.services.pending_enrichment import PendingEnrichmentService

    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="hA", raw_name="[G] Show 01", homepage="https://mikanani.me/Home/Episode/hA",
        url="magnet:?xt=urn:btih:hA", rss_id=1, published_at=None,
    )
    await svc.enqueue(
        info_hash="hB", raw_name="[G] Show 02", homepage="https://mikanani.me/Home/Episode/hB",
        url="magnet:?xt=urn:btih:hB", rss_id=1, published_at=None,
    )
    await db_session.commit()

    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=MikanRef(
        mikan_bangumi_id=99, mikan_subgroup_id=7,
        canonical_title="Show", poster_url=None,
    ))

    summary = await drain_pending(db_session, mikan_resolver=resolver)

    assert summary["resolved"] == 2
    assert await svc.list_pending() == []

    from module.domain.models.bangumi import Bangumi
    from module.domain.models.torrent import Torrent
    assert (await db_session.execute(select(func.count(Bangumi.id)))).scalar() == 1
    assert (await db_session.execute(select(func.count(Torrent.id)))).scalar() == 2
