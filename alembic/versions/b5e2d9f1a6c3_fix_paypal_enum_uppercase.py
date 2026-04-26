"""fix paypal enum uppercase

Revision ID: b5e2d9f1a6c3
Revises: a3f1c8b2d4e5
Create Date: 2026-04-25 00:01:00.000000
"""
from alembic import op

revision = 'b5e2d9f1a6c3'
down_revision = 'a3f1c8b2d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE payment_method_enum ADD VALUE IF NOT EXISTS 'PAYPAL'")


def downgrade():
    pass  # PostgreSQL no soporta eliminar valores de enums
