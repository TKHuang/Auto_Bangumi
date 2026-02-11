import asyncio
import logging
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.database.engine import get_db_session
from module.domain.parser.title_parser import TitleParser
from module.domain.value_objects import gen_save_path
from module.models.bangumi import Bangumi, BangumiUpdate
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.factory import create_downloader
from module.services.renamer import RenamerService
from module.services.rss_engine import RSSEngine as AsyncRSSEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bangumi", tags=["bangumi"])


def _gen_save_path(data) -> str:
    return gen_save_path(settings.downloader.path, data.official_title, data.season, getattr(data, "year", None))


async def _match_torrents_list(downloader, torrent_repo, bangumi) -> list[str]:
    torrents = await downloader.torrents_info(status_filter=None)
    matched = [t.hash for t in torrents if t.save_path == bangumi.save_path]
    if not matched and bangumi.id:
        db_torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        matched = [t.hash for t in db_torrents if t.hash]
    return matched


@router.get(
    "/get/all", response_model=list[Bangumi], dependencies=[Depends(get_current_user)]
)
async def get_all_data(session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)
    
    orm_bangumi_list = await bangumi_repo.get_active()
    schema_bangumi_list = []
    
    for orm_bangumi in orm_bangumi_list:
        schema_bangumi = Bangumi.model_validate(orm_bangumi)
        if orm_bangumi.id:
            torrents = await torrent_repo.get_by_bangumi(orm_bangumi.id)
            schema_bangumi.torrent_count = len(torrents)
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

    rename_fields_changed = (
        old_data.season != data.season or old_data.official_title != data.official_title
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
        renamer = RenamerService(session)
        renamed_results = await renamer.rename_bangumi(downloader, bangumi_id)
        renamed_count = sum(r.get("file_count", 0) for r in renamed_results)
        logger.info(f"[API] Re-renamed {renamed_count} files for bangumi {bangumi_id}")
    else:
        await session.commit()

    msg_suffix_en = f" (renamed {renamed_count} files)" if renamed_count else ""
    msg_suffix_zh = f"（重命名了 {renamed_count} 个文件）" if renamed_count else ""
    return JSONResponse(
        status_code=200,
        content={
            "msg_en": f"Update rule for {data.official_title}{msg_suffix_en}",
            "msg_zh": f"更新 {data.official_title} 规则{msg_suffix_zh}",
        },
    )


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

    torrent_msg_en = ""
    torrent_msg_zh = ""
    if file:
        downloader = create_downloader(settings, session)
        hash_list = await _match_torrents_list(downloader, torrent_repo, data)
        if hash_list:
            await downloader.torrents_delete(hash_list, delete_files=True)
            torrent_msg_en = f"Delete rule and torrents for {data.official_title}"
            torrent_msg_zh = f"删除 {data.official_title} 规则和种子"

    await bangumi_repo.delete_one(bangumi_id)
    await session.commit()

    return JSONResponse(
        status_code=200,
        content={
            "msg_en": f"Delete rule for {data.official_title}. {torrent_msg_en}",
            "msg_zh": f"删除 {data.official_title} 规则。{torrent_msg_zh}",
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

    if file:
        downloader = create_downloader(settings, session)
        hash_list = await _match_torrents_list(downloader, torrent_repo, data)
        if hash_list:
            await downloader.torrents_delete(hash_list, delete_files=True)
            return JSONResponse(
                status_code=200,
                content={
                    "msg_en": f"Delete rule and torrents for {data.official_title}",
                    "msg_zh": f"删除 {data.official_title} 规则和种子",
                },
            )

    return JSONResponse(
        status_code=200,
        content={"msg_en": f"Disable rule for {data.official_title}", "msg_zh": f"禁用 {data.official_title} 规则"},
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

    return JSONResponse(
        status_code=200,
        content={"msg_en": f"Enable rule for {data.official_title}", "msg_zh": f"启用 {data.official_title} 规则"},
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
        if not bangumi.poster_link:
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
                            logger.warning(f"[Poster] Mikan parser failed for {bangumi.official_title}: {e}")

            if not poster_fetched:
                await asyncio.to_thread(parser.tmdb_poster_parser, bangumi)
                if bangumi.poster_link:
                    await bangumi_repo.update_simple(bangumi.id, {"poster_link": bangumi.poster_link})

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
                    logger.warning(f"[Poster] Mikan parser failed for {bangumi.official_title}: {e}")

    if not poster_fetched:
        await asyncio.to_thread(parser.tmdb_poster_parser, bangumi)
        if bangumi.poster_link:
            await bangumi_repo.update_simple(bangumi.id, {"poster_link": bangumi.poster_link})

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

    db_torrents = await torrent_repo.get_by_bangumi(bangumi_id)
    if not db_torrents:
        return []

    online_torrents = await downloader.torrents_info(status_filter="all")

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
        else:
            status_list.append({
                "id": db_t.id, "name": db_t.name, "url": db_t.url,
                "downloaded": db_t.downloaded, "status": "missing",
                "progress": 0, "hash": db_t.hash,
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
    save_path_before = bangumi.save_path

    success = await downloader.add_torrents(
        urls=[torrent.url],
        save_path=bangumi.save_path or "",
        torrent_files=None,
    )

    if success:
        torrent.downloaded = True
        torrent.renamed_at = None
        torrent.renamed_file_count = None
        torrent.pikpak_cloud_path = bangumi.save_path
        if torrent.bangumi_id != bangumi.id:
            torrent.bangumi_id = bangumi.id
        if not save_path_before and bangumi.save_path:
            await bangumi_repo.update_simple(bangumi.id, {"save_path": bangumi.save_path})
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
    session: AsyncSession = Depends(get_db_session),
):
    bangumi_repo = BangumiRepository(session)
    success, message = await bangumi_repo.activate_pending(bangumi_id, filter)
    if not success:
        return JSONResponse(
            status_code=400,
            content={"msg_en": message, "msg_zh": "该番剧不在待审核状态"},
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
    download_result = await AsyncRSSEngine.download_bangumi(session, downloader, bangumi_id)

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
    downloader = create_downloader(settings, session)
    renamer = RenamerService(session)
    renamed_results = await renamer.rename_bangumi(downloader, bangumi_id, retrigger=True)
    renamed_count = sum(r.get("file_count", 0) for r in renamed_results)
    return JSONResponse(
        status_code=200,
        content={
            "msg_en": f"Re-rename completed, renamed {renamed_count} files",
            "msg_zh": f"重新重命名完成，重命名了 {renamed_count} 个文件",
        },
    )
