from typing import Optional

from sqlmodel import Field, SQLModel


class RSSItem(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True, alias="id")
    name: Optional[str] = Field(None, alias="name")
    url: str = Field("https://mikanani.me", alias="url")
    aggregate: bool = Field(False, alias="aggregate")
    parser: str = Field("mikan", alias="parser")
    enabled: bool = Field(True, alias="enabled")
    last_update: Optional[str] = Field(None, alias="last_update")
    last_status: Optional[str] = Field(None, alias="last_status")
    last_error: Optional[str] = Field(None, alias="last_error")


class RSSUpdate(SQLModel):
    name: Optional[str] = Field(None, alias="name")
    url: Optional[str] = Field("https://mikanani.me", alias="url")
    aggregate: Optional[bool] = Field(True, alias="aggregate")
    parser: Optional[str] = Field("mikan", alias="parser")
    enabled: Optional[bool] = Field(True, alias="enabled")
    last_update: Optional[str] = Field(None, alias="last_update")
    last_status: Optional[str] = Field(None, alias="last_status")
    last_error: Optional[str] = Field(None, alias="last_error")
