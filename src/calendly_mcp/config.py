"""Configuration management for Calendly MCP Server.

Loads settings from environment variables with sensible defaults.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Valid log level names accepted by the LOG_LEVEL environment variable.
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass(frozen=True)
class Config:
    """Immutable server configuration loaded from the environment.

    Attributes:
        calendly_access_token: Calendly Personal Access Token or OAuth2 token. Required.
        license_key: Lemon Squeezy license key that unlocks premium tools. Optional.
        log_level: Python logging level name. Defaults to INFO.
        calendly_base_url: Base URL for the Calendly REST API v2.
        license_cache_ttl_seconds: How long to cache a successful license validation.
    """

    calendly_access_token: str
    license_key: str | None = None
    log_level: str = "INFO"
    calendly_base_url: str = "https://api.calendly.com"
    license_cache_ttl_seconds: int = field(default=86400)  # 24 hours

    def __post_init__(self) -> None:
        if not self.calendly_access_token:
            raise ValueError(
                "CALENDLY_ACCESS_TOKEN is required. "
                "Get one at https://calendly.com/integrations/api_webhooks"
            )


def load_config() -> Config:
    """Build a ``Config`` from environment variables.

    Environment variables
    ---------------------
    CALENDLY_ACCESS_TOKEN : str  (required)
        Calendly Personal Access Token or OAuth2 access token.
    LICENSE_KEY : str  (optional)
        Lemon Squeezy license key for premium features.
    LOG_LEVEL : str  (optional, default ``INFO``)
        Python log level name.
    CALENDLY_BASE_URL : str  (optional)
        Override the Calendly API base URL (useful for testing).

    Returns
    -------
    Config
        Validated, immutable configuration object.

    Raises
    ------
    ValueError
        If required configuration is missing.
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    if log_level not in VALID_LOG_LEVELS:
        logger.warning("Invalid LOG_LEVEL '%s', falling back to INFO", log_level)
        log_level = "INFO"

    return Config(
        calendly_access_token=os.environ.get("CALENDLY_ACCESS_TOKEN", ""),
        license_key=os.environ.get("LICENSE_KEY") or None,
        log_level=log_level,
        calendly_base_url=os.environ.get("CALENDLY_BASE_URL", "https://api.calendly.com"),
    )
