"""
Persistence layer (SQLAlchemy models + metadata).

Import `app.db.models` before using metadata (e.g. Alembic) so all tables register.
"""

from app.db.base import Base

__all__ = ["Base"]
