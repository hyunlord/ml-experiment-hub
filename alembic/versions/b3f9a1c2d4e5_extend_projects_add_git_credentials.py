"""extend_projects_add_git_credentials

Revision ID: b3f9a1c2d4e5
Revises: eada77caf3d3
Create Date: 2026-02-15 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b3f9a1c2d4e5"
down_revision: Union[str, Sequence[str], None] = "eada77caf3d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add git_credentials table and new columns to projects."""
    # Create git_credentials table
    op.create_table(
        "git_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("git_credentials", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_git_credentials_name"), ["name"], unique=False)

    # Add new columns to projects
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_type",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="local",
            )
        )
        batch_op.add_column(
            sa.Column("git_branch", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(sa.Column("git_token_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("template_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("template_task", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("template_model", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_projects_git_token_id", "git_credentials", ["git_token_id"], ["id"]
        )


def downgrade() -> None:
    """Remove new project columns and git_credentials table."""
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint("fk_projects_git_token_id", type_="foreignkey")
        batch_op.drop_column("template_model")
        batch_op.drop_column("template_task")
        batch_op.drop_column("template_type")
        batch_op.drop_column("git_token_id")
        batch_op.drop_column("git_branch")
        batch_op.drop_column("source_type")

    with op.batch_alter_table("git_credentials", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_git_credentials_name"))

    op.drop_table("git_credentials")
