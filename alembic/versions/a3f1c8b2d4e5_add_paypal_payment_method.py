"""add paypal payment method

Revision ID: a3f1c8b2d4e5
Revises: 987b6d3c945b
Create Date: 2026-04-25 00:00:00.000000
"""
from alembic import op

revision = 'a3f1c8b2d4e5'
down_revision = '987b6d3c945b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE payment_method_enum ADD VALUE IF NOT EXISTS 'paypal'")


def downgrade():
    pass  # PostgreSQL no soporta eliminar valores de enums
