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

from sqlalchemy import create_engine, event, text
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


# Super Admin operations need a BYPASSRLS connection to read/write across
# all tenants. The m369_sa_runner role is provisioned externally with
# BYPASSRLS but NOSUPERUSER — so it can still only do CRUD on tables,
# never CREATE/DROP/ROLE/etc.
super_admin_engine: Engine = _build_engine(get_settings().database_url_super_admin)
SuperAdminSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=super_admin_engine, autoflush=False, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""

    pass


# ---------------------------------------------------------------------------
# RLS GUC persistence: re-issue SET LOCAL app.tenant_id at every txn begin
# ---------------------------------------------------------------------------


TENANT_GUC = "app.tenant_id"


@event.listens_for(Session, "after_begin")
def _reissue_tenant_guc_on_txn_begin(session: Session, transaction: Any, connection: Any) -> None:
    """After a new transaction starts, re-apply the tenant GUC if set.

    ``SET LOCAL`` only lasts for the current transaction. After commit /
    rollback the GUC is gone. This listener restores it from
    ``session.info`` so subsequent SELECTs (e.g. ``db.refresh``) hit RLS
    with the correct tenant context.
    """
    tenant_id = session.info.get("tenant_id")
    if tenant_id is not None:
        connection.execute(text(f"SET LOCAL {TENANT_GUC} = '{tenant_id}'"))


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session, ensure it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_super_admin_db() -> Iterator[Session]:
    """FastAPI dependency: yield a Super Admin session connected as m369_sa_runner.

    The ``m369_sa_runner`` role has BYPASSRLS — RLS policies are skipped,
    so the session sees every tenant's rows. Use ONLY for Super Admin
    endpoints (verified by ``get_super_admin_context``).

    The session's ``info["is_super_admin"]`` flag is set so the
    ``after_begin`` listener knows to skip re-issuing SET LOCAL
    app.tenant_id (Super Admin has no tenant scope).
    """
    db = SuperAdminSessionLocal()
    db.info["is_super_admin"] = True
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
