from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.api.models import (
    BangumiActivateRequest,
    BangumiResponse,
    BangumiUpdateRequest,
    MessageResponse,
    TorrentResponse,
)
from zen_bangumi.domain.models.user import User
from zen_bangumi.repositories.bangumi import BangumiRepository
from zen_bangumi.repositories.exceptions import ConcurrentModificationError
from zen_bangumi.repositories.torrent import TorrentRepository

router = APIRouter(prefix="/api/v1/bangumi", tags=["bangumi"])


def get_bangumi_repo(request: Request) -> BangumiRepository:
    return BangumiRepository(request.state.db)


def get_torrent_repo(request: Request) -> TorrentRepository:
    return TorrentRepository(request.state.db)


@router.get("/", response_model=list[BangumiResponse])
async def list_bangumi(
    deleted: bool = Query(False, description="Include deleted bangumi"),
    season: Optional[int] = Query(None, description="Filter by season number"),
    active: bool = Query(
        False, description="Only active (not pending review) bangumi"
    ),
    pending_review: bool = Query(False, description="Only pending review bangumi"),
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    filters = {}
    
    if not deleted:
        filters["deleted"] = False
    
    if season is not None:
        filters["season"] = season
    
    if pending_review:
        bangumi_list = await repo.get_pending_review()
    elif active:
        bangumi_list = await repo.get_active()
    else:
        bangumi_list = await repo.get_all(filters)
    
    return bangumi_list


@router.get("/{id}", response_model=BangumiResponse)
async def get_bangumi(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    return bangumi


@router.put("/{id}", response_model=BangumiResponse)
async def update_bangumi(
    id: int,
    data: BangumiUpdateRequest,
    request: Request,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    update_data = data.model_dump(exclude={"version"}, exclude_none=True)
    
    try:
        bangumi = await repo.update(id, update_data, data.version)
        await request.state.db.commit()
        return bangumi
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ConcurrentModificationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version conflict - bangumi was modified by another request",
        )


@router.delete("/batch", response_model=MessageResponse)
async def batch_delete_bangumi(
    request: Request,
    bangumi_ids: list[int] = Body(..., embed=False),
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
    file: bool = Query(False, description="Also delete files from downloader"),
):
    deleted_count = 0
    errors = []
    
    for bangumi_id in bangumi_ids:
        try:
            await repo.delete(bangumi_id)
            deleted_count += 1
            
            if file:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="File deletion not yet implemented (Task 12-13 blocked)",
                )
        except ValueError as e:
            errors.append(f"Bangumi {bangumi_id}: {str(e)}")
    
    await request.state.db.commit()
    
    if errors:
        return MessageResponse(
            message=f"Deleted {deleted_count} bangumi, {len(errors)} errors: {'; '.join(errors)}"
        )
    
    return MessageResponse(message=f"Deleted {deleted_count} bangumi successfully")


@router.delete("/{id}", response_model=MessageResponse)
async def delete_bangumi(
    id: int,
    request: Request,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    torrent_repo: TorrentRepository = Depends(get_torrent_repo),
    current_user: User = Depends(get_current_user),
    file: bool = Query(False, description="Also delete files from downloader"),
):
    try:
        await repo.delete(id)
        
        if file:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="File deletion not yet implemented (Task 12-13 blocked)",
            )
        
        await request.state.db.commit()
        return MessageResponse(message=f"Bangumi {id} deleted successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{id}/rename", response_model=MessageResponse)
async def rename_bangumi(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Rename not yet implemented (Task 17 blocked)",
    )


@router.post("/{id}/activate", response_model=MessageResponse)
async def activate_bangumi(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    
    if not bangumi.pending_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bangumi {id} is not in pending review state",
        )
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Activation logic not yet implemented (depends on RSSEngine)",
    )


@router.post("/{id}/collect", response_model=MessageResponse)
async def collect_bangumi(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Collection not yet implemented (Task 19 blocked)",
    )


@router.get("/{id}/torrents", response_model=list[TorrentResponse])
async def get_bangumi_torrents(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    torrent_repo: TorrentRepository = Depends(get_torrent_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    
    torrents = await torrent_repo.get_by_bangumi(id)
    return torrents


@router.get("/{id}/poster", response_model=MessageResponse)
async def get_bangumi_poster(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    
    if not bangumi.poster_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi {id} has no poster",
        )
    
    return MessageResponse(message=bangumi.poster_link)


@router.put("/{id}/poster", response_model=MessageResponse)
async def refresh_bangumi_poster(
    id: int,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    bangumi = await repo.get_by_id(id)
    if not bangumi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bangumi with id {id} not found",
        )
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Poster refresh not yet implemented (depends on TMDB/Mikan service)",
    )


@router.post("/activate/batch", response_model=MessageResponse)
async def batch_activate_bangumi(
    data: BangumiActivateRequest,
    repo: BangumiRepository = Depends(get_bangumi_repo),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Batch activation not yet implemented (depends on RSSEngine)",
    )
