"""Integration tests for database persistence bugs (TDD RED phase).

These tests demonstrate bugs where database operations return success
but data is not actually committed. Tests should FAIL until fixes are applied.
"""

import pytest
from sqlmodel import Session, select, SQLModel

from module.manager.torrent import TorrentManager
from module.models.bangumi import Bangumi, BangumiUpdate
from module.models.rss import RSSItem
from module.rss.engine import RSSEngine


class TestPersistenceBugs:
    """Tests demonstrating database persistence bugs."""

    @pytest.mark.integration
    def test_add_rss_persists_after_session_close(self, in_memory_engine):
        """Test that add_rss() persists data after session closes.

        Expected to FAIL until bug is fixed.
        Bug: add_rss() returns success but doesn't call commit()
        """
        SQLModel.metadata.create_all(in_memory_engine)

        with RSSEngine(in_memory_engine) as engine:
            result = engine.add_rss(
                rss_link="https://mikanani.me/RSS/Test?id=persist001",
                name="Persistence Test RSS",
                aggregate=False,
                parser="mikan",
            )
            assert result.status is True, f"add_rss should return success: {result.msg_en}"

        with Session(in_memory_engine) as fresh_session:
            statement = select(RSSItem).where(RSSItem.name == "Persistence Test RSS")
            rss_item = fresh_session.exec(statement).first()

            assert rss_item is not None, (
                "RSS should persist after session close. "
                "Bug: add_rss() doesn't commit."
            )

    @pytest.mark.integration
    def test_add_aggregate_rss_persists(self, in_memory_engine):
        """Test aggregate RSS persistence. Expected to FAIL.

        Bug: add_rss() returns success but doesn't call commit()
        """
        SQLModel.metadata.create_all(in_memory_engine)

        with RSSEngine(in_memory_engine) as engine:
            result = engine.add_rss(
                rss_link="https://mikanani.me/RSS/MyBangumi?token=persist002",
                name="Aggregate Persistence Test",
                aggregate=True,
                parser="mikan",
            )
            assert result.status is True

        with Session(in_memory_engine) as fresh_session:
            statement = select(RSSItem).where(
                RSSItem.name == "Aggregate Persistence Test"
            )
            rss_item = fresh_session.exec(statement).first()

            assert rss_item is not None, "Aggregate RSS should persist."

    @pytest.mark.integration
    def test_update_rule_persists_after_session_close(self, in_memory_engine):
        """Test update_rule() persistence. Expected to FAIL.

        Bug: update_rule() returns success but doesn't call commit()
        
        This test directly calls the database update method to avoid
        TorrentManager's DownloadClient dependency.
        """
        from module.database import Database

        SQLModel.metadata.create_all(in_memory_engine)

        with Session(in_memory_engine) as setup_session:
            bangumi = Bangumi(
                id=1,
                official_title="Original Title",
                title_raw="[Group] Original Title",
                season=1,
                group_name="TestGroup",
                filter="720",
                rss_link="https://example.com/rss",
                added=True,
                year=None,
                season_raw=None,
                dpi=None,
                source=None,
                subtitle=None,
                poster_link=None,
                rule_name=None,
                save_path=None,
                deleted=False,
            )
            setup_session.add(bangumi)
            setup_session.commit()

        new_filter = "1080,HEVC"
        with Database(in_memory_engine) as db:
            update_data = BangumiUpdate(
                official_title="Original Title",
                title_raw="[Group] Original Title",
                season=1,
                group_name="TestGroup",
                filter=new_filter,
                rss_link="https://example.com/rss",
                year=None,
                season_raw=None,
                dpi=None,
                source=None,
                subtitle=None,
                poster_link=None,
                rule_name=None,
                save_path=None,
                deleted=False,
            )
            db.bangumi.update(update_data, 1)

        with Session(in_memory_engine) as fresh_session:
            statement = select(Bangumi).where(Bangumi.id == 1)
            bangumi = fresh_session.exec(statement).first()

            assert bangumi is not None
            assert bangumi.filter == new_filter, (
                f"Filter should be '{new_filter}' not '{bangumi.filter}'. "
                "Bug: update() doesn't commit."
            )

    @pytest.mark.integration
    def test_add_rss_with_different_parsers_persist(self, in_memory_engine):
        """Test that add_rss() persists with different parser types.

        Expected to FAIL until bug is fixed.
        """
        SQLModel.metadata.create_all(in_memory_engine)

        parsers = ["mikan", "raw", "tmdb"]
        for parser_type in parsers:
            with RSSEngine(in_memory_engine) as engine:
                result = engine.add_rss(
                    rss_link=f"https://example.com/rss/{parser_type}",
                    name=f"Parser Test {parser_type}",
                    aggregate=False,
                    parser=parser_type,
                )
                assert result.status is True

        with Session(in_memory_engine) as fresh_session:
            for parser_type in parsers:
                statement = select(RSSItem).where(
                    RSSItem.name == f"Parser Test {parser_type}"
                )
                rss_item = fresh_session.exec(statement).first()
                assert rss_item is not None, (
                    f"RSS with parser '{parser_type}' should persist. "
                    "Bug: add_rss() doesn't commit."
                )

    @pytest.mark.integration
    def test_update_rule_multiple_fields_persist(self, in_memory_engine):
        """Test update_rule() persists multiple field changes.

        Expected to FAIL until bug is fixed.
        
        This test directly calls the database update method to avoid
        TorrentManager's DownloadClient dependency.
        """
        from module.database import Database

        SQLModel.metadata.create_all(in_memory_engine)

        with Session(in_memory_engine) as setup_session:
            bangumi = Bangumi(
                id=2,
                official_title="Original Title",
                title_raw="[Group] Original Title",
                season=1,
                group_name="TestGroup",
                filter="720",
                rss_link="https://example.com/rss",
                added=True,
                dpi="1080P",
                source="WebRip",
                year=None,
                season_raw=None,
                subtitle=None,
                poster_link=None,
                rule_name=None,
                save_path=None,
                deleted=False,
            )
            setup_session.add(bangumi)
            setup_session.commit()

        with Database(in_memory_engine) as db:
            update_data = BangumiUpdate(
                official_title="Updated Title",
                title_raw="[NewGroup] Updated Title",
                season=2,
                group_name="NewGroup",
                filter="1080,HEVC",
                rss_link="https://example.com/rss",
                dpi="2160P",
                source="BluRay",
                year=None,
                season_raw=None,
                subtitle=None,
                poster_link=None,
                rule_name=None,
                save_path=None,
                deleted=False,
            )
            db.bangumi.update(update_data, 2)

        with Session(in_memory_engine) as fresh_session:
            statement = select(Bangumi).where(Bangumi.id == 2)
            bangumi = fresh_session.exec(statement).first()

            assert bangumi is not None
            assert bangumi.official_title == "Updated Title"
            assert bangumi.season == 2
            assert bangumi.filter == "1080,HEVC"
            assert bangumi.dpi == "2160P"
            assert bangumi.source == "BluRay"
