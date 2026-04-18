"""New BangumiRepository helpers for series-driven identity (Plan 04)."""
import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.repositories.bangumi import BangumiRepository


async def _seed_series(db_session, **kw) -> Series:
    s = Series(
        canonical_title=kw.pop("canonical_title", "S"),
        normalized_title=kw.pop("normalized_title", "s"),
        season=kw.pop("season", 1),
        root_path=kw.pop("root_path", "/downloads/S"),
        pending_review=False,
        **kw,
    )
    db_session.add(s)
    await db_session.flush()
    return s


_bangumi_counter = 0


async def _seed_bangumi(db_session, *, series_id, **overrides) -> Bangumi:
    global _bangumi_counter
    _bangumi_counter += 1
    # Use unique group_name per call to avoid the (official_title, season, group_name) UNIQUE constraint.
    data = dict(
        official_title="legacy",
        title_raw="legacy",
        season=1,
        group_name=f"G{_bangumi_counter}",
        rss_link="",
        series_id=series_id,
        active=True,
    )
    data.update(overrides)
    b = Bangumi(**data)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.mark.integration
async def test_get_by_series_and_subgroup_finds_match(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=1)
    b = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=370)

    hit = await repo.get_by_series_and_subgroup(s.id, 370)
    assert hit is not None and hit.id == b.id


@pytest.mark.integration
async def test_get_by_series_and_subgroup_excludes_deleted(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=2)
    await _seed_bangumi(
        db_session, series_id=s.id, mikan_subgroup_id=99, deleted=True,
    )

    assert await repo.get_by_series_and_subgroup(s.id, 99) is None


@pytest.mark.integration
async def test_get_by_series_and_rss_for_fallback_identity(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, normalized_title="t1")
    await _seed_bangumi(
        db_session, series_id=s.id, mikan_subgroup_id=None, rss_id=None,
    )
    # rss_id None should not match — fallback identity needs a real rss_id
    assert await repo.get_by_series_and_rss(s.id, None) is None


@pytest.mark.integration
async def test_list_by_series_returns_only_undeleted(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=3)
    b1 = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=1)
    await _seed_bangumi(
        db_session, series_id=s.id, mikan_subgroup_id=2, deleted=True,
    )
    rows = await repo.list_by_series(s.id)
    assert {b.id for b in rows} == {b1.id}


@pytest.mark.integration
async def test_get_by_series_and_rss_returns_undeleted_fallback_match(db_session):
    """Positive + negative paths for fallback identity:
    - When mikan_subgroup_id IS NULL and rss_id matches -> returns row.
    - When mikan_subgroup_id is set -> NOT a fallback row, returns None for that sibling.
    """
    from module.domain.models.rss import RSSItem

    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, normalized_title="fallback")

    rss = RSSItem(name="r", url="https://example.com/rss", parser="mikan")
    db_session.add(rss)
    await db_session.flush()

    # Positive: fallback row (mikan_subgroup_id IS NULL)
    fallback_b = await _seed_bangumi(
        db_session,
        series_id=s.id,
        rss_id=rss.id,
        mikan_subgroup_id=None,
    )
    # Negative sibling: same series + rss but mikan_subgroup_id is set ->
    # should NOT be returned by get_by_series_and_rss.
    await _seed_bangumi(
        db_session,
        series_id=s.id,
        rss_id=rss.id,
        mikan_subgroup_id=42,
    )

    hit = await repo.get_by_series_and_rss(s.id, rss.id)
    assert hit is not None
    assert hit.id == fallback_b.id
    assert hit.mikan_subgroup_id is None


@pytest.mark.integration
async def test_deactivate_siblings_in_series(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=4)
    b_keep = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=1)
    b_other = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=2)
    await repo.deactivate_siblings_in_series(s.id, except_bangumi_id=b_keep.id)
    await db_session.refresh(b_keep)
    await db_session.refresh(b_other)
    assert b_keep.active is True
    assert b_other.active is False
