import asyncio
import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.api.response import u_response
from module.conf import settings
from module.database.engine import get_db_session
from module.domain.models.bangumi import Bangumi as DomainBangumi
from module.domain.value_objects import gen_save_path
from module.domain.value_objects import APIResponse, BangumiParsingError, ResponseModel
from module.models import (
    Bangumi,
    RSSItem,
    RSSUpdate,
)
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.repositories.series import SeriesRepository
from module.repositories.torrent import TorrentRepository
from module.services.collector import SeasonCollectorService
from module.services.downloader.factory import create_downloader
from module.services.identity_resolver import resolve_series_for_rss
from module.network.request_contents import RequestContent
from module.services.rss_engine import RSSEngine as AsyncRSSEngine
from module.services.search_adapter import AsyncRSSAnalyserAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rss", tags=["rss"])

analyser = AsyncRSSAnalyserAdapter()


def _sqlmodel_to_domain_bangumi(data: Bangumi) -> DomainBangumi:
    """Map a Pydantic Bangumi schema onto an ORM Bangumi instance.

    Post-0008: official_title, season, year, save_path, poster_link are
    read-only properties on the ORM model (delegated to Series). We skip
    those here; callers of collect_season / subscribe_season that need
    these values should fetch the ORM Bangumi from DB directly by id.

    Fields mapped to their ORM equivalents:
      save_path → path_override  (stored per-bangumi override)
    Fields silently skipped (read-only properties on ORM):
      official_title, year, season, poster_link
    Fields dropped (no longer on ORM after 0008):
      title_raw, season_raw
    """
    # Direct ORM columns safe to set
    _DIRECT_FIELDS = frozenset({
        "id", "rss_id", "group_name", "dpi", "source", "subtitle",
        "eps_collect", "offset", "filter", "rss_link", "added",
        "rule_name", "deleted", "pending_review", "global_filter_matches",
        "active",
    })
    domain = DomainBangumi.__new__(DomainBangumi)
    for field in _DIRECT_FIELDS:
        if hasattr(data, field):
            try:
                setattr(domain, field, getattr(data, field))
            except (AttributeError, TypeError):
                pass
    # Map save_path → path_override
    if hasattr(data, "save_path") and data.save_path is not None:
        try:
            domain.path_override = data.save_path
        except AttributeError:
            pass
    return domain


def _rss_update_to_dict(data: RSSUpdate) -> dict:
    result = {}
    for field in ["name", "url", "aggregate", "parser", "enabled", "last_update", "last_status", "last_error"]:
        val = getattr(data, field, None)
        if val is not None:
            result[field] = val
    return result


@router.get(
    path="", response_model=list[RSSItem], dependencies=[Depends(get_current_user)]
)
async def get_rss(session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    return await rss_repo.get_all()


@router.post(
    path="/add", dependencies=[Depends(get_current_user)]
)
async def add_rss(
    rss: RSSItem,
    official_title: str | None = None,
    season: int | None = None,
    group_name: str | None = None,
    skip_bangumi: bool = False,
    session: AsyncSession = Depends(get_db_session),
):
    rss_repo = RSSRepository(session)
    bangumi_repo = BangumiRepository(session)

    if rss.name:
        rss_name = rss.name
    else:
        def _fetch_title():
            with RequestContent() as req:
                return req.get_rss_title(rss.url)
        rss_name = await asyncio.to_thread(_fetch_title) or rss.url

    try:
        if skip_bangumi:
            new_rss = await rss_repo.create({
                "url": rss.url, "name": rss_name,
                "aggregate": rss.aggregate, "parser": rss.parser, "enabled": True,
            })
            await session.commit()
            return JSONResponse(
                status_code=200,
                content={"status": True, "msg_en": "RSS added successfully.", "msg_zh": "RSS 添加成功。", "rss_id": new_rss.id},
            )

        if not rss.aggregate:
            data = await analyser.link_to_data(rss, official_title, season, group_name)
            if isinstance(data, ResponseModel) and not data.status:
                return u_response(data)

            if isinstance(data, Bangumi) and not official_title:
                existing_series = await SeriesRepository(session).find_by_canonical_title(
                    data.official_title
                )
                if existing_series is not None:
                    return u_response(ResponseModel(
                        status=False,
                        status_code=409,
                        msg_en=(
                            f"Series '{data.official_title}' already exists "
                            f"(id={existing_series.id})."
                        ),
                        msg_zh=f"番剧「{data.official_title}」已存在（id={existing_series.id}）。",
                    ))

            if isinstance(data, Bangumi) and data.rss_link:
                rss_links = data.rss_link.split(",") if data.rss_link else []
                existing_by_rss = await bangumi_repo.find_by_any_rss_link(rss_links)
                if existing_by_rss:
                    _exist_series = getattr(existing_by_rss, "series", None)
                    _exist_title = (
                        _exist_series.canonical_title
                        if _exist_series is not None
                        else ""
                    )
                    return u_response(ResponseModel(
                        status=False,
                        status_code=409,
                        msg_en=f"This RSS link is already subscribed in bangumi '{_exist_title}'.",
                        msg_zh=f"此 RSS 链接已在番剧「{_exist_title}」中訂閱。",
                    ))

            new_rss = await rss_repo.create({
                "url": rss.url, "name": rss_name,
                "aggregate": rss.aggregate, "parser": rss.parser, "enabled": True,
            })
            await session.flush()

            if isinstance(data, Bangumi):
                # Resolve or create Series — required since migration 0008
                # (Bangumi.series_id is NOT NULL).
                _resolved = await resolve_series_for_rss(
                    session,
                    rss_link=data.rss_link or rss.url,
                    parsed_title=data.official_title or "",
                    parsed_season=data.season,
                    parsed_poster=data.poster_link,
                )
                _series_id = _resolved.series.id

                created = await bangumi_repo.create({
                    "series_id": _series_id,
                    "group_name": data.group_name or "Unknown",
                    "dpi": data.dpi,
                    "source": data.source,
                    "subtitle": data.subtitle,
                    "rss_link": data.rss_link,
                    "rss_id": new_rss.id,
                    "filter": data.filter or "",
                    "eps_collect": False,
                    "offset": data.offset,
                    "added": False,
                    "deleted": False,
                    "pending_review": False,
                    "active": True,
                })
                await session.commit()

                downloader = create_downloader(settings, session)
                download_result = await AsyncRSSEngine.download_bangumi(session, downloader, created.id)

                if (
                    isinstance(download_result, dict)
                    and not download_result.get("status")
                    and download_result.get("count") == 0
                    and "filtered out" in download_result.get("message", "").lower()
                ):
                    await bangumi_repo.update_pending_review(created.id, True, data.filter)
                    await session.commit()
                    logger.info(
                        f"[RSS] Bangumi {data.official_title} set to pending review "
                        f"(all torrents filtered by: {data.filter})"
                    )

            else:
                await session.commit()

            return JSONResponse(
                status_code=200,
                content={"msg_en": "RSS added successfully.", "msg_zh": "RSS 添加成功。"},
            )
        else:
            new_rss = await rss_repo.create({
                "url": rss.url, "name": rss_name,
                "aggregate": rss.aggregate, "parser": rss.parser, "enabled": True,
            })
            await session.commit()
            return JSONResponse(
                status_code=200,
                content={"msg_en": "RSS added successfully.", "msg_zh": "RSS 添加成功。"},
            )

    except BangumiParsingError as e:
        return JSONResponse(
            status_code=422,
            content={
                "status": False,
                "status_code": 422,
                "error_type": "bangumi_parsing_failed",
                "msg_en": e.msg_en,
                "msg_zh": e.msg_zh,
                "partial_data": {
                    "raw_title": e.raw_title,
                    "group": e.partial_data.get("group"),
                    "season": e.partial_data.get("season"),
                    "resolution": e.partial_data.get("resolution"),
                    "subtitle": e.partial_data.get("subtitle"),
                },
            },
        )


@router.post(
    path="/enable/many",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def enable_many_rss(rss_ids: list[int], session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    for rss_id in rss_ids:
        await rss_repo.enable(rss_id)
    await session.commit()
    return u_response(ResponseModel(
        status=True, status_code=200,
        msg_en="Enable RSS successfully.", msg_zh="启用 RSS 成功。",
    ))


@router.delete(
    path="/delete/{rss_id}",
    dependencies=[Depends(get_current_user)],
)
async def delete_rss(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    result = await rss_repo.cascade_delete(rss_id)
    await session.commit()
    if result:
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Delete RSS successfully.", "msg_zh": "删除 RSS 成功。"},
        )
    else:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "Delete RSS failed.", "msg_zh": "删除 RSS 失败。"},
        )


@router.post(
    path="/delete/many",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_many_rss(rss_ids: list[int], session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    deleted = 0
    for rss_id in rss_ids:
        if await rss_repo.cascade_delete(rss_id):
            deleted += 1
    await session.commit()
    return u_response(ResponseModel(
        status=True, status_code=200,
        msg_en=f"Deleted {deleted} RSS feeds.", msg_zh=f"已删除 {deleted} 个 RSS 订阅。",
    ))


@router.patch(
    path="/disable/{rss_id}",
    dependencies=[Depends(get_current_user)],
)
async def disable_rss(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    result = await rss_repo.disable(rss_id)
    await session.commit()
    if result:
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Disable RSS successfully.", "msg_zh": "禁用 RSS 成功。"},
        )
    else:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "Disable RSS failed.", "msg_zh": "禁用 RSS 失败。"},
        )


@router.post(
    path="/disable/many",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_many_rss(rss_ids: list[int], session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    for rss_id in rss_ids:
        await rss_repo.disable(rss_id)
    await session.commit()
    return u_response(ResponseModel(
        status=True, status_code=200,
        msg_en="Disable RSS successfully.", msg_zh="禁用 RSS 成功。",
    ))


@router.patch(
    path="/update/{rss_id}",
    dependencies=[Depends(get_current_user)],
)
async def update_rss(
    rss_id: int, data: RSSUpdate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    rss_repo = RSSRepository(session)
    update_dict = _rss_update_to_dict(data)
    try:
        await rss_repo.update(rss_id, update_dict)
        await session.commit()
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Update RSS successfully.", "msg_zh": "更新 RSS 成功。"},
        )
    except ValueError:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "Update RSS failed.", "msg_zh": "更新 RSS 失败。"},
        )


@router.post(
    path="/refresh/all",
    dependencies=[Depends(get_current_user)],
)
async def refresh_all(session: AsyncSession = Depends(get_db_session)):
    downloader = create_downloader(settings, session)
    await AsyncRSSEngine.refresh_rss(session, downloader)
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh all RSS successfully.", "msg_zh": "刷新 RSS 成功。"},
    )


@router.post(
    path="/refresh/{rss_id}",
    dependencies=[Depends(get_current_user)],
)
async def refresh_rss(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    downloader = create_downloader(settings, session)
    await AsyncRSSEngine.refresh_rss(session, downloader, rss_id)
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh RSS successfully.", "msg_zh": "刷新 RSS 成功。"},
    )


@router.get(
    path="/torrent",
    response_model=list[dict],  # type: ignore[type-arg]
    dependencies=[Depends(get_current_user)],
)
async def get_torrent(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    torrent_repo = TorrentRepository(session)
    downloader = create_downloader(settings, session)

    db_torrents = await torrent_repo.get_visible_by_rss(rss_id)
    if not db_torrents:
        return []

    cloud_paths = {
        t.hash.lower(): t.pikpak_cloud_path
        for t in db_torrents
        if t.hash and t.pikpak_cloud_path
    }
    online_torrents = await downloader.torrents_info(
        status_filter="all", cloud_paths=cloud_paths,
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
        else:
            status_list.append({
                "id": db_t.id, "name": db_t.name, "url": db_t.url,
                "downloaded": db_t.downloaded, "status": "missing",
                "progress": 0, "hash": db_t.hash,
            })
    return status_list


@router.post(
    path="/recreate/{rss_id}",
    response_model=list[Bangumi],
    dependencies=[Depends(get_current_user)],
)
async def recreate_rss_rules(
    rss_id: int,
    official_title: str | None = None,
    season: int | None = None,
    group_name: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    rss_repo = RSSRepository(session)
    rss = await rss_repo.get_by_id(rss_id)

    if not rss:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "RSS feed not found.", "msg_zh": "RSS订阅未找到。"},
        )

    try:
        local_analyser = AsyncRSSAnalyserAdapter()

        if rss.aggregate:
            logger.info(f"[RSS] Recreate aggregate RSS: {rss.name}")

            torrents = await local_analyser.get_rss_torrents(rss.url, full_parse=True, apply_filter=False)
            if not torrents:
                return JSONResponse(
                    status_code=404,
                    content={"msg_en": "Cannot find any torrent in the RSS feed.", "msg_zh": "无法在 RSS 订阅中找到任何种子。"},
                )

            bangumi_list = await local_analyser.torrents_to_data(torrents, rss, full_parse=True)
            if not bangumi_list:
                return JSONResponse(
                    status_code=404,
                    content={"msg_en": "Cannot parse any torrent from the RSS feed.", "msg_zh": "无法解析 RSS 订阅中的任何种子。"},
                )

            logger.info(f"[RSS] Recreate found {len(bangumi_list)} bangumi rules")
            return bangumi_list

        else:
            logger.info(f"[RSS] Recreate non-aggregate RSS: {rss.name}")
            result = await local_analyser.link_to_data(rss, official_title, season, group_name)

            if isinstance(result, Bangumi):
                return [result]
            else:
                return JSONResponse(
                    status_code=result.status_code,
                    content={"msg_en": result.msg_en, "msg_zh": result.msg_zh},
                )

    except BangumiParsingError as e:
        return JSONResponse(
            status_code=422,
            content={
                "status": False,
                "status_code": 422,
                "error_type": "bangumi_parsing_failed",
                "msg_en": e.msg_en,
                "msg_zh": e.msg_zh,
                "partial_data": {
                    "raw_title": e.raw_title,
                    "group": e.partial_data.get("group"),
                    "season": e.partial_data.get("season"),
                    "resolution": e.partial_data.get("resolution"),
                    "subtitle": e.partial_data.get("subtitle"),
                },
            },
        )
    except Exception as e:
        logger.error(f"[RSS] Recreate rules failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"msg_en": f"Failed to parse RSS feed: {str(e)}", "msg_zh": f"解析 RSS 订阅失败：{str(e)}"},
        )


@router.post(
    "/analysis", response_model=Bangumi, dependencies=[Depends(get_current_user)]
)
async def analysis(rss: RSSItem):
    data = await analyser.link_to_data(rss)
    if isinstance(data, Bangumi):
        return data
    else:
        return u_response(data)


@router.post(
    "/analysis/torrents", response_model=list[dict], dependencies=[Depends(get_current_user)]  # type: ignore[type-arg]
)
async def analysis_torrents(rss: RSSItem, _filter: str | None = None, title_raw: str | None = None):
    return await analyser.analyse_torrents(rss, _filter or "", title_raw or "")


@router.post(
    "/collect", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def download_collection(data: Bangumi, session: AsyncSession = Depends(get_db_session)):
    downloader = create_downloader(settings, session)
    # Pass the Pydantic schema directly — collect_season only reads attributes,
    # it does not require an ORM-tracked instance.
    result = await SeasonCollectorService.collect_season(session, downloader, data, data.rss_link)  # type: ignore[arg-type]
    return u_response(result)


@router.post(
    "/subscribe", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def subscribe(
    data: Bangumi, rss: RSSItem, file: bool = False,
    excluded_hashes: list[str] | None = Body(default=None),
    session: AsyncSession = Depends(get_db_session),
):
    downloader = create_downloader(settings, session)
    # Pass the Pydantic schema directly — subscribe_season uses it as a DTO.
    try:
        result = await SeasonCollectorService.subscribe_season(
            session, downloader, data, parser=rss.parser, delete_files=file,  # type: ignore[arg-type]
            excluded_hashes=excluded_hashes,
        )
        return u_response(result)
    except ValueError as e:
        return u_response(ResponseModel(
            status=False, status_code=409,
            msg_en=str(e),
            msg_zh=f"该番剧已从其他 RSS 源订阅。请先删除现有订阅。({e})",
        ))


@router.post(
    "/subscribe/batch", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def subscribe_batch(
    bangumi_list: list[Bangumi], rss: RSSItem, file: bool = False,
    session: AsyncSession = Depends(get_db_session),
):
    downloader = create_downloader(settings, session)
    # Pass Pydantic schemas directly — subscribe_batch uses them as DTOs.
    try:
        result = await SeasonCollectorService.subscribe_batch(
            session, downloader, bangumi_list, rss.id, parser=rss.parser, delete_files=file,  # type: ignore[arg-type]
        )
        return u_response(result)
    except Exception as e:
        logger.error(f"Batch subscription failed: {e}")
        return u_response(ResponseModel(
            status=False, status_code=500,
            msg_en=f"Batch subscription failed: {str(e)}",
            msg_zh=f"批量订阅失败: {str(e)}",
        ))


@router.get(
    path="/{rss_id}/pending-count",
    response_model=dict,
    dependencies=[Depends(get_current_user)],
)
async def get_pending_count(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    count = await bangumi_repo.count_pending_by_rss_id(rss_id)
    return {"pending_count": count}


@router.get(
    path="/{rss_id}/pending",
    response_model=list[Bangumi],
    dependencies=[Depends(get_current_user)],
)
async def get_pending_bangumi(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    bangumi_repo = BangumiRepository(session)
    return await bangumi_repo.get_pending_review(rss_id=rss_id)


@router.get(
    path="/aggregate/pending/{rss_id}",
    response_model=dict,
    dependencies=[Depends(get_current_user)],
)
async def get_pending_bangumi_list(rss_id: int, session: AsyncSession = Depends(get_db_session)):
    rss_repo = RSSRepository(session)
    bangumi_repo = BangumiRepository(session)

    rss = await rss_repo.get_by_id(rss_id)
    if not rss:
        return JSONResponse(
            status_code=404,
            content={"detail": "RSS feed not found"},
        )
    if not rss.aggregate:
        return JSONResponse(
            status_code=400,
            content={"detail": "This endpoint only works for aggregate RSS feeds"},
        )

    pending_list = await bangumi_repo.get_pending_review(rss_id=rss_id)

    bangumi_data = []
    for bangumi in pending_list:
        _b_series = bangumi.series
        _b_title = _b_series.canonical_title if _b_series is not None else None
        _b_year = _b_series.year if _b_series is not None else None
        _b_season = _b_series.season if _b_series is not None else 1
        _b_poster = _b_series.poster_url if _b_series is not None else None
        bangumi_data.append({
            "id": bangumi.id,
            "rss_id": bangumi.rss_id,
            "official_title": _b_title,
            "year": _b_year,
            "title_raw": getattr(bangumi, "title_raw", None),
            "season": _b_season,
            "season_raw": getattr(bangumi, "season_raw", None),
            "group_name": bangumi.group_name,
            "dpi": bangumi.dpi,
            "source": bangumi.source,
            "subtitle": bangumi.subtitle,
            "filter": bangumi.filter,
            "rss_link": bangumi.rss_link,
            "poster_link": _b_poster,
            "pending_review": bangumi.pending_review,
            "global_filter_matches": (
                [m.strip() for m in bangumi.global_filter_matches.split(",")]
                if bangumi.global_filter_matches
                else []
            ),
        })

    active_count = await bangumi_repo.count_active_by_rss_id(rss_id)

    return {
        "pending_count": len(pending_list),
        "active_count": active_count,
        "bangumi": bangumi_data,
    }
