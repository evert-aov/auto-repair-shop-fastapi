import base64
import json
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.audit.utils.auditoria_utils import AuditoriaUtils

logger = logging.getLogger("audit.encryption")

AUDIT_ENCRYPTION_KEY = os.getenv("AUDIT_ENCRYPTION_KEY", "Lk+JyPYKgx7Ooxz6kYCU1/A7pZOQb+iz0B4qc3qHHgg=")


class AuditEncryptionService:

    def __init__(self) -> None:
        key_bytes = base64.b64decode(AUDIT_ENCRYPTION_KEY)
        if len(key_bytes) != 32:
            logger.warning("AUDIT_ENCRYPTION_KEY is not 32 bytes (256 bits), may cause issues")
        self._aesgcm = AESGCM(key_bytes)

    def encrypt(self, plaintext: str | None) -> bytes | None:
        if plaintext is None:
            return None
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + ciphertext

    def decrypt(self, encrypted: bytes | None) -> str | None:
        if encrypted is None:
            return None
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    def encrypt_map(self, data: dict | None) -> bytes | None:
        if data is None:
            return None
        sanitized = AuditoriaUtils.sanitize_map(data)
        return self.encrypt(json.dumps(sanitized, default=str))

    def decrypt_map(self, encrypted: bytes | None) -> dict | None:
        if encrypted is None:
            return None
        try:
            plain = self.decrypt(encrypted)
            if plain is None:
                return None
            return json.loads(plain)
        except Exception as e:
            logger.warning("Error decrypting audit field, returning None: %s", e)
            return None
