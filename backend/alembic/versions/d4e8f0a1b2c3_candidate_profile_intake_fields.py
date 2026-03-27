"""candidate_profiles: intake demographics (country, DOB, intake flag)

Revision ID: d4e8f0a1b2c3
Revises: b2f8a1c0d4e5
Create Date: 2026-03-27

Existing profile rows are marked intake_form_completed=true so current users
are not blocked; new profiles default to false via the application model.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e8f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "b2f8a1c0d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("country_of_residence", sa.String(length=128), nullable=True),
    )
    op.add_column("candidate_profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "intake_form_completed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute(sa.text("UPDATE candidate_profiles SET intake_form_completed = true"))
    op.alter_column("candidate_profiles", "intake_form_completed", server_default=None)


def downgrade() -> None:
    op.drop_column("candidate_profiles", "intake_form_completed")
    op.drop_column("candidate_profiles", "date_of_birth")
    op.drop_column("candidate_profiles", "country_of_residence")
