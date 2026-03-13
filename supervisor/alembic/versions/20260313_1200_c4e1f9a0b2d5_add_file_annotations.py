"""Add file_annotations table for one-file to many-samples metadata.

Revision ID: c4e1f9a0b2d5
Revises: 8a7c3d2e1f0b
Create Date: 2026-03-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e1f9a0b2d5'
down_revision: Union[str, None] = '8a7c3d2e1f0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'file_annotations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('raw_data_item_id', sa.Integer(), nullable=False),
        sa.Column('sample_id', sa.Integer(), nullable=True),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('index_json', sa.JSON(), nullable=True),
        sa.Column('value_json', sa.JSON(), nullable=True),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=True,
        ),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by'], ['users.id'],
            name='fk_file_annotations_created_by',
        ),
        sa.ForeignKeyConstraint(
            ['raw_data_item_id'], ['raw_data_items.id'],
            name='fk_file_annotations_raw_data_item_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['sample_id'], ['samples.id'],
            name='fk_file_annotations_sample_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_file_annotations_id',
        'file_annotations',
        ['id'],
        unique=False,
    )
    op.create_index(
        'ix_file_annotations_item_key',
        'file_annotations',
        ['raw_data_item_id', 'key'],
        unique=False,
    )
    op.create_index(
        'ix_file_annotations_item_sample',
        'file_annotations',
        ['raw_data_item_id', 'sample_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_file_annotations_item_sample', table_name='file_annotations')
    op.drop_index('ix_file_annotations_item_key', table_name='file_annotations')
    op.drop_index('ix_file_annotations_id', table_name='file_annotations')
    op.drop_table('file_annotations')
