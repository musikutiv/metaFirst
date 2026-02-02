"""Add retention_days, embargo_until to RDMP and remediation_tasks table.

Revision ID: add_remediation_tasks
Revises: add_sample_visibility
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_remediation_tasks'
down_revision: Union[str, None] = 'add_sample_visibility'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add retention_days and embargo_until to rdmp_versions
    with op.batch_alter_table('rdmp_versions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('retention_days', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('embargo_until', sa.DateTime(timezone=True), nullable=True))

    # Add enable_automated_execution flag to supervisors
    with op.batch_alter_table('supervisors', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('enable_automated_execution', sa.Boolean(), nullable=False, server_default='0')
        )

    # Create remediation_tasks table
    op.create_table(
        'remediation_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('supervisor_id', sa.Integer(), sa.ForeignKey('supervisors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sample_id', sa.Integer(), sa.ForeignKey('samples.id', ondelete='CASCADE'), nullable=True),
        sa.Column('issue_type', sa.String(50), nullable=False),  # retention_exceeded, embargo_active
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),  # PENDING, ACKED, APPROVED, DISMISSED, EXECUTED
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),  # Additional context
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('acked_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('acked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Index('ix_remediation_tasks_supervisor', 'supervisor_id'),
        sa.Index('ix_remediation_tasks_project', 'project_id'),
        sa.Index('ix_remediation_tasks_status', 'status'),
    )


def downgrade() -> None:
    op.drop_table('remediation_tasks')

    with op.batch_alter_table('supervisors', schema=None) as batch_op:
        batch_op.drop_column('enable_automated_execution')

    with op.batch_alter_table('rdmp_versions', schema=None) as batch_op:
        batch_op.drop_column('embargo_until')
        batch_op.drop_column('retention_days')
