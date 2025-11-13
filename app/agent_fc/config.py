"""Configuration helpers for the function-calling router."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings for client-side function calling."""

    call_timeout_ms: int = 2000
    max_retries: int = 1
    log_level: str = "DEBUG"


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(parsed, 0)


def get_settings() -> Settings:
    """Load settings from environment variables with sane defaults."""

    return Settings(
        call_timeout_ms=_get_int_env("FC_CALL_TIMEOUT_MS", Settings.call_timeout_ms),
        max_retries=_get_int_env("FC_MAX_RETRIES", Settings.max_retries),
        log_level=os.getenv("FC_LOG_LEVEL", Settings.log_level).upper(),
    )
