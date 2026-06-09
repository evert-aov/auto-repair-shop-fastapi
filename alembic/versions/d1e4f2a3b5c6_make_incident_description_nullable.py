"""make incident description nullable

Revision ID: d1e4f2a3b5c6
Revises: c7f3a1e8d2b4
Create Date: 2026-05-04 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'd1e4f2a3b5c6'
down_revision = 'c7f3a1e8d2b4'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('incidents', 'description', nullable=True)


def downgrade():
    op.execute("UPDATE incidents SET description = '' WHERE description IS NULL")
    op.alter_column('incidents', 'description', nullable=False)
