"""stage2 article management

Revision ID: 202605030002
Revises: 202605030001
Create Date: 2026-05-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202605030002"
down_revision: Union[str, None] = "202605030001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "style_categories",
        sa.Column("writing_type_hint", sa.String(length=40), nullable=False, server_default="混合风格"),
    )

    op.add_column(
        "source_articles",
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="txt"),
    )
    op.add_column("source_articles", sa.Column("raw_text", sa.Text(), nullable=True))
    op.add_column("source_articles", sa.Column("cleaned_text", sa.Text(), nullable=True))
    op.add_column("source_articles", sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"))

    op.execute(
        """
        UPDATE source_articles
        SET
          raw_text = COALESCE(content, ''),
          cleaned_text = COALESCE(content, ''),
          word_count = char_length(COALESCE(content, '')),
          status = CASE WHEN status = 'uploaded' THEN 'completed' ELSE status END,
          source_type = CASE
            WHEN lower(original_filename) LIKE '%.md' THEN 'markdown'
            WHEN lower(original_filename) LIKE '%.docx' THEN 'docx'
            ELSE 'txt'
          END
        """
    )

    op.alter_column("source_articles", "raw_text", nullable=False)
    op.alter_column("source_articles", "cleaned_text", nullable=False)
    op.drop_column("source_articles", "content")


def downgrade() -> None:
    op.add_column("source_articles", sa.Column("content", sa.Text(), nullable=True))
    op.execute("UPDATE source_articles SET content = COALESCE(cleaned_text, raw_text, '')")
    op.alter_column("source_articles", "content", nullable=False)
    op.drop_column("source_articles", "word_count")
    op.drop_column("source_articles", "cleaned_text")
    op.drop_column("source_articles", "raw_text")
    op.drop_column("source_articles", "source_type")
    op.drop_column("style_categories", "writing_type_hint")

