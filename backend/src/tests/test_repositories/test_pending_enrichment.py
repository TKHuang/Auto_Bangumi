"""PendingTorrentEnrichmentRepository tests."""
import pytest
import pytest_asyncio

from module.domain.models.rss import RSSItem
from module.repositories.pending_enrichment import PendingTorrentEnrichmentRepository


@pytest_asyncio.fixture
async def rss_id(db_session):
    rss = RSSItem(name="test", url="https://example.com/rss", enabled=True)
    db_session.add(rss)
    await db_session.flush()
    await db_session.commit()
    return rss.id


@pytest_asyncio.fixture
async def pending_repo(db_session):
    return PendingTorrentEnrichmentRepository(db_session)


@pytest.mark.integration
class TestPendingEnrichmentEnqueue:
    async def test_enqueue_new_row(self, pending_repo, db_session, rss_id):
        row = await pending_repo.enqueue(
            info_hash="a", raw_name="[Group] X - 01",
            homepage="https://mikanani.me/Home/Episode/a",
            url="https://mikanani.me/Download/a.torrent",
            rss_id=rss_id,
        )
        await db_session.commit()
        assert row.info_hash == "a"
        assert row.attempt_count == 0
        assert row.last_error is None
        assert row.first_seen_at is not None

    async def test_enqueue_duplicate_is_noop(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(
            info_hash="b", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()
        row = await pending_repo.enqueue(
            info_hash="b", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()
        assert row.attempt_count == 0


@pytest.mark.integration
class TestPendingEnrichmentMarkAttempt:
    async def test_mark_attempt_increments(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(
            info_hash="c", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()

        await pending_repo.mark_attempt("c", error="timeout")
        await db_session.commit()
        await pending_repo.mark_attempt("c", error="503")
        await db_session.commit()

        row = await pending_repo.get("c")
        assert row.attempt_count == 2
        assert row.last_error == "503"
        assert row.last_attempt_at is not None


@pytest.mark.integration
class TestPendingEnrichmentDelete:
    async def test_delete_removes_row(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(
            info_hash="d", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()

        await pending_repo.delete("d")
        await db_session.commit()
        assert await pending_repo.get("d") is None


@pytest.mark.integration
class TestPendingEnrichmentList:
    async def test_list_all_ordered_by_first_seen(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(info_hash="e1", raw_name="A", homepage="h", url="u", rss_id=rss_id)
        await pending_repo.enqueue(info_hash="e2", raw_name="B", homepage="h", url="u", rss_id=rss_id)
        await pending_repo.enqueue(info_hash="e3", raw_name="C", homepage="h", url="u", rss_id=rss_id)
        await db_session.commit()

        rows = await pending_repo.list_all(limit=10)
        assert [r.info_hash for r in rows] == ["e1", "e2", "e3"]

    async def test_list_all_respects_limit(self, pending_repo, db_session, rss_id):
        for i in range(5):
            await pending_repo.enqueue(info_hash=f"l{i}", raw_name="A", homepage="h", url="u", rss_id=rss_id)
        await db_session.commit()

        rows = await pending_repo.list_all(limit=2)
        assert len(rows) == 2

    async def test_count(self, pending_repo, db_session, rss_id):
        for i in range(3):
            await pending_repo.enqueue(info_hash=f"n{i}", raw_name="A", homepage="h", url="u", rss_id=rss_id)
        await db_session.commit()
        assert await pending_repo.count() == 3
