"""Common Pydantic primitives shared across schemas.

- ``PaginationParams`` is the dependency used by every list endpoint to
  parse ``limit`` / ``offset`` query parameters with safe defaults and
  hard caps (max 100 per page).
- ``PaginatedResponse[T]`` is the generic envelope every list endpoint
  returns. Carrying ``total`` + ``limit`` + ``offset`` makes the API
  self-describing for paginators.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field


DEFAULT_LIMIT = 25
MAX_LIMIT = 100


class PaginationParams(BaseModel):
    """Query params for any list endpoint. Bound by ``MAX_LIMIT``."""

    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


__all__ = ["PaginationParams", "PaginatedResponse", "DEFAULT_LIMIT", "MAX_LIMIT"]
