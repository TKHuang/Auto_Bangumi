"""Search API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse

from ..middleware.auth import get_current_user
from ...services.search import get_providers, search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/provider")
async def search_provider(
    current_user: str = Depends(get_current_user),
) -> list[str]:
    """Get list of available search providers.
    
    Returns:
        List of provider names (e.g., ['mikan', 'nyaa', 'dmhy'])
    """
    return get_providers()


@router.get("/bangumi")
async def search_bangumi(
    site: str = Query("mikan"),
    keywords: str = Query(None),
    current_user: str = Depends(get_current_user),
):
    """Search for bangumi torrents with SSE streaming.
    
    Args:
        site: Search provider name (default: 'mikan')
        keywords: Space-separated search keywords
        
    Returns:
        Server-Sent Events stream of Bangumi objects as JSON
        
    Raises:
        400: If keywords are empty
        400: If provider is not supported
    """
    if not keywords or not keywords.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="keywords parameter is required",
        )
    
    # Split keywords by space
    keyword_list = keywords.strip().split()
    
    try:
        return EventSourceResponse(
            content=search(
                keywords=keyword_list,
                provider=site,
                limit=5,
            ),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
