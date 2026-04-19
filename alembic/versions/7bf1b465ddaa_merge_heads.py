"""merge_heads

Revision ID: 7bf1b465ddaa
Revises: 57ad3162a7a3, a9c818d49532
Create Date: 2026-04-18 12:24:18.198812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bf1b465ddaa'
down_revision: Union[str, None] = ('57ad3162a7a3', 'a9c818d49532')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
