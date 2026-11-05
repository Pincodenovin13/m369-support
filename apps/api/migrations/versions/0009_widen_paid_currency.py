"""Migration 0009: Widen payments.paid_currency to String(10).

Migration 0006 created ``payments.paid_currency`` as ``String(3)`` which
is correct for ISO 4217 fiat codes (USD, EUR, IRR...). But for crypto
payments — the primary Phase 1 billing method — the on-chain code is
``USDT`` (4 chars). Rejecting these as too long was a real bug.

This migration widens the column to ``String(10)`` which comfortably
fits both ISO 4217 and any current/future crypto ticker (USDT, USDC,
DAI, WBTC, ETH...). No data is lost — VARCHAR widening is non-breaking.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_widen_paid_currency"
down_revision: Union[str, None] = "0008_create_sa_runner_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "paid_currency",
        existing_type=sa.String(3),
        type_=sa.String(10),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Re-widening on downgrade would silently truncate USDT → USD which
    # is data-corrupting. Downgrade is therefore a no-op by design.
    pass
