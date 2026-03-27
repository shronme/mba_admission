"""add file_status reviewing

Revision ID: 33bb08565a7d
Revises: 7ee03b175ee9
Create Date: 2026-03-27 13:33:04.074125

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '33bb08565a7d'
down_revision: Union[str, Sequence[str], None] = '7ee03b175ee9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum change lives in b2f8a1c0d4e5 (autogenerate left this empty).
    pass


def downgrade() -> None:
    pass
