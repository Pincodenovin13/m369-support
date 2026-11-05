"""Slug generation: kebab-case, uniqueness enforced against existing rows."""
from __future__ import annotations

import re
import unicodedata
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

T = TypeVar("T")


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_LEADING_TRAILING_DASH = re.compile(r"^-+|-+$")


def slugify(value: str) -> str:
    """Convert a display name to a URL-safe slug.

    Lowercase, ASCII, hyphen-separated. Strips diacritics (NFKD decomposition).
    Falls back to ``"agency"`` if the input produces nothing usable.
    """
    if not value:
        return "agency"
    nfkd = unicodedata.normalize("NFKD", value)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = _SLUG_RE.sub("-", lowered)
    slug = _LEADING_TRAILING_DASH.sub("", slug)
    return slug or "agency"


def unique_slug(db: Session, model: type, column: str, base: str, *, max_attempts: int = 100) -> str:
    """Generate a slug unique within ``model.column``.

    Tries ``slugify(base)`` first; if taken, appends ``-2``, ``-3``, … until
    a free slot is found.
    """
    base_slug = slugify(base)
    if not base_slug:
        base_slug = "agency"
    candidate = base_slug
    col = getattr(model, column)
    for i in range(2, max_attempts + 2):
        existing = db.scalar(select(model).where(col == candidate))
        if existing is None:
            return candidate
        candidate = f"{base_slug}-{i}"
    raise RuntimeError(f"Could not find a unique slug for {model.__name__}.{column} after {max_attempts} attempts")
