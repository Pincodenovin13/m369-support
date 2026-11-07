"""Migration 0014: Add token_version to users table.

This enables server-side session revocation for agency users — the same
mechanism already used for Super Admins (migration 0010). When a user
logs out, ``token_version`` is incremented atomically via SQL UPDATE,
invalidating all previously-issued access + refresh tokens.

The ``tver`` claim in the JWT is compared against ``users.token_version``
in ``get_current_user`` (for access tokens) and in ``/auth/refresh``
(for refresh tokens). Any mismatch → 401.

down_revision = 0013_package_b1_2_final_security (the actual current head)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0014_agency_user_token_version"
down_revision: Union[str, None] = "0013_package_b1_2_final_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
