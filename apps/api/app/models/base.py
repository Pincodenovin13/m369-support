"""Model base: utilities, mixins, and Base re-export.

All domain model modules import from here to avoid circular dependencies.
``phase1_extended.py`` imports ``new_uuid``, ``now_utc``, ``TimestampMixin``,
``AgencyOwnedMixin`` from the parent package (``from . import ...``), which
works because ``__init__.py`` re-exports them from this module.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base
from ..tenancy.context import TenantOwned


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        server_default=text("now()"),
        onupdate=now_utc,
        nullable=False,
    )


class AgencyOwnedMixin(TenantOwned):
    """Marker for any model that carries ``agency_id``."""

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


__all__ = [
    "Base",
    "new_uuid",
    "now_utc",
    "TimestampMixin",
    "AgencyOwnedMixin",
]
