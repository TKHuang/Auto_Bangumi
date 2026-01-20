import asyncio

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from module.manager import TorrentManager, TorrentStatusManager
from module.models import APIResponse, Bangumi, BangumiUpdate, ResponseModel
from module.security.api import UNAUTHORIZED, get_current_user

from .response import u_response

router = APIRouter(prefix="/bangumi", tags=["bangumi"])


def str_to_list(data: Bangumi):
    data.filter = data.filter.split(",")
    data.rss_link = data.rss_link.split(",")
    return data


@router.get(
    "/get/all", response_model=list[Bangumi], dependencies=[Depends(get_current_user)]
)
async def get_all_data():
    def _sync():
        with TorrentManager() as manager:
            return manager.bangumi.search_all()
    return await asyncio.to_thread(_sync)


@router.get(
    "/get/{bangumi_id}",
    response_model=Bangumi,
    dependencies=[Depends(get_current_user)],
)
async def get_data(bangumi_id: int):
    def _sync():
        with TorrentManager() as manager:
            return manager.search_one(bangumi_id)
    return await asyncio.to_thread(_sync)


@router.patch(
    "/update/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def update_rule(
    bangumi_id: int,
    data: BangumiUpdate,
):
    def _sync():
        with TorrentManager() as manager:
            return manager.update_rule(bangumi_id, data)
    return u_response(await asyncio.to_thread(_sync))


@router.delete(
    path="/delete/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_rule(bangumi_id: int, file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.delete_rule(bangumi_id, file)
    return u_response(await asyncio.to_thread(_sync))


@router.delete(
    path="/delete",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_many_rule(bangumi_id: list[int] = Body(...), file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.delete_many_rules(bangumi_id, file)
    return u_response(await asyncio.to_thread(_sync))


@router.delete(
    path="/disable/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_rule(bangumi_id: int, file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.disable_rule(bangumi_id, file)
    return u_response(await asyncio.to_thread(_sync))


@router.delete(
    path="/disable",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_many_rule(bangumi_id: list[int] = Body(...), file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.disable_many_rules(bangumi_id, file)
    return u_response(await asyncio.to_thread(_sync))


@router.get(
    path="/enable/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def enable_rule(bangumi_id: int):
    def _sync():
        with TorrentManager() as manager:
            return manager.enable_rule(bangumi_id)
    return u_response(await asyncio.to_thread(_sync))


@router.get(
    path="/refresh/poster/all",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def refresh_poster():
    def _sync():
        with TorrentManager() as manager:
            return manager.refresh_poster()
    return u_response(await asyncio.to_thread(_sync))


@router.get(
    path="/refresh/poster/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def refresh_poster_by_id(bangumi_id: int):
    def _sync():
        with TorrentManager() as manager:
            return manager.refind_poster(bangumi_id)
    return u_response(await asyncio.to_thread(_sync))


@router.get(
    "/reset/all", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def reset_all():
    def _sync():
        with TorrentManager() as manager:
            manager.bangumi.delete_all()
    await asyncio.to_thread(_sync)
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Reset all rules successfully.", "msg_zh": "重置所有规则成功。"},
    )


@router.get(
    "/torrent/{bangumi_id}",
    response_model=list[dict],
    dependencies=[Depends(get_current_user)],
)
async def get_torrent_status(bangumi_id: int):
    def _sync():
        with TorrentStatusManager() as manager:
            return manager.get_bangumi_torrents_status(bangumi_id)
    return await asyncio.to_thread(_sync)


@router.post(
    "/torrent/download",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def download_torrent(torrent_id: int = Query(...)):
    def _sync():
        with TorrentStatusManager() as manager:
            return manager.download_torrent(torrent_id)
    return u_response(await asyncio.to_thread(_sync))
