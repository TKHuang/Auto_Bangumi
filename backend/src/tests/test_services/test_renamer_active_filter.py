"""Inactive bangumi must not reach the renamer."""
import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.torrent import TorrentRepository


@pytest.mark.integration
async def test_get_unrenamed_filters_inactive_bangumi(db_session):
    s = Series(
        canonical_title="X", normalized_title="x", season=1,
        root_path="/p/X", pending_review=False,
    )
    db_session.add(s)
    await db_session.flush()

    active = Bangumi(
        group_name="A", rss_link="", series_id=s.id, active=True,
    )
    inactive = Bangumi(
        group_name="B", rss_link="", series_id=s.id, mikan_subgroup_id=2,
        active=False,
    )
    db_session.add_all([active, inactive])
    await db_session.flush()

    db_session.add_all([
        Torrent(name="ta", url="u", hash="ha", bangumi_id=active.id),
        Torrent(name="ti", url="u", hash="hi", bangumi_id=inactive.id),
    ])
    await db_session.flush()

    repo = TorrentRepository(db_session)
    rows = await repo.get_unrenamed()
    ids = {t.id for t in rows}
    assert any(t.bangumi_id == active.id for t in rows)
    assert not any(t.bangumi_id == inactive.id for t in rows)
