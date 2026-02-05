import anyio
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from module.api.middleware.auth import get_current_user
from module.manager import Renamer, TorrentManager, TorrentStatusManager
from module.models import APIResponse, Bangumi, BangumiUpdate
from module.rss import RSSEngine

router = APIRouter(prefix="/bangumi", tags=["bangumi"])


def str_to_list(data: Bangumi):
    """Convert comma-separated filter and rss_link strings to lists.
    
    IMPORTANT: Frontend expects filter and rss_link as ARRAYS,
    but database stores them as comma-separated STRINGS.
    This function converts DB format to API format.
    """
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
    return await anyio.to_thread.run_sync(_sync)


@router.get(
    "/get/{bangumi_id}",
    response_model=Bangumi,
    dependencies=[Depends(get_current_user)],
)
async def get_data(bangumi_id: int):
    def _sync():
        with TorrentManager() as manager:
            return manager.search_one(bangumi_id)
    return await anyio.to_thread.run_sync(_sync)


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
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.delete(
    path="/delete/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_rule(bangumi_id: int, file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.delete_rule(bangumi_id, file)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.delete(
    path="/delete",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def delete_many_rule(bangumi_id: list[int] = Body(...), file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.delete_many_rules(bangumi_id, file)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.delete(
    path="/disable/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_rule(bangumi_id: int, file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.disable_rule(bangumi_id, file)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.delete(
    path="/disable",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def disable_many_rule(bangumi_id: list[int] = Body(...), file: bool = False):
    def _sync():
        with TorrentManager() as manager:
            return manager.disable_many_rules(bangumi_id, file)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.get(
    path="/enable/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def enable_rule(bangumi_id: int):
    def _sync():
        with TorrentManager() as manager:
            return manager.enable_rule(bangumi_id)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.get(
    "/reset/all", response_model=APIResponse, dependencies=[Depends(get_current_user)]
)
async def reset_all():
    def _sync():
        with TorrentManager() as manager:
            manager.bangumi.delete_all()
            manager.commit()
    
    await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=200,
        content={"msg_en": "Reset all rules successfully.", "msg_zh": "重置所有规则成功。"},
    )


@router.get(
    path="/refresh/poster/all",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def refresh_poster():
    def _sync():
        with TorrentManager() as manager:
            return manager.refresh_poster()
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.get(
    path="/refresh/poster/{bangumi_id}",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def refresh_poster_by_id(bangumi_id: int):
    def _sync():
        with TorrentManager() as manager:
            return manager.refind_poster(bangumi_id)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
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
    return await anyio.to_thread.run_sync(_sync)


@router.post(
    "/torrent/download",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def download_torrent(torrent_id: int = Query(...)):
    def _sync():
        with TorrentStatusManager() as manager:
            return manager.download_torrent(torrent_id)
    
    result = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=result.status_code,
        content={
            "msg_en": result.msg_en,
            "msg_zh": result.msg_zh,
        },
    )


@router.post(
    path="/{bangumi_id}/activate",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def activate_pending_bangumi(
    bangumi_id: int,
    filter: str = Body(default=None, embed=True),
):
    """Activate a pending review bangumi and download its torrents.

    Args:
        bangumi_id: The bangumi ID to activate.
        filter: Optional filter value to set on the bangumi.

    Returns:
        {msg_en, msg_zh} with success or error message, including download status.
    """
    def _sync():
        with TorrentManager() as manager:
            success, message = manager.bangumi.activate_pending(bangumi_id, filter)
            if not success:
                return False, message, None
            
            manager.commit()

            bangumi = manager.bangumi.search_id(bangumi_id)
            if not bangumi:
                return False, "Bangumi not found after activation", None

            return True, "Activated", bangumi

    success, message, bangumi = await anyio.to_thread.run_sync(_sync)
    if not success:
        return JSONResponse(
            status_code=400,
            content={
                "msg_en": message,
                "msg_zh": "该番剧不在待审核状态",
            },
        )

    def _download():
        with RSSEngine() as engine:
            return engine.download_bangumi(bangumi)

    download_result = await anyio.to_thread.run_sync(_download)

    if download_result.status:
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Bangumi activated and {download_result.msg_en}",
                "msg_zh": f"番剧已激活，{download_result.msg_zh}",
            },
        )
    else:
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": f"Bangumi activated but download issue: {download_result.msg_en}",
                "msg_zh": f"番剧已激活，但下载出现问题：{download_result.msg_zh}",
            },
        )


@router.post(
    path="/{bangumi_id}/retrigger-rename",
    response_model=APIResponse,
    dependencies=[Depends(get_current_user)],
)
async def retrigger_rename(bangumi_id: int):
    """Clear rename status and immediately trigger rename for a bangumi.

    This resets renamed_at and renamed_file_count for all torrents
    belonging to the specified bangumi, then immediately triggers
    the rename process for those torrents.

    Both operations happen atomically under the rename lock to prevent
    the background rename loop from picking up cleared torrents.

    Args:
        bangumi_id: The bangumi ID whose torrents should be re-renamed.

    Returns:
        {msg_en, msg_zh} with count of renamed files.
    """
    def _sync():
        with Renamer() as renamer:
            renamed_files = renamer.rename_bangumi(bangumi_id, clear_status=True)
        return len(renamed_files)

    renamed_count = await anyio.to_thread.run_sync(_sync)
    return JSONResponse(
        status_code=200,
        content={
            "msg_en": f"Re-rename completed, renamed {renamed_count} files",
            "msg_zh": f"重新重命名完成，重命名了 {renamed_count} 个文件",
        },
    )
