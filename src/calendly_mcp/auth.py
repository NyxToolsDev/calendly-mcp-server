"""Authentication helpers for the Calendly API and license validation.

Supports Personal Access Tokens and OAuth2 bearer tokens.  License key
validation is delegated to ``utils.license``.
"""

from __future__ import annotations

import logging

import httpx

from calendly_mcp.config import Config

logger = logging.getLogger(__name__)


async def get_current_user(config: Config) -> dict:
    """Fetch the authenticated Calendly user profile.

    This doubles as a token-validity check: if the token is invalid or expired
    the Calendly API will return a 401 and we surface a clear error.

    Parameters
    ----------
    config:
        Server configuration containing the access token.

    Returns
    -------
    dict
        The ``resource`` object from ``GET /users/me``.

    Raises
    ------
    httpx.HTTPStatusError
        On non-2xx responses from Calendly.
    """
    async with httpx.AsyncClient(
        base_url=config.calendly_base_url,
        headers=_auth_headers(config),
        timeout=30.0,
    ) as client:
        resp = await client.get("/users/me")
        resp.raise_for_status()
        data: dict = resp.json()
        return data.get("resource", data)


def _auth_headers(config: Config) -> dict[str, str]:
    """Return authorization headers for the Calendly API."""
    return {
        "Authorization": f"Bearer {config.calendly_access_token}",
        "Content-Type": "application/json",
    }
