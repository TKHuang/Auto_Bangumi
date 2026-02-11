"""RSS schema models (pure Pydantic/SQLModel schemas — NOT ORM tables).

The real ORM tables live in module.domain.models.rss.
These schemas are used for API serialization and request/response validation.
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class RSSItem(SQLModel, table=False):
    model_config = {"from_attributes": True}

    id: Optional[int] = Field(default=None)
    name: Optional[str] = Field(default=None)
    url: str = Field(default="https://mikanani.me")
    aggregate: bool = Field(default=False)
    parser: str = Field(default="mikan")
    enabled: bool = Field(default=True)
    last_update: Optional[str] = Field(default=None)
    last_status: Optional[str] = Field(default=None)
    last_error: Optional[str] = Field(default=None)


class RSSUpdate(SQLModel):
    model_config = {"from_attributes": True}

    name: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default="https://mikanani.me")
    aggregate: Optional[bool] = Field(default=True)
    parser: Optional[str] = Field(default="mikan")
    enabled: Optional[bool] = Field(default=True)
    last_update: Optional[str] = Field(default=None)
    last_status: Optional[str] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
