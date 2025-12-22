from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_users"
down_revision: Union[str, None] = "002_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("firebase_uid"),
    )

    op.create_index("idx_users_email", "users", ["email"])
    op.create_index(
        "idx_users_firebase_uid",
        "users",
        ["firebase_uid"],
        postgresql_where=sa.text("firebase_uid IS NOT NULL"),
    )
    op.create_index(
        "idx_users_organization_id",
        "users",
        ["organization_id"],
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_users_organization_id", table_name="users")
    op.drop_index("idx_users_firebase_uid", table_name="users")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
