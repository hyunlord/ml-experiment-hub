"""add project snapshot fields to experiment_configs

Revision ID: 0002abcd0002
Revises: 0001abcd0001
Create Date: 2026-02-16 00:30:00.000000

Adds 7 columns to experiment_configs for capturing the project's git state
at experiment creation time, enabling reproducibility tracking.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "0002abcd0002"
down_revision: Union[str, Sequence[str], None] = "0001abcd0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add project snapshot columns to experiment_configs."""
    with op.batch_alter_table("experiment_configs") as batch_op:
        batch_op.add_column(
            sa.Column("project_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("project_git_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("project_git_branch", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("project_git_commit", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("project_git_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "project_git_dirty", sa.Boolean(), nullable=False, server_default=sa.text("0")
            )
        )
        batch_op.add_column(
            sa.Column("project_python_env", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )


def downgrade() -> None:
    """Remove project snapshot columns from experiment_configs."""
    with op.batch_alter_table("experiment_configs") as batch_op:
        batch_op.drop_column("project_python_env")
        batch_op.drop_column("project_git_dirty")
        batch_op.drop_column("project_git_message")
        batch_op.drop_column("project_git_commit")
        batch_op.drop_column("project_git_branch")
        batch_op.drop_column("project_git_url")
        batch_op.drop_column("project_name")
