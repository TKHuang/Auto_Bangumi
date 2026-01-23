import asyncio
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from module.downloader import DownloadClient
from module.manager import SeasonCollector, TorrentStatusManager
from module.models import (
    APIResponse,
    Bangumi,
    ResponseModel,
    RSSItem,
    RSSUpdate,
    Torrent,
)
from module.models.bangumi import BangumiParsingError
from module.rss import RSSAnalyser, RSSEngine
from module.security.api import UNAUTHORIZED, get_current_user

from .response import u_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rss", tags=["rss"])


@router.get(
    path="", response_model=list[RSSItem], dependencies=[Depends(get_current_user)]
)
async def get_rss():
    def _sync():
        with RSSEngine() as engine:
            return engine.rss.search_all()
    return await asyncio.to_thread(_sync)


@router.post(
    path="/add", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def add_rss(
    rss: RSSItem,
    title: str | None = None,
    season: int | None = None,
    group_name: str | None = None,
):
    analyser = RSSAnalyser()

    def _sync():
        with RSSEngine() as engine:
            # First add the RSS to database
            result = engine.add_rss(rss.url, rss.name, rss.aggregate, rss.parser)
            if not result.status:
                return result

            # For non-aggregate RSS, trigger parsing with optional manual overrides
            # This allows BangumiParsingError to be raised when parsing fails
            if not rss.aggregate:
                data = analyser.link_to_data(rss, title, season, group_name)
                if isinstance(data, Bangumi):
                    # Parsing succeeded, add bangumi to database
                    engine.bangumi.add(data)
                    engine.commit()
                elif isinstance(data, ResponseModel) and not data.status:
                    return data

            return result

    try:
        return u_response(await asyncio.to_thread(_sync))
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
async def enable_many_rss(
    rss_ids: list[int],
):
    def _sync():
        with RSSEngine() as engine:
            return engine.enable_list(rss_ids)
    return u_response(await asyncio.to_thread(_sync))


@router.delete(
    path="/delete/{rss_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_rss(rss_id: int):
    def _sync():
        with RSSEngine() as engine:
            return engine.rss.delete(rss_id)
    result = await asyncio.to_thread(_sync)
    if result:
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Delete RSS successfully.", "msg_zh": "删除 RSS 成功。"},
        )
    else:
        return JSONResponse(
            status_code=406,
            content={"msg_en": "Delete RSS failed.", "msg_zh": "删除 RSS 失败。"},
        )


@router.post(
    path="/delete/many",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_many_rss(
    rss_ids: list[int],
):
    def _sync():
        with RSSEngine() as engine:
            return engine.delete_list(rss_ids)
    return u_response(await asyncio.to_thread(_sync))


@router.patch(
    path="/disable/{rss_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_rss(rss_id: int):
    def _sync():
        with RSSEngine() as engine:
            return engine.rss.disable(rss_id)
    result = await asyncio.to_thread(_sync)
    if result:
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Disable RSS successfully.", "msg_zh": "禁用 RSS 成功。"},
        )
    else:
        return JSONResponse(
            status_code=406,
            content={"msg_en": "Disable RSS failed.", "msg_zh": "禁用 RSS 失败。"},
        )


@router.post(
    path="/disable/many",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_many_rss(rss_ids: list[int]):
    def _sync():
        with RSSEngine() as engine:
            return engine.disable_list(rss_ids)
    return u_response(await asyncio.to_thread(_sync))


@router.patch(
    path="/update/{rss_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def update_rss(
    rss_id: int, data: RSSUpdate, current_user=Depends(get_current_user)
):
    if not current_user:
        raise UNAUTHORIZED
    def _sync():
        with RSSEngine() as engine:
            return engine.rss.update(rss_id, data)
    result = await asyncio.to_thread(_sync)
    if result:
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Update RSS successfully.", "msg_zh": "更新 RSS 成功。"},
        )
    else:
        return JSONResponse(
            status_code=406,
            content={"msg_en": "Update RSS failed.", "msg_zh": "更新 RSS 失败。"},
        )


@router.get(
    path="/refresh/all",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def refresh_all():
    def _sync():
        with RSSEngine() as engine, DownloadClient() as client:
            engine.refresh_rss(client)
    await asyncio.to_thread(_sync)
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh all RSS successfully.", "msg_zh": "刷新 RSS 成功。"},
    )


@router.get(
    path="/refresh/{rss_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def refresh_rss(rss_id: int):
    def _sync():
        with RSSEngine() as engine, DownloadClient() as client:
            engine.refresh_rss(client, rss_id)
    await asyncio.to_thread(_sync)
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh RSS successfully.", "msg_zh": "刷新 RSS 成功。"},
    )


@router.get(
    path="/torrent",
    response_model=list[dict],
    dependencies=[Depends(get_current_user)],
)
async def get_torrent(
    rss_id: int,
):
    """Get torrents from database that match this rss_id and check their status in qBittorrent."""
    def _sync():
        with TorrentStatusManager() as manager:
            return manager.get_rss_torrents_status(rss_id)
    return await asyncio.to_thread(_sync)


@router.post(
    path="/recreate/{rss_id}",
    response_model=list[Bangumi],
    dependencies=[Depends(get_current_user)],
)
async def recreate_rss_rules(rss_id: int):
    """Parse torrents from RSS feed and return Bangumi rules for review.

    For aggregate RSS (aggregate=True): Parse ALL torrents and return multiple Bangumi.
    For non-aggregate RSS: Parse only first torrent (original behavior).

    Both modes use full parsing (Level 2) to get official_title, poster, and season RSS.
    This enables the torrent preview feature in the UI.
    """
    def _sync():
        with RSSEngine() as engine:
            rss = engine.rss.search_id(rss_id)
            if not rss:
                return {"error": "not_found"}

            try:
                analyser = RSSAnalyser()

                if rss.aggregate:
                    # For aggregate RSS: Full parse all torrents to get multiple Bangumi
                    logger.info(f"[RSS] Recreate aggregate RSS: {rss.name}")

                    torrents = analyser.get_rss_torrents(rss.url, full_parse=True)

                    if not torrents:
                        return {"error": "no_torrents"}

                    bangumi_list = analyser.torrents_to_data(torrents, rss, full_parse=True)

                    if not bangumi_list:
                        return {"error": "no_parse"}

                    logger.info(f"[RSS] Recreate found {len(bangumi_list)} bangumi rules")
                    return {"bangumi_list": bangumi_list}

                else:
                    # For non-aggregate RSS: Parse only FIRST torrent
                    logger.info(f"[RSS] Recreate non-aggregate RSS: {rss.name}")
                    bangumi = analyser.link_to_data(rss)

                    if isinstance(bangumi, Bangumi):
                        return {"bangumi_list": [bangumi]}
                    else:
                        return {"error": "response_model", "data": bangumi}

            except Exception as e:
                logger.error(f"[RSS] Recreate rules failed: {e}")
                return {"error": "exception", "message": str(e)}

    result = await asyncio.to_thread(_sync)

    if result.get("error") == "not_found":
        return JSONResponse(
            status_code=404,
            content={"msg_en": "RSS feed not found.", "msg_zh": "RSS订阅未找到。"},
        )
    elif result.get("error") == "no_torrents":
        return JSONResponse(
            status_code=406,
            content={"msg_en": "Cannot find any torrent in the RSS feed.", "msg_zh": "无法在 RSS 订阅中找到任何种子。"},
        )
    elif result.get("error") == "no_parse":
        return JSONResponse(
            status_code=406,
            content={"msg_en": "Cannot parse any torrent from the RSS feed.", "msg_zh": "无法解析 RSS 订阅中的任何种子。"},
        )
    elif result.get("error") == "response_model":
        data = result["data"]
        return JSONResponse(
            status_code=data.status_code,
            content={"msg_en": data.msg_en, "msg_zh": data.msg_zh},
        )
    elif result.get("error") == "exception":
        return JSONResponse(
            status_code=500,
            content={"msg_en": f"Failed to parse RSS feed: {result['message']}", "msg_zh": f"解析 RSS 订阅失败：{result['message']}"},
        )
    else:
        return result["bangumi_list"]


# Old API
analyser = RSSAnalyser()


@router.post(
    "/analysis", response_model=Bangumi, dependencies=[Depends(get_current_user)]
)
async def analysis(rss: RSSItem):
    def _sync():
        return analyser.link_to_data(rss)
    data = await asyncio.to_thread(_sync)
    if isinstance(data, Bangumi):
        return data
    else:
        return u_response(data)


@router.post(
    "/analysis/torrents", response_model=list[dict], dependencies=[Depends(get_current_user)]
)
async def analysis_torrents(rss: RSSItem, _filter: str = None, title_raw: str = None):
    """Analyse torrents from RSS with optional filtering.

    Args:
        rss: RSS item to fetch torrents from
        _filter: Regex pattern to exclude torrents (mark as filtered=True)
        title_raw: If provided, only include torrents that parse to this title_raw
                  (useful for aggregate RSS to show only torrents for a specific bangumi)
    """
    def _sync():
        return analyser.analyse_torrents(rss, _filter, title_raw)
    return await asyncio.to_thread(_sync)


@router.post(
    "/collect", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def download_collection(data: Bangumi):
    def _sync():
        with SeasonCollector() as collector:
            return collector.collect_season(data, data.rss_link)
    return u_response(await asyncio.to_thread(_sync))


@router.post(
    "/subscribe", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def subscribe(data: Bangumi, rss: RSSItem):
    def _sync():
        with SeasonCollector() as collector:
            try:
                return collector.subscribe_season(data, parser=rss.parser)
            except ValueError as e:
                # Handle duplicate subscription error (composite key conflict)
                error_msg = str(e)
                return ResponseModel(
                    status=False,
                    status_code=409,
                    msg_en=error_msg,
                    msg_zh=f"该番剧已从其他 RSS 源订阅。请先删除现有订阅。({error_msg})",
                )
    return u_response(await asyncio.to_thread(_sync))



@router.get(
    path="/{rss_id}/pending-count",
    response_model=dict,
    dependencies=[Depends(get_current_user)],
)
async def get_pending_count(rss_id: int):
    """Get the count of pending review bangumi for a specific RSS feed."""
    def _sync():
        with RSSEngine() as engine:
            return {"pending_count": engine.bangumi.count_pending_by_rss_id(rss_id)}
    return await asyncio.to_thread(_sync)


@router.get(
    path="/aggregate/pending/{rss_id}",
    response_model=dict,
    dependencies=[Depends(get_current_user)],
)
async def get_pending_bangumi_list(rss_id: int):
    """Get all pending review bangumi for a specific aggregate RSS feed.

    Returns list of pending bangumi with parsed global_filter_matches as arrays,
    plus summary counts for pending and active bangumi.

    Returns 400 if the RSS is not an aggregate RSS feed.
    """
    def _sync():
        with RSSEngine() as engine:
            # Check if RSS exists and is aggregate
            rss = engine.rss.search_id(rss_id)
            if not rss:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "RSS feed not found"}
                )
            if not rss.aggregate:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "This endpoint only works for aggregate RSS feeds"}
                )

            # Get pending bangumi list
            pending_list = engine.bangumi.get_pending_by_rss_id(rss_id)

            # Convert to dict and parse global_filter_matches as array
            bangumi_data = []
            for bangumi in pending_list:
                data = {
                    "id": bangumi.id,
                    "rss_id": bangumi.rss_id,
                    "official_title": bangumi.official_title,
                    "year": bangumi.year,
                    "title_raw": bangumi.title_raw,
                    "season": bangumi.season,
                    "season_raw": bangumi.season_raw,
                    "group_name": bangumi.group_name,
                    "dpi": bangumi.dpi,
                    "source": bangumi.source,
                    "subtitle": bangumi.subtitle,
                    "filter": bangumi.filter,
                    "rss_link": bangumi.rss_link,
                    "poster_link": bangumi.poster_link,
                    "pending_review": bangumi.pending_review,
                    # Parse comma-separated global_filter_matches into array
                    "global_filter_matches": (
                        [m.strip() for m in bangumi.global_filter_matches.split(",")]
                        if bangumi.global_filter_matches
                        else []
                    ),
                }
                bangumi_data.append(data)

            # Get counts
            pending_count = len(pending_list)
            active_count = engine.bangumi.count_active_by_rss_id(rss_id)

            return {
                "pending_count": pending_count,
                "active_count": active_count,
                "bangumi": bangumi_data,
            }
    return await asyncio.to_thread(_sync)
