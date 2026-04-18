"""Rename target collisions are reported, not crashed (spec §10.3)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.services.renamer import RenamerService


class _FakeFile:
    def __init__(self, name):
        self.name = name


class _FakeTorrentInfo:
    def __init__(self, *, name, hash, files, save_path="/dl"):
        self.name = name
        self.hash = hash
        self.files = files
        self.save_path = save_path


@pytest.mark.integration
async def test_rename_records_conflict_when_target_exists(db_session, monkeypatch):
    s = Series(
        canonical_title="Demo", normalized_title="demo", season=1,
        root_path="/dl/Demo", pending_review=False, mikan_bangumi_id=1,
    )
    db_session.add(s)
    await db_session.flush()
    bangumi = Bangumi(
        group_name="G", rss_link="", series_id=s.id, mikan_subgroup_id=1,
        active=True,
    )
    db_session.add(bangumi)
    await db_session.flush()
    torrent = Torrent(
        name="src", url="u", hash="hash-new", bangumi_id=bangumi.id,
    )
    db_session.add(torrent)
    await db_session.flush()

    downloader = MagicMock()
    downloader.torrents_info = AsyncMock(return_value=[
        _FakeTorrentInfo(
            name="src", hash="hash-new",
            files=[_FakeFile("Demo S01E01.mkv")],
        ),
    ])
    downloader.torrents_rename_file = AsyncMock(return_value=False)

    svc = RenamerService(db_session)
    monkeypatch.setattr(svc, "_target_exists_with_different_hash",
                        MagicMock(return_value=True))

    result = await svc.rename_all(downloader)

    await db_session.refresh(torrent)
    assert torrent.renamed_at is None
    assert any(r.get("conflict") for r in result), result
