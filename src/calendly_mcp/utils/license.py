"""Lemon Squeezy license key validation.

Validates premium license keys against the Lemon Squeezy API and caches
the result for 24 hours to avoid excessive API calls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LEMON_SQUEEZY_VALIDATE_URL = "https://api.lemonsqueezy.com/v1/licenses/validate"

# The product slug registered with Lemon Squeezy.
PRODUCT_SLUG = "calendly-mcp-premium"


@dataclass
class LicenseStatus:
    """Cached result of a license validation check."""

    is_valid: bool
    license_key: str | None
    customer_name: str | None
    validated_at: float  # time.monotonic() timestamp
    error: str | None = None


class LicenseValidator:
    """Validates and caches Lemon Squeezy license keys.

    Parameters
    ----------
    cache_ttl_seconds:
        How long a successful validation remains cached before re-checking.
    """

    def __init__(self, cache_ttl_seconds: int = 86400) -> None:
        self._cache_ttl = cache_ttl_seconds
        self._cached_status: LicenseStatus | None = None

    @property
    def is_premium(self) -> bool:
        """Return True if a valid premium license is currently cached."""
        if self._cached_status is None:
            return False
        if not self._cached_status.is_valid:
            return False
        age = time.monotonic() - self._cached_status.validated_at
        if age > self._cache_ttl:
            # Cache expired; treat as not premium until re-validated.
            return False
        return True

    async def validate(self, license_key: str | None) -> LicenseStatus:
        """Validate a license key against the Lemon Squeezy API.

        If ``license_key`` is None or empty, returns an invalid status immediately.
        Caches successful validations for ``cache_ttl_seconds``.

        Parameters
        ----------
        license_key:
            The customer's Lemon Squeezy license key.

        Returns
        -------
        LicenseStatus
            The validation result (always returned, never raises).
        """
        if not license_key:
            self._cached_status = LicenseStatus(
                is_valid=False,
                license_key=None,
                customer_name=None,
                validated_at=time.monotonic(),
                error="No license key provided",
            )
            return self._cached_status

        # Return cached result if still fresh
        if (
            self._cached_status is not None
            and self._cached_status.is_valid
            and self._cached_status.license_key == license_key
        ):
            age = time.monotonic() - self._cached_status.validated_at
            if age < self._cache_ttl:
                logger.debug("Using cached license validation (age: %.0fs)", age)
                return self._cached_status

        # Call Lemon Squeezy validation API
        try:
            status = await self._call_validate_api(license_key)
        except Exception:
            logger.exception("License validation request failed")
            status = LicenseStatus(
                is_valid=False,
                license_key=license_key,
                customer_name=None,
                validated_at=time.monotonic(),
                error="License validation service unavailable. Premium features disabled.",
            )

        self._cached_status = status
        return status

    async def _call_validate_api(self, license_key: str) -> LicenseStatus:
        """Make the actual HTTP request to Lemon Squeezy."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                LEMON_SQUEEZY_VALIDATE_URL,
                json={"license_key": license_key},
                headers={"Accept": "application/json"},
            )

        if resp.status_code != 200:
            return LicenseStatus(
                is_valid=False,
                license_key=license_key,
                customer_name=None,
                validated_at=time.monotonic(),
                error=f"Validation failed (HTTP {resp.status_code})",
            )

        body: dict[str, Any] = resp.json()
        valid = body.get("valid", False)
        meta = body.get("meta", {})
        customer_name = meta.get("customer_name")

        if not valid:
            error_msg = body.get("error", "License key is not valid or has been deactivated.")
            return LicenseStatus(
                is_valid=False,
                license_key=license_key,
                customer_name=customer_name,
                validated_at=time.monotonic(),
                error=error_msg,
            )

        logger.info("Premium license validated for %s", customer_name or "unknown customer")
        return LicenseStatus(
            is_valid=True,
            license_key=license_key,
            customer_name=customer_name,
            validated_at=time.monotonic(),
        )
