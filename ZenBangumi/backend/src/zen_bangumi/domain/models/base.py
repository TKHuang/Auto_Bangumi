"""Base model classes and mixins for SQLAlchemy models."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


metadata_obj = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = metadata_obj
    
    __abstract__ = True


class TimestampMixin:
    """Mixin for created_at/updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class VersionMixin:
    """Mixin for optimistic locking with version column."""

    version: Mapped[int] = mapped_column(default=1, nullable=False)
