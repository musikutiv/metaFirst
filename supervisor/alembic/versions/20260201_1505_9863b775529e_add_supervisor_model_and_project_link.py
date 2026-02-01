"""add_supervisor_model_and_project_link

Revision ID: 9863b775529e
Revises:
Create Date: 2026-02-01 15:05:33.550976

This migration adds the Supervisor model and links projects to supervisors.
For existing projects, a default "Default Supervisor" is created and all
existing projects are linked to it.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9863b775529e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create supervisors table
    op.create_table('supervisors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supervisors_id'), 'supervisors', ['id'], unique=False)
    op.create_index(op.f('ix_supervisors_name'), 'supervisors', ['name'], unique=True)

    # 2. Insert a default supervisor for existing projects
    op.execute(
        "INSERT INTO supervisors (name, description, is_active) "
        "VALUES ('Default Supervisor', 'Auto-created for existing projects during v0.2 migration', 1)"
    )

    # 3. Add supervisor_id column (nullable initially for SQLite compatibility)
    op.add_column('projects', sa.Column('supervisor_id', sa.Integer(), nullable=True))

    # 4. Backfill existing projects to the default supervisor
    op.execute(
        "UPDATE projects SET supervisor_id = (SELECT id FROM supervisors WHERE name = 'Default Supervisor')"
    )

    # 5. For SQLite, we need to recreate the table to change nullable=True to nullable=False
    # Using batch mode which handles SQLite's limited ALTER TABLE support
    with op.batch_alter_table('projects') as batch_op:
        batch_op.alter_column('supervisor_id', nullable=False)
        batch_op.create_index('ix_projects_supervisor_id', ['supervisor_id'])
        batch_op.create_foreign_key('fk_projects_supervisor_id', 'supervisors', ['supervisor_id'], ['id'])


def downgrade() -> None:
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_constraint('fk_projects_supervisor_id', type_='foreignkey')
        batch_op.drop_index('ix_projects_supervisor_id')
        batch_op.drop_column('supervisor_id')

    op.drop_index(op.f('ix_supervisors_name'), table_name='supervisors')
    op.drop_index(op.f('ix_supervisors_id'), table_name='supervisors')
    op.drop_table('supervisors')
