import logging

from sqlalchemy import text
from sqlmodel import Session, SQLModel

from module.models import Bangumi, User

from .bangumi import BangumiDatabase
from .engine import engine as e
from .rss import RSSDatabase
from .torrent import TorrentDatabase
from .user import UserDatabase

logger = logging.getLogger(__name__)


class Database(Session):
    def __init__(self, engine=e):
        self.engine = engine
        super().__init__(engine)
        self.rss = RSSDatabase(self)
        self.torrent = TorrentDatabase(self)
        self.bangumi = BangumiDatabase(self)
        self.user = UserDatabase(self)

    def create_table(self):
        SQLModel.metadata.create_all(self.engine)
        # Migration for new columns in rssitem
        cursor = self.execute(text("PRAGMA table_info(rssitem)"))
        columns = [row[1] for row in cursor.fetchall()]
        if "last_update" not in columns:
            self.execute(text("ALTER TABLE rssitem ADD COLUMN last_update TEXT"))
            self.execute(text("ALTER TABLE rssitem ADD COLUMN last_status TEXT"))
            self.execute(text("ALTER TABLE rssitem ADD COLUMN last_error TEXT"))
            self.commit()
        
        # Migration for bangumi table - ensure rss_id column exists
        cursor = self.execute(text("PRAGMA table_info(bangumi)"))
        bangumi_columns = [row[1] for row in cursor.fetchall()]
        
        if "rss_id" not in bangumi_columns:
            logger.info("[Migration] Adding rss_id column to bangumi table")
            self.execute(text("ALTER TABLE bangumi ADD COLUMN rss_id INTEGER REFERENCES rssitem(id)"))
            self.commit()

        # Migration for pending_review columns in bangumi
        if "pending_review" not in bangumi_columns:
            logger.info("[Migration] Adding pending_review column to bangumi table")
            self.execute(text("ALTER TABLE bangumi ADD COLUMN pending_review INTEGER DEFAULT 0"))
            self.commit()

        if "global_filter_matches" not in bangumi_columns:
            logger.info("[Migration] Adding global_filter_matches column to bangumi table")
            self.execute(text("ALTER TABLE bangumi ADD COLUMN global_filter_matches TEXT"))
            self.commit()

        # Migration for new hash column in torrent
        cursor = self.execute(text("PRAGMA table_info(torrent)"))
        torrent_columns = [row[1] for row in cursor.fetchall()]
        if "hash" not in torrent_columns:
            self.execute(text("ALTER TABLE torrent ADD COLUMN hash TEXT"))
            self.commit()

        # Migration for rename tracking columns in torrent
        if "renamed_at" not in torrent_columns:
            logger.info("[Migration] Adding renamed_at column to torrent table")
            self.execute(text("ALTER TABLE torrent ADD COLUMN renamed_at TEXT"))
            self.commit()
        if "renamed_file_count" not in torrent_columns:
            logger.info("[Migration] Adding renamed_file_count column to torrent table")
            self.execute(text("ALTER TABLE torrent ADD COLUMN renamed_file_count INTEGER"))
            self.commit()
        
        # Migration for group_name: update NULL/empty values to "Unknown"
        # This ensures composite key (title_raw, season, group_name) works correctly
        result = self.execute(
            text("UPDATE bangumi SET group_name = 'Unknown' WHERE group_name IS NULL OR group_name = ''")
        )
        if result.rowcount > 0:
            logger.info(f"[Migration] Updated {result.rowcount} bangumi records with NULL/empty group_name to 'Unknown'")
            self.commit()

    def drop_table(self):
        SQLModel.metadata.drop_all(self.engine)

    def migrate(self):
        # Run migration online
        bangumi_data = self.bangumi.search_all()
        user_data = self.exec("SELECT * FROM user").all()
        readd_bangumi = []
        for bangumi in bangumi_data:
            dict_data = bangumi.dict()
            del dict_data["id"]
            readd_bangumi.append(Bangumi(**dict_data))
        self.drop_table()
        self.create_table()
        self.commit()
        bangumi_data = self.bangumi.search_all()
        self.bangumi.add_all(readd_bangumi)
        self.add(User(**user_data[0]))
        self.commit()
