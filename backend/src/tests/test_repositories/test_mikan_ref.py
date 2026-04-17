"""MikanEpisodeRefRepository tests."""
import pytest
import pytest_asyncio

from module.repositories.mikan_ref import MikanEpisodeRefRepository


@pytest_asyncio.fixture
async def mikan_repo(db_session):
    return MikanEpisodeRefRepository(db_session)


@pytest.mark.integration
class TestMikanRefUpsert:
    async def test_upsert_inserts_new_row(self, mikan_repo, db_session):
        ref = await mikan_repo.upsert(
            info_hash="abc123",
            parse_status="ok",
            mikan_bangumi_id=3906,
            mikan_subgroup_id=370,
            canonical_title="LasTame S2",
            poster_url="posters/730372c2.jpg",
        )
        await db_session.commit()
        assert ref.info_hash == "abc123"
        assert ref.parse_status == "ok"
        assert ref.attempt_count == 1

    async def test_upsert_updates_existing_row(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="x", parse_status="failed", last_error="timeout")
        await db_session.commit()

        ref = await mikan_repo.upsert(
            info_hash="x",
            parse_status="ok",
            mikan_bangumi_id=100,
            mikan_subgroup_id=50,
        )
        await db_session.commit()

        assert ref.parse_status == "ok"
        assert ref.mikan_bangumi_id == 100
        assert ref.attempt_count == 2
        assert ref.last_error is None

    async def test_upsert_increments_attempts_on_repeated_failure(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="y", parse_status="failed", last_error="timeout")
        await db_session.commit()
        await mikan_repo.upsert(info_hash="y", parse_status="failed", last_error="timeout")
        await db_session.commit()
        ref = await mikan_repo.upsert(info_hash="y", parse_status="failed", last_error="503")
        await db_session.commit()

        assert ref.attempt_count == 3
        assert ref.last_error == "503"


@pytest.mark.integration
class TestMikanRefGet:
    async def test_get_hit(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="h", parse_status="ok", mikan_bangumi_id=1)
        await db_session.commit()
        assert (await mikan_repo.get("h")).parse_status == "ok"

    async def test_get_miss(self, mikan_repo):
        assert await mikan_repo.get("nothere") is None


@pytest.mark.integration
class TestMikanRefHealth:
    async def test_last_success_at(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="a", parse_status="ok", mikan_bangumi_id=1)
        await db_session.commit()
        assert await mikan_repo.last_success_at() is not None

    async def test_last_success_at_none_if_all_failed(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="f1", parse_status="failed")
        await mikan_repo.upsert(info_hash="f2", parse_status="failed")
        await db_session.commit()
        assert await mikan_repo.last_success_at() is None

    async def test_consecutive_failures(self, mikan_repo, db_session):
        for i in range(3):
            await mikan_repo.upsert(info_hash=f"z{i}", parse_status="failed")
        await db_session.commit()
        assert await mikan_repo.consecutive_failures() == 3

    async def test_consecutive_failures_resets_on_success(self, mikan_repo, db_session):
        for i in range(3):
            await mikan_repo.upsert(info_hash=f"z{i}", parse_status="failed")
        await db_session.commit()

        await mikan_repo.upsert(info_hash="ok1", parse_status="ok", mikan_bangumi_id=1)
        await db_session.commit()
        assert await mikan_repo.consecutive_failures() == 0
