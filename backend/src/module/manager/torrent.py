import logging

from module.database import Database
from module.downloader import DownloadClient
from module.models import Bangumi, BangumiUpdate, ResponseModel
from module.parser import TitleParser

logger = logging.getLogger(__name__)


class TorrentManager(Database):
    def __match_torrents_list(self, data: Bangumi | BangumiUpdate, bangumi_id: int = None) -> list:
        """Match torrents by save_path, with database fallback for PikPak.
        
        Primary method: Match by save_path (works for qBittorrent)
        Fallback: Query database by bangumi_id (for PikPak when hash_map is empty)
        """
        with DownloadClient() as client:
            torrents = client.get_torrent_info(status_filter=None)
        logger.debug(f"[DEBUG] __match_torrents_list: looking for save_path={data.save_path}")
        logger.debug(f"[DEBUG] __match_torrents_list: found {len(torrents)} torrents total")
        for torrent in torrents:
            logger.debug(f"[DEBUG]   torrent: hash={torrent.hash[:8]}..., save_path={torrent.save_path}, match={torrent.save_path == data.save_path}")
        
        # Primary: match by save_path (works for qBittorrent)
        matched = [
            torrent.hash for torrent in torrents if torrent.save_path == data.save_path
        ]
        logger.debug(f"[DEBUG] __match_torrents_list: matched {len(matched)} torrents by path")
        
        # Fallback: if no matches and we have bangumi_id, query database
        # This handles PikPak where hash_map may be empty
        if not matched and bangumi_id:
            logger.debug(f"[DEBUG] __match_torrents_list: path matching failed, trying database fallback")
            db_torrents = self.torrent.search_by_bangumi_id(bangumi_id)
            # Only return hashes that exist in the downloader (case-insensitive)
            downloader_hashes = {t.hash.lower() for t in torrents if t.hash}
            matched = [
                t.hash for t in db_torrents 
                if t.hash and t.hash.lower() in downloader_hashes
            ]
            logger.debug(f"[DEBUG] __match_torrents_list: matched {len(matched)} torrents from database")
        
        return matched

    def delete_torrents(self, data: Bangumi, client: DownloadClient):
        hash_list = self.__match_torrents_list(data, bangumi_id=data.id)
        if hash_list:
            client.delete_torrent(hash_list)
            logger.info(f"Delete rule and torrents for {data.official_title}")
            return ResponseModel(
                status_code=200,
                status=True,
                msg_en=f"Delete rule and torrents for {data.official_title}",
                msg_zh=f"删除 {data.official_title} 规则和种子",
            )
        else:
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en=f"Can't find torrents for {data.official_title}",
                msg_zh=f"无法找到 {data.official_title} 的种子",
            )

    def delete_rule(self, _id: int | str, file: bool = False):
        data = self.bangumi.search_id(int(_id))
        if isinstance(data, Bangumi):
            with DownloadClient() as client:
                # Delete the bangumi rule (this cascades to delete associated torrents)
                self.bangumi.delete_one(int(_id))
                if file:
                    torrent_message = self.delete_torrents(data, client)
                logger.info(f"[Manager] Delete rule for {data.official_title}")
                return ResponseModel(
                    status_code=200,
                    status=True,
                    msg_en=f"Delete rule for {data.official_title}. {torrent_message.msg_en if file else ''}",
                    msg_zh=f"删除 {data.official_title} 规则。{torrent_message.msg_zh if file else ''}",
                )
        else:
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en=f"Can't find id {_id}",
                msg_zh=f"无法找到 id {_id}",
            )

    def disable_rule(self, _id: str | int, file: bool = False):
        data = self.bangumi.search_id(int(_id))
        if isinstance(data, Bangumi):
            with DownloadClient() as client:
                # client.remove_rule(data.rule_name)
                data.deleted = True
                self.bangumi.update(data)
                if file:
                    torrent_message = self.delete_torrents(data, client)
                    return torrent_message
                logger.info(f"[Manager] Disable rule for {data.official_title}")
                return ResponseModel(
                    status_code=200,
                    status=True,
                    msg_en=f"Disable rule for {data.official_title}",
                    msg_zh=f"禁用 {data.official_title} 规则",
                )
        else:
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en=f"Can't find id {_id}",
                msg_zh=f"无法找到 id {_id}",
            )

    def delete_many_rules(self, ids: list[int], file: bool = False) -> ResponseModel:
        """Delete multiple bangumi rules in a single batch operation.

        Args:
            ids: List of bangumi IDs to delete.
            file: Whether to also delete associated torrent files.

        Returns:
            ResponseModel with operation result.
        """
        if not ids:
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en="No IDs provided",
                msg_zh="未提供 ID",
            )

        # If deleting files, need to handle each separately for torrent deletion
        if file:
            with DownloadClient() as client:
                for _id in ids:
                    data = self.bangumi.search_id(_id)
                    if isinstance(data, Bangumi):
                        self.delete_torrents(data, client)

        # Batch delete from database
        count = self.bangumi.delete_many(ids)
        logger.info(f"[Manager] Batch deleted {count} bangumi rules")

        return ResponseModel(
            status_code=200,
            status=True,
            msg_en=f"Deleted {count} rules",
            msg_zh=f"已删除 {count} 条规则",
        )

    def disable_many_rules(self, ids: list[int], file: bool = False) -> ResponseModel:
        """Disable multiple bangumi rules in a single batch operation.

        Args:
            ids: List of bangumi IDs to disable.
            file: Whether to also delete associated torrent files.

        Returns:
            ResponseModel with operation result.
        """
        if not ids:
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en="No IDs provided",
                msg_zh="未提供 ID",
            )

        # If deleting files, need to handle each separately for torrent deletion
        if file:
            with DownloadClient() as client:
                for _id in ids:
                    data = self.bangumi.search_id(_id)
                    if isinstance(data, Bangumi):
                        self.delete_torrents(data, client)

        # Batch disable in database
        count = self.bangumi.disable_many(ids)
        logger.info(f"[Manager] Batch disabled {count} bangumi rules")

        return ResponseModel(
            status_code=200,
            status=True,
            msg_en=f"Disabled {count} rules",
            msg_zh=f"已禁用 {count} 条规则",
        )

    def enable_rule(self, _id: str | int):
        data = self.bangumi.search_id(int(_id))
        if data:
            data.deleted = False
            self.bangumi.update(data)
            logger.info(f"[Manager] Enable rule for {data.official_title}")
            return ResponseModel(
                status_code=200,
                status=True,
                msg_en=f"Enable rule for {data.official_title}",
                msg_zh=f"启用 {data.official_title} 规则",
            )
        else:
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en=f"Can't find id {_id}",
                msg_zh=f"无法找到 id {_id}",
            )

    def update_rule(self, bangumi_id, data: BangumiUpdate):
        old_data: Bangumi = self.bangumi.search_id(bangumi_id)
        if old_data:
            logger.debug(f"[DEBUG] update_rule: bangumi_id={bangumi_id}")
            logger.debug(f"[DEBUG] update_rule: old_data.save_path={old_data.save_path}")
            logger.debug(f"[DEBUG] update_rule: old_data.season={old_data.season}, new_data.season={data.season}")

            # Check if rename-relevant fields changed
            rename_fields_changed = (
                old_data.season != data.season
                or old_data.official_title != data.official_title
            )

            # Move torrent
            match_list = self.__match_torrents_list(old_data, bangumi_id=bangumi_id)
            logger.debug(f"[DEBUG] update_rule: match_list={match_list}")
            with DownloadClient() as client:
                path = client._gen_save_path(data)
                logger.debug(f"[DEBUG] update_rule: new path={path}")
                if match_list:
                    logger.debug(f"[DEBUG] update_rule: calling move_torrent with {len(match_list)} hashes")
                    client.move_torrent(match_list, path)
                else:
                    logger.debug("[DEBUG] update_rule: match_list is empty, skipping move_torrent")
            data.save_path = path
            self.bangumi.update(data, bangumi_id)

            # Clear rename status if rename-relevant fields changed
            if rename_fields_changed:
                reset_count = self.torrent.clear_rename_status(bangumi_id)
                logger.info(
                    f"[Manager] Cleared rename status for {reset_count} torrents "
                    f"(season/title changed for bangumi {bangumi_id})"
                )

            return ResponseModel(
                status_code=200,
                status=True,
                msg_en=f"Update rule for {data.official_title}",
                msg_zh=f"更新 {data.official_title} 规则",
            )
        else:
            logger.error(f"[Manager] Can't find data with {bangumi_id}")
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en=f"Can't find data with {bangumi_id}",
                msg_zh=f"无法找到 id {bangumi_id} 的数据",
            )

    def refresh_poster(self):
        bangumis = self.bangumi.search_all()
        for bangumi in bangumis:
            if not bangumi.poster_link:
                poster_fetched = False

                # Try Mikan parser if RSS uses mikan parser
                if bangumi.rss_id:
                    rss = self.rss.search_id(bangumi.rss_id)
                    if rss and rss.parser == "mikan":
                        # Find a torrent with homepage for this bangumi
                        torrent = self.torrent.search_by_bangumi_id_with_homepage(
                            bangumi.id
                        )
                        if torrent and torrent.homepage:
                            try:
                                result = TitleParser().mikan_parser_with_rss(
                                    torrent.homepage
                                )
                                if result.poster_link:
                                    bangumi.poster_link = result.poster_link
                                    poster_fetched = True
                                    logger.debug(
                                        f"[Poster] Fetched from Mikan: {bangumi.official_title}"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"[Poster] Mikan parser failed for {bangumi.official_title}: {e}"
                                )

                # Fallback to TMDB if Mikan didn't work or not applicable
                if not poster_fetched:
                    TitleParser().tmdb_poster_parser(bangumi)

        self.bangumi.update_all(bangumis)
        return ResponseModel(
            status_code=200,
            status=True,
            msg_en="Refresh poster link successfully.",
            msg_zh="刷新海报链接成功。",
        )

    def refind_poster(self, bangumi_id: int):
        bangumi = self.bangumi.search_id(bangumi_id)
        poster_fetched = False

        # Try Mikan parser if RSS uses mikan parser
        if bangumi.rss_id:
            rss = self.rss.search_id(bangumi.rss_id)
            if rss and rss.parser == "mikan":
                # Find a torrent with homepage for this bangumi
                torrent = self.torrent.search_by_bangumi_id_with_homepage(bangumi.id)
                if torrent and torrent.homepage:
                    try:
                        result = TitleParser().mikan_parser_with_rss(torrent.homepage)
                        if result.poster_link:
                            bangumi.poster_link = result.poster_link
                            poster_fetched = True
                            logger.debug(
                                f"[Poster] Fetched from Mikan: {bangumi.official_title}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[Poster] Mikan parser failed for {bangumi.official_title}: {e}"
                        )

        # Fallback to TMDB if Mikan didn't work or not applicable
        if not poster_fetched:
            TitleParser().tmdb_poster_parser(bangumi)

        self.bangumi.update(bangumi)
        return ResponseModel(
            status_code=200,
            status=True,
            msg_en="Refresh poster link successfully.",
            msg_zh="刷新海报链接成功。",
        )

    def search_all_bangumi(self):
        datas = self.bangumi.search_all()
        if not datas:
            return []
        return [data for data in datas if not data.deleted]

    def search_one(self, _id: int | str):
        data = self.bangumi.search_id(int(_id))
        if not data:
            logger.error(f"[Manager] Can't find data with {_id}")
            return ResponseModel(
                status_code=406,
                status=False,
                msg_en=f"Can't find data with {_id}",
                msg_zh=f"无法找到 id {_id} 的数据",
            )
        else:
            return data


if __name__ == "__main__":
    with TorrentManager() as manager:
        manager.refresh_poster()
