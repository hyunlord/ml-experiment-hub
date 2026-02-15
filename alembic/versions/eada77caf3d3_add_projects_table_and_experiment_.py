"""add_projects_table_and_experiment_project_fk

Revision ID: eada77caf3d3
Revises: 430b08747772
Create Date: 2026-02-15 19:07:40.683516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'eada77caf3d3'
down_revision: Union[str, Sequence[str], None] = '430b08747772'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add projects table and project_id FK on experiment_configs."""
    op.create_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('git_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('project_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('train_command_template', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('eval_command_template', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('config_dir', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('config_format', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('checkpoint_dir', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('python_env', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('env_path', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('status', sa.Enum('REGISTERED', 'SCANNING', 'READY', 'ERROR', name='projectstatus'), nullable=False),
    sa.Column('detected_configs', sa.JSON(), nullable=True),
    sa.Column('detected_scripts', sa.JSON(), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_projects_name'), ['name'], unique=False)

    with op.batch_alter_table('experiment_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('project_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_experiment_configs_project_id'), ['project_id'], unique=False)
        batch_op.create_foreign_key('fk_experiment_configs_project_id', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    """Remove projects table and project_id FK."""
    with op.batch_alter_table('experiment_configs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_experiment_configs_project_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_experiment_configs_project_id'))
        batch_op.drop_column('project_id')

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_name'))

    op.drop_table('projects')
