import random
import threading
import time
from typing import Optional


class CodeStore:
    """Almacén en memoria de códigos de verificación con TTL.
    Reemplaza Redis usado en main-si2 para los flujos de verificación."""

    def __init__(self, default_ttl_seconds: int = 600):
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl_seconds

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now >= exp]
        for k in expired:
            del self._store[k]

    def generate_and_store(self, key: str) -> str:
        code = f"{random.randint(0, 999999):06d}"
        with self._lock:
            self._cleanup_expired()
            self._store[key] = (code, time.time() + self._default_ttl)
        return code

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._cleanup_expired()
            entry = self._store.get(key)
            if entry is None:
                return None
            code, expires_at = entry
            if time.time() >= expires_at:
                del self._store[key]
                return None
            return code

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


code_store = CodeStore()
