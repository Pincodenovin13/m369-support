"""System schemas: health and readiness responses."""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str


__all__ = ["HealthResponse", "ReadinessResponse"]
