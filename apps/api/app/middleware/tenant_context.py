"""Tenant context middleware: resolve JWT, set on request.state, set DB GUC.

This runs *before* FastAPI dependencies, so the tenant context is available
both to the dependency layer and to the database session (via ``SET LOCAL``).

RLS is enforced at the database level. The middleware issues ``SET LOCAL``
on the request's session so policies on tenant-owned tables filter automatically.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ..security import decode_access_token, decode_super_admin_token
from ..tenancy.context import TenantContext


PUBLIC_PATHS = frozenset({
    "/health",
    "/health/ready",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/super-admin/auth/login",
    "/docs",
    "/redoc",
    "/openapi.json",
})


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Resolve the tenant and set on request.state.

    Note: actual ``SET LOCAL app.tenant_id`` is done in the ``get_db`` dependency
    chain (or by the test fixture). This middleware only resolves the tenant
    context from the JWT and stores it on ``request.state.tenant``.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/api/v1/widget"):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        token: str | None = None
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        else:
            token = request.cookies.get("access_token") or request.cookies.get("super_admin_access_token")

        if not token:
            return await call_next(request)

        # Try agency first; fall back to super admin
        payload = decode_access_token(token)
        is_super_admin = False
        if payload is None:
            payload = decode_super_admin_token(token)
            if payload is None:
                return await call_next(request)
            is_super_admin = True

        try:
            user_id = uuid.UUID(payload["sub"]) if not is_super_admin else None
            agency_id_str = payload.get("agency_id")
            agency_id = uuid.UUID(agency_id_str) if agency_id_str else None
        except (KeyError, ValueError):
            return await call_next(request)

        ctx = TenantContext(
            agency_id=agency_id,
            user_id=user_id,
            is_super_admin=is_super_admin,
            raw_token=token,
        )
        request.state.tenant = ctx

        return await call_next(request)
