"""enrichment_retry scheduled job tests."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.mikan.parser import MikanRef
from module.scheduler.jobs.enrichment_retry import drain_pending


async def _seed_rss(db_session):
    from module.domain.models.rss import RSSItem
    db_session.add(RSSItem(id=1, name="X", url="https://x", aggregate=False, parser="mikan"))
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
async def test_drain_marks_resolved_items_pending_for_now(db_session):
    """Until full pipeline reintegration (later task), resolved items stay
    queued with a clear marker."""
    await _seed_rss(db_session)
    from module.services.pending_enrichment import PendingEnrichmentService
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h", raw_name="x", homepage="u",
                      url="m", rss_id=1, published_at=None)
    await db_session.commit()

    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=MikanRef(
        mikan_bangumi_id=1, mikan_subgroup_id=2,
        canonical_title="T", poster_url=None,
    ))

    summary = await drain_pending(db_session, mikan_resolver=resolver)
    assert summary["resolved"] == 1
    pending = await svc.list_pending()
    assert pending[0].attempt_count == 1
    assert "resolved" in (pending[0].last_error or "").lower()
