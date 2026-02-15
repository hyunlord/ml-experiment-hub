"""add_servers_and_system_history

Revision ID: 430b08747772
Revises: c2fe5ac0d414
Create Date: 2026-02-15 18:17:29.925907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '430b08747772'
down_revision: Union[str, Sequence[str], None] = 'c2fe5ac0d414'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add servers and system_history tables."""
    op.create_table('servers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('host', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.Column('auth_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('api_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_local', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('servers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_servers_name'), ['name'], unique=False)

    op.create_table('system_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('gpu_util', sa.Float(), nullable=True),
    sa.Column('gpu_memory_percent', sa.Float(), nullable=True),
    sa.Column('gpu_temperature', sa.Float(), nullable=True),
    sa.Column('cpu_percent', sa.Float(), nullable=True),
    sa.Column('ram_percent', sa.Float(), nullable=True),
    sa.Column('disk_percent', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('system_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_system_history_server_id'), ['server_id'], unique=False)
        batch_op.create_index('ix_system_history_ts', ['timestamp'], unique=False)


def downgrade() -> None:
    """Remove servers and system_history tables."""
    with op.batch_alter_table('system_history', schema=None) as batch_op:
        batch_op.drop_index('ix_system_history_ts')
        batch_op.drop_index(batch_op.f('ix_system_history_server_id'))

    op.drop_table('system_history')
    with op.batch_alter_table('servers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_servers_name'))

    op.drop_table('servers')
