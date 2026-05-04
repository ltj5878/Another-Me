"""style profiles

Revision ID: 202605030004
Revises: 202605030003
Create Date: 2026-05-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202605030004"
down_revision: Union[str, None] = "202605030003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROFILE_TEXT_COLUMNS = [
    "summary",
    "sentence_style",
    "structure_style",
    "rhetoric_style",
    "imagery_style",
    "vocabulary_style",
    "tone_style",
    "argument_style",
    "opening_style",
    "ending_style",
    "do_rules",
    "dont_rules",
    "prompt_instruction",
]


def upgrade() -> None:
    for column_name in PROFILE_TEXT_COLUMNS:
        op.add_column("style_profiles", sa.Column(column_name, sa.Text(), nullable=True))

    op.add_column(
        "style_profiles",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("style_profiles", "version")
    for column_name in reversed(PROFILE_TEXT_COLUMNS):
        op.drop_column("style_profiles", column_name)
