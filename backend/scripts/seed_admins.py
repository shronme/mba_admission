#!/usr/bin/env python3
"""
Seed one or more admin users (User + Admin rows) into the database.

Usage (from `backend/`):

  export PYTHONPATH=.
  export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mba_admissions

  # Seed defaults (admin@example.com / Admin User)
  python scripts/seed_admins.py

  # Seed specific email + name pairs
  python scripts/seed_admins.py admin@yourdomain.com "Your Name" advisor@firm.com "Jane Doe"

Requires schema applied: `alembic upgrade head`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.enums import UserRole
from app.db.models.admin import Admin
from app.db.models.user import User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("seed_admins")

DEFAULT_ADMINS: list[tuple[str, str]] = [
    ("admin@example.com", "Admin User"),
]


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    args = sys.argv[1:]
    if args:
        if len(args) % 2 != 0:
            raise SystemExit("Args must be pairs: email name email name …")
        admins_to_seed = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    else:
        admins_to_seed = DEFAULT_ADMINS

    logger.info("Seeding %d admin account(s)", len(admins_to_seed))

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            for idx, (email, full_name) in enumerate(admins_to_seed, start=1):
                email_norm = email.strip().lower()
                logger.info("[%d/%d] processing %s", idx, len(admins_to_seed), email_norm)

                existing_user = (
                    await session.execute(select(User).where(User.email == email_norm))
                ).scalar_one_or_none()

                if existing_user is not None:
                    if existing_user.role != UserRole.ADMIN:
                        logger.warning(
                            "user exists but is not admin email=%s role=%s — skipping",
                            email_norm,
                            existing_user.role,
                        )
                    else:
                        logger.info("admin already exists email=%s user_id=%s", email_norm, existing_user.id)
                    continue

                new_user = User(
                    email=email_norm,
                    full_name=full_name.strip(),
                    role=UserRole.ADMIN,
                )
                session.add(new_user)
                await session.flush()

                admin_row = Admin(user_id=new_user.id)
                session.add(admin_row)
                await session.flush()

                logger.info(
                    "created admin email=%s user_id=%s admin_id=%s",
                    email_norm,
                    new_user.id,
                    admin_row.id,
                )

            await session.commit()
            logger.info("done")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
