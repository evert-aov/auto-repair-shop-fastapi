"""add paypal payout fields

Revision ID: c7f3a1e8d2b4
Revises: b5e2d9f1a6c3
Create Date: 2026-04-26 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'c7f3a1e8d2b4'
down_revision = 'b5e2d9f1a6c3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('workshops', sa.Column('paypal_email', sa.String(255), nullable=True))
    op.add_column('payments', sa.Column('payout_id', sa.String(200), nullable=True))
    op.add_column('payments', sa.Column('payout_status', sa.String(30), nullable=True))


def downgrade():
    op.drop_column('workshops', 'paypal_email')
    op.drop_column('payments', 'payout_id')
    op.drop_column('payments', 'payout_status')
