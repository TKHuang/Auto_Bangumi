from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.api.models import (
    BangumiResponse,
    MessageResponse,
    PendingCountResponse,
    RSSCreateRequest,
    RSSResponse,
    RSSUpdateRequest,
)
from zen_bangumi.domain.models.rss import RSSItem
from zen_bangumi.domain.models.user import User
from zen_bangumi.repositories.bangumi import BangumiRepository
from zen_bangumi.repositories.rss import RSSRepository

router = APIRouter(prefix="/api/v1/rss", tags=["rss"])


def get_rss_repo(request: Request) -> RSSRepository:
    return RSSRepository(request.state.db)


def get_bangumi_repo(request: Request) -> BangumiRepository:
    return BangumiRepository(request.state.db)


@router.get("/", response_model=list[RSSResponse])
async def list_rss(
    repo: RSSRepository = Depends(get_rss_repo),
    _current_user: User = Depends(get_current_user),
):
    rss_list = await repo.get_all()
    return rss_list


@router.post("/", response_model=RSSResponse, status_code=status.HTTP_201_CREATED)
async def create_rss(
    data: RSSCreateRequest,
    request: Request,
    repo: RSSRepository = Depends(get_rss_repo),
    _current_user: User = Depends(get_current_user),
    _skip_bangumi: bool = Query(
        True, description="Skip automatic bangumi creation (for now always true)"
    ),
):
    rss_item = await repo.create(
        url=data.url,
        name=data.name,
        enabled=data.enabled,
        aggregate=data.aggregate,
    )
    
    update_data = {"parser": data.parser}
    rss_item = await repo.update(rss_item.id, update_data)
    
    await request.state.db.commit()
    return rss_item


@router.put("/{id}", response_model=RSSResponse)
async def update_rss(
    id: int,
    data: RSSUpdateRequest,
    request: Request,
    repo: RSSRepository = Depends(get_rss_repo),
    _current_user: User = Depends(get_current_user),
):
    update_data = data.model_dump(exclude_none=True)
    
    try:
        rss_item = await repo.update(id, update_data)
        await request.state.db.commit()
        return rss_item
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{id}", response_model=MessageResponse)
async def delete_rss(
    id: int,
    request: Request,
    repo: RSSRepository = Depends(get_rss_repo),
    _current_user: User = Depends(get_current_user),
):
    try:
        await repo.delete(id)
        await request.state.db.commit()
        return MessageResponse(message=f"RSS {id} deleted successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{id}/refresh", response_model=MessageResponse)
async def refresh_rss(
    id: int,
    repo: RSSRepository = Depends(get_rss_repo),
    _current_user: User = Depends(get_current_user),
):
    rss_item = await repo.session.get(RSSItem, id)
    if not rss_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RSS with id {id} not found",
        )
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 18 (RSS Engine)",
    )


@router.post("/refresh/all", response_model=MessageResponse)
async def refresh_all_rss(
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 18 (RSS Engine)",
    )


@router.post("/{id}/recreate", response_model=MessageResponse)
async def recreate_bangumi_rules(
    id: int,
    repo: RSSRepository = Depends(get_rss_repo),
    _current_user: User = Depends(get_current_user),
    _official_title: str | None = Query(None),
    _season: int | None = Query(None),
    _group_name: str | None = Query(None),
):
    rss_item = await repo.session.get(RSSItem, id)
    if not rss_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RSS with id {id} not found",
        )
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 9 (Parser)",
    )


@router.post("/analysis/torrents", response_model=MessageResponse)
async def analyze_torrents(
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 9 (Parser)",
    )


@router.post("/subscribe", response_model=MessageResponse)
async def subscribe_bangumi(
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 19 (Collector)",
    )


@router.post("/subscribe/batch", response_model=MessageResponse)
async def subscribe_bangumi_batch(
    _current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 19 (Collector)",
    )


@router.get("/{id}/pending", response_model=list[BangumiResponse])
async def get_pending_bangumi(
    id: int,
    repo: RSSRepository = Depends(get_rss_repo),
    bangumi_repo: BangumiRepository = Depends(get_bangumi_repo),
    _current_user: User = Depends(get_current_user),
):
    rss_item = await repo.session.get(RSSItem, id)
    if not rss_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RSS with id {id} not found",
        )
    
    all_bangumi = await bangumi_repo.get_all(filters={"rss_id": id, "pending_review": True})
    return all_bangumi


@router.get("/{id}/pending-count", response_model=PendingCountResponse)
async def get_pending_count(
    id: int,
    repo: RSSRepository = Depends(get_rss_repo),
    bangumi_repo: BangumiRepository = Depends(get_bangumi_repo),
    _current_user: User = Depends(get_current_user),
):
    rss_item = await repo.session.get(RSSItem, id)
    if not rss_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RSS with id {id} not found",
        )
    
    all_bangumi = await bangumi_repo.get_all(filters={"rss_id": id, "pending_review": True})
    return PendingCountResponse(pending_count=len(all_bangumi))
