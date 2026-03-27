"""file_status: add REVIEWING enum label (idempotent)

Revision ID: b2f8a1c0d4e5
Revises: 33bb08565a7d
Create Date: 2026-03-27

Earlier revision 33bb08565a7d was applied empty in some environments; this
migration actually extends the PostgreSQL enum. IF NOT EXISTS is safe when
the value was already added by a fixed 33bb08565a7d upgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2f8a1c0d4e5"
down_revision: Union[str, Sequence[str], None] = "33bb08565a7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE file_status ADD VALUE IF NOT EXISTS 'REVIEWING'"))


def downgrade() -> None:
    pass
