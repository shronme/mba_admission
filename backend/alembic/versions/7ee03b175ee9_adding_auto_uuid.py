"""adding_auto_uuid

Revision ID: 7ee03b175ee9
Revises: c041aced2d1e
Create Date: 2026-03-22 18:49:23.682986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ee03b175ee9'
down_revision: Union[str, Sequence[str], None] = 'c041aced2d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ID_TABLES = [
    "users",
    "admins",
    "candidates",
    "candidate_profiles",
    "ai_runs",
    "audit_events",
    "chat_threads",
    "chat_messages",
    "essay_drafts",
    "essay_reviews",
    "uploaded_files",
    "strategy_decisions",
    "task_items",
    "document_chunks",
]

_TOKEN_TABLES = [
    "user_sessions",
    "candidate_sessions",
]


def upgrade() -> None:
    for table in _ID_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    for table in _TOKEN_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN token SET DEFAULT gen_random_uuid()")


def downgrade() -> None:
    for table in _ID_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")
    for table in _TOKEN_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN token DROP DEFAULT")
