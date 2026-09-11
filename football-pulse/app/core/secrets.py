"""Secrets management: env-first with optional file/SM hooks, no secrets in code."""
from __future__ import annotations

import os
from pathlib import Path

from app.core.logging import get_logger

log = get_logger("core.secrets")


class SecretsManager:
    """Read secrets from environment, with optional `_FILE` indirection (Docker secrets).

    Example: YOUTUBE_API_KEY_FILE=/run/secrets/youtube_api_key
    takes precedence over YOUTUBE_API_KEY value if the file exists.
    """

    @staticmethod
    def get(name: str, default: str | None = None, required: bool = False) -> str | None:
        file_var = f"{name}_FILE"
        file_path = os.getenv(file_var)
        if file_path:
            try:
                value = Path(file_path).read_text(encoding="utf-8").strip()
                if value:
                    return value
            except OSError as exc:
                log.warning("secret_file_unreadable", secret=name, path=file_path, error=str(exc))
        value = os.getenv(name, default)
        if required and not value:
            raise RuntimeError(f"Required secret missing: {name}")
        return value

    @classmethod
    def get_required(cls, name: str) -> str:
        value = cls.get(name, required=True)
        assert value is not None
        return value
