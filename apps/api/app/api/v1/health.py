"""Health endpoints — public, no tenant context."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...db.database import get_db
from ...schemas import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["System"])


@router.get("", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=get_settings().environment,
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return ReadinessResponse(status="ok", database="ok")
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "fail", "database": str(exc)[:200]},
        )
