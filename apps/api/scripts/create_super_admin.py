"""CLI script: create the first Super Admin."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import session_scope  # noqa: E402
from app.models import SuperAdmin  # noqa: E402
from app.security import hash_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first M369 Super Admin")
    parser.add_argument("--email", required=True, help="Super Admin email (lowercase)")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--password", required=True, help="Password (min 12 chars)")
    parser.add_argument(
        "--allow-multiple",
        action="store_true",
        help="Allow creating a second Super Admin",
    )
    args = parser.parse_args()

    if len(args.password) < 12:
        print("Password must be at least 12 characters", file=sys.stderr)
        return 2

    with session_scope() as db:
        existing = db.scalar(select(SuperAdmin).limit(1))
        if existing is not None and not args.allow_multiple:
            print(
                f"A Super Admin already exists ({existing.email}). "
                "Pass --allow-multiple to create another.",
                file=sys.stderr,
            )
            return 1

        admin = SuperAdmin(
            email=args.email.lower(),
            name=args.name,
            password_hash=hash_password(args.password),
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"Created Super Admin: id={admin.id} email={admin.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
