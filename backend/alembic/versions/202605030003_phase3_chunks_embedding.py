"""phase3 chunks embedding

Revision ID: 202605030003
Revises: 202605030002
Create Date: 2026-05-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "202605030003"
down_revision: Union[str, None] = "202605030002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("article_chunks", sa.Column(
        "style_category_id",
        postgresql.UUID(as_uuid=True),
        nullable=True,
    ))
    op.add_column("article_chunks", sa.Column(
        "token_count",
        sa.Integer(),
        nullable=True,
        server_default="0",
    ))
    op.add_column("article_chunks", sa.Column(
        "metadata",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ))

    op.execute("""
        UPDATE article_chunks
        SET style_category_id = sa.style_category_id
        FROM source_articles sa
        WHERE article_chunks.source_article_id = sa.id
    """)

    op.alter_column("article_chunks", "style_category_id", nullable=False)
    op.create_foreign_key(
        "fk_article_chunks_style_category_id",
        "article_chunks",
        "style_categories",
        ["style_category_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_article_chunks_style_category_id",
        "article_chunks",
        ["style_category_id"],
    )

    op.execute("""
        CREATE INDEX ix_article_chunks_embedding_cosine
        ON article_chunks USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_article_chunks_embedding_cosine")
    op.drop_index("ix_article_chunks_style_category_id", table_name="article_chunks")
    op.drop_constraint("fk_article_chunks_style_category_id", "article_chunks", type_="foreignkey")
    op.drop_column("article_chunks", "metadata")
    op.drop_column("article_chunks", "token_count")
    op.drop_column("article_chunks", "style_category_id")
