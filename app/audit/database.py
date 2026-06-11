import os
import uuid
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("audit.db")

AUDIT_DATABASE_URL = os.getenv("AUDIT_DATABASE_URL")

if not AUDIT_DATABASE_URL:
    logger.warning("AUDIT_DATABASE_URL not set, using main DATABASE_URL as fallback")
    AUDIT_DATABASE_URL = os.getenv("DATABASE_URL")

audit_engine = create_engine(AUDIT_DATABASE_URL, pool_pre_ping=True)
AuditSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=audit_engine)
AuditBase = declarative_base()

_AUDIT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workshop_id       UUID,
    user_id           UUID,
    user_email        VARCHAR(255),
    user_name         VARCHAR(255),
    action_type       VARCHAR(50)  NOT NULL,
    resource_type     VARCHAR(100) NOT NULL,
    resource_id       VARCHAR(100),
    resource_name     VARCHAR(255),
    ip_address        VARCHAR(45),
    user_agent        TEXT,
    request_method    VARCHAR(10),
    request_path      VARCHAR(500),
    request_body      BYTEA,
    changes_before    BYTEA,
    changes_after     BYTEA,
    response_status   INTEGER,
    error_message     TEXT,
    integrity_hash    VARCHAR(64),
    client_time       TIMESTAMPTZ,
    session_id        UUID,
    severity          VARCHAR(50)  DEFAULT 'INFO',
    execution_time_ms BIGINT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE audit_log IS 'Bitacora de auditoria forense con cifrado AES-256-GCM y verificacion HMAC. Acceso exclusivo para ADMIN.';
COMMENT ON COLUMN audit_log.request_body IS 'Cifrado AES-256-GCM: body del request sanitizado (passwords enmascaradas)';
COMMENT ON COLUMN audit_log.changes_before IS 'Cifrado AES-256-GCM: estado anterior del recurso (JSON)';
COMMENT ON COLUMN audit_log.changes_after IS 'Cifrado AES-256-GCM: estado nuevo del recurso (JSON)';
COMMENT ON COLUMN audit_log.integrity_hash IS 'HMAC-SHA256: hash de integridad para detectar manipulacion de logs';
COMMENT ON COLUMN audit_log.client_time IS 'Fecha y hora capturada desde el dispositivo cliente';
COMMENT ON COLUMN audit_log.session_id IS 'Identificador de sesion o correlacion de la transaccion';
COMMENT ON COLUMN audit_log.severity IS 'Severidad de la accion: INFO, WARNING, CRITICAL';
COMMENT ON COLUMN audit_log.execution_time_ms IS 'Tiempo de ejecucion de la accion en milisegundos';

CREATE INDEX IF NOT EXISTS idx_audit_workshop_timestamp ON audit_log(workshop_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user_timestamp    ON audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource          ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_action_type       ON audit_log(action_type);
CREATE INDEX IF NOT EXISTS idx_audit_ip                ON audit_log(ip_address);
CREATE INDEX IF NOT EXISTS idx_audit_created_at        ON audit_log(created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_hash       ON audit_log(integrity_hash);
"""


def get_audit_db():
    db = AuditSessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_audit_table():
    try:
        with audit_engine.connect() as conn:
            conn.execute(text(_AUDIT_TABLE_DDL))
            conn.commit()
        logger.info("Audit log table ensured")
    except Exception as e:
        logger.error("Failed to ensure audit log table: %s", e)
