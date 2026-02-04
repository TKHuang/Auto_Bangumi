"""Pydantic models for API requests and responses."""

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
