"""Database engine, session factory, and ``get_db`` dependency.

A single ``SessionLocal`` is created per process; FastAPI's ``get_db`` yields a
fresh session per request. The session's ``info`` dict carries the current
tenant context so the tenant-aware repository and RLS helpers can pick it up
without threading it through every call site.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..core.config import get_settings


KEEPALIVE_ARGS = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
    "connect_timeout": 10,
}


def _build_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=240,
        pool_size=10,
        max_overflow=20,
        connect_args=KEEPALIVE_ARGS,
    )


engine: Engine = _build_engine(get_settings().database_url)
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""

    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session, ensure it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope(*, tenant_id: Any = None) -> Iterator[Session]:
    """Open a session outside a request (background jobs, scripts, tests)."""
    db = SessionLocal()
    try:
        if tenant_id is not None:
            from ..tenancy.context import set_tenant_context

            set_tenant_context(db, tenant_id)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_engine_factory(test_url: str | None = None) -> Engine:
    """Build a separate engine for tests (against the test database)."""
    url = test_url or get_settings().test_database_url
    return create_engine(url, pool_pre_ping=True, connect_args=KEEPALIVE_ARGS)
