"""Add sample_id_rule_type and sample_id_regex to projects.

Revision ID: add_sample_id_rule
Revises: add_remediation_tasks
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_sample_id_rule'
down_revision: Union[str, None] = 'add_remediation_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sample ID extraction rule fields to projects
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sample_id_rule_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('sample_id_regex', sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('sample_id_regex')
        batch_op.drop_column('sample_id_rule_type')
