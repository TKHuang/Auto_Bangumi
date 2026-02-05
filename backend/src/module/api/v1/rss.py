"""RSS API endpoints - All RSS CRUD, analysis, subscribe, collect operations."""
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.database.engine import get_db_session
from module.domain.models import Bangumi, RSSItem
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.factory import create_downloader
from module.services.rss_engine import (
    RSSEngineService,
    create_bangumi_from_torrent,
    download_bangumi,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rss", tags=["rss"])


# === GET /api/v1/rss ===
@router.get("", response_model=list[RSSItem])
async def get_rss(
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Get all RSS feeds."""
    rss_repo = RSSRepository(session)
    return await rss_repo.get_all()


# === POST /api/v1/rss/add ===
@router.post("/add")
async def add_rss(
    rss: RSSItem,
    official_title: str | None = None,
    season: int | None = None,
    group_name: str | None = None,
    skip_bangumi: bool = False,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Add RSS feed and optionally create bangumi from first torrent.
    
    If skip_bangumi=True, only add RSS without parsing bangumi.
    If skip_bangumi=False (default), parse bangumi from first torrent and add to database.
    
    Manual override params (official_title, season, group_name) used when parsing fails.
    """
    from module.conf import settings
    from module.rss import RSSAnalyser
    from module.models.bangumi import BangumiParsingError

    rss_repo = RSSRepository(session)
    bangumi_repo = BangumiRepository(session)
    analyser = RSSAnalyser()

    try:
        async with session.begin():
            if skip_bangumi:
                # Just add RSS, no parsing
                rss_data = {
                    "url": rss.url,
                    "name": rss.name,
                    "aggregate": rss.aggregate,
                    "parser": rss.parser,
                }
                created_rss = await rss_repo.create(rss_data)
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": True,
                        "msg_en": "RSS added successfully.",
                        "msg_zh": "RSS 添加成功。",
                        "rss_id": created_rss.id,
                    },
                )

            if not rss.aggregate:
                # Parse first torrent to get bangumi data
                from module.rss.analyser import link_to_data
                
                bangumi_data = await link_to_data(
                    rss, official_title, season, group_name
                )

                if not isinstance(bangumi_data, Bangumi):
                    # Return error response
                    return JSONResponse(
                        status_code=bangumi_data.status_code,
                        content={
                            "status": False,
                            "msg_en": bangumi_data.msg_en,
                            "msg_zh": bangumi_data.msg_zh,
                        },
                    )

                # Check for duplicate official_title (only if not manually overridden)
                if not official_title:
                    existing = await bangumi_repo.get_by_composite_key(
                        bangumi_data.official_title,
                        bangumi_data.season,
                        bangumi_data.group_name,
                    )
                    if existing:
                        return JSONResponse(
                            status_code=409,
                            content={
                                "status": False,
                                "status_code": 409,
                                "msg_en": f"A bangumi with title '{bangumi_data.official_title}' already exists. Please use manual input to specify a different title.",
                                "msg_zh": f"已存在标题为「{bangumi_data.official_title}」的番剧。请使用手动输入指定不同的标题。",
                                "error_type": "duplicate_official_title",
                                "existing_bangumi": {
                                    "id": existing.id,
                                    "official_title": existing.official_title,
                                    "season": existing.season,
                                    "group_name": existing.group_name,
                                },
                            },
                        )

                # Add RSS first
                rss_data = {
                    "url": rss.url,
                    "name": rss.name,
                    "aggregate": rss.aggregate,
                    "parser": rss.parser,
                }
                created_rss = await rss_repo.create(rss_data)

                # Add bangumi with rss_id
                bangumi_data.rss_id = created_rss.id
                await bangumi_repo.create(bangumi_data.__dict__)

                # Download torrents immediately
                downloader = create_downloader(settings)
                try:
                    await download_bangumi(session, downloader, bangumi_data.id)
                except Exception as e:
                    logger.warning(f"Failed to download bangumi torrents: {e}")

                return JSONResponse(
                    status_code=200,
                    content={
                        "status": True,
                        "msg_en": "RSS added successfully.",
                        "msg_zh": "RSS 添加成功。",
                    },
                )
            else:
                # For aggregate RSS: just add RSS, no immediate parsing
                rss_data = {
                    "url": rss.url,
                    "name": rss.name,
                    "aggregate": rss.aggregate,
                    "parser": rss.parser,
                }
                created_rss = await rss_repo.create(rss_data)
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": True,
                        "msg_en": "RSS added successfully.",
                        "msg_zh": "RSS 添加成功。",
                    },
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


# === DELETE /api/v1/rss/delete/{rss_id} ===
@router.delete("/delete/{rss_id}")
async def delete_rss(
    rss_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Delete RSS feed."""
    rss_repo = RSSRepository(session)
    async with session.begin():
        result = await rss_repo.delete(rss_id)
    
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


# === POST /api/v1/rss/delete/many ===
@router.post("/delete/many")
async def delete_many_rss(
    rss_ids: list[int],
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Delete multiple RSS feeds."""
    rss_repo = RSSRepository(session)
    async with session.begin():
        for rss_id in rss_ids:
            await rss_repo.delete(rss_id)
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Delete RSS successfully.", "msg_zh": "删除 RSS 成功。"},
    )


# === PATCH /api/v1/rss/disable/{rss_id} ===
@router.patch("/disable/{rss_id}")
async def disable_rss(
    rss_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Disable RSS feed."""
    rss_repo = RSSRepository(session)
    async with session.begin():
        rss = await rss_repo.get_by_id(rss_id)
        if not rss:
            return JSONResponse(
                status_code=404,
                content={"msg_en": "RSS not found.", "msg_zh": "RSS 未找到。"},
            )
        await rss_repo.update(rss_id, {"enabled": False})
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Disable RSS successfully.", "msg_zh": "禁用 RSS 成功。"},
    )


# === POST /api/v1/rss/disable/many ===
@router.post("/disable/many")
async def disable_many_rss(
    rss_ids: list[int],
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Disable multiple RSS feeds."""
    rss_repo = RSSRepository(session)
    async with session.begin():
        for rss_id in rss_ids:
            await rss_repo.update(rss_id, {"enabled": False})
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Disable RSS successfully.", "msg_zh": "禁用 RSS 成功。"},
    )


# === PATCH /api/v1/rss/update/{rss_id} ===
@router.patch("/update/{rss_id}")
async def update_rss(
    rss_id: int,
    data: dict,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Update RSS feed."""
    rss_repo = RSSRepository(session)
    async with session.begin():
        rss = await rss_repo.get_by_id(rss_id)
        if not rss:
            return JSONResponse(
                status_code=404,
                content={"msg_en": "RSS not found.", "msg_zh": "RSS 未找到。"},
            )
        await rss_repo.update(rss_id, data)
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Update RSS successfully.", "msg_zh": "更新 RSS 成功。"},
    )


# === POST /api/v1/rss/enable/many ===
@router.post("/enable/many")
async def enable_many_rss(
    rss_ids: list[int],
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Enable multiple RSS feeds."""
    rss_repo = RSSRepository(session)
    async with session.begin():
        for rss_id in rss_ids:
            await rss_repo.update(rss_id, {"enabled": True})
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Enable RSS successfully.", "msg_zh": "启用 RSS 成功。"},
    )


# === GET /api/v1/rss/refresh/all ===
@router.get("/refresh/all")
async def refresh_all(
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Refresh all enabled RSS feeds."""
    from module.conf import settings
    
    downloader = create_downloader(settings)
    rss_service = RSSEngineService()
    
    await rss_service.refresh_all_rss(session, downloader)
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh all RSS successfully.", "msg_zh": "刷新 RSS 成功。"},
    )


# === GET /api/v1/rss/refresh/{rss_id} ===
@router.get("/refresh/{rss_id}")
async def refresh_rss(
    rss_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Refresh specific RSS feed."""
    from module.conf import settings
    
    downloader = create_downloader(settings)
    rss_service = RSSEngineService()
    
    await rss_service.refresh_rss(session, downloader, rss_id)
    
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Refresh RSS successfully.", "msg_zh": "刷新 RSS 成功。"},
    )


# === GET /api/v1/rss/torrent?rss_id=N ===
@router.get("/torrent")
async def get_torrent(
    rss_id: int = Query(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Get torrents for specific RSS feed with real-time status."""
    from module.conf import settings
    
    torrent_repo = TorrentRepository(session)
    downloader = create_downloader(settings)
    
    # Get torrents from database
    torrents = await torrent_repo.get_by_rss(rss_id)
    
    # Get real-time status from downloader
    result = []
    for torrent in torrents:
        torrent_info = await downloader.get_torrent_path(torrent.hash)
        result.append({
            "id": torrent.id,
            "name": torrent.name,
            "hash": torrent.hash,
            "downloaded": torrent.downloaded,
            "state": torrent.state.value if torrent.state else None,
            "path": torrent_info,
        })
    
    return result


# === POST /api/v1/rss/recreate/{rss_id} ===
@router.post("/recreate/{rss_id}")
async def recreate_rss_rules(
    rss_id: int,
    official_title: str | None = None,
    season: int | None = None,
    group_name: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Parse torrents from RSS feed and return Bangumi rules for review.
    
    For aggregate RSS: Parse ALL torrents and return multiple Bangumi.
    For non-aggregate RSS: Parse only first torrent.
    """
    from module.models.bangumi import BangumiParsingError
    from module.rss import RSSAnalyser

    rss_repo = RSSRepository(session)
    rss = await rss_repo.get_by_id(rss_id)
    
    if not rss:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "RSS feed not found.", "msg_zh": "RSS订阅未找到。"},
        )

    analyser = RSSAnalyser()

    try:
        if rss.aggregate:
            # For aggregate RSS: Full parse all torrents
            torrents = await analyser.get_rss_torrents(
                rss.url, full_parse=True, apply_filter=False
            )
            
            if not torrents:
                return JSONResponse(
                    status_code=406,
                    content={
                        "msg_en": "Cannot find any torrent in the RSS feed.",
                        "msg_zh": "无法在 RSS 订阅中找到任何种子。",
                    },
                )
            
            bangumi_list = await analyser.torrents_to_data(
                torrents, rss, full_parse=True
            )
            
            if not bangumi_list:
                return JSONResponse(
                    status_code=406,
                    content={
                        "msg_en": "Cannot parse any torrent from the RSS feed.",
                        "msg_zh": "无法解析 RSS 订阅中的任何种子。",
                    },
                )
            
            return bangumi_list
        else:
            # For non-aggregate RSS: Parse only FIRST torrent
            from module.rss.analyser import link_to_data
            
            bangumi = await link_to_data(rss, official_title, season, group_name)
            
            if isinstance(bangumi, Bangumi):
                return [bangumi]
            else:
                return JSONResponse(
                    status_code=bangumi.status_code,
                    content={"msg_en": bangumi.msg_en, "msg_zh": bangumi.msg_zh},
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
            content={
                "msg_en": f"Failed to parse RSS feed: {str(e)}",
                "msg_zh": f"解析 RSS 订阅失败：{str(e)}",
            },
        )


# === POST /api/v1/rss/analysis ===
@router.post("/analysis")
async def analysis(
    rss: RSSItem,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Analyze RSS feed and return Bangumi data."""
    from module.rss import RSSAnalyser
    from module.rss.analyser import link_to_data

    bangumi_data = await link_to_data(rss)
    
    if isinstance(bangumi_data, Bangumi):
        return bangumi_data
    else:
        return JSONResponse(
            status_code=bangumi_data.status_code,
            content={"msg_en": bangumi_data.msg_en, "msg_zh": bangumi_data.msg_zh},
        )


# === POST /api/v1/rss/analysis/torrents ===
@router.post("/analysis/torrents")
async def analysis_torrents(
    rss: RSSItem,
    _filter: str | None = None,
    title_raw: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Analyze torrents from RSS with optional filtering.
    
    Args:
        rss: RSS item to fetch torrents from
        _filter: Regex pattern to exclude torrents (mark as filtered=True)
        title_raw: If provided, only include torrents that parse to this title_raw
    """
    from module.rss import RSSAnalyser

    analyser = RSSAnalyser()
    result = await analyser.analyse_torrents(rss, _filter, title_raw)
    
    return result


# === POST /api/v1/rss/collect ===
@router.post("/collect")
async def download_collection(
    data: Bangumi,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Collect/backfill all episodes for bangumi."""
    from module.conf import settings

    downloader = create_downloader(settings)
    
    async with session.begin():
        result = await download_bangumi(session, downloader, data.id)
    
    if result.get("status"):
        return JSONResponse(
            status_code=200,
            content={"msg_en": result["msg_en"], "msg_zh": result["msg_zh"]},
        )
    else:
        return JSONResponse(
            status_code=result.get("status_code", 500),
            content={"msg_en": result["msg_en"], "msg_zh": result["msg_zh"]},
        )


# === POST /api/v1/rss/subscribe?file=bool ===
@router.post("/subscribe")
async def subscribe(
    data: Bangumi,
    rss: RSSItem,
    file: bool = False,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Subscribe to bangumi and trigger download.
    
    Args:
        data: Bangumi data to subscribe
        rss: RSS item info (for parser)
        file: Whether to delete files on error (default False)
    """
    from module.conf import settings
    
    downloader = create_downloader(settings)
    bangumi_repo = BangumiRepository(session)
    
    try:
        async with session.begin():
            # Check for duplicate
            existing = await bangumi_repo.get_by_composite_key(
                data.official_title, data.season, data.group_name
            )
            if existing:
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": False,
                        "msg_en": "This bangumi is already subscribed.",
                        "msg_zh": "该番剧已订阅。",
                    },
                )
            
            # Create bangumi
            bangumi_data = data.__dict__
            bangumi_data["rss_id"] = rss.id
            created_bangumi = await bangumi_repo.create(bangumi_data)
            
            # Download torrents
            await download_bangumi(session, downloader, created_bangumi.id)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "msg_en": "Subscribe successfully.",
                "msg_zh": "订阅成功。",
            },
        )
    
    except ValueError as e:
        return JSONResponse(
            status_code=409,
            content={
                "status": False,
                "msg_en": str(e),
                "msg_zh": f"订阅失败：{str(e)}",
            },
        )


# === POST /api/v1/rss/subscribe/batch?file=bool ===
@router.post("/subscribe/batch")
async def subscribe_batch(
    bangumi_list: list[Bangumi],
    rss: RSSItem,
    file: bool = False,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Batch subscribe to multiple bangumi.
    
    Args:
        bangumi_list: List of bangumi to subscribe
        rss: RSS item info (for parser)
        file: Whether to delete files on error (default False)
    """
    from module.conf import settings
    
    downloader = create_downloader(settings)
    bangumi_repo = BangumiRepository(session)
    
    try:
        async with session.begin():
            for bangumi_data in bangumi_list:
                # Check for duplicate
                existing = await bangumi_repo.get_by_composite_key(
                    bangumi_data.official_title,
                    bangumi_data.season,
                    bangumi_data.group_name,
                )
                if existing:
                    logger.warning(
                        f"Skipping duplicate bangumi: {bangumi_data.official_title}"
                    )
                    continue
                
                # Create bangumi
                data_dict = bangumi_data.__dict__
                data_dict["rss_id"] = rss.id
                created_bangumi = await bangumi_repo.create(data_dict)
                
                # Download torrents
                await download_bangumi(session, downloader, created_bangumi.id)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "msg_en": "Batch subscribe successfully.",
                "msg_zh": "批量订阅成功。",
            },
        )
    
    except Exception as e:
        logger.error(f"Batch subscription failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "msg_en": f"Batch subscription failed: {str(e)}",
                "msg_zh": f"批量订阅失败: {str(e)}",
            },
        )


# === GET /api/v1/rss/{rss_id}/pending-count ===
@router.get("/{rss_id}/pending-count")
async def get_pending_count(
    rss_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Get the count of pending review bangumi for specific RSS feed."""
    bangumi_repo = BangumiRepository(session)
    pending_list = await bangumi_repo.get_pending_review(rss_id)
    
    return {"pending_count": len(pending_list)}


# === GET /api/v1/rss/{rss_id}/pending ===
@router.get("/{rss_id}/pending")
async def get_pending_bangumi(
    rss_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Get pending review bangumi for any RSS feed.
    
    For non-aggregate RSS, typically returns 0 or 1 bangumi.
    For aggregate RSS, may return multiple pending bangumi.
    """
    bangumi_repo = BangumiRepository(session)
    pending_list = await bangumi_repo.get_pending_review(rss_id)
    
    return pending_list


# === GET /api/v1/rss/aggregate/pending/{rss_id} ===
@router.get("/aggregate/pending/{rss_id}")
async def get_pending_bangumi_list(
    rss_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
):
    """Get all pending review bangumi for specific aggregate RSS feed.
    
    Returns list of pending bangumi with parsed global_filter_matches as arrays,
    plus summary counts for pending and active bangumi.
    
    Returns 400 if the RSS is not an aggregate RSS feed.
    """
    rss_repo = RSSRepository(session)
    bangumi_repo = BangumiRepository(session)
    
    # Check if RSS exists and is aggregate
    rss = await rss_repo.get_by_id(rss_id)
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
    pending_list = await bangumi_repo.get_pending_review(rss_id)
    
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
            "global_filter_matches": (
                [m.strip() for m in bangumi.global_filter_matches.split(",")]
                if bangumi.global_filter_matches
                else []
            ),
        }
        bangumi_data.append(data)
    
    # Get counts
    pending_count = len(pending_list)
    active_bangumi = await bangumi_repo.get_by_rss(rss_id)
    active_count = len([b for b in active_bangumi if not b.pending_review])
    
    return {
        "pending_count": pending_count,
        "active_count": active_count,
        "bangumi": bangumi_data,
    }
