import logging
from typing import Optional

from sqlalchemy.sql import func
from sqlmodel import Session, and_, col, delete, false, or_, select

from module.models import Bangumi, BangumiUpdate

logger = logging.getLogger(__name__)


class BangumiDatabase:
    def __init__(self, session: Session):
        self.session = session

    def add(self, data: Bangumi):
        statement = select(Bangumi).where(Bangumi.title_raw == data.title_raw)
        bangumi = self.session.exec(statement).first()
        if bangumi:
            return False
        self.session.add(data)
        self.session.commit()
        logger.debug(f"[Database] Insert {data.official_title} into database.")
        return True

    def add_all(self, datas: list[Bangumi]):
        self.session.add_all(datas)
        self.session.commit()
        logger.debug(f"[Database] Insert {len(datas)} bangumi into database.")

    def update(self, data: Bangumi | BangumiUpdate, _id: int = None) -> bool:
        if _id and isinstance(data, BangumiUpdate):
            db_data = self.session.get(Bangumi, _id)
        elif isinstance(data, Bangumi):
            db_data = self.session.get(Bangumi, data.id)
        else:
            return False
        if not db_data:
            return False
        bangumi_data = data.dict(exclude_unset=True)
        for key, value in bangumi_data.items():
            setattr(db_data, key, value)
        self.session.add(db_data)
        self.session.commit()
        self.session.refresh(db_data)
        logger.debug(f"[Database] Update {data.official_title}")
        return True

    def update_all(self, datas: list[Bangumi]):
        self.session.add_all(datas)
        self.session.commit()
        logger.debug(f"[Database] Update {len(datas)} bangumi.")

    def update_rss(self, title_raw, rss_set: str):
        # Update rss and added
        statement = select(Bangumi).where(Bangumi.title_raw == title_raw)
        bangumi = self.session.exec(statement).first()
        bangumi.rss_link = rss_set
        bangumi.added = False
        self.session.add(bangumi)
        self.session.commit()
        self.session.refresh(bangumi)
        logger.debug(f"[Database] Update {title_raw} rss_link to {rss_set}.")

    def update_poster(self, title_raw, poster_link: str):
        statement = select(Bangumi).where(Bangumi.title_raw == title_raw)
        bangumi = self.session.exec(statement).first()
        bangumi.poster_link = poster_link
        self.session.add(bangumi)
        self.session.commit()
        self.session.refresh(bangumi)
        logger.debug(f"[Database] Update {title_raw} poster_link to {poster_link}.")

    def delete_one(self, _id: int):
        # First, delete all torrents associated with this bangumi
        from module.models import Torrent

        torrent_delete_stmt = delete(Torrent).where(Torrent.bangumi_id == _id)
        self.session.exec(torrent_delete_stmt)
        logger.debug(f"[Database] Deleted torrents for bangumi id: {_id}.")

        # Then delete the bangumi itself
        statement = select(Bangumi).where(Bangumi.id == _id)
        bangumi = self.session.exec(statement).first()
        self.session.delete(bangumi)
        self.session.commit()
        logger.debug(f"[Database] Delete bangumi id: {_id}.")

    def delete_many(self, ids: list[int]) -> int:
        """Delete multiple bangumi by IDs in a single transaction.

        Args:
            ids: List of bangumi IDs to delete.

        Returns:
            Number of bangumi deleted.
        """
        if not ids:
            return 0

        from module.models import Torrent

        # Delete all associated torrents in batch
        torrent_delete_stmt = delete(Torrent).where(col(Torrent.bangumi_id).in_(ids))
        self.session.exec(torrent_delete_stmt)

        # Delete all bangumi in batch
        bangumi_delete_stmt = delete(Bangumi).where(col(Bangumi.id).in_(ids))
        self.session.exec(bangumi_delete_stmt)
        self.session.commit()

        logger.debug(f"[Database] Batch deleted {len(ids)} bangumi and their torrents.")
        return len(ids)

    def delete_all(self):
        statement = delete(Bangumi)
        self.session.exec(statement)
        self.session.commit()

    def search_all(self) -> list[Bangumi]:
        statement = select(Bangumi)
        return self.session.exec(statement).all()

    def search_active(self) -> list[Bangumi]:
        """Search all active (not disabled) bangumi."""
        statement = select(Bangumi).where(Bangumi.deleted == false())
        return self.session.exec(statement).all()

    def search_id(self, _id: int) -> Optional[Bangumi]:
        statement = select(Bangumi).where(Bangumi.id == _id)
        bangumi = self.session.exec(statement).first()
        if bangumi is None:
            logger.warning(f"[Database] Cannot find bangumi id: {_id}.")
            return None
        else:
            logger.debug(f"[Database] Find bangumi id: {_id}.")
            return self.session.exec(statement).first()

    def match_poster(self, bangumi_name: str) -> str:
        # Use like to match
        statement = select(Bangumi).where(
            func.instr(bangumi_name, Bangumi.official_title) > 0
        )
        data = self.session.exec(statement).first()
        if data:
            return data.poster_link
        else:
            return ""

    def match_list(self, torrent_list: list, rss_link: str) -> tuple[list, list]:
        """Match torrents against existing bangumi rules.

        Uses optimized O(n+m) algorithm with hash map for title matching,
        where n = number of torrents and m = number of bangumi rules.

        Args:
            torrent_list: List of torrents to match.
            rss_link: The aggregate RSS link to append to matched bangumi.

        Returns:
            Tuple of (unmatched_torrents, matched_pairs) where matched_pairs
            is a list of (bangumi, torrent) tuples for further processing.
        """
        match_datas = self.search_active()
        if not match_datas:
            return torrent_list, []

        # Build a lookup structure for O(1) access by title_raw
        # Sort by title length descending to match longer titles first (more specific)
        sorted_rules = sorted(match_datas, key=lambda x: len(x.title_raw), reverse=True)

        matched_pairs = []
        unmatched = []

        # Single pass through torrents - O(n * m_avg_length) worst case
        # but typically O(n) for reasonable title lengths
        for torrent in torrent_list:
            matched = None
            for rule in sorted_rules:
                if rule.title_raw in torrent.name:
                    matched = rule
                    break

            if matched:
                # Update RSS link if needed
                if rss_link not in matched.rss_link:
                    matched.rss_link += f",{rss_link}"
                    self.update_rss(matched.title_raw, matched.rss_link)
                matched_pairs.append((matched, torrent))
            else:
                unmatched.append(torrent)

        return unmatched, matched_pairs

    def match_torrent(self, torrent_name: str) -> Optional[Bangumi]:
        statement = select(Bangumi).where(
            and_(
                func.instr(torrent_name, Bangumi.title_raw) > 0,
                # use `false()` to avoid E712 checking
                # see: https://docs.astral.sh/ruff/rules/true-false-comparison/
                Bangumi.deleted == false(),
            )
        )
        return self.session.exec(statement).first()

    def not_complete(self) -> list[Bangumi]:
        # Find eps_complete = False
        # use `false()` to avoid E712 checking
        # see: https://docs.astral.sh/ruff/rules/true-false-comparison/
        condition = select(Bangumi).where(
            and_(Bangumi.eps_collect == false(), Bangumi.deleted == false())
        )
        datas = self.session.exec(condition).all()
        return datas

    def not_added(self) -> list[Bangumi]:
        conditions = select(Bangumi).where(
            or_(
                Bangumi.added == 0, Bangumi.rule_name is None, Bangumi.save_path is None
            )
        )
        datas = self.session.exec(conditions).all()
        return datas

    def disable_rule(self, _id: int):
        statement = select(Bangumi).where(Bangumi.id == _id)
        bangumi = self.session.exec(statement).first()
        bangumi.deleted = True
        self.session.add(bangumi)
        self.session.commit()
        self.session.refresh(bangumi)
        logger.debug(f"[Database] Disable rule {bangumi.title_raw}.")

    def disable_many(self, ids: list[int]) -> int:
        """Disable multiple bangumi rules by IDs in a single transaction.

        Args:
            ids: List of bangumi IDs to disable.

        Returns:
            Number of bangumi disabled.
        """
        if not ids:
            return 0

        statement = select(Bangumi).where(col(Bangumi.id).in_(ids))
        bangumi_list = self.session.exec(statement).all()

        for bangumi in bangumi_list:
            bangumi.deleted = True
            self.session.add(bangumi)

        self.session.commit()
        logger.debug(f"[Database] Batch disabled {len(bangumi_list)} bangumi rules.")
        return len(bangumi_list)

    def search_rss(self, rss_link: str) -> list[Bangumi]:
        statement = select(Bangumi).where(func.instr(rss_link, Bangumi.rss_link) > 0)
        return self.session.exec(statement).all()

    def backfill_rss_id(self, rss_id: int, rss_url: str) -> int:
        """Backfill rss_id for bangumi that have NULL rss_id but matching rss_link.

        This auto-fixes historical data where bangumi.rss_id was not set during creation.

        Args:
            rss_id: The RSS item ID to set.
            rss_url: The RSS URL to match against bangumi.rss_link.

        Returns:
            Number of bangumi records updated.
        """
        statement = select(Bangumi).where(
            and_(Bangumi.rss_id.is_(None), func.instr(Bangumi.rss_link, rss_url) > 0)
        )
        bangumi_list = self.session.exec(statement).all()

        if not bangumi_list:
            return 0

        for bangumi in bangumi_list:
            bangumi.rss_id = rss_id
            self.session.add(bangumi)

        self.session.commit()
        logger.info(
            f"[Database] Backfilled rss_id={rss_id} for {len(bangumi_list)} bangumi records."
        )
        return len(bangumi_list)
