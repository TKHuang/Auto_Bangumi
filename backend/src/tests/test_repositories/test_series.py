"""SeriesRepository tests (spec §6.4 Tier 1 / Tier 2 identity lookup)."""
import pytest
import pytest_asyncio

from module.repositories.series import SeriesRepository


@pytest_asyncio.fixture
async def series_repo(db_session):
    return SeriesRepository(db_session)


@pytest.mark.integration
class TestSeriesCreate:
    async def test_create_minimal(self, series_repo, db_session):
        s = await series_repo.create({
            "canonical_title": "葬送的芙莉蓮",
            "normalized_title": "葬送的芙莉莲",
            "season": 1,
            "root_path": "/downloads/葬送的芙莉蓮",
        })
        await db_session.commit()
        assert s.id is not None
        assert s.canonical_title == "葬送的芙莉蓮"
        assert s.mikan_bangumi_id is None
        assert s.pending_review is False
        assert s.version == 1

    async def test_create_with_mikan_id(self, series_repo, db_session):
        s = await series_repo.create({
            "mikan_bangumi_id": 3906,
            "canonical_title": "身为悲剧始作俑者...",
            "normalized_title": "悲剧始作俑者",
            "season": 2,
            "root_path": "/downloads/LasTame/Season 2",
        })
        await db_session.commit()
        assert s.mikan_bangumi_id == 3906


@pytest.mark.integration
class TestSeriesGetByMikanId:
    async def test_get_by_mikan_id_hit(self, series_repo, db_session):
        await series_repo.create({
            "mikan_bangumi_id": 3906, "canonical_title": "X",
            "normalized_title": "x", "season": 1, "root_path": "/x",
        })
        await db_session.commit()

        found = await series_repo.get_by_mikan_id(3906)
        assert found is not None
        assert found.mikan_bangumi_id == 3906

    async def test_get_by_mikan_id_miss(self, series_repo):
        assert await series_repo.get_by_mikan_id(99999) is None


@pytest.mark.integration
class TestSeriesGetByFallback:
    async def test_hit(self, series_repo, db_session):
        await series_repo.create({
            "canonical_title": "Y", "normalized_title": "y",
            "season": 2, "cour_part": "latter", "root_path": "/y",
        })
        await db_session.commit()
        assert await series_repo.get_by_fallback("y", 2, "latter") is not None

    async def test_miss_wrong_season(self, series_repo, db_session):
        await series_repo.create({
            "canonical_title": "Y", "normalized_title": "y",
            "season": 2, "root_path": "/y",
        })
        await db_session.commit()
        assert await series_repo.get_by_fallback("y", 1, None) is None

    async def test_miss_wrong_cour(self, series_repo, db_session):
        await series_repo.create({
            "canonical_title": "Y", "normalized_title": "y",
            "season": 2, "cour_part": "latter", "root_path": "/y",
        })
        await db_session.commit()
        assert await series_repo.get_by_fallback("y", 2, None) is None


@pytest.mark.integration
class TestSeriesUniqueness:
    async def test_duplicate_mikan_id_rejected(self, series_repo, db_session):
        import sqlalchemy.exc

        await series_repo.create({
            "mikan_bangumi_id": 100, "canonical_title": "A",
            "normalized_title": "a1", "season": 1, "root_path": "/a",
        })
        await db_session.commit()

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await series_repo.create({
                "mikan_bangumi_id": 100, "canonical_title": "A dup",
                "normalized_title": "a2", "season": 1, "root_path": "/a2",
            })
            await db_session.commit()

    async def test_duplicate_fallback_key_rejected(self, series_repo, db_session):
        import sqlalchemy.exc

        await series_repo.create({
            "canonical_title": "B", "normalized_title": "b",
            "season": 1, "cour_part": None, "root_path": "/b",
        })
        await db_session.commit()

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await series_repo.create({
                "canonical_title": "B2", "normalized_title": "b",
                "season": 1, "cour_part": None, "root_path": "/b2",
            })
            await db_session.commit()


@pytest.mark.integration
class TestSeriesFindCrossSourceCandidates:
    async def test_finds_mikan_series_with_matching_fallback(self, series_repo, db_session):
        await series_repo.create({
            "mikan_bangumi_id": 3906, "canonical_title": "X Mikan",
            "normalized_title": "x", "season": 2, "cour_part": None,
            "root_path": "/x",
        })
        await db_session.commit()

        candidates = await series_repo.find_possible_cross_source_merge("x", 2, None)
        assert len(candidates) == 1
        assert candidates[0].mikan_bangumi_id == 3906

    async def test_returns_empty_when_no_match(self, series_repo):
        assert await series_repo.find_possible_cross_source_merge("none", 1, None) == []
