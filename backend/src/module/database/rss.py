import logging

from sqlmodel import Session, and_, delete, select

from module.models import RSSItem, RSSUpdate

logger = logging.getLogger(__name__)


class RSSDatabase:
    def __init__(self, session: Session):
        self.session = session

    def add(self, data: RSSItem):
        # Check if exists
        statement = select(RSSItem).where(RSSItem.url == data.url)
        db_data = self.session.exec(statement).first()
        if db_data:
            logger.debug(f"RSS Item {data.url} already exists.")
            return False
        else:
            logger.debug(f"RSS Item {data.url} not exists, adding...")
            self.session.add(data)
            return True

    def add_all(self, data: list[RSSItem]):
        for item in data:
            self.add(item)

    def update(self, _id: int, data: RSSUpdate):
        # Check if exists
        statement = select(RSSItem).where(RSSItem.id == _id)
        db_data = self.session.exec(statement).first()
        if not db_data:
            return False
        # Update
        dict_data = data.dict(exclude_unset=True)
        for key, value in dict_data.items():
            setattr(db_data, key, value)
        self.session.add(db_data)
        return True

    def enable(self, _id: int):
        statement = select(RSSItem).where(RSSItem.id == _id)
        db_data = self.session.exec(statement).first()
        if not db_data:
            return False
        db_data.enabled = True
        self.session.add(db_data)
        return True

    def disable(self, _id: int):
        statement = select(RSSItem).where(RSSItem.id == _id)
        db_data = self.session.exec(statement).first()
        if not db_data:
            return False
        db_data.enabled = False
        self.session.add(db_data)
        return True

    def search_id(self, _id: int) -> RSSItem:
        return self.session.get(RSSItem, _id)

    def search_all(self) -> list[RSSItem]:
        return self.session.exec(select(RSSItem)).all()

    def search_active(self) -> list[RSSItem]:
        return self.session.exec(select(RSSItem).where(RSSItem.enabled)).all()

    def search_aggregate(self) -> list[RSSItem]:
        return self.session.exec(
            select(RSSItem).where(and_(RSSItem.aggregate, RSSItem.enabled))
        ).all()

    def set_status(self, _id: int, status: str) -> bool:
        db_data = self.session.get(RSSItem, _id)
        if not db_data:
            return False
        db_data.last_status = status
        self.session.add(db_data)
        return True

    def delete(self, _id: int) -> bool:
        """Delete RSS and cascade delete all associated Bangumi rules and torrents."""
        try:
            from sqlalchemy.sql import func

            from module.models import Bangumi, Torrent

            # Get RSS URL for fallback lookup
            rss_item = self.search_id(_id)
            if not rss_item:
                logger.warning(f"[RSS] RSS ID {_id} not found.")
                return False

            # Step 1: Delete all torrents with this rss_id
            # This catches all torrents from this RSS, regardless of bangumi_id
            torrent_by_rss = delete(Torrent).where(Torrent.rss_id == _id)
            self.session.exec(torrent_by_rss)
            logger.debug(f"[RSS] Deleted all torrents with rss_id: {_id}")

            # Step 2: Find all Bangumi with this rss_id OR matching rss_link (fallback)
            # Primary: Find by rss_id (fast, indexed)
            bangumi_by_id = select(Bangumi).where(Bangumi.rss_id == _id)
            bangumi_list = list(self.session.exec(bangumi_by_id).all())

            # Fallback: Find by rss_link for bangumi with NULL rss_id (historical data)
            bangumi_by_link = select(Bangumi).where(
                and_(
                    Bangumi.rss_id.is_(None),
                    func.instr(Bangumi.rss_link, rss_item.url) > 0,
                )
            )
            bangumi_list_fallback = self.session.exec(bangumi_by_link).all()
            bangumi_list.extend(bangumi_list_fallback)

            if bangumi_list_fallback:
                logger.info(
                    f"[RSS] Found {len(bangumi_list_fallback)} bangumi with NULL rss_id via fallback lookup."
                )

            # Step 3: Delete torrents by bangumi_id and the Bangumi rules
            for bangumi in bangumi_list:
                # Delete any remaining torrents for this bangumi (with different rss_id)
                torrent_condition = delete(Torrent).where(
                    Torrent.bangumi_id == bangumi.id
                )
                self.session.exec(torrent_condition)
                logger.debug(f"[RSS] Deleted torrents for Bangumi ID: {bangumi.id}")

                # Delete the Bangumi rule
                bangumi_condition = delete(Bangumi).where(Bangumi.id == bangumi.id)
                self.session.exec(bangumi_condition)
                logger.debug(f"[RSS] Deleted Bangumi rule: {bangumi.official_title}")

            # Step 4: Delete the RSS item
            rss_condition = delete(RSSItem).where(RSSItem.id == _id)
            self.session.exec(rss_condition)
            logger.debug(f"[RSS] Successfully deleted RSS ID: {_id} with cascade")
            return True
        except Exception as e:
            logger.error(f"Delete RSS Item failed. Because: {e}")
            self.session.rollback()
            return False

    def delete_all(self):
        condition = delete(RSSItem)
        self.session.exec(condition)
