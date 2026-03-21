"""add_stage_to_candidate

Revision ID: e3a9ca9bb06e
Revises: cc961c750d3d
Create Date: 2026-03-21 13:24:06.652597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3a9ca9bb06e'
down_revision: Union[str, Sequence[str], None] = 'cc961c750d3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


candidate_stage = sa.Enum(
    'INTAKE', 'DIAGNOSIS', 'PROGRAM_RESEARCH', 'STRATEGY', 'NARRATIVE',
    'SCHOOL_LIST', 'APPLICATION_WORK', 'ITERATION', 'INTERVIEW_PREPARATION',
    name='candidate_stage',
)


def upgrade() -> None:
    candidate_stage.create(op.get_bind(), checkfirst=True)
    op.add_column('candidates', sa.Column(
        'stage',
        candidate_stage,
        nullable=False,
        server_default='INTAKE',
    ))
    op.alter_column('candidates', 'stage', server_default=None)


def downgrade() -> None:
    op.drop_column('candidates', 'stage')
    candidate_stage.drop(op.get_bind(), checkfirst=True)
