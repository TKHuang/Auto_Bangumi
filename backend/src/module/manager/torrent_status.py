import logging
import re
from typing import Optional

from module.database import Database
from module.downloader import DownloadClient
from module.models import Bangumi, ResponseModel, Torrent

logger = logging.getLogger(__name__)


class TorrentStatusManager(Database):
    def get_bangumi_torrents_status(self, bangumi_id: int) -> list[dict]:
        bangumi_torrents = self.torrent.search_all()
        bangumi_torrents = [t for t in bangumi_torrents if t.bangumi_id == bangumi_id]
        return self._get_torrents_status(bangumi_torrents)

    def get_rss_torrents_status(self, rss_id: int) -> list[dict]:
        rss_torrents = self.torrent.search_rss(rss_id)
        return self._get_torrents_status(rss_torrents)

    def _get_torrents_status(self, torrents: list[Torrent]) -> list[dict]:
        if not torrents:
            return []

        # Get torrents from download client
        with DownloadClient() as client:
            # Get ALL torrents, not just completed ones
            online_torrents = client.get_torrent_info(status_filter="all")
            logger.debug(
                f"[TorrentStatus] Found {len(online_torrents)} torrents in download client"
            )

            # Log qBittorrent hashes for debugging
            qb_hashes = [ot.hash for ot in online_torrents]
            logger.debug(
                f"[TorrentStatus] qBittorrent hashes (first 3): {qb_hashes[:3]}"
            )

            status_list = []
            for db_t in torrents:
                # Match by hash ONLY (reliable and accurate)
                matched_online = None
                if db_t.hash:
                    logger.debug(f"[TorrentStatus] Looking for DB hash: {db_t.hash}")
                    matched_online = next(
                        (
                            ot
                            for ot in online_torrents
                            if ot.hash.lower() == db_t.hash.lower()
                        ),
                        None,
                    )
                    if matched_online:
                        logger.debug(f"[TorrentStatus] ✓ Matched: {db_t.name}")
                    else:
                        logger.debug(
                            f"[TorrentStatus] ✗ Not found in download client: {db_t.name}"
                        )
                else:
                    logger.debug(f"[TorrentStatus] ✗ No hash in DB for: {db_t.name}")

                if matched_online:
                    status_list.append(
                        {
                            "id": db_t.id,
                            "name": db_t.name,
                            "url": db_t.url,
                            "downloaded": db_t.downloaded,
                            "status": matched_online.state,  # qBittorrent uses 'state' not 'status'
                            "progress": matched_online.progress,
                            "hash": matched_online.hash,
                        }
                    )
                else:
                    # If no hash or not found in qBittorrent, mark as missing
                    status_list.append(
                        {
                            "id": db_t.id,
                            "name": db_t.name,
                            "url": db_t.url,
                            "downloaded": db_t.downloaded,
                            "status": "missing",
                            "progress": 0,
                            "hash": db_t.hash,
                        }
                    )
            return status_list

    def download_torrent(self, torrent_id: int) -> ResponseModel:
        torrent = self.torrent.search(torrent_id)
        if not torrent:
            return ResponseModel(
                status=False,
                status_code=406,
                msg_en="Torrent not found in database.",
                msg_zh="数据库中未找到该种子。",
            )

        bangumi = None
        if torrent.bangumi_id:
            bangumi = self.bangumi.search_id(torrent.bangumi_id)

        if not bangumi:
            # Try to match it
            matched = self.bangumi.match_torrent(torrent.name)
            if matched:
                # Basic filter check similar to RSSEngine
                if matched.filter == "":
                    bangumi = matched
                else:
                    _filter = matched.filter.replace(",", "|")
                    if not re.search(_filter, torrent.name, re.IGNORECASE):
                        bangumi = matched

                if bangumi:
                    torrent.bangumi_id = bangumi.id
                    self.torrent.update(torrent)

        if not bangumi:
            return ResponseModel(
                status=False,
                status_code=406,
                msg_en="Associated Bangumi rule not found or matched.",
                msg_zh="未找到或匹配到关联的番剧规则。",
            )

        with DownloadClient() as client:
            save_path_before = bangumi.save_path
            if client.add_torrent(torrent, bangumi):
                torrent.downloaded = True
                # Clear rename status so the file gets renamed after download
                torrent.renamed_at = None
                torrent.renamed_file_count = None
                # Set pikpak_cloud_path here to avoid DB lock conflicts
                torrent.pikpak_cloud_path = bangumi.save_path
                self.torrent.update(torrent)
                # Persist newly generated save_path to database
                if not save_path_before and bangumi.save_path:
                    self.bangumi.update_save_path(bangumi.id, bangumi.save_path)
                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"Successfully re-added {torrent.name} to downloader.",
                    msg_zh=f"成功将 {torrent.name} 重新添加到下载器。",
                )
            else:
                return ResponseModel(
                    status=False,
                    status_code=406,
                    msg_en=f"Failed to add {torrent.name} to downloader. It might already exist.",
                    msg_zh=f"添加 {torrent.name} 失败，可能已存在。",
                )
