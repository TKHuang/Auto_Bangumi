import logging

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from module.models import Torrent

logger = logging.getLogger(__name__)


class TorrentDatabase:
    def __init__(self, session: Session):
        self.session = session

    def add(self, data: Torrent):
        self.session.add(data)
        logger.debug(f"Insert {data.name} in database.")

    def add_all(self, datas: list[Torrent]):
        self.session.add_all(datas)
        logger.debug(f"Insert {len(datas)} torrents in database.")

    def add_all_or_ignore(self, datas: list[Torrent]) -> int:
        if not datas:
            return 0
        inserted = 0
        for data in datas:
            stmt = sqlite_insert(Torrent).values(
                bangumi_id=data.bangumi_id,
                rss_id=data.rss_id,
                name=data.name,
                url=data.url,
                homepage=data.homepage,
                downloaded=data.downloaded,
                hash=data.hash,
                renamed_at=data.renamed_at,
                renamed_file_count=data.renamed_file_count,
                pikpak_cloud_path=data.pikpak_cloud_path,
            ).on_conflict_do_nothing(
                index_elements=["hash", "bangumi_id"],
            )
            result = self.session.execute(stmt)
            if result.rowcount > 0:
                inserted += 1
        logger.debug(f"Insert-or-ignore {inserted}/{len(datas)} torrents in database.")
        return inserted

    def update(self, data: Torrent):
        self.session.add(data)
        logger.debug(f"Update {data.name} in database.")

    def update_all(self, datas: list[Torrent]):
        self.session.add_all(datas)

    def update_one_user(self, data: Torrent):
        self.session.add(data)
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

    def search_by_hash(self, hash: str) -> Torrent | None:
        """Find torrent by hash.

        Args:
            hash: The torrent hash to search for.

        Returns:
            Torrent if found, None otherwise.
        """
        return self.session.exec(select(Torrent).where(Torrent.hash == hash)).first()

    def clear_rename_status(self, bangumi_id: int) -> int:
        """Clear rename status for all torrents of a bangumi.

        Resets renamed_at and renamed_file_count to None for all torrents
        belonging to the specified bangumi, forcing them to be re-processed
        in the next rename cycle.

        Args:
            bangumi_id: The bangumi ID whose torrents should be reset.

        Returns:
            Count of torrents that were reset.
        """
        torrents = self.search_by_bangumi_id(bangumi_id)
        count = 0
        for t in torrents:
            if t.renamed_at is not None:
                t.renamed_at = None
                t.renamed_file_count = None
                count += 1
        return count

    def get_unrenamed_hashes(self) -> set[str]:
        """Get hashes of torrents that haven't been renamed yet.

        Returns:
            Set of torrent hashes (lowercase) where renamed_at is None.
        """
        statement = select(Torrent).where(Torrent.renamed_at.is_(None))
        torrents = self.session.exec(statement).all()
        return {t.hash.lower() for t in torrents if t.hash}

    def mark_downloaded(self, hash: str, bangumi_id: int, save_path: str | None = None) -> int:
        # Direct SQL UPDATE — bypasses ORM to avoid StaleDataError after add_all_or_ignore
        values: dict = {"downloaded": True}
        if save_path is not None:
            values["pikpak_cloud_path"] = save_path
        stmt = (
            update(Torrent)
            .where(Torrent.hash == hash, Torrent.bangumi_id == bangumi_id)
            .values(**values)
        )
        result = self.session.execute(stmt)
        rows = result.rowcount  # type: ignore[union-attr]
        logger.debug(f"[Database] mark_downloaded hash={hash[:12]}... bangumi_id={bangumi_id} save_path={save_path} -> {rows} row(s)")
        return rows
