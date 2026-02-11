"""User schema models (pure Pydantic/SQLModel schemas — NOT ORM tables).

The real ORM tables live in module.domain.models.user.
These schemas are used for API serialization and request/response validation.
"""

from typing import Optional

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class User(SQLModel, table=False):
    model_config = {"from_attributes": True}

    id: Optional[int] = Field(default=None)
    username: str = Field(
        default="admin", min_length=4, max_length=20, regex=r"^[a-zA-Z0-9_]+$"
    )
    password: str = Field(default="adminadmin", min_length=8)


class UserUpdate(SQLModel):
    username: Optional[str] = Field(
        default=None, min_length=4, max_length=20, regex=r"^[a-zA-Z0-9_]+$"
    )
    password: Optional[str] = Field(default=None, min_length=8)


class UserLogin(SQLModel):
    username: str
    password: str = Field(..., min_length=8)


class Token(BaseModel):
    token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
