"""add service_completed to notification_type_enum

Revision ID: f1a8c3d9b4e2
Revises: d1e4f2a3b5c6
Create Date: 2026-05-28 01:20:00.000000
"""
from alembic import op

revision = 'f1a8c3d9b4e2'
down_revision = 'd1e4f2a3b5c6'
branch_labels = None
depends_on = None


def upgrade():
    # En PostgreSQL ALTER TYPE ... ADD VALUE no se puede ejecutar fácilmente dentro de una transacción en versiones antiguas,
    # pero alembic y psycopg2 generalmente lo permiten o el usuario puede ejecutarlo con auto-commit si es necesario.
    # Usamos la sintaxis estándar que ya se usó en otras migraciones.
    op.execute("ALTER TYPE notification_type_enum ADD VALUE IF NOT EXISTS 'SERVICE_COMPLETED'")


def downgrade():
    pass  # PostgreSQL no soporta eliminar valores de enums directamente sin recrear el tipo.
