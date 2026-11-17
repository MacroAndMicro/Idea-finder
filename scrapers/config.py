"""Configuration from environment variables only.

Errors name the missing variable but never echo any secret value.
"""

from __future__ import annotations

import os

DEFAULT_USER_AGENT = "idea-finder-scrapers/0.1 (+https://gitlab.com/personal-group8954246/idea-finder)"


class MissingSecretError(RuntimeError):
    """Raised when a required environment variable is unset or empty."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Required environment variable {name} is not set")
        self.name = name


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def require_env(name: str) -> str:
    value = get_env(name)
    if value is None:
        raise MissingSecretError(name)
    return value


def user_agent() -> str:
    """Honest, identifying User-Agent. Override with SCRAPER_USER_AGENT."""
    return get_env("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT) or DEFAULT_USER_AGENT
