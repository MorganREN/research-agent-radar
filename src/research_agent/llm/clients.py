"""Shared LLM provider configuration helpers."""
from __future__ import annotations

import os


def get_env_any(*names: str) -> str | None:
    """Return the first non-empty environment variable value from names."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None
