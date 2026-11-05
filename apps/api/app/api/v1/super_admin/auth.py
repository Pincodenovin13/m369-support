"""Super Admin auth — separate from agency auth.

Separate JWT signing key, separate cookie name, separate audit log.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....core.config import get_settings
from ....db.database import get_db
from ....dependencies import get_super_admin_context
from ....models import SuperAdmin, SuperAdminAuditLog
from ....schemas import SuperAdminLoginRequest, SuperAdminOut
from ....security import create_access_token, verify_password

router = APIRouter(prefix="/super-admin/auth", tags=["Super Admin Authentication"])


def _set_super_admin_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key="super_admin_access_token",
        value=token,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=s.jwt_access_token_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=SuperAdminOut)
def login(payload: SuperAdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Super Admin login. Uses the separate ``super_admins`` table."""
    admin = db.scalar(select(SuperAdmin).where(SuperAdmin.email == payload.email.lower()))
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    now = datetime.now(timezone.utc)
    if admin.locked_until is not None and admin.locked_until > now:
        raise HTTPException(status_code=423, detail="Account temporarily locked. Try again later.")

    token = create_access_token(
        subject=str(admin.id),
        token_type="super_admin",
    )
    admin.last_login_at = now
    admin.failed_mfa_attempts = 0
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.login",
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()
    _set_super_admin_cookie(response, token)
    return admin


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie("super_admin_access_token", path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=SuperAdminOut)
def me(
    request: Request,
    db: Session = Depends(get_db),
    ctx=Depends(get_super_admin_context),
):
    """Return the current Super Admin profile."""
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    return admin
