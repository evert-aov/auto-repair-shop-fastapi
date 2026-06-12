from collections import OrderedDict
from typing import Any


SENSITIVE_KEYS = {"password", "passwordConfirm", "currentPassword", "newPassword"}


class AuditoriaUtils:

    @staticmethod
    def calculate_diff(
        antes: dict[str, Any] | None, despues: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if antes is None and despues is None:
            return {}, {}

        diff_antes: dict[str, Any] = OrderedDict()
        diff_despues: dict[str, Any] = OrderedDict()

        if antes is None:
            diff_despues.update(despues)
            return diff_antes, diff_despues

        if despues is None:
            diff_antes.update(antes)
            return diff_antes, diff_despues

        all_keys = {*antes.keys(), *despues.keys()}
        for key in sorted(all_keys):
            val_antes = antes.get(key)
            val_despues = despues.get(key)
            if val_antes != val_despues:
                diff_antes[key] = val_antes
                diff_despues[key] = val_despues

        if not diff_antes and not diff_despues:
            return antes, despues

        return diff_antes, diff_despues

    @staticmethod
    def sanitize_map(data: dict[str, Any] | None) -> dict[str, Any] | None:
        if data is None:
            return None
        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            if key in SENSITIVE_KEYS:
                sanitized[key] = "***ENMASCARADO***"
            elif isinstance(value, dict):
                sanitized[key] = AuditoriaUtils.sanitize_map(value)
            else:
                sanitized[key] = value
        return sanitized
