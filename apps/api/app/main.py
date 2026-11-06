"""M369 Support API — FastAPI entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import (
    agencies,
    audit_logs,
    auth,
    canned_responses,
    channels,
    contacts,
    conversations,
    health,
    kb,
    messages,
    super_admin,
    teams,
    workspaces,
)
from .core.config import get_settings
from .middleware.tenant_context import TenantContextMiddleware


def create_app() -> FastAPI:
    """Application factory."""
    s = get_settings()
    app = FastAPI(
        title="M369 Support API",
        description="Multi-tenant SaaS customer support platform",
        version="0.1.0",
        docs_url="/docs" if s.environment == "development" else None,
        redoc_url="/redoc" if s.environment == "development" else None,
        openapi_url="/openapi.json" if s.environment == "development" else None,
    )

    origins = [s.frontend_url]
    if s.environment == "development":
        origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(TenantContextMiddleware)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(agencies.router, prefix="/api/v1")
    app.include_router(workspaces.router, prefix="/api/v1")
    app.include_router(contacts.router, prefix="/api/v1")
    app.include_router(conversations.router, prefix="/api/v1")
    app.include_router(messages.router, prefix="/api/v1")
    app.include_router(teams.router, prefix="/api/v1")
    app.include_router(channels.router, prefix="/api/v1")
    app.include_router(kb.router, prefix="/api/v1")
    app.include_router(canned_responses.router, prefix="/api/v1")
    app.include_router(audit_logs.router, prefix="/api/v1")
    app.include_router(super_admin.auth.router, prefix="/api/v1")
    app.include_router(super_admin.agencies.router, prefix="/api/v1")
    app.include_router(super_admin.plans.router, prefix="/api/v1")
    app.include_router(super_admin.subscriptions.router, prefix="/api/v1")
    app.include_router(super_admin.payments.router, prefix="/api/v1")
    app.include_router(super_admin.settings_notes_audit.settings_router, prefix="/api/v1")
    app.include_router(super_admin.settings_notes_audit.notes_router, prefix="/api/v1")
    app.include_router(super_admin.settings_notes_audit.audit_router, prefix="/api/v1")

    @app.get("/health", tags=["System"])
    def root_health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
