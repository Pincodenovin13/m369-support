"""Preserve full-precision raw blockchain token amounts.

Revision ID: 0020_payment_raw_amount_precision
Revises: 0019_signed_tenant_context_rls
Create Date: 2026-11-09

The raw ERC-20/TRC-20 token amount is an integer in the token's smallest
unit. A PostgreSQL INTEGER cannot represent even common 18-decimal token
amounts. NUMERIC(78, 0) safely holds the full uint256 range without FLOAT
rounding.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_payment_raw_amount_precision"
down_revision: Union[str, None] = "0019_signed_tenant_context_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "paid_amount_raw",
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=78, scale=0),
        existing_nullable=True,
        postgresql_using="paid_amount_raw::numeric(78,0)",
    )
    op.create_check_constraint(
        "ck_payments_raw_amount_nonneg",
        "payments",
        "paid_amount_raw IS NULL OR (paid_amount_raw >= 0 AND "
        "paid_amount_raw <= 115792089237316195423570985008687907853269984665640564039457584007913129639935)",
    )


def downgrade() -> None:
    # Never silently truncate or overflow a raw token amount on rollback.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM payments
                WHERE paid_amount_raw > 2147483647
                   OR paid_amount_raw < -2147483648
            ) THEN
                RAISE EXCEPTION
                    'Unsafe downgrade refused: payments.paid_amount_raw contains values outside INTEGER range';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint("ck_payments_raw_amount_nonneg", "payments", type_="check")
    op.alter_column(
        "payments",
        "paid_amount_raw",
        existing_type=sa.Numeric(precision=78, scale=0),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="paid_amount_raw::integer",
    )
