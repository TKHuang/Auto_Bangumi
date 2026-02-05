"""Base models and mixins for SQLAlchemy 2.0 async domain models."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Naming conventions for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all domain models."""

    metadata = metadata

    # Type annotation for the primary key (to be overridden in subclasses)
    id: Any


class TimestampMixin:
    """Mixin for automatic timestamp management.

    Provides created_at and updated_at columns that are automatically
    managed by SQLAlchemy events.
    """

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
    """Mixin for optimistic locking.

    Provides a version column that is automatically incremented on each update.
    Use this to prevent lost updates in concurrent scenarios.

    Example:
        # In repository:
        stmt = (
            update(Bangumi)
            .where(Bangumi.id == bangumi_id, Bangumi.version == current_version)
            .values(official_title="New Title", version=Bangumi.version + 1)
        )
        result = await session.execute(stmt)
        if result.rowcount == 0:
            raise OptimisticLockError("Bangumi was modified by another transaction")
    """

    version: Mapped[int] = mapped_column(default=1, nullable=False)


# Event listener to auto-increment version on update
@event.listens_for(VersionMixin, "before_update", propagate=True)
def increment_version(mapper: Any, connection: Any, target: VersionMixin) -> None:
    """Automatically increment version on update."""
    target.version += 1
