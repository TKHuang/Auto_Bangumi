import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from module.concurrency.activation_lock import try_acquire_bangumi_activation_lock
from module.concurrency.rename_lock import try_acquire_rename_lock
from module.database.engine import get_db_session
from module.domain.parser.title_parser import TitleParser
from module.domain.value_objects import gen_save_path
from module.models.bangumi import Bangumi, BangumiUpdate
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.domain.models.torrent import TorrentState
from module.repositories.torrent import TorrentRepository
from module.services.downloader.factory import create_downloader
from module.services.renamer import RenamerService
from module.services.rss_engine import RSSEngine as AsyncRSSEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bangumi", tags=["bangumi"])


def _gen_save_path(data) -> str:
    return gen_save_path(settings.downloader.path, data.official_title, data.season, getattr(data, "year", None))


def _orm_title(bangumi) -> str:
    """Extract display title from an ORM Bangumi (reads through series relationship)."""
    _series = getattr(bangumi, "series", None)
    if _series is not None:
        return _series.canonical_title or ""
    return ""


def _bangumi_save_path(bangumi) -> Optional[str]:
    """Compute full per-season save path from ORM Bangumi."""
    if bangumi.path_override:
        return bangumi.path_override
    if bangumi.series is None:
        return None
    from pathlib import PurePosixPath
    return str(PurePosixPath(bangumi.series.root_path) / f"Season {bangumi.series.season}")


def _poster_needs_refresh(bangumi) -> bool:
    """Return True when a bangumi poster should be refreshed.

    We treat missing local poster cache files as stale even when the DB still
    points to a `posters/*.jpg` path. This is the migration/cache-loss case the
    old UI button failed to recover from.
    """
    poster = bangumi.series.poster_url if bangumi.series is not None else None
    if not poster:
        return True
    if isinstance(poster, str) and poster.startswith("posters/"):
        return not (Path("data") / poster).exists()
    return False


def _is_mikan_season_rss(rss_link: str) -> bool:
    if not rss_link:
        return False
    first_rss_link = rss_link.split(",")[0]
    return bool(MIKAN_SEASON_RSS_PATTERN.search(first_rss_link))


async def _match_torrents_list(downloader, torrent_repo, bangumi) -> list[str]:
    _sp = _bangumi_save_path(bangumi)
    torrents = await downloader.torrents_info(status_filter=None)
    matched = [t.hash for t in torrents if t.save_path == _sp]
    if not matched and bangumi.id:
        db_torrents = await torrent_repo.get_visible_by_bangumi(bangumi.id)
        matched = [t.hash for t in db_torrents if t.hash]
    return matched


@router.get(
    "/get/all", response_model=list[Bangumi], dependencies=[Depends(get_current_user)]
)
async def get_all_data(session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    # States that indicate a torrent is NOT successfully available
    error_states = {"error", "missing"}

    hash_status_map: dict[str, str] | None = None
    try:
        downloader = create_downloader(settings, session)
        hash_status_map = await downloader.get_hash_status_map()
    except Exception:
        await session.rollback()
        logger.debug("Failed to query downloader for hash status, using DB-only counts")

    orm_bangumi_list = await bangumi_repo.get_active()
    schema_bangumi_list = []

    for orm_bangumi in orm_bangumi_list:
        schema_bangumi = Bangumi.model_validate(orm_bangumi)
        if orm_bangumi.id:
            torrents = await torrent_repo.get_visible_by_bangumi(orm_bangumi.id)
            schema_bangumi.torrent_count = len(torrents)
            if hash_status_map is not None:
                def _is_completed(t) -> bool:
                    if not t.downloaded:
                        return False
                    # Downloader state takes priority when available
                    if t.hash and t.hash.lower() in hash_status_map:
                        return hash_status_map[t.hash.lower()] not in error_states
                    # Not in downloader — count as completed only if renamed
                    return bool(t.renamed_at)

                schema_bangumi.completed_count = sum(
                    1 for t in torrents if _is_completed(t)
                )
            else:
                schema_bangumi.completed_count = sum(1 for t in torrents if t.downloaded)
        schema_bangumi_list.append(schema_bangumi)

    return schema_bangumi_list


@router.get(
    "/get/{bangumi_id}",
    response_model=Bangumi,
    dependencies=[Depends(get_current_user)],
)
async def get_data(bangumi_id: int, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    data = await bangumi_repo.get_by_id(bangumi_id)
    if not data:
        return JSONResponse(
            status_code=404,
            content={"msg_en": f"Can't find data with {bangumi_id}", "msg_zh": f"无法找到 id {bangumi_id} 的数据"},
        )
    return data


@router.patch(
    "/update/{bangumi_id}",
    dependencies=[Depends(get_current_user)],
)
async def update_rule(
    bangumi_id: int,
    data: BangumiUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    old_data = await bangumi_repo.get_by_id(bangumi_id)
    if not old_data:
        return JSONResponse(
            status_code=404,
            content={"msg_en": f"Can't find data with {bangumi_id}", "msg_zh": f"无法找到 id {bangumi_id} 的数据"},
        )

    lock = await try_acquire_rename_lock()
    if lock is None:
        return JSONResponse(
            status_code=409,
            content={
                "msg_en": "Rename is already in progress. Please try Apply again shortly.",
                "msg_zh": "当前正在执行重命名，请稍后再试。",
            },
        )

    try:
        _old_season = old_data.series.season if old_data.series is not None else 1
        _old_title = old_data.series.canonical_title if old_data.series is not None else ""
        rename_fields_changed = (
            _old_season != data.season or _old_title != data.official_title
        )

        downloader = create_downloader(settings, session)
        match_list = await _match_torrents_list(downloader, torrent_repo, old_data)

        path = _gen_save_path(data)
        if match_list:
            await downloader.move_torrent(match_list, path)

        update_dict = {
            "official_title": data.official_title,
            "title_raw": data.title_raw,
            "season": data.season,
            "season_raw": data.season_raw,
            "group_name": data.group_name,
            "dpi": data.dpi,
            "source": data.source,
            "subtitle": data.subtitle,
            "eps_collect": data.eps_collect,
            "offset": data.offset,
            "filter": data.filter,
            "rss_link": data.rss_link,
            "poster_link": data.poster_link,
            "added": data.added,
            "rule_name": data.rule_name,
            "save_path": path,
            "deleted": data.deleted,
            "year": data.year,
            "rss_id": data.rss_id,
        }
        await bangumi_repo.update_simple(bangumi_id, update_dict)

        renamed_count = 0
        if rename_fields_changed:
            await torrent_repo.clear_rename_status(bangumi_id, new_cloud_path=path)
            logger.info(f"[API] Cleared rename status (season/title changed for bangumi {bangumi_id})")
            await session.commit()

            # Trigger immediate re-rename so renamed_at gets set right away
            renamer = RenamerService(
                session, rename_method=settings.bangumi_manage.rename_method
            )
            renamed_results = await renamer.rename_bangumi(downloader, bangumi_id)
            renamed_count = sum(r.get("file_count", 0) for r in renamed_results)
            logger.info(f"[API] Re-renamed {renamed_count} files for bangumi {bangumi_id}")
        else:
            await session.commit()

        msg_suffix_en = f" (renamed {renamed_count} files)" if renamed_count else ""
        msg_suffix_zh = f"（重命名了 {renamed_count} 个文件）" if renamed_count else ""
        _title = _orm_title(old_data)
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Update rule for {_title}{msg_suffix_en}",
                "msg_zh": f"更新 {_title} 规則{msg_suffix_zh}",
            },
        )
    finally:
        lock.release()


@router.delete(
    path="/delete/{bangumi_id}",
    dependencies=[Depends(get_current_user)],
)
async def delete_rule(bangumi_id: int, file: bool = False, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    data = await bangumi_repo.get_by_id(bangumi_id)
    if not data:
        return JSONResponse(
            status_code=404,
            content={"msg_en": f"Can't find id {bangumi_id}", "msg_zh": f"无法找到 id {bangumi_id}"},
        )

    _title = _orm_title(data)
    torrent_msg_en = ""
    torrent_msg_zh = ""
    if file:
        downloader = create_downloader(settings, session)
        hash_list = await _match_torrents_list(downloader, torrent_repo, data)
        if hash_list:
            await downloader.torrents_delete(hash_list, delete_files=True)
            torrent_msg_en = f"Delete rule and torrents for {_title}"
            torrent_msg_zh = f"删除 {_title} 规则和种子"

    await bangumi_repo.delete_one(bangumi_id)
    await session.commit()

    return JSONResponse(
        status_code=200,
        content={
            "msg_en": f"Delete rule for {_title}. {torrent_msg_en}",
            "msg_zh": f"删除 {_title} 规则。{torrent_msg_zh}",
        },
    )


@router.delete(
    path="/delete",
    dependencies=[Depends(get_current_user)],
)
async def delete_many_rule(bangumi_id: list[int] = Body(...), file: bool = False, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    if not bangumi_id:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "No IDs provided", "msg_zh": "未提供 ID"},
        )

    if file:
        downloader = create_downloader(settings, session)
        for _id in bangumi_id:
            data = await bangumi_repo.get_by_id(_id)
            if data:
                hash_list = await _match_torrents_list(downloader, torrent_repo, data)
                if hash_list:
                    await downloader.torrents_delete(hash_list, delete_files=True)

    count = await bangumi_repo.delete_many(bangumi_id)
    await session.commit()

    return JSONResponse(
        status_code=200,
        content={"msg_en": f"Deleted {count} rules", "msg_zh": f"已删除 {count} 条规则"},
    )


@router.delete(
    path="/disable/{bangumi_id}",
    dependencies=[Depends(get_current_user)],
)
async def disable_rule(bangumi_id: int, file: bool = False, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    data = await bangumi_repo.get_by_id(bangumi_id)
    if not data:
        return JSONResponse(
            status_code=404,
            content={"msg_en": f"Can't find id {bangumi_id}", "msg_zh": f"无法找到 id {bangumi_id}"},
        )

    await bangumi_repo.update_simple(bangumi_id, {"deleted": True})
    await session.commit()

    _title = _orm_title(data)
    if file:
        downloader = create_downloader(settings, session)
        hash_list = await _match_torrents_list(downloader, torrent_repo, data)
        if hash_list:
            await downloader.torrents_delete(hash_list, delete_files=True)
            return JSONResponse(
                status_code=200,
                content={
                    "msg_en": f"Delete rule and torrents for {_title}",
                    "msg_zh": f"删除 {_title} 规则和种子",
                },
            )

    return JSONResponse(
        status_code=200,
        content={"msg_en": f"Disable rule for {_title}", "msg_zh": f"禁用 {_title} 规则"},
    )


@router.delete(
    path="/disable",
    dependencies=[Depends(get_current_user)],
)
async def disable_many_rule(bangumi_id: list[int] = Body(...), file: bool = False, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    if not bangumi_id:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "No IDs provided", "msg_zh": "未提供 ID"},
        )

    if file:
        downloader = create_downloader(settings, session)
        for _id in bangumi_id:
            data = await bangumi_repo.get_by_id(_id)
            if data:
                hash_list = await _match_torrents_list(downloader, torrent_repo, data)
                if hash_list:
                    await downloader.torrents_delete(hash_list, delete_files=True)

    count = await bangumi_repo.disable_many(bangumi_id)
    await session.commit()

    return JSONResponse(
        status_code=200,
        content={"msg_en": f"Disabled {count} rules", "msg_zh": f"已禁用 {count} 条规则"},
    )


@router.patch(
    path="/enable/{bangumi_id}",
    dependencies=[Depends(get_current_user)],
)
async def enable_rule(bangumi_id: int, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    data = await bangumi_repo.get_by_id(bangumi_id)
    if not data:
        return JSONResponse(
            status_code=404,
            content={"msg_en": f"Can't find id {bangumi_id}", "msg_zh": f"无法找到 id {bangumi_id}"},
        )

    await bangumi_repo.update_simple(bangumi_id, {"deleted": False})
    await session.commit()

    _title = _orm_title(data)
    return JSONResponse(
        status_code=200,
        content={"msg_en": f"Enable rule for {_title}", "msg_zh": f"启用 {_title} 规则"},
    )


@router.delete(
    "/reset/all", dependencies=[Depends(get_current_user)]
)
async def reset_all(session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    await bangumi_repo.delete_all()
    await session.commit()
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Reset all rules successfully.", "msg_zh": "重置所有规则成功。"},
    )


@router.post(
    path="/refresh/poster/all",
    dependencies=[Depends(get_current_user)],
)
async def refresh_poster(session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    rss_repo = RSSRepository(session)
    torrent_repo = TorrentRepository(session)

    bangumis = await bangumi_repo.get_all()
    parser = TitleParser()

    for bangumi in bangumis:
        _canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
        if _poster_needs_refresh(bangumi):
            poster_fetched = False

            if bangumi.rss_id:
                rss = await rss_repo.get_by_id(bangumi.rss_id)
                if rss and rss.parser == "mikan":
                    torrent = await torrent_repo.get_by_bangumi_with_homepage(bangumi.id)
                    if torrent and torrent.homepage:
                        try:
                            result = await asyncio.to_thread(parser.mikan_parser_with_rss, torrent.homepage)
                            if result.poster_link:
                                await bangumi_repo.update_simple(bangumi.id, {"poster_link": result.poster_link})
                                poster_fetched = True
                        except Exception as e:
                            logger.warning(f"[Poster] Mikan parser failed for {_canonical}: {e}")

            if not poster_fetched:
                from module.domain.parser.analyser.tmdb_parser import tmdb_parser
                _language = settings.rss_parser.language
                _tmdb_info = await asyncio.to_thread(tmdb_parser, _canonical, _language)
                if _tmdb_info and _tmdb_info.poster_link:
                    await bangumi_repo.update_simple(bangumi.id, {"poster_link": _tmdb_info.poster_link})

    await session.commit()
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh poster link successfully.", "msg_zh": "刷新海报链接成功。"},
    )


@router.post(
    path="/refresh/poster/{bangumi_id}",
    dependencies=[Depends(get_current_user)],
)
async def refresh_poster_by_id(bangumi_id: int, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    rss_repo = RSSRepository(session)
    torrent_repo = TorrentRepository(session)

    bangumi = await bangumi_repo.get_by_id(bangumi_id)
    if not bangumi:
        return JSONResponse(
            status_code=404,
            content={"msg_en": f"Can't find id {bangumi_id}", "msg_zh": f"无法找到 id {bangumi_id}"},
        )

    _bg_canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
    poster_fetched = False
    parser = TitleParser()

    if bangumi.rss_id:
        rss = await rss_repo.get_by_id(bangumi.rss_id)
        if rss and rss.parser == "mikan":
            torrent = await torrent_repo.get_by_bangumi_with_homepage(bangumi.id)
            if torrent and torrent.homepage:
                try:
                    result = await asyncio.to_thread(parser.mikan_parser_with_rss, torrent.homepage)
                    if result.poster_link:
                        await bangumi_repo.update_simple(bangumi.id, {"poster_link": result.poster_link})
                        poster_fetched = True
                except Exception as e:
                    logger.warning(f"[Poster] Mikan parser failed for {_bg_canonical}: {e}")

    if not poster_fetched:
        from module.domain.parser.analyser.tmdb_parser import tmdb_parser
        _language = settings.rss_parser.language
        _tmdb_info = await asyncio.to_thread(tmdb_parser, _bg_canonical, _language)
        if _tmdb_info and _tmdb_info.poster_link:
            await bangumi_repo.update_simple(bangumi.id, {"poster_link": _tmdb_info.poster_link})

    await session.commit()
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh poster link successfully.", "msg_zh": "刷新海报链接成功。"},
    )


@router.get(
    "/torrent/{bangumi_id}",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(get_current_user)],
)
async def get_torrent_status(bangumi_id: int, session: AsyncSession = Depends(get_db_session)):
    torrent_repo = TorrentRepository(session)
    downloader = create_downloader(settings, session)

    db_torrents = await torrent_repo.get_visible_by_bangumi(bangumi_id)
    if not db_torrents:
        return []

    cloud_paths = {
        t.hash.lower(): t.pikpak_cloud_path
        for t in db_torrents
        if t.hash and t.pikpak_cloud_path
    }
    # Downloader queries can fail (auth issues, rate-limit cooldown, network).
    # Surface DB-only state with a clear "downloader_unreachable" marker rather
    # than 500-ing — the user still wants to see what's been collected and the
    # error message can guide them to fix their downloader config.
    online_torrents = []
    downloader_error: str | None = None
    try:
        online_torrents = await downloader.torrents_info(
            status_filter="all", cloud_paths=cloud_paths,
        )
    except Exception as exc:
        downloader_error = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "[bangumi] torrent status fetch failed for bangumi=%d: %s",
            bangumi_id, downloader_error,
        )

    status_list = []
    for db_t in db_torrents:
        matched_online = None
        if db_t.hash:
            matched_online = next(
                (ot for ot in online_torrents if ot.hash.lower() == db_t.hash.lower()),
                None,
            )
        if matched_online:
            status_list.append({
                "id": db_t.id, "name": db_t.name, "url": db_t.url,
                "downloaded": db_t.downloaded, "status": matched_online.state,
                "progress": matched_online.progress, "hash": matched_online.hash,
            })
        elif downloader_error is not None:
            status_list.append({
                "id": db_t.id, "name": db_t.name, "url": db_t.url,
                "downloaded": db_t.downloaded,
                "status": "downloader_unreachable",
                "progress": 0,
                "hash": db_t.hash,
                "downloader_error": downloader_error,
            })
        else:
            status = "archived" if db_t.renamed_at else "missing"
            status_list.append({
                "id": db_t.id, "name": db_t.name, "url": db_t.url,
                "downloaded": db_t.downloaded, "status": status,
                "progress": 1.0 if status == "archived" else 0,
                "hash": db_t.hash,
            })
    return status_list


@router.post(
    "/torrent/download",
    dependencies=[Depends(get_current_user)],
)
async def download_torrent(torrent_id: int = Query(...), session: AsyncSession = Depends(get_db_session)):
    torrent_repo = TorrentRepository(session)
    bangumi_repo = BangumiRepository(session)

    torrent = await torrent_repo.get_by_id(torrent_id)
    if not torrent:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "Torrent not found in database.", "msg_zh": "数据库中未找到该种子。"},
        )

    if torrent.state == TorrentState.EXCLUDED:
        return JSONResponse(
            status_code=400,
            content={
                "msg_en": "Cannot download an excluded torrent.",
                "msg_zh": "无法下载已排除的种子。",
            },
        )

    bangumi = None
    if torrent.bangumi_id:
        bangumi = await bangumi_repo.get_by_id(torrent.bangumi_id)

    if not bangumi:
        matched = await bangumi_repo.match_torrent(torrent.name)
        if matched:
            if matched.filter == "":
                bangumi = matched
            else:
                _filter = matched.filter.replace(",", "|")
                if not re.search(_filter, torrent.name, re.IGNORECASE):
                    bangumi = matched

    if not bangumi:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "Associated Bangumi rule not found or matched.", "msg_zh": "未找到或匹配到关联的番剧规则。"},
        )

    downloader = create_downloader(settings, session)
    _redl_sp = _bangumi_save_path(bangumi)
    save_path_before = _redl_sp

    if torrent.hash:
        try:
            await downloader.torrents_delete([torrent.hash], delete_files=True)
        except Exception:
            logger.debug(f"Failed to delete old torrent {torrent.hash} before re-download (may not exist)")

    success = await downloader.add_torrents(
        urls=[torrent.url],
        save_path=_redl_sp or "",
        torrent_files=None,
    )

    if success:
        torrent.downloaded = True
        torrent.renamed_at = None
        torrent.renamed_file_count = None
        torrent.pikpak_cloud_path = _redl_sp
        if torrent.bangumi_id != bangumi.id:
            torrent.bangumi_id = bangumi.id
        if not save_path_before and _redl_sp:
            await bangumi_repo.update_simple(bangumi.id, {"save_path": _redl_sp})
        await session.commit()
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Successfully re-added {torrent.name} to downloader.",
                "msg_zh": f"成功将 {torrent.name} 重新添加到下载器。",
            },
        )
    else:
        return JSONResponse(
            status_code=404,
            content={
                "msg_en": f"Failed to add {torrent.name} to downloader. It might already exist.",
                "msg_zh": f"添加 {torrent.name} 失败，可能已存在。",
            },
        )


@router.post(
    path="/{bangumi_id}/activate",
    dependencies=[Depends(get_current_user)],
)
async def activate_pending_bangumi(
    bangumi_id: int,
    filter: str = Body(default=None, embed=True),
    included_hashes: list[str] | None = Body(default=None, embed=True),
    excluded_hashes: list[str] | None = Body(default=None, embed=True),
    session: AsyncSession = Depends(get_db_session),
):
    activation_lock = await try_acquire_bangumi_activation_lock(bangumi_id)
    if activation_lock is None:
        return JSONResponse(
            status_code=409,
            content={
                "msg_en": "Bangumi activation is already running.",
                "msg_zh": "该番剧正在激活中，请稍后再试。",
            },
        )

    try:
        return await _activate_pending_bangumi_locked(
            bangumi_id,
            filter,
            included_hashes,
            excluded_hashes,
            session,
        )
    finally:
        activation_lock.release()


async def _activate_pending_bangumi_locked(
    bangumi_id: int,
    filter: str | None,
    included_hashes: list[str] | None,
    excluded_hashes: list[str] | None,
    session: AsyncSession,
):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)
    success, message = await bangumi_repo.activate_pending(bangumi_id, filter)
    if not success:
        return JSONResponse(
            status_code=400,
            content={"msg_en": message, "msg_zh": "该番剧不在待审核状态"},
        )

    if excluded_hashes:
        bangumi = await bangumi_repo.get_by_id(bangumi_id)
        await torrent_repo.exclude_hashes(
            excluded_hashes,
            bangumi_id,
            rss_id=bangumi.rss_id if bangumi else None,
        )

    await session.commit()

    bangumi = await bangumi_repo.get_by_id(bangumi_id)
    if not bangumi:
        return JSONResponse(
            status_code=500,
            content={
                "msg_en": "Internal error: bangumi not found after activation",
                "msg_zh": "内部错误：激活后未找到番剧",
            },
        )

    downloader = create_downloader(settings, session)
    download_result = await AsyncRSSEngine.download_bangumi(
        session,
        downloader,
        bangumi_id,
        included_hashes=included_hashes,
    )

    if isinstance(download_result, dict) and download_result.get("status"):
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Bangumi activated and {download_result.get('message', '')}",
                "msg_zh": f"番剧已激活，{download_result.get('message', '')}",
            },
        )
    else:
        msg = download_result.get("message", "") if isinstance(download_result, dict) else str(download_result)
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Bangumi activated but download issue: {msg}",
                "msg_zh": f"番剧已激活，但下载出现问题：{msg}",
            },
        )


@router.post(
    path="/{bangumi_id}/retrigger-rename",
    dependencies=[Depends(get_current_user)],
)
async def retrigger_rename(bangumi_id: int, session: AsyncSession = Depends(get_db_session)):
    lock = await try_acquire_rename_lock()
    if lock is None:
        return JSONResponse(
            status_code=409,
            content={
                "msg_en": "Rename is already in progress. Please try again shortly.",
                "msg_zh": "当前正在执行重命名，请稍后再试。",
            },
        )

    downloader = create_downloader(settings, session)
    renamer = RenamerService(
        session, rename_method=settings.bangumi_manage.rename_method
    )
    try:
        renamed_results = await renamer.rename_bangumi(downloader, bangumi_id, retrigger=True)
        renamed_count = sum(r.get("file_count", 0) for r in renamed_results)
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Re-rename completed, renamed {renamed_count} files",
                "msg_zh": f"重新重命名完成，重命名了 {renamed_count} 个文件",
            },
        )
    finally:
        lock.release()


@router.get(
    path="/rename-conflicts",
    dependencies=[Depends(get_current_user)],
)
async def list_rename_conflicts(
    bangumi_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    """List torrents that the renamer skipped due to a name collision.

    These torrents are stuck on ``rename_status=CONFLICT`` and the auto-renamer
    will NOT retry them. The user must either delete one of the duplicates
    (``DELETE /bangumi/torrent/{torrent_id}``), tweak the bangumi rule so the
    targets no longer collide, or call
    ``POST /bangumi/rename-conflicts/{torrent_id}/retry`` to ask the renamer
    to try again on the next tick.
    """
    torrent_repo = TorrentRepository(session)
    bangumi_repo = BangumiRepository(session)
    rows = await torrent_repo.get_rename_conflicts(bangumi_id)

    bangumi_titles: dict[int, str] = {}
    for row in rows:
        if row.bangumi_id is None or row.bangumi_id in bangumi_titles:
            continue
        b = await bangumi_repo.get_by_id(row.bangumi_id)
        if b is not None:
            bangumi_titles[row.bangumi_id] = _orm_title(b) or ""

    return JSONResponse(
        status_code=200,
        content={
            "conflicts": [
                {
                    "torrent_id": row.id,
                    "bangumi_id": row.bangumi_id,
                    "bangumi_title": bangumi_titles.get(row.bangumi_id or -1, ""),
                    "torrent_name": row.name,
                    "torrent_hash": row.hash,
                    "conflict_target": row.rename_conflict_target,
                }
                for row in rows
            ],
        },
    )


@router.post(
    path="/rename-conflicts/{torrent_id}/retry",
    dependencies=[Depends(get_current_user)],
)
async def retry_rename_conflict(
    torrent_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Move a CONFLICT row back to PENDING so the renamer retries it.

    Use after the user has manually resolved the collision (e.g. removed the
    duplicate file in the cloud, or changed the bangumi rule).
    """
    torrent_repo = TorrentRepository(session)
    torrent = await torrent_repo.get_by_id(torrent_id)
    if torrent is None:
        return JSONResponse(
            status_code=404,
            content={
                "msg_en": f"Torrent {torrent_id} not found.",
                "msg_zh": f"找不到 torrent {torrent_id}。",
            },
        )
    await torrent_repo.clear_rename_conflict(torrent_id)
    await session.commit()
    return JSONResponse(
        status_code=200,
        content={
            "msg_en": "Conflict cleared; renamer will retry on next tick.",
            "msg_zh": "冲突已清除，下一次重命名将重试。",
        },
    )


@router.post(
    path="/{bangumi_id}/backfill-source",
    dependencies=[Depends(get_current_user)],
)
async def backfill_source(bangumi_id: int, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    bangumi = await bangumi_repo.get_by_id(bangumi_id)
    if not bangumi:
        return JSONResponse(
            status_code=404,
            content={
                "msg_en": f"Can't find data with {bangumi_id}",
                "msg_zh": f"无法找到 id {bangumi_id} 的数据",
            },
        )

    if not _is_mikan_season_rss(bangumi.rss_link):
        return JSONResponse(
            status_code=400,
            content={
                "msg_en": "Backfill from source requires a season-specific Mikan RSS link.",
                "msg_zh": "来源回补需要 season-specific 的 Mikan RSS 链接。",
            },
        )

    downloader = create_downloader(settings, session)
    result = await AsyncRSSEngine.download_bangumi(session, downloader, bangumi_id)
    count = result.get("count", 0) if isinstance(result, dict) else 0
    message = result.get("message", "") if isinstance(result, dict) else str(result)
    title = _orm_title(bangumi)

    if isinstance(result, dict) and result.get("status"):
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Backfilled {title} from source, downloaded {count} torrents",
                "msg_zh": f"已从来源回补 {title}，下载了 {count} 个种子",
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "msg_en": f"Backfill finished for {title} with issue: {message}",
            "msg_zh": f"{title} 回补完成，但出现问题：{message}",
        },
    )
