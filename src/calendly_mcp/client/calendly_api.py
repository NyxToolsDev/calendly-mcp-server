"""Async client for the Calendly REST API v2.

Wraps ``httpx.AsyncClient`` with automatic authorization, retry logic with
exponential backoff, and rate-limit handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from calendly_mcp.config import Config

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0
RATE_LIMIT_STATUS = 429
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class CalendlyAPIError(Exception):
    """Raised when the Calendly API returns an unrecoverable error."""

    def __init__(self, status_code: int, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"Calendly API error {status_code}: {message}")


class CalendlyClient:
    """Async wrapper around the Calendly REST API v2.

    Parameters
    ----------
    config:
        Server configuration containing the access token and base URL.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._base_url = config.calendly_base_url
        self._headers = {
            "Authorization": f"Bearer {config.calendly_access_token}",
            "Content-Type": "application/json",
        }
        self._user_uri: str | None = None

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an HTTP request with retry and rate-limit handling.

        Returns the parsed JSON body on success.

        Raises
        ------
        CalendlyAPIError
            After all retries are exhausted or on non-retryable errors.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    headers=self._headers,
                    timeout=30.0,
                ) as client:
                    resp = await client.request(method, path, params=params, json=json_body)

                    if resp.status_code == RATE_LIMIT_STATUS:
                        retry_after = float(resp.headers.get("Retry-After", backoff))
                        logger.warning(
                            "Rate limited (attempt %d/%d). Retrying after %.1fs",
                            attempt,
                            MAX_RETRIES,
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        backoff *= BACKOFF_MULTIPLIER
                        continue

                    if resp.status_code in RETRYABLE_STATUS_CODES:
                        logger.warning(
                            "Retryable %d (attempt %d/%d). Backing off %.1fs",
                            resp.status_code,
                            attempt,
                            MAX_RETRIES,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff *= BACKOFF_MULTIPLIER
                        continue

                    if resp.status_code >= 400:
                        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                        msg = body.get("message", resp.text[:200])
                        raise CalendlyAPIError(resp.status_code, msg, body)

                    if resp.status_code == 204:
                        return {}

                    return resp.json()  # type: ignore[no-any-return]

            except httpx.RequestError as exc:
                if attempt == MAX_RETRIES:
                    raise CalendlyAPIError(0, f"Connection error: {exc}") from exc
                logger.warning("Request error (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
                await asyncio.sleep(backoff)
                backoff *= BACKOFF_MULTIPLIER

        raise CalendlyAPIError(0, "Max retries exceeded")

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        cleaned = {k: v for k, v in params.items() if v is not None}
        return await self._request("GET", path, params=cleaned)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json_body=body)

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    async def get_current_user_uri(self) -> str:
        """Return the URI of the authenticated user, caching after first call."""
        if self._user_uri is None:
            data = await self._get("/users/me")
            resource = data.get("resource", data)
            self._user_uri = resource["uri"]
        return self._user_uri

    # ------------------------------------------------------------------
    # Scheduled Events
    # ------------------------------------------------------------------

    async def list_scheduled_events(
        self,
        *,
        count: int = 10,
        min_start_time: str | None = None,
        max_start_time: str | None = None,
        status: str | None = None,
        sort: str = "start_time:asc",
    ) -> list[dict[str, Any]]:
        """List scheduled events for the authenticated user.

        Parameters
        ----------
        count:
            Maximum number of events to return (1-100).
        min_start_time:
            ISO 8601 lower bound for event start time.
        max_start_time:
            ISO 8601 upper bound for event start time.
        status:
            Filter by status: ``active`` or ``canceled``.
        sort:
            Sort order, e.g. ``start_time:asc``.
        """
        user_uri = await self.get_current_user_uri()
        data = await self._get(
            "/scheduled_events",
            user=user_uri,
            count=min(count, 100),
            min_start_time=min_start_time,
            max_start_time=max_start_time,
            status=status,
            sort=sort,
        )
        return data.get("collection", [])

    async def get_scheduled_event(self, event_uuid: str) -> dict[str, Any]:
        """Get full details of a single scheduled event."""
        data = await self._get(f"/scheduled_events/{event_uuid}")
        return data.get("resource", data)

    async def get_event_invitees(
        self, event_uuid: str, *, count: int = 50
    ) -> list[dict[str, Any]]:
        """List invitees for a scheduled event."""
        data = await self._get(
            f"/scheduled_events/{event_uuid}/invitees",
            count=min(count, 100),
        )
        return data.get("collection", [])

    # ------------------------------------------------------------------
    # Event Types
    # ------------------------------------------------------------------

    async def list_event_types(self, *, active: bool | None = True) -> list[dict[str, Any]]:
        """List event types configured by the authenticated user."""
        user_uri = await self.get_current_user_uri()
        params: dict[str, Any] = {"user": user_uri}
        if active is not None:
            params["active"] = str(active).lower()
        data = await self._get("/event_types", **params)
        return data.get("collection", [])

    async def get_event_type(self, event_type_uuid: str) -> dict[str, Any]:
        """Get details of a single event type."""
        data = await self._get(f"/event_types/{event_type_uuid}")
        return data.get("resource", data)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    async def get_user_availability_schedules(self) -> list[dict[str, Any]]:
        """List availability schedules for the authenticated user."""
        user_uri = await self.get_current_user_uri()
        data = await self._get("/user_availability_schedules", user=user_uri)
        return data.get("collection", [])

    async def get_user_busy_times(
        self,
        start_time: str,
        end_time: str,
    ) -> list[dict[str, Any]]:
        """Get busy/unavailable time periods.

        Parameters
        ----------
        start_time:
            ISO 8601 start of the query range.
        end_time:
            ISO 8601 end of the query range.
        """
        user_uri = await self.get_current_user_uri()
        data = await self._get(
            "/user_busy_times",
            user=user_uri,
            start_time=start_time,
            end_time=end_time,
        )
        return data.get("collection", [])

    # ------------------------------------------------------------------
    # Scheduling (Premium)
    # ------------------------------------------------------------------

    async def create_scheduling_link(
        self,
        event_type_uri: str,
        *,
        max_event_count: int = 1,
    ) -> dict[str, Any]:
        """Create a single-use scheduling link for an event type.

        Parameters
        ----------
        event_type_uri:
            The full URI of the event type.
        max_event_count:
            Maximum bookings allowed through this link.
        """
        body = {
            "max_event_count": max_event_count,
            "owner": event_type_uri,
            "owner_type": "EventType",
        }
        data = await self._post("/scheduling_links", body)
        return data.get("resource", data)

    async def cancel_event(
        self, event_uuid: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        """Cancel a scheduled event.

        Parameters
        ----------
        event_uuid:
            UUID of the event to cancel.
        reason:
            Optional cancellation reason shown to invitees.
        """
        body: dict[str, Any] = {}
        if reason:
            body["reason"] = reason
        return await self._post(f"/scheduled_events/{event_uuid}/cancellation", body)

    # ------------------------------------------------------------------
    # Search helpers (client-side filtering)
    # ------------------------------------------------------------------

    async def search_events_by_invitee(
        self,
        query: str,
        *,
        min_start_time: str | None = None,
        max_start_time: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search events by invitee name or email.

        Fetches recent events and filters invitees client-side because
        the Calendly API does not support server-side invitee search across
        all events.
        """
        events = await self.list_scheduled_events(
            count=100,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
        )

        query_lower = query.lower()
        matches: list[dict[str, Any]] = []

        for event in events:
            event_uuid = event["uri"].rsplit("/", 1)[-1]
            invitees = await self.get_event_invitees(event_uuid)
            for inv in invitees:
                name = (inv.get("name") or "").lower()
                email = (inv.get("email") or "").lower()
                if query_lower in name or query_lower in email:
                    matches.append({**event, "_matched_invitees": invitees})
                    break

        return matches
