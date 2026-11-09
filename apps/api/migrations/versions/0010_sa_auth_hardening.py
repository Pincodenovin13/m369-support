"""Migration 0010: Super Admin authentication & session security hardening.

Adds server-side session revocation, brute-force protection fields, and
the tables required for real TOTP-based MFA on the Super Admin identity.

This migration is part of "Phase 1 Security Hardening / Package A" and
does NOT alter any tenant-owned table. Existing migrations 0001-0009
remain unchanged.

Schema changes:

  super_admins (existing table, new columns):
    - token_version INTEGER NOT NULL DEFAULT 0
        Server-side session revocation. Bumped on logout-all, password
        change, account deactivation. The JWT carries this value as the
        ``tver`` claim; the request dependency compares token.tver vs
        super_admins.token_version and rejects on mismatch.
    - failed_login_attempts INTEGER NOT NULL DEFAULT 0
        Counter of consecutive failed password verifications. Reset to 0
        on successful login. Atomically incremented via
        ``UPDATE ... SET failed_login_attempts = failed_login_attempts + 1``
        to survive concurrent attempts.
    - last_failed_login_at TIMESTAMPTZ NULL
        For audit + observability. Never contains the password or any
        secret — only a timestamp.

  super_admin_mfa_challenges (new table):
    Short-lived challenge tokens issued AFTER password verification when
    MFA is enabled. The challenge authorizes the bearer to call
    ``/super-admin/auth/login/verify-mfa`` ONLY — it cannot be used on
    any management endpoint (verified by token scope + dependency).

    Columns:
      - id (UUID, PK)
      - super_admin_id (UUID FK → super_admins ON DELETE CASCADE)
      - challenge_hash (TEXT, NOT NULL) — SHA-256 of the challenge token
        we issue. The plaintext is never stored.
      - expires_at (TIMESTAMPTZ NOT NULL) — short TTL (default 5 min)
      - used_at (TIMESTAMPTZ NULL) — set when consumed; replay rejected
      - created_at (TIMESTAMPTZ NOT NULL)

  super_admin_used_totp_codes (new table):
    Single-use TOTP replay protection. Each successfully-verified TOTP
    code is recorded here with a TTL equal to the TOTP step window
    (default 90s = one full step before + current step). Old entries are
    purged lazily on insert.

    Columns:
      - id (UUID, PK)
      - super_admin_id (UUID FK → super_admins ON DELETE CASCADE)
      - code_hash (TEXT, NOT NULL) — SHA-256 of (super_admin_id, code, window_start_ts)
      - window_start_ts (BIGINT NOT NULL) — Unix epoch seconds of the
        TOTP window the code was issued for
      - used_at (TIMESTAMPTZ NOT NULL DEFAULT now())

    Unique index on (super_admin_id, code_hash) prevents two requests
    with the same code in the same window from both succeeding.

  super_admin_mfa_recovery_codes (new table):
    Single-use recovery codes for account access when TOTP device is
    lost. Stored as Argon2id hash (reusing the password hasher) — never
    plaintext.

    Columns:
      - id (UUID, PK)
      - super_admin_id (UUID FK → super_admins ON DELETE CASCADE)
      - code_hash (TEXT, NOT NULL) — Argon2id hash of the recovery code
      - used_at (TIMESTAMPTZ NULL) — set when consumed; replay rejected
      - created_at (TIMESTAMPTZ NOT NULL DEFAULT now())

No default admin accounts are created. No passwords are inserted.
Existing super_admins rows get token_version=0, failed_login_attempts=0
via the column server_defaults.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0010_sa_auth_hardening"
down_revision: Union[str, None] = "0009_widen_paid_currency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Add new columns to super_admins ---
    op.add_column(
        "super_admins",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "super_admins",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "super_admins",
        sa.Column(
            "last_failed_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Index for fast lookup of locked accounts (used at login time)
    op.create_index(
        "ix_super_admins_locked_until",
        "super_admins",
        ["locked_until"],
    )

    # --- 2. super_admin_mfa_challenges ---
    op.create_table(
        "super_admin_mfa_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("challenge_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_sa_mfa_challenges_sa_expires",
        "super_admin_mfa_challenges",
        ["super_admin_id", "expires_at"],
    )

    # --- 3. super_admin_used_totp_codes ---
    op.create_table(
        "super_admin_used_totp_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column("window_start_ts", sa.BigInteger, nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "super_admin_id",
            "code_hash",
            name="uq_sa_totp_codes_sa_codehash",
        ),
    )
    op.create_index(
        "ix_sa_totp_codes_window",
        "super_admin_used_totp_codes",
        ["super_admin_id", "window_start_ts"],
    )

    # --- 4. super_admin_mfa_recovery_codes ---
    op.create_table(
        "super_admin_mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- 5. Grants for new tables (m369_app + m369_sa_runner both need CRUD) ---
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_mfa_challenges TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_mfa_challenges TO m369_sa_runner")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_sa_runner")

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_used_totp_codes TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_used_totp_codes TO m369_sa_runner")

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_mfa_recovery_codes TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_mfa_recovery_codes TO m369_sa_runner")

    # IMPORTANT: super_admins is a global table (NOT tenant-owned). It has
    # NO row-level security policy in 0001. We do NOT add RLS here either —
    # the application layer enforces access control via the separate
    # m369_sa_runner engine + the get_super_admin_context dependency.


def downgrade() -> None:
    # Drop in reverse-dependency order.
    op.drop_table("super_admin_mfa_recovery_codes")
    op.drop_table("super_admin_used_totp_codes")
    op.drop_table("super_admin_mfa_challenges")
    op.drop_index("ix_super_admins_locked_until", table_name="super_admins")
    op.drop_column("super_admins", "last_failed_login_at")
    op.drop_column("super_admins", "failed_login_attempts")
    op.drop_column("super_admins", "token_version")
