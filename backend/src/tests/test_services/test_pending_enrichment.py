"""PendingEnrichmentService tests."""
import pytest

from module.domain.models.rss import RSSItem
from module.services.pending_enrichment import PendingEnrichmentService


async def _seed_rss(session) -> None:
    """Insert a minimal RSSItem row so FK constraint is satisfied."""
    session.add(
        RSSItem(id=1, name="Test Feed", url="https://mikanani.me", aggregate=False, parser="mikan")
    )
    await session.flush()


@pytest.mark.integration
async def test_enqueue_then_list(db_session):
    await _seed_rss(db_session)
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="hash-1",
        raw_name="[Group] Title",
        homepage="https://mikanani.me/Home/Episode/hash-1",
        url="magnet:?",
        rss_id=1,
        published_at=None,
    )
    pending = await svc.list_pending()
    assert len(pending) == 1
    assert pending[0].info_hash == "hash-1"


@pytest.mark.integration
async def test_enqueue_idempotent_on_same_hash(db_session):
    await _seed_rss(db_session)
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="h", raw_name="x", homepage=None, url="u", rss_id=1, published_at=None
    )
    await svc.enqueue(
        info_hash="h", raw_name="x", homepage=None, url="u", rss_id=1, published_at=None
    )
    pending = await svc.list_pending()
    assert len(pending) == 1


@pytest.mark.integration
async def test_mark_attempted_increments_count(db_session):
    await _seed_rss(db_session)
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="h", raw_name="x", homepage=None, url="u", rss_id=1, published_at=None
    )
    await svc.mark_attempted("h", error="503 Service Unavailable")
    pending = await svc.list_pending()
    assert pending[0].attempt_count == 1
    assert pending[0].last_error == "503 Service Unavailable"
    assert pending[0].last_attempt_at is not None


@pytest.mark.integration
async def test_remove_by_hash(db_session):
    await _seed_rss(db_session)
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="h", raw_name="x", homepage=None, url="u", rss_id=1, published_at=None
    )
    await svc.remove("h")
    assert await svc.list_pending() == []
