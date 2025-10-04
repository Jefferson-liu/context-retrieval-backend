"""Multi-tenant core schema upgrade

Revision ID: 20251003_multi_tenant_core
Revises: 
Create Date: 2025-10-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251003_multi_tenant_core"
down_revision = None
branch_labels = None
depends_on = None


DEFAULT_TENANT_SLUG = "default"
DEFAULT_TENANT_NAME = "Default Tenant"
DEFAULT_PROJECT_SLUG = "default"
DEFAULT_PROJECT_NAME = "Default Project"
DEFAULT_USER_ID = "demo-user"
DEFAULT_USER_ROLE = "admin"


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_project_tenant_slug"),
    )

    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=False)

    op.create_table(
        "user_project_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "project_id", name="uq_user_project_role"),
    )

    op.create_index("ix_user_project_roles_user_id", "user_project_roles", ["user_id"])
    op.create_index("ix_user_project_roles_tenant_id", "user_project_roles", ["tenant_id"])
    op.create_index("ix_user_project_roles_project_id", "user_project_roles", ["project_id"])

    tenant_id = conn.execute(
        sa.text(
            """
            INSERT INTO tenants (name, slug)
            VALUES (:name, :slug)
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """
        ),
        {"name": DEFAULT_TENANT_NAME, "slug": DEFAULT_TENANT_SLUG},
    ).scalar_one()

    project_id = conn.execute(
        sa.text(
            """
            INSERT INTO projects (tenant_id, name, slug, status)
            VALUES (:tenant_id, :name, :slug, 'active')
            ON CONFLICT (tenant_id, slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """
        ),
        {
            "tenant_id": tenant_id,
            "name": DEFAULT_PROJECT_NAME,
            "slug": DEFAULT_PROJECT_SLUG,
        },
    ).scalar_one()

    conn.execute(
        sa.text(
            """
            INSERT INTO user_project_roles (user_id, tenant_id, project_id, role)
            VALUES (:user_id, :tenant_id, :project_id, :role)
            ON CONFLICT (user_id, project_id) DO NOTHING
            """
        ),
        {
            "user_id": DEFAULT_USER_ID,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "role": DEFAULT_USER_ROLE,
        },
    )

    # uploaded_documents
    op.add_column("uploaded_documents", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("uploaded_documents", sa.Column("project_id", sa.Integer(), nullable=True))
    op.add_column("uploaded_documents", sa.Column("created_by_user_id", sa.String(), nullable=True))
    op.create_index("ix_uploaded_documents_tenant_id", "uploaded_documents", ["tenant_id"])
    op.create_index("ix_uploaded_documents_project_id", "uploaded_documents", ["project_id"])
    op.create_foreign_key(
        "fk_uploaded_documents_tenant_id",
        "uploaded_documents",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_uploaded_documents_project_id",
        "uploaded_documents",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    conn.execute(
        sa.text(
            """
            UPDATE uploaded_documents
            SET tenant_id = :tenant_id,
                project_id = :project_id,
                created_by_user_id = COALESCE(created_by_user_id, :user_id)
            """
        ),
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "user_id": DEFAULT_USER_ID,
        },
    )

    op.alter_column(
        "uploaded_documents",
        "tenant_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "uploaded_documents",
        "project_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "uploaded_documents",
        "created_by_user_id",
        existing_type=sa.String(),
        nullable=False,
    )

    # chunks
    op.add_column("chunks", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("project_id", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("created_by_user_id", sa.String(), nullable=True))
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_project_id", "chunks", ["project_id"])
    op.create_foreign_key(
        "fk_chunks_tenant_id",
        "chunks",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_chunks_project_id",
        "chunks",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    conn.execute(
        sa.text(
            """
            UPDATE chunks AS c
            SET tenant_id = d.tenant_id,
                project_id = d.project_id,
                created_by_user_id = d.created_by_user_id
            FROM uploaded_documents AS d
            WHERE c.doc_id = d.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE chunks
            SET tenant_id = COALESCE(tenant_id, :tenant_id),
                project_id = COALESCE(project_id, :project_id),
                created_by_user_id = COALESCE(created_by_user_id, :user_id)
            """
        ),
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "user_id": DEFAULT_USER_ID,
        },
    )

    op.alter_column("chunks", "tenant_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("chunks", "project_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("chunks", "created_by_user_id", existing_type=sa.String(), nullable=False)

    # embeddings
    op.add_column("embeddings", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("embeddings", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index("ix_embeddings_tenant_id", "embeddings", ["tenant_id"])
    op.create_index("ix_embeddings_project_id", "embeddings", ["project_id"])
    op.create_foreign_key(
        "fk_embeddings_tenant_id",
        "embeddings",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_embeddings_project_id",
        "embeddings",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    conn.execute(
        sa.text(
            """
            UPDATE embeddings AS e
            SET tenant_id = c.tenant_id,
                project_id = c.project_id
            FROM chunks AS c
            WHERE e.chunk_id = c.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE embeddings
            SET tenant_id = COALESCE(tenant_id, :tenant_id),
                project_id = COALESCE(project_id, :project_id)
            """
        ),
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
        },
    )

    op.alter_column("embeddings", "tenant_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("embeddings", "project_id", existing_type=sa.Integer(), nullable=False)

    # queries
    op.add_column("queries", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("queries", sa.Column("project_id", sa.Integer(), nullable=True))
    op.add_column("queries", sa.Column("user_id", sa.String(), nullable=True))
    op.create_index("ix_queries_tenant_id", "queries", ["tenant_id"])
    op.create_index("ix_queries_project_id", "queries", ["project_id"])
    op.create_foreign_key(
        "fk_queries_tenant_id",
        "queries",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_queries_project_id",
        "queries",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    conn.execute(
        sa.text(
            """
            UPDATE queries
            SET tenant_id = :tenant_id,
                project_id = :project_id,
                user_id = COALESCE(user_id, :user_id)
            """
        ),
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "user_id": DEFAULT_USER_ID,
        },
    )

    op.alter_column("queries", "tenant_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("queries", "project_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("queries", "user_id", existing_type=sa.String(), nullable=False)

    # responses
    op.add_column("responses", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("responses", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index("ix_responses_tenant_id", "responses", ["tenant_id"])
    op.create_index("ix_responses_project_id", "responses", ["project_id"])
    op.create_foreign_key(
        "fk_responses_tenant_id",
        "responses",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_responses_project_id",
        "responses",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    conn.execute(
        sa.text(
            """
            UPDATE responses AS r
            SET tenant_id = q.tenant_id,
                project_id = q.project_id
            FROM queries AS q
            WHERE r.query_id = q.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE responses
            SET tenant_id = COALESCE(tenant_id, :tenant_id),
                project_id = COALESCE(project_id, :project_id)
            """
        ),
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
        },
    )

    op.alter_column("responses", "tenant_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("responses", "project_id", existing_type=sa.Integer(), nullable=False)

    # sources
    op.add_column("sources", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index("ix_sources_tenant_id", "sources", ["tenant_id"])
    op.create_index("ix_sources_project_id", "sources", ["project_id"])
    op.create_foreign_key(
        "fk_sources_tenant_id",
        "sources",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_sources_project_id",
        "sources",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    conn.execute(
        sa.text(
            """
            UPDATE sources AS s
            SET tenant_id = r.tenant_id,
                project_id = r.project_id
            FROM responses AS r
            WHERE s.response_id = r.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE sources
            SET tenant_id = COALESCE(tenant_id, :tenant_id),
                project_id = COALESCE(project_id, :project_id)
            """
        ),
        {
            "tenant_id": tenant_id,
            "project_id": project_id,
        },
    )

    op.alter_column("sources", "tenant_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("sources", "project_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # sources
    op.alter_column("sources", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("sources", "project_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("fk_sources_tenant_id", "sources", type_="foreignkey")
    op.drop_constraint("fk_sources_project_id", "sources", type_="foreignkey")
    op.drop_index("ix_sources_tenant_id", table_name="sources")
    op.drop_index("ix_sources_project_id", table_name="sources")
    op.drop_column("sources", "tenant_id")
    op.drop_column("sources", "project_id")

    # responses
    op.alter_column("responses", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("responses", "project_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("fk_responses_tenant_id", "responses", type_="foreignkey")
    op.drop_constraint("fk_responses_project_id", "responses", type_="foreignkey")
    op.drop_index("ix_responses_tenant_id", table_name="responses")
    op.drop_index("ix_responses_project_id", table_name="responses")
    op.drop_column("responses", "tenant_id")
    op.drop_column("responses", "project_id")

    # queries
    op.alter_column("queries", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("queries", "project_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("queries", "user_id", existing_type=sa.String(), nullable=True)
    op.drop_constraint("fk_queries_tenant_id", "queries", type_="foreignkey")
    op.drop_constraint("fk_queries_project_id", "queries", type_="foreignkey")
    op.drop_index("ix_queries_tenant_id", table_name="queries")
    op.drop_index("ix_queries_project_id", table_name="queries")
    op.drop_column("queries", "tenant_id")
    op.drop_column("queries", "project_id")
    op.drop_column("queries", "user_id")

    # embeddings
    op.alter_column("embeddings", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("embeddings", "project_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("fk_embeddings_tenant_id", "embeddings", type_="foreignkey")
    op.drop_constraint("fk_embeddings_project_id", "embeddings", type_="foreignkey")
    op.drop_index("ix_embeddings_tenant_id", table_name="embeddings")
    op.drop_index("ix_embeddings_project_id", table_name="embeddings")
    op.drop_column("embeddings", "tenant_id")
    op.drop_column("embeddings", "project_id")

    # chunks
    op.alter_column("chunks", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("chunks", "project_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("chunks", "created_by_user_id", existing_type=sa.String(), nullable=True)
    op.drop_constraint("fk_chunks_tenant_id", "chunks", type_="foreignkey")
    op.drop_constraint("fk_chunks_project_id", "chunks", type_="foreignkey")
    op.drop_index("ix_chunks_tenant_id", table_name="chunks")
    op.drop_index("ix_chunks_project_id", table_name="chunks")
    op.drop_column("chunks", "tenant_id")
    op.drop_column("chunks", "project_id")
    op.drop_column("chunks", "created_by_user_id")

    # uploaded_documents
    op.alter_column("uploaded_documents", "tenant_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("uploaded_documents", "project_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("uploaded_documents", "created_by_user_id", existing_type=sa.String(), nullable=True)
    op.drop_constraint("fk_uploaded_documents_tenant_id", "uploaded_documents", type_="foreignkey")
    op.drop_constraint("fk_uploaded_documents_project_id", "uploaded_documents", type_="foreignkey")
    op.drop_index("ix_uploaded_documents_tenant_id", table_name="uploaded_documents")
    op.drop_index("ix_uploaded_documents_project_id", table_name="uploaded_documents")
    op.drop_column("uploaded_documents", "tenant_id")
    op.drop_column("uploaded_documents", "project_id")
    op.drop_column("uploaded_documents", "created_by_user_id")

    # user_project_roles
    op.drop_index("ix_user_project_roles_user_id", table_name="user_project_roles")
    op.drop_index("ix_user_project_roles_tenant_id", table_name="user_project_roles")
    op.drop_index("ix_user_project_roles_project_id", table_name="user_project_roles")
    op.drop_table("user_project_roles")

    # projects
    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")

    # tenants
    op.drop_table("tenants")
