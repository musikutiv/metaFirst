"""Add index on sample_field_values.sample_id for eager loading performance.

Revision ID: 8a7c3d2e1f0b
Revises: 20260202_1200_add_sample_id_rule_to_projects
Create Date: 2026-02-02 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a7c3d2e1f0b'
down_revision = '20260202_1200_add_sample_id_rule_to_projects'
branch_labels = None
depends_on = None


def upgrade():
    # Add index on sample_field_values.sample_id for faster eager loading
    op.create_index('ix_field_values_sample', 'sample_field_values', ['sample_id'], unique=False)


def downgrade():
    op.drop_index('ix_field_values_sample', table_name='sample_field_values')
