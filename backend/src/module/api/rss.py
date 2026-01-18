import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from module.downloader import DownloadClient
from module.manager import SeasonCollector, TorrentStatusManager
from module.models import APIResponse, Bangumi, RSSItem, RSSUpdate, Torrent
from module.rss import RSSAnalyser, RSSEngine
from module.security.api import UNAUTHORIZED, get_current_user

from .response import u_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rss", tags=["rss"])


@router.get(
    path="", response_model=list[RSSItem], dependencies=[Depends(get_current_user)]
)
async def get_rss():
    with RSSEngine() as engine:
        return engine.rss.search_all()


@router.post(
    path="/add", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def add_rss(rss: RSSItem):
    with RSSEngine() as engine:
        result = engine.add_rss(rss.url, rss.name, rss.aggregate, rss.parser)
    return u_response(result)


@router.post(
    path="/enable/many",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def enable_many_rss(
    rss_ids: list[int],
):
    with RSSEngine() as engine:
        result = engine.enable_list(rss_ids)
    return u_response(result)


@router.delete(
    path="/delete/{rss_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_rss(rss_id: int):
    with RSSEngine() as engine:
        if engine.rss.delete(rss_id):
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
    with RSSEngine() as engine:
        result = engine.delete_list(rss_ids)
    return u_response(result)


@router.patch(
    path="/disable/{rss_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_rss(rss_id: int):
    with RSSEngine() as engine:
        if engine.rss.disable(rss_id):
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
    with RSSEngine() as engine:
        result = engine.disable_list(rss_ids)
    return u_response(result)


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
    with RSSEngine() as engine:
        if engine.rss.update(rss_id, data):
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
    with RSSEngine() as engine, DownloadClient() as client:
        engine.refresh_rss(client)
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
    with RSSEngine() as engine, DownloadClient() as client:
        engine.refresh_rss(client, rss_id)
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
    with TorrentStatusManager() as manager:
        return manager.get_rss_torrents_status(rss_id)




@router.post(
    path="/recreate/{rss_id}",
    response_model=list[Bangumi],
    dependencies=[Depends(get_current_user)],
)
async def recreate_rss_rules(rss_id: int):
    """Parse first torrent from RSS feed and return Bangumi rule for review."""
    with RSSEngine() as engine:
        rss = engine.rss.search_id(rss_id)
        if not rss:
            return JSONResponse(
                status_code=404,
                content={
                    "msg_en": "RSS feed not found.",
                    "msg_zh": "RSS订阅未找到。",
                },
            )
        
        try:
            analyser = RSSAnalyser()
            # Use the same logic as original Add RSS: parse only first torrent
            bangumi = analyser.link_to_data(rss)
            
            if isinstance(bangumi, Bangumi):
                return [bangumi]
            else:
                # bangumi is a ResponseModel error
                return JSONResponse(
                    status_code=bangumi.status_code,
                    content={
                        "msg_en": bangumi.msg_en,
                        "msg_zh": bangumi.msg_zh,
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


# Old API
analyser = RSSAnalyser()


@router.post(
    "/analysis", response_model=Bangumi, dependencies=[Depends(get_current_user)]
)
async def analysis(rss: RSSItem):
    data = analyser.link_to_data(rss)
    if isinstance(data, Bangumi):
        return data
    else:
        return u_response(data)


@router.post(
    "/collect", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def download_collection(data: Bangumi):
    with SeasonCollector() as collector:
        resp = collector.collect_season(data, data.rss_link)
        return u_response(resp)


@router.post(
    "/subscribe", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def subscribe(data: Bangumi, rss: RSSItem):
    with SeasonCollector() as collector:
        resp = collector.subscribe_season(data, parser=rss.parser)
        return u_response(resp)
