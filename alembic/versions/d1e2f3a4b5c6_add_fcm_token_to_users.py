"""add fcm_token to users

Revision ID: d1e2f3a4b5c6
Revises: bfbd69bfe534
Create Date: 2026-04-25 02:22:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'bfbd69bfe534'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Añadir columna fcm_token a la tabla users
    op.add_column('users', sa.Column('fcm_token', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Eliminar columna fcm_token de la tabla users
    op.drop_column('users', 'fcm_token')
