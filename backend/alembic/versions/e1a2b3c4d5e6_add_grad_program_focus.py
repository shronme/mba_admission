"""candidate_profiles.grad_program_focus for intake program detail

Revision ID: e1a2b3c4d5e6
Revises: d4e8f0a1b2c3
Create Date: 2026-03-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d4e8f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("grad_program_focus", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "grad_program_focus")
