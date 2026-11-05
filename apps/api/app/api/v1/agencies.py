"""Agency endpoints — read current agency."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id
from ...models import Agency
from ...schemas import AgencyOut

router = APIRouter(prefix="/agencies", tags=["Agencies"])


@router.get("/current", response_model=AgencyOut)
def get_current_agency(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
):
    """Return the agency the current token is scoped to."""
    return db.get(Agency, agency_id)
