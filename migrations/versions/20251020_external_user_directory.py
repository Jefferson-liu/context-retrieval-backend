"""transition to external user directory"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251020_external_user_directory"
down_revision = "20251015_document_project_summaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_products",
        sa.Column("owner_external_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_user_products_owner_external_id",
        "user_products",
        ["owner_external_id"],
    )

    op.execute(
        """
        UPDATE user_products AS up
        SET owner_external_id = au.external_id
        FROM app_users AS au
        WHERE up.user_id = au.id
        """
    )

    op.alter_column(
        "user_products",
        "owner_external_id",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.drop_constraint("uq_user_product_external", "user_products", type_="unique")
    op.create_unique_constraint(
        "uq_user_product_owner_external",
        "user_products",
        ["tenant_id", "owner_external_id", "external_id"],
    )

    op.drop_constraint("user_products_user_id_fkey", "user_products", type_="foreignkey")
    op.drop_index("ix_user_products_user_id", table_name="user_products")
    op.drop_column("user_products", "user_id")

    op.drop_table("app_users")


def downgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "project_id", name="uq_app_user_project"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_app_user_external_id"),
    )
    op.create_index("ix_app_users_tenant_id", "app_users", ["tenant_id"])
    op.create_index("ix_app_users_project_id", "app_users", ["project_id"])
    op.create_index("ix_app_users_external_id", "app_users", ["external_id"])

    op.add_column(
        "user_products",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_user_products_user_id", "user_products", ["user_id"])
    op.create_foreign_key(
        "user_products_user_id_fkey",
        "user_products",
        "app_users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index("ix_user_products_owner_external_id", table_name="user_products")
    op.drop_constraint("uq_user_product_owner_external", "user_products", type_="unique")

    op.execute(
        """
        INSERT INTO app_users (tenant_id, project_id, external_id, name, created_at, updated_at)
        SELECT DISTINCT tenant_id, project_id, owner_external_id, NULL, NOW(), NOW()
        FROM user_products
        WHERE owner_external_id IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE user_products AS up
        SET user_id = au.id
        FROM app_users AS au
        WHERE up.tenant_id = au.tenant_id
          AND up.project_id = au.project_id
          AND up.owner_external_id = au.external_id
        """
    )

    op.alter_column(
        "user_products",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_user_product_external",
        "user_products",
        ["tenant_id", "user_id", "external_id"],
    )

    op.drop_column("user_products", "owner_external_id")
