"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request model for user login."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Response model for successful login."""
    message: str
    username: str


class UpdatePasswordRequest(BaseModel):
    """Request model for password update."""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    """Generic response model with a message."""
    message: str


# Bangumi API Models


class BangumiUpdateRequest(BaseModel):
    """Request model for updating bangumi fields (user-editable only)."""
    official_title: Optional[str] = None
    year: Optional[str] = Field(None, max_length=10)
    season: Optional[int] = Field(None, ge=1)
    filter: Optional[str] = Field(None, max_length=100)
    offset: Optional[int] = Field(None, ge=0)
    group_name: Optional[str] = Field(None, max_length=100)
    version: int = Field(..., description="Version for optimistic locking")


class BangumiActivateRequest(BaseModel):
    """Request model for batch activating pending review bangumi."""
    bangumi_ids: list[int] = Field(..., min_length=1)


class BangumiResponse(BaseModel):
    """Response model for bangumi data."""
    model_config = {"from_attributes": True}
    
    id: int
    rss_id: Optional[int]
    official_title: str
    year: Optional[str]
    title_raw: str
    season: int
    season_raw: Optional[str]
    group_name: str
    dpi: Optional[str]
    source: Optional[str]
    subtitle: Optional[str]
    eps_collect: bool
    offset: int
    filter: str
    rss_link: str
    poster_link: Optional[str]
    added: bool
    rule_name: Optional[str]
    save_path: Optional[str]
    deleted: bool
    pending_review: bool
    global_filter_matches: Optional[str]
    version: int


class TorrentResponse(BaseModel):
    """Response model for torrent data."""
    model_config = {"from_attributes": True}
    
    id: int
    hash: str
    name: str
    bangumi_id: int
    downloaded: bool
    renamed_at: Optional[datetime]
    renamed_file_count: Optional[int]
    pikpak_cloud_path: Optional[str]


class BangumiDeleteRequest(BaseModel):
    """Request model for batch delete."""
    bangumi_ids: list[int] = Field(..., min_length=1)
