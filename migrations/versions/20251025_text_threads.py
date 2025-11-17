"""Add tables for storing raw text threads and messages

Revision ID: 20251025_text_threads
Revises: 20251020_external_user_directory
Create Date: 2025-10-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251025_text_threads"
down_revision = "20251020_external_user_directory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "text_threads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.String(length=255), nullable=False),
        sa.Column("user_product_id", sa.Integer(), nullable=True),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("external_thread_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("thread_text", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("thread_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("thread_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_product_id"], ["user_products.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "tenant_id",
            "project_id",
            "source_system",
            "external_thread_id",
            name="uq_text_threads_source_external",
        ),
    )
    op.create_index("ix_text_threads_tenant_id", "text_threads", ["tenant_id"])
    op.create_index("ix_text_threads_project_id", "text_threads", ["project_id"])
    op.create_index("ix_text_threads_owner_user_id", "text_threads", ["owner_user_id"])
    op.create_index("ix_text_threads_user_product_id", "text_threads", ["user_product_id"])
    op.create_index("ix_text_threads_external_thread_id", "text_threads", ["external_thread_id"])

    op.create_table(
        "text_thread_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("sender_user_id", sa.String(length=255), nullable=True),
        sa.Column("sender_display_name", sa.String(length=255), nullable=True),
        sa.Column("sender_type", sa.String(length=50), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["text_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("thread_id", "position", name="uq_text_thread_messages_position"),
    )
    op.create_index("ix_text_thread_messages_thread_id", "text_thread_messages", ["thread_id"])
    op.create_index("ix_text_thread_messages_tenant_id", "text_thread_messages", ["tenant_id"])
    op.create_index("ix_text_thread_messages_project_id", "text_thread_messages", ["project_id"])
    op.create_index(
        "ix_text_thread_messages_sender_user_id",
        "text_thread_messages",
        ["sender_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_text_thread_messages_sender_user_id", table_name="text_thread_messages")
    op.drop_index("ix_text_thread_messages_project_id", table_name="text_thread_messages")
    op.drop_index("ix_text_thread_messages_tenant_id", table_name="text_thread_messages")
    op.drop_index("ix_text_thread_messages_thread_id", table_name="text_thread_messages")
    op.drop_table("text_thread_messages")

    op.drop_index("ix_text_threads_external_thread_id", table_name="text_threads")
    op.drop_index("ix_text_threads_user_product_id", table_name="text_threads")
    op.drop_index("ix_text_threads_owner_user_id", table_name="text_threads")
    op.drop_index("ix_text_threads_project_id", table_name="text_threads")
    op.drop_index("ix_text_threads_tenant_id", table_name="text_threads")
    op.drop_table("text_threads")
