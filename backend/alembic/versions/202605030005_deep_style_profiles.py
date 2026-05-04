"""deep style profiles

Revision ID: 202605030005
Revises: 202605030004
Create Date: 2026-05-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202605030005"
down_revision: Union[str, None] = "202605030004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEEP_PROFILE_COLUMNS = [
    "syntax_fingerprint",
    "punctuation_fingerprint",
    "preferred_words",
    "structure_template",
    "style_constraints",
]


def upgrade() -> None:
    for column_name in DEEP_PROFILE_COLUMNS:
        op.add_column("style_profiles", sa.Column(column_name, sa.Text(), nullable=True))


def downgrade() -> None:
    for column_name in reversed(DEEP_PROFILE_COLUMNS):
        op.drop_column("style_profiles", column_name)
