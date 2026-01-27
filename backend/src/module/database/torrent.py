import logging

from sqlmodel import Session, select

from module.models import Torrent

logger = logging.getLogger(__name__)


class TorrentDatabase:
    def __init__(self, session: Session):
        self.session = session

    def add(self, data: Torrent):
        self.session.add(data)
        self.session.commit()
        self.session.refresh(data)
        logger.debug(f"Insert {data.name} in database.")

    def add_all(self, datas: list[Torrent]):
        self.session.add_all(datas)
        self.session.commit()
        logger.debug(f"Insert {len(datas)} torrents in database.")

    def update(self, data: Torrent):
        self.session.add(data)
        self.session.commit()
        self.session.refresh(data)
        logger.debug(f"Update {data.name} in database.")

    def update_all(self, datas: list[Torrent]):
        self.session.add_all(datas)
        self.session.commit()

    def update_one_user(self, data: Torrent):
        self.session.add(data)
        self.session.commit()
        self.session.refresh(data)
        logger.debug(f"Update {data.name} in database.")

    def search(self, _id: int) -> Torrent:
        return self.session.exec(select(Torrent).where(Torrent.id == _id)).first()

    def search_all(self) -> list[Torrent]:
        return self.session.exec(select(Torrent)).all()

    def search_rss(self, rss_id: int) -> list[Torrent]:
        return self.session.exec(select(Torrent).where(Torrent.rss_id == rss_id)).all()

    def search_by_bangumi_id(self, bangumi_id: int) -> list[Torrent]:
        """Get all torrents for a bangumi by its ID."""
        return self.session.exec(
            select(Torrent).where(Torrent.bangumi_id == bangumi_id)
        ).all()

    def search_by_bangumi_id_with_homepage(self, bangumi_id: int) -> Torrent | None:
        """Find a torrent with homepage URL for a given bangumi_id.

        Args:
            bangumi_id: The bangumi ID to search for.

        Returns:
            Torrent with homepage if found, None otherwise.
        """
        statement = select(Torrent).where(
            Torrent.bangumi_id == bangumi_id,
            Torrent.homepage.is_not(None),
            Torrent.homepage != "",
        )
        return self.session.exec(statement).first()

    def check_new(self, torrents_list: list[Torrent]) -> list[Torrent]:
        new_torrents = []
        old_torrents = self.search_all()
        old_urls = [t.url for t in old_torrents]
        for torrent in torrents_list:
            if torrent.url not in old_urls:
                new_torrents.append(torrent)
        return new_torrents

    def check_new_by_hash(self, torrents_list: list[Torrent]) -> list[Torrent]:
        """Check for new torrents by hash to prevent duplicates.

        Uses hash as the unique identifier instead of URL, which is more reliable
        for detecting duplicate torrents from different sources (aggregate vs season RSS).

        Args:
            torrents_list: List of torrents to check.

        Returns:
            List of torrents that don't exist in the database (by hash).
        """
        new_torrents = []
        old_torrents = self.search_all()
        # Build set of existing hashes (None hashes are treated as unique)
        old_hashes = {t.hash for t in old_torrents if t.hash is not None}

        for torrent in torrents_list:
            # If torrent has no hash, treat as new (edge case for old data)
            if torrent.hash is None:
                new_torrents.append(torrent)
            # If hash not in database, it's new
            elif torrent.hash not in old_hashes:
                new_torrents.append(torrent)
            else:
                logger.debug(
                    f"[Database] Skipping duplicate torrent (hash exists): {torrent.name}"
                )

        return new_torrents
