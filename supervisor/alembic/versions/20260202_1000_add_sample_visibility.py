"""Add visibility column to samples table.

Revision ID: add_sample_visibility
Revises: 427a6cc9186d
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_sample_visibility'
down_revision: Union[str, None] = '427a6cc9186d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add visibility column with default PRIVATE
    # Using batch mode for SQLite compatibility
    with op.batch_alter_table('samples', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'visibility',
                sa.Enum('PRIVATE', 'INSTITUTION', 'PUBLIC', name='metadatavisibility'),
                nullable=False,
                server_default='PRIVATE'
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('samples', schema=None) as batch_op:
        batch_op.drop_column('visibility')
