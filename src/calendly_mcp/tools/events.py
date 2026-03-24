"""Event-related MCP tools (free tier).

Provides tools for listing, viewing, and searching scheduled events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.utils.formatting import format_event_summary

logger = logging.getLogger(__name__)


async def list_upcoming_events(
    client: CalendlyClient,
    *,
    count: int = 10,
    min_start_time: str | None = None,
    max_start_time: str | None = None,
    status: str | None = None,
) -> str:
    """List upcoming scheduled events with optional filters.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    count:
        Number of events to return (1-100, default 10).
    min_start_time:
        ISO 8601 lower bound for event start time. Defaults to now.
    max_start_time:
        ISO 8601 upper bound for event start time.
    status:
        Filter by status: ``active`` or ``canceled``.

    Returns
    -------
    str
        Formatted list of events for display.
    """
    if min_start_time is None:
        min_start_time = datetime.now(timezone.utc).isoformat()

    try:
        events = await client.list_scheduled_events(
            count=count,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
            status=status,
        )
    except CalendlyAPIError as exc:
        return f"Error fetching events: {exc.message}"

    if not events:
        return "No upcoming events found."

    summaries: list[str] = []
    for event in events:
        event_uuid = event["uri"].rsplit("/", 1)[-1]
        try:
            invitees = await client.get_event_invitees(event_uuid)
        except CalendlyAPIError:
            invitees = []
        summaries.append(format_event_summary(event, invitees))

    header = f"Found {len(events)} upcoming event(s):\n"
    return header + "\n\n".join(summaries)


async def get_event_details(client: CalendlyClient, *, event_uuid: str) -> str:
    """Get full details of a specific scheduled event.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    event_uuid:
        UUID of the event to retrieve.

    Returns
    -------
    str
        Formatted event details for display.
    """
    try:
        event = await client.get_scheduled_event(event_uuid)
        invitees = await client.get_event_invitees(event_uuid)
    except CalendlyAPIError as exc:
        return f"Error fetching event details: {exc.message}"

    summary = format_event_summary(event, invitees)

    # Add extra detail fields not in the summary
    extras: list[str] = []
    if event.get("event_type"):
        et_uuid = event["event_type"].rsplit("/", 1)[-1]
        extras.append(f"  Event Type ID: {et_uuid}")
    if event.get("created_at"):
        extras.append(f"  Created: {event['created_at']}")
    if event.get("updated_at"):
        extras.append(f"  Updated: {event['updated_at']}")

    cancellation = event.get("cancellation")
    if cancellation:
        reason = cancellation.get("reason", "No reason provided")
        canceled_by = cancellation.get("canceled_by", "Unknown")
        extras.append(f"  Cancellation reason: {reason}")
        extras.append(f"  Canceled by: {canceled_by}")

    if extras:
        summary += "\n" + "\n".join(extras)

    return summary


async def search_events(
    client: CalendlyClient,
    *,
    query: str,
    min_start_time: str | None = None,
    max_start_time: str | None = None,
) -> str:
    """Search events by invitee name or email.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    query:
        Name or email to search for (case-insensitive partial match).
    min_start_time:
        ISO 8601 lower bound for event start time.
    max_start_time:
        ISO 8601 upper bound for event start time.

    Returns
    -------
    str
        Formatted list of matching events.
    """
    try:
        matches = await client.search_events_by_invitee(
            query,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
        )
    except CalendlyAPIError as exc:
        return f"Error searching events: {exc.message}"

    if not matches:
        return f"No events found matching '{query}'."

    summaries: list[str] = []
    for event in matches:
        invitees = event.get("_matched_invitees", [])
        summaries.append(format_event_summary(event, invitees))

    header = f"Found {len(matches)} event(s) matching '{query}':\n"
    return header + "\n\n".join(summaries)
