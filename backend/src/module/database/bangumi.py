import logging
from typing import Optional

from sqlalchemy.sql import func
from sqlmodel import Session, and_, col, delete, false, or_, select, true

from module.models import Bangumi, BangumiUpdate

logger = logging.getLogger(__name__)


class BangumiDatabase:
    def __init__(self, session: Session):
        self.session = session

    def add(self, data: Bangumi):
        # Use composite key (official_title, season, group_name) for duplicate check
        # This matches search_by_composite_key logic
        normalized_group = data.group_name if data.group_name else "Unknown"
        statement = select(Bangumi).where(
            and_(
                Bangumi.official_title == data.official_title,
                Bangumi.season == data.season,
                Bangumi.group_name == normalized_group,
                Bangumi.deleted == false(),
            )
        )
        bangumi = self.session.exec(statement).first()
        if bangumi:
            logger.debug(
                f"[Database] Bangumi already exists: {data.official_title} S{data.season} ({normalized_group})"
            )
            return False
        self.session.add(data)
        logger.debug(f"[Database] Insert {data.official_title} into database.")
        return True

    def add_all(self, datas: list[Bangumi]):
        self.session.add_all(datas)
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
        logger.debug(f"[Database] Update {data.official_title}")
        return True

    def update_all(self, datas: list[Bangumi]):
        self.session.add_all(datas)
        logger.debug(f"[Database] Update {len(datas)} bangumi.")

    def update_rss(self, title_raw, rss_set: str):
        # Update rss and added
        statement = select(Bangumi).where(Bangumi.title_raw == title_raw)
        bangumi = self.session.exec(statement).first()
        bangumi.rss_link = rss_set
        bangumi.added = False
        self.session.add(bangumi)
        logger.debug(f"[Database] Update {title_raw} rss_link to {rss_set}.")

    def update_poster(self, title_raw, poster_link: str):
        statement = select(Bangumi).where(Bangumi.title_raw == title_raw)
        bangumi = self.session.exec(statement).first()
        bangumi.poster_link = poster_link
        self.session.add(bangumi)
        logger.debug(f"[Database] Update {title_raw} poster_link to {poster_link}.")

    def update_save_path(self, bangumi_id: int, save_path: str):
        """Update the save_path for a bangumi after torrents are downloaded.
        
        This ensures the generated save_path is persisted to the database,
        allowing future torrents to be downloaded to the correct location.
        """
        bangumi = self.session.get(Bangumi, bangumi_id)
        if not bangumi:
            logger.warning(f"[Database] Cannot find bangumi id: {bangumi_id} for save_path update.")
            return
        bangumi.save_path = save_path
        self.session.add(bangumi)
        logger.debug(f"[Database] Update bangumi {bangumi_id} save_path to {save_path}.")

    def delete_one(self, _id: int) -> bool:
        from module.models import Torrent

        torrent_delete_stmt = delete(Torrent).where(Torrent.bangumi_id == _id)
        self.session.exec(torrent_delete_stmt)
        logger.debug(f"[Database] Deleted torrents for bangumi id: {_id}.")

        bangumi_delete_stmt = delete(Bangumi).where(Bangumi.id == _id)
        result = self.session.exec(bangumi_delete_stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"[Database] Delete bangumi id: {_id}.")
        else:
            logger.debug(f"[Database] Bangumi id: {_id} already deleted (idempotent).")
        return deleted

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

        logger.debug(f"[Database] Batch deleted {len(ids)} bangumi and their torrents.")
        return len(ids)

    def delete_all(self):
        from module.models import Torrent

        self.session.exec(delete(Torrent))
        self.session.exec(delete(Bangumi))

    def search_all(self) -> list[Bangumi]:
        statement = select(Bangumi).where(Bangumi.pending_review == false())
        return self.session.exec(statement).all()

    def search_active(self) -> list[Bangumi]:
        """Search all active (not disabled, not pending review) bangumi."""
        statement = select(Bangumi).where(
            and_(
                Bangumi.deleted == false(),
                Bangumi.pending_review == false(),
            )
        )
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

    def search_by_composite_key(
        self, official_title: str, season: int, group_name: str
    ) -> Optional[Bangumi]:
        """Search for active bangumi by composite key (official_title, season, group_name).

        This allows subscribing to the same anime from different subgroups:
        - [LoliHouse] Anime X S1 → OK
        - [ANi] Anime X S1       → OK (different group)
        - [LoliHouse] Anime X S1 → BLOCKED (duplicate)

        Args:
            official_title: The official/standardized title.
            season: Season number.
            group_name: Subgroup name (defaults to "Unknown" if empty/None).

        Returns:
            Bangumi if exact match found, None otherwise.
        """
        # Normalize: use "Unknown" for empty/None
        normalized_group = group_name if group_name else "Unknown"

        statement = select(Bangumi).where(
            and_(
                Bangumi.official_title == official_title,
                Bangumi.season == season,
                Bangumi.group_name == normalized_group,
                Bangumi.deleted == false(),
            )
        )
        result = self.session.exec(statement).first()
        if result:
            logger.debug(
                f"[Database] Found existing bangumi by composite key: "
                f"official_title='{official_title}', season={season}, group='{normalized_group}'"
            )
        return result

    def exists_by_composite_key(
        self, official_title: str, season: int, group_name: str
    ) -> bool:
        """Check if any bangumi exists by composite key (active OR pending).

        Unlike search_by_composite_key, this method checks for ANY bangumi
        (including pending_review=True) to prevent creating duplicates.

        Args:
            official_title: The official/standardized title.
            season: Season number.
            group_name: Subgroup name (defaults to "Unknown" if empty/None).

        Returns:
            True if a bangumi exists with this composite key, False otherwise.
        """
        # Normalize: use "Unknown" for empty/None
        normalized_group = group_name if group_name else "Unknown"

        statement = select(Bangumi).where(
            and_(
                Bangumi.official_title == official_title,
                Bangumi.season == season,
                Bangumi.group_name == normalized_group,
                Bangumi.deleted == false(),
            )
        )
        result = self.session.exec(statement).first()
        return result is not None

    def get_pending_by_composite_key(
        self, official_title: str, season: int, group_name: str
    ) -> list[Bangumi]:
        """Get pending review bangumi by composite key.

        Used during recreation to find and delete existing pending bangumi
        before creating new ones, preventing duplicates.

        Args:
            official_title: The official/standardized title.
            season: Season number.
            group_name: Subgroup name (defaults to "Unknown" if empty/None).

        Returns:
            List of pending review bangumi matching the composite key.
        """
        # Normalize: use "Unknown" for empty/None
        normalized_group = group_name if group_name else "Unknown"

        statement = select(Bangumi).where(
            and_(
                Bangumi.official_title == official_title,
                Bangumi.season == season,
                Bangumi.group_name == normalized_group,
                Bangumi.deleted == false(),
                Bangumi.pending_review == true(),
            )
        )
        return self.session.exec(statement).all()

    def get_all_by_rss_id(self, rss_id: int) -> list[Bangumi]:
        """Get ALL bangumi associated with an RSS feed (active AND pending).

        Used during RSS recreation to find and delete ALL existing bangumi
        from the RSS before inserting new ones, preventing orphaned entries.

        Args:
            rss_id: The RSS item ID.

        Returns:
            List of all bangumi records with this rss_id (active or pending).
        """
        statement = select(Bangumi).where(
            and_(
                Bangumi.rss_id == rss_id,
                Bangumi.deleted == false(),
            )
        )
        return self.session.exec(statement).all()

    def delete_all_by_rss_id(self, rss_id: int) -> int:
        from module.models import Torrent

        bangumi_ids_stmt = select(Bangumi.id).where(
            and_(
                Bangumi.rss_id == rss_id,
                Bangumi.deleted == false(),
            )
        )
        bangumi_ids = [row for row in self.session.exec(bangumi_ids_stmt).all()]

        if not bangumi_ids:
            return 0

        self.session.exec(
            delete(Torrent).where(col(Torrent.bangumi_id).in_(bangumi_ids))
        )
        result = self.session.exec(
            delete(Bangumi).where(col(Bangumi.id).in_(bangumi_ids))
        )
        count = result.rowcount

        logger.info(
            f"[Database] Deleted {count} bangumi records for RSS ID {rss_id} during recreation"
        )
        return count

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
        """Match a torrent name to an active bangumi rule.
        
        Only matches active (non-pending, non-deleted) bangumi to ensure
        pending review bangumi don't have torrents downloaded until activated.
        """
        statement = select(Bangumi).where(
            and_(
                func.instr(torrent_name, Bangumi.title_raw) > 0,
                # use `false()` to avoid E712 checking
                # see: https://docs.astral.sh/ruff/rules/true-false-comparison/
                Bangumi.deleted == false(),
                Bangumi.pending_review == false(),
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

        logger.debug(f"[Database] Batch disabled {len(bangumi_list)} bangumi rules.")
        return len(bangumi_list)

    def search_rss(self, rss_link: str) -> list[Bangumi]:
        statement = select(Bangumi).where(func.instr(rss_link, Bangumi.rss_link) > 0)
        return self.session.exec(statement).all()

    def find_by_official_title(self, official_title: str) -> Bangumi | None:
        """Find an active (non-deleted) bangumi by official_title.

        Args:
            official_title: The official title to search for.

        Returns:
            Bangumi object if found, None otherwise.
        """
        statement = select(Bangumi).where(
            and_(
                Bangumi.official_title == official_title,
                Bangumi.deleted == false(),
            )
        )
        return self.session.exec(statement).first()

    def find_by_any_rss_link(self, rss_links: list[str]) -> Bangumi | None:
        """Find an active bangumi that contains any of the given RSS links.

        Checks if any of the provided RSS links already exist in any bangumi's
        rss_link field (which is a comma-separated string).

        Args:
            rss_links: List of RSS URLs to check.

        Returns:
            First Bangumi object found with a matching rss_link, None otherwise.
        """
        for rss_link in rss_links:
            if not rss_link:
                continue
            # Check if this rss_link exists in any bangumi's rss_link field
            statement = select(Bangumi).where(
                and_(
                    func.instr(Bangumi.rss_link, rss_link) > 0,
                    Bangumi.deleted == false(),
                )
            )
            result = self.session.exec(statement).first()
            if result:
                return result
        return None

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

        logger.info(
            f"[Database] Backfilled rss_id={rss_id} for {len(bangumi_list)} bangumi records."
        )
        return len(bangumi_list)

    def count_pending_by_rss_id(self, rss_id: int) -> int:
        """Count pending review bangumi for a specific RSS feed.

        Args:
            rss_id: The RSS item ID to count pending reviews for.

        Returns:
            Number of pending review bangumi records.
        """
        statement = select(func.count()).select_from(Bangumi).where(
            and_(Bangumi.rss_id == rss_id, Bangumi.pending_review == true())
        )
        return self.session.exec(statement).one()

    def get_pending_by_rss_id(self, rss_id: int) -> list[Bangumi]:
        """Get pending review bangumi for a specific RSS feed.

        Args:
            rss_id: The RSS item ID to get pending reviews for.

        Returns:
            List of pending review bangumi records.
        """
        statement = select(Bangumi).where(
            and_(Bangumi.rss_id == rss_id, Bangumi.pending_review == true())
        )
        return self.session.exec(statement).all()

    def count_active_by_rss_id(self, rss_id: int) -> int:
        """Count active (non-pending) bangumi for a specific RSS feed.

        Args:
            rss_id: The RSS item ID to count active bangumi for.

        Returns:
            Number of active bangumi records.
        """
        statement = select(func.count()).select_from(Bangumi).where(
            and_(Bangumi.rss_id == rss_id, Bangumi.pending_review == false())
        )
        return self.session.exec(statement).one()


    def activate_pending(
        self, bangumi_id: int, filter_value: Optional[str] = None
    ) -> tuple[bool, str]:
        """Activate a pending review bangumi.

        Args:
            bangumi_id: The bangumi ID to activate.
            filter_value: Optional filter value to set. If None, keeps existing filter.

        Returns:
            Tuple of (success, message). Returns (False, error_msg) if bangumi
            is not found or not pending review.
        """
        bangumi = self.session.get(Bangumi, bangumi_id)
        if not bangumi:
            return False, "Bangumi not found"
        if not bangumi.pending_review:
            return False, "Bangumi is not pending review"

        bangumi.pending_review = False
        bangumi.global_filter_matches = None
        if filter_value is not None:
            bangumi.filter = filter_value

        self.session.add(bangumi)
        logger.debug(f"[Database] Activated pending bangumi: {bangumi.official_title}")
        return True, "Bangumi activated successfully"

    def update_pending_review(
        self, bangumi_id: int, pending: bool, global_filter_matches: Optional[str] = None
    ) -> bool:
        """Update the pending_review status of a bangumi.

        Args:
            bangumi_id: The bangumi ID to update.
            pending: Whether to set pending_review to True or False.
            global_filter_matches: Optional filter pattern that caused the pending status.

        Returns:
            True if successful, False if bangumi not found.
        """
        bangumi = self.session.get(Bangumi, bangumi_id)
        if not bangumi:
            return False

        bangumi.pending_review = pending
        if pending and global_filter_matches:
            bangumi.global_filter_matches = global_filter_matches
        elif not pending:
            bangumi.global_filter_matches = None

        self.session.add(bangumi)
        logger.debug(
            f"[Database] Updated pending_review for {bangumi.official_title}: {pending}"
        )
        return True
