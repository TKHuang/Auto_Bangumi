import asyncio
import hashlib
from typing import Any

from qbittorrentapi import Client

from zen_bangumi.domain.commands.base import DeleteTorrent, DownloadTorrent
from zen_bangumi.effects.result import EffectResult, EffectStatus


class QBittorrentAdapter:
    def __init__(self, host: str, username: str, password: str, ssl: bool = False):
        self.client: Client = Client(
            host=host,
            username=username,
            password=password,
            VERIFY_WEBUI_CERTIFICATE=ssl,
            DISABLE_LOGGING_DEBUG_OUTPUT=True,
            REQUESTS_ARGS={"timeout": (3.1, 10)},
        )

    async def download_torrent(self, command: DownloadTorrent) -> EffectResult:
        def _download():
            torrent_hash = hashlib.sha1(command.torrent_url.encode()).hexdigest()
            
            existing_torrents = self.client.torrents_info()
            existing_hashes = {t.hash for t in existing_torrents}
            
            if torrent_hash in existing_hashes:
                return EffectResult(
                    command=command,
                    status=EffectStatus.SKIPPED,
                    error=f"Torrent already exists: {torrent_hash}"
                )
            
            response = self.client.torrents_add(
                is_paused=False,
                urls=command.torrent_url,
                save_path=command.save_path,
                use_auto_torrent_management=False,
                content_layout="NoSubfolder"
            )
            
            if response == "Ok.":
                return EffectResult(
                    command=command,
                    status=EffectStatus.SUCCESS
                )
            else:
                return EffectResult(
                    command=command,
                    status=EffectStatus.FAILED,
                    error=f"Failed to add torrent: {response}"
                )
        
        try:
            return await asyncio.to_thread(_download)
        except Exception as e:
            return EffectResult(
                command=command,
                status=EffectStatus.FAILED,
                error=str(e)
            )

    async def delete_torrent(self, command: DeleteTorrent) -> EffectResult:
        def _delete():
            self.client.torrents_delete(
                delete_files=command.delete_files,
                torrent_hashes=command.torrent_hash
            )
            return EffectResult(
                command=command,
                status=EffectStatus.SUCCESS
            )
        
        try:
            return await asyncio.to_thread(_delete)
        except Exception as e:
            return EffectResult(
                command=command,
                status=EffectStatus.FAILED,
                error=str(e)
            )

    async def get_torrent_info(self, hash: str) -> dict[str, Any] | None:
        def _get_info():
            torrents = self.client.torrents_info(hashes=hash)
            if not torrents:
                return None
            
            torrent = torrents[0]
            return {
                "hash": torrent.hash,
                "name": torrent.name,
                "progress": torrent.progress,
                "state": torrent.state,
            }
        
        try:
            return await asyncio.to_thread(_get_info)
        except Exception:
            return None
