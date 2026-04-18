"""IdentityResolver integration tests (spec §6.4)."""
import pytest

from module.mikan.parser import MikanRef
from module.repositories.series import SeriesRepository
from module.services.identity_resolver import IdentityResolver, ResolvedIdentity


@pytest.mark.integration
class TestIdentityResolverTier1:
    async def test_mikan_match_returns_existing_series(self, db_session):
        series_repo = SeriesRepository(db_session)
        existing = await series_repo.create({
            "mikan_bangumi_id": 3906,
            "canonical_title": "LasTame S2",
            "normalized_title": "lastame",
            "season": 2,
            "root_path": "/downloads/LasTame/Season 2",
        })
        await db_session.commit()

        resolver = IdentityResolver(series_repo=series_repo)
        result = await resolver.resolve(
            mikan_ref=MikanRef(mikan_bangumi_id=3906, mikan_subgroup_id=370,
                               canonical_title="LasTame S2", poster_url=None),
            normalized_title="different_but_ignored",
            season=2,
            cour_part=None,
            raw_title_for_root="LasTame Season2",
        )
        assert isinstance(result, ResolvedIdentity)
        assert result.series.id == existing.id
        assert result.tier == "mikan"
        assert result.newly_created is False

    async def test_mikan_miss_creates_new_series_from_mikan_ref(self, db_session):
        series_repo = SeriesRepository(db_session)
        resolver = IdentityResolver(series_repo=series_repo)

        result = await resolver.resolve(
            mikan_ref=MikanRef(mikan_bangumi_id=1234, mikan_subgroup_id=99,
                               canonical_title="葬送的芙莉蓮",
                               poster_url="/p/frieren.jpg"),
            normalized_title="葬送的芙莉莲",
            season=1,
            cour_part=None,
            raw_title_for_root="葬送的芙莉蓮",
        )
        await db_session.commit()

        assert result.series.mikan_bangumi_id == 1234
        assert result.series.canonical_title == "葬送的芙莉蓮"
        assert result.series.normalized_title == "葬送的芙莉莲"
        assert result.series.poster_url == "/p/frieren.jpg"
        assert result.tier == "mikan"
        assert result.newly_created is True
        assert result.series.pending_review is False


@pytest.mark.integration
class TestIdentityResolverTier2:
    async def test_no_mikan_ref_falls_back_to_existing_series(self, db_session):
        series_repo = SeriesRepository(db_session)
        existing = await series_repo.create({
            "canonical_title": "Fallback Show",
            "normalized_title": "fallbackshow",
            "season": 1,
            "root_path": "/downloads/fallbackshow",
        })
        await db_session.commit()

        resolver = IdentityResolver(series_repo=series_repo)
        result = await resolver.resolve(
            mikan_ref=None,
            normalized_title="fallbackshow",
            season=1,
            cour_part=None,
            raw_title_for_root="Fallback Show",
        )
        assert result.series.id == existing.id
        assert result.tier == "fallback"
        assert result.newly_created is False
        assert result.series.pending_review is False


@pytest.mark.integration
class TestIdentityResolverTier3:
    async def test_creates_pending_review_series_when_no_match(self, db_session):
        series_repo = SeriesRepository(db_session)
        resolver = IdentityResolver(series_repo=series_repo)

        result = await resolver.resolve(
            mikan_ref=None,
            normalized_title="unknownshow",
            season=1,
            cour_part=None,
            raw_title_for_root="Unknown Show",
        )
        await db_session.commit()

        assert result.series.pending_review is True
        assert result.tier == "pending_review"
        assert result.newly_created is True
        assert result.series.canonical_title == "Unknown Show"

    async def test_tier3_creates_new_pending_series_with_cross_source_candidates(
        self, db_session,
    ):
        """When a non-Mikan torrent's fallback key matches an existing Mikan
        series, IdentityResolver creates a NEW pending series and surfaces the
        Mikan candidate ID for manual review (spec §6.4 Tier 3)."""
        repo = SeriesRepository(db_session)
        # Existing Mikan series with the same fallback key
        mikan_row = await repo.create({
            "mikan_bangumi_id": 9999,
            "canonical_title": "Foo",
            "normalized_title": "foo",
            "season": 1,
            "cour_part": None,
            "root_path": "/downloads/Foo",
            "pending_review": False,
        })
        await db_session.commit()

        resolver = IdentityResolver(series_repo=repo)
        result = await resolver.resolve(
            mikan_ref=None,
            normalized_title="foo",
            season=1,
            cour_part=None,
            raw_title_for_root="Foo (nyaa)",
        )
        await db_session.commit()

        assert result.tier == "pending_review"
        assert result.newly_created is True
        assert result.series.id != mikan_row.id
        assert result.series.mikan_bangumi_id is None
        assert result.series.pending_review is True
        assert result.merge_candidates == [mikan_row.id]

        # Mikan row must NOT have been mutated
        refreshed = await repo.get_by_id(mikan_row.id)
        assert refreshed.pending_review is False
