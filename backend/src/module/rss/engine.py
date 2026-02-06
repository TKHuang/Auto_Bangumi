import logging
import re
from datetime import datetime
from typing import Optional

from module.database import Database, sync_engine
from module.downloader import DownloadClient
from module.models import Bangumi, ResponseModel, RSSItem, Torrent
from module.network import RequestContent

logger = logging.getLogger(__name__)


def _extract_mikan_bangumi_id(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"bangumiId=(\d+)", url)
    return match.group(1) if match else None


def _is_cross_season(source_rss_url: str, bangumi_rss_link: str) -> bool:
    """True when source RSS and bangumi RSS are both Mikan season feeds
    with different bangumiIds (i.e. different seasons of the same show)."""
    source_id = _extract_mikan_bangumi_id(source_rss_url)
    target_id = _extract_mikan_bangumi_id(
        bangumi_rss_link.split(",")[0] if bangumi_rss_link else ""
    )
    return bool(source_id and target_id and source_id != target_id)


class RSSEngine(Database):
    def __init__(self, _engine=sync_engine):
        super().__init__(_engine)
        self._to_refresh = False

    @staticmethod
    def _get_torrents(rss: RSSItem) -> list[Torrent]:
        with RequestContent() as req:
            # _filter="" bypasses global filter; per-bangumi filters apply during match_torrent
            torrents = req.get_torrents(rss.url, _filter="")
            for torrent in torrents:
                torrent.rss_id = rss.id
        return torrents

    def get_rss_torrents(self, rss_id: int) -> list[Torrent]:
        rss = self.rss.search_id(rss_id)
        if rss:
            return self.torrent.search_rss(rss_id)
        else:
            return []

    def create_bangumi_from_torrent(self, torrent_id: int) -> ResponseModel:
        """Create a new Bangumi rule from an RSS torrent.

        Args:
            torrent_id: ID of the torrent to create Bangumi from

        Returns:
            ResponseModel with success/failure status
        """
        # Get torrent from database
        torrent = self.torrent.search(torrent_id)
        if not torrent:
            return ResponseModel(
                status=False,
                status_code=404,
                msg_en="Torrent not found in database.",
                msg_zh="数据库中未找到该种子。",
            )

        # Get associated RSS item
        if not torrent.rss_id:
            return ResponseModel(
                status=False,
                status_code=406,
                msg_en="Torrent is not from an RSS feed.",
                msg_zh="该种子不是来自 RSS 订阅。",
            )

        rss = self.rss.search_id(torrent.rss_id)
        if not rss:
            return ResponseModel(
                status=False,
                status_code=404,
                msg_en="Associated RSS feed not found.",
                msg_zh="未找到关联的 RSS 订阅。",
            )

        # Use RSSAnalyser to parse torrent into Bangumi
        from module.rss import RSSAnalyser

        analyser = RSSAnalyser()
        bangumi = analyser.torrent_to_data(torrent, rss)

        if not bangumi:
            return ResponseModel(
                status=False,
                status_code=406,
                msg_en="Failed to parse torrent. The torrent name may not be in a recognized format.",
                msg_zh="无法解析种子。种子名称可能不是可识别的格式。",
            )

        # Check if similar Bangumi already exists
        existing = self.bangumi.match_torrent(torrent.name)
        if existing:
            return ResponseModel(
                status=False,
                status_code=406,
                msg_en=f"A similar Bangumi rule already exists: {existing.official_title}",
                msg_zh=f"已存在相似的番剧规则：{existing.official_title}",
            )

        # Add Bangumi to database
        self.bangumi.add(bangumi)
        self.commit()

        # Link torrent to new Bangumi
        torrent.bangumi_id = bangumi.id
        self.torrent.update(torrent)

        # Try to download the torrent
        with DownloadClient() as client:
            save_path_before = bangumi.save_path
            if client.add_torrent(torrent, bangumi):
                torrent.downloaded = True
                # Set pikpak_cloud_path here to avoid DB lock conflicts
                torrent.pikpak_cloud_path = bangumi.save_path
                self.torrent.update(torrent)
                # Persist newly generated save_path to database
                if not save_path_before and bangumi.save_path:
                    self.bangumi.update_save_path(bangumi.id, bangumi.save_path)
        
        self.commit()

        return ResponseModel(
            status=True,
            status_code=200,
            msg_en=f"Successfully created Bangumi rule: {bangumi.official_title}",
            msg_zh=f"成功创建番剧规则：{bangumi.official_title}",
        )

    def add_rss(
        self,
        rss_link: str,
        name: str | None = None,
        aggregate: bool = True,
        parser: str = "mikan",
    ):
        if not name:
            with RequestContent() as req:
                name = req.get_rss_title(rss_link)
                if not name:
                    return ResponseModel(
                        status=False,
                        status_code=406,
                        msg_en="Invalid RSS URL. Please provide a valid RSS feed link, not a webpage URL.",
                        msg_zh="无效的 RSS 链接。请提供有效的 RSS 订阅链接，而非网页链接。",
                    )
        rss_data = RSSItem(name=name, url=rss_link, aggregate=aggregate, parser=parser)
        if self.rss.add(rss_data):
            self.commit()
            return ResponseModel(
                status=True,
                status_code=200,
                msg_en="RSS added successfully.",
                msg_zh="RSS 添加成功。",
            )
        else:
            return ResponseModel(
                status=False,
                status_code=406,
                msg_en="RSS already exists or failed to add.",
                msg_zh="RSS 已存在或添加失败。",
            )

    def disable_list(self, rss_id_list: list[int]):
        for rss_id in rss_id_list:
            self.rss.disable(rss_id)
        self.commit()
        return ResponseModel(
            status=True,
            status_code=200,
            msg_en="Disable RSS successfully.",
            msg_zh="禁用 RSS 成功。",
        )

    def enable_list(self, rss_id_list: list[int]):
        for rss_id in rss_id_list:
            self.rss.enable(rss_id)
        self.commit()
        return ResponseModel(
            status=True,
            status_code=200,
            msg_en="Enable RSS successfully.",
            msg_zh="启用 RSS 成功。",
        )

    def delete_list(self, rss_id_list: list[int]):
        for rss_id in rss_id_list:
            self.rss.delete(rss_id)
        self.commit()
        return ResponseModel(
            status=True,
            status_code=200,
            msg_en="Delete RSS successfully.",
            msg_zh="删除 RSS 成功。",
        )

    def pull_rss(self, rss_item: RSSItem) -> list[Torrent]:
        torrents = self._get_torrents(rss_item)
        new_torrents = self.torrent.check_new(torrents)
        return new_torrents

    def match_torrent(self, torrent: Torrent) -> Optional[Bangumi]:
        matched: Bangumi = self.bangumi.match_torrent(torrent.name)
        if matched:
            # Always set bangumi_id when we find a match
            torrent.bangumi_id = matched.id

            # If no filter, accept the torrent
            if matched.filter == "":
                return matched

            # If filter exists, check if torrent name should be excluded
            _filter = matched.filter.replace(",", "|")
            if re.search(_filter, torrent.name, re.IGNORECASE):
                # Filter MATCHES, so we EXCLUDE this torrent (don't return matched)
                logger.debug(
                    f"[Engine] Torrent {torrent.name} excluded by filter: {matched.filter}"
                )
                return None
            else:
                # Filter does not match, so we accept this torrent
                return matched
        return None

    def refresh_rss(self, client: DownloadClient, rss_id: Optional[int] = None):
        # Get All RSS Items
        if not rss_id:
            rss_items: list[RSSItem] = self.rss.search_active()
        else:
            rss_item = self.rss.search_id(rss_id)
            rss_items = [rss_item] if rss_item else []
        # From RSS Items, get all torrents
        logger.debug(f"[Engine] Get {len(rss_items)} RSS items")
        for rss_item in rss_items:
            if rss_item.last_status == "Recreating":
                logger.debug(f"[Engine] Skipping RSS {rss_item.name} - recreation in progress")
                continue
            try:
                # This auto-fixes historical data from before the fix was applied
                backfilled = self.bangumi.backfill_rss_id(rss_item.id, rss_item.url)
                if backfilled > 0:
                    logger.info(
                        f"[Engine] Auto-fixed {backfilled} bangumi records for RSS: {rss_item.name}"
                    )
                    self.commit()

                new_torrents = self.pull_rss(rss_item)
                rss_item.last_status = "Success"
                rss_item.last_error = None

                matched_torrents = []
                for torrent in new_torrents:
                    matched_data = self.match_torrent(torrent)
                    if matched_data:
                        if _is_cross_season(rss_item.url, matched_data.rss_link):
                            logger.debug(
                                f"[Engine] Skip {torrent.name} - cross-season RSS mismatch"
                            )
                            continue
                        matched_torrents.append(torrent)
                    else:
                        logger.debug(
                            f"[Engine] Skip torrent {torrent.name} - no matching Bangumi rule"
                        )

                if matched_torrents:
                    self.torrent.add_all_or_ignore(matched_torrents)
                    self.commit()
                    logger.debug(
                        f"[Engine] Stored {len(matched_torrents)} matched torrents out of {len(new_torrents)} total"
                    )

                for torrent in matched_torrents:
                    matched_data = self.match_torrent(torrent)
                    if matched_data:
                        save_path_before = matched_data.save_path
                        if client.add_torrent(torrent, matched_data):
                            logger.debug(
                                f"[Engine] Add torrent {torrent.name} to client"
                            )
                            if not save_path_before and matched_data.save_path:
                                self.bangumi.update_save_path(matched_data.id, matched_data.save_path)
                        if torrent.hash and torrent.bangumi_id is not None:
                            self.torrent.mark_downloaded(torrent.hash, torrent.bangumi_id, matched_data.save_path)
                
                self.commit()
            except Exception as e:
                logger.error(f"[Engine] Refresh RSS {rss_item.name} failed: {e}")
                rss_item.last_status = "Error"
                rss_item.last_error = str(e)
            finally:
                rss_item.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.rss.update(rss_item.id, rss_item)
                self.commit()

    def download_bangumi(self, bangumi: Bangumi):
        with RequestContent() as req:
            # Fetch all torrents from the RSS feed (pass empty filter to get all)
            all_torrents = req.get_torrents(bangumi.rss_link, _filter="")
            logger.debug(
                f"[Engine] Fetched {len(all_torrents)} torrents from {bangumi.rss_link}"
            )

            if not all_torrents:
                return ResponseModel(
                    status=False,
                    status_code=406,
                    msg_en=f"No torrents found for {bangumi.official_title} in the RSS feed.",
                    msg_zh=f"在 RSS 订阅中未找到 {bangumi.official_title} 的种子。",
                )

            # Apply exclusion filter if it exists
            torrents = []
            logger.debug(f"[Engine] Bangumi filter: '{bangumi.filter}'")
            if bangumi.filter:
                _filter = bangumi.filter.replace(",", "|")
                logger.debug(f"[Engine] Applying exclusion filter: {_filter}")
                for torrent in all_torrents:
                    if not re.search(_filter, torrent.name, re.IGNORECASE):
                        # Torrent does not match exclusion filter, include it
                        torrents.append(torrent)
                        logger.debug(f"[Engine] ✓ Accepted: {torrent.name}")
                    else:
                        logger.debug(
                            f"[Engine] ✗ Excluded: {torrent.name} (matched filter)"
                        )
            else:
                # No filter, use all torrents
                logger.debug(
                    f"[Engine] No filter set, accepting all {len(all_torrents)} torrents"
                )
                torrents = all_torrents

            logger.debug(
                f"[Engine] After filtering: {len(torrents)}/{len(all_torrents)} torrents accepted"
            )

            if not torrents:
                return ResponseModel(
                    status=False,
                    status_code=406,
                    msg_en=f"Subscription failed: All found torrents for {bangumi.official_title} were filtered out. Please check your filter settings.",
                    msg_zh=f"订阅失败：{bangumi.official_title} 的所有种子都被过滤。请检查过滤规则。",
                )

            # Set bangumi_id and rss_id on torrents
            for torrent in torrents:
                torrent.bangumi_id = bangumi.id
                # Use the rss_id from bangumi if available
                if bangumi.rss_id:
                    torrent.rss_id = bangumi.rss_id

            # Filter out duplicate torrents by hash to prevent duplicates across RSS sources
            new_torrents = self.torrent.check_new_by_hash(torrents)
            logger.debug(
                f"[Engine] After hash deduplication: {len(new_torrents)}/{len(torrents)} new torrents"
            )

            if not new_torrents:
                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"[Engine] No new torrents for {bangumi.official_title} (all already downloaded).",
                    msg_zh=f"[Engine] {bangumi.official_title} 没有新种子（已全部下载）。",
                )

            self.torrent.add_all_or_ignore(new_torrents)
            self.commit()

            with DownloadClient() as client:
                save_path_before = bangumi.save_path
                try:
                    client.add_torrent(new_torrents, bangumi)
                except Exception as e:
                    logger.warning(f"[Engine] Partial download failure for {bangumi.official_title}: {e}")
                if not save_path_before and bangumi.save_path:
                    self.bangumi.update_save_path(bangumi.id, bangumi.save_path)
                for torrent in new_torrents:
                    if torrent.hash and bangumi.id is not None:
                        self.torrent.mark_downloaded(torrent.hash, bangumi.id, bangumi.save_path)
                self.commit()
                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"[Engine] Downloaded {len(new_torrents)} torrents for {bangumi.official_title}.",
                    msg_zh=f"[Engine] 为 {bangumi.official_title} 下载了 {len(new_torrents)} 个种子。",
                )
