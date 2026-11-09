"""Cryptographically bound tenant context for PostgreSQL RLS."""
from __future__ import annotations
import hashlib, hmac, uuid
from dataclasses import dataclass
from typing import Any, TypeVar
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..core.config import get_settings

TENANT_GUC = "app.tenant_id"
TENANT_SIGNATURE_GUC = "app.tenant_sig"
_DOMAIN = "m369:tenant:v1:"

@dataclass(frozen=True)
class TenantContext:
    agency_id: uuid.UUID | None
    user_id: uuid.UUID | None
    is_super_admin: bool
    raw_token: str
    def require_agency_id(self) -> uuid.UUID:
        if self.agency_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="The session is not bound to an agency")
        return self.agency_id
    def scoped_to(self, agency_id: uuid.UUID) -> "TenantContext":
        return TenantContext(agency_id, self.user_id, self.is_super_admin, self.raw_token)

def tenant_context_signature(agency_id: uuid.UUID | str, secret: str | None = None) -> str:
    normalized = str(uuid.UUID(str(agency_id)))
    key = secret if secret is not None else get_settings().tenant_context_secret
    if len(key.encode("utf-8")) < 32:
        raise RuntimeError("M369_TENANT_CONTEXT_SECRET must contain at least 32 UTF-8 bytes")
    return hmac.new(key.encode("utf-8"), (_DOMAIN + normalized).encode("utf-8"), hashlib.sha256).hexdigest()

def set_tenant_context(db: Session, agency_id: uuid.UUID | str) -> None:
    normalized = str(uuid.UUID(str(agency_id)))
    signature = tenant_context_signature(normalized)
    db.info["tenant_id"] = normalized
    db.info["tenant_signature"] = signature
    db.execute(text("SELECT pg_catalog.set_config(:k1,:v1,true), pg_catalog.set_config(:k2,:v2,true)"),
               {"k1": TENANT_GUC, "v1": normalized, "k2": TENANT_SIGNATURE_GUC, "v2": signature})

def clear_tenant_context(db: Session) -> None:
    db.info.pop("tenant_id", None); db.info.pop("tenant_signature", None)
    db.execute(text("SELECT pg_catalog.set_config(:k1,'',true), pg_catalog.set_config(:k2,'',true)"),
               {"k1": TENANT_GUC, "k2": TENANT_SIGNATURE_GUC})

T = TypeVar("T")
class TenantOwned:
    agency_id: uuid.UUID | None

def assert_tenant_owned(record: Any, agency_id: uuid.UUID, *, agency_attr: str = "agency_id") -> None:
    if getattr(record, agency_attr, None) != agency_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
