"""ORM additions for Bangumi (series link, active flag, etc.) and Torrent
(mikan refs). Post-0008: official_title/title_raw/season are now @property shims."""
import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent


@pytest.mark.unit
def test_bangumi_has_new_columns():
    cols = {c.name for c in Bangumi.__table__.columns}
    assert "series_id" in cols
    assert "mikan_subgroup_id" in cols
    assert "active" in cols
    assert "path_override" in cols
    assert "observed_groups" in cols


@pytest.mark.unit
def test_bangumi_has_series_relationship():
    assert "series" in Bangumi.__mapper__.relationships


@pytest.mark.unit
def test_torrent_has_mikan_columns():
    cols = {c.name for c in Torrent.__table__.columns}
    assert "mikan_bangumi_id" in cols
    assert "mikan_subgroup_id" in cols


@pytest.mark.integration
async def test_bangumi_can_set_series_id_and_load_relationship(db_session):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    s = Series(
        mikan_bangumi_id=42,
        canonical_title="Demo",
        normalized_title="demo",
        season=1,
        root_path="/downloads/Demo",
        pending_review=False,
    )
    db_session.add(s)
    await db_session.flush()

    b = Bangumi(
        group_name="G",
        rss_link="",
        series_id=s.id,
        mikan_subgroup_id=370,
        active=True,
    )
    db_session.add(b)
    await db_session.flush()

    stmt = (
        select(Bangumi)
        .where(Bangumi.id == b.id)
        .options(selectinload(Bangumi.series))
    )
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.series.canonical_title == "Demo"
    assert refreshed.series_id == s.id
    assert refreshed.active is True
    assert refreshed.mikan_subgroup_id == 370
