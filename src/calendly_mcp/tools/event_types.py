"""Event type MCP tools (free tier).

Provides tools for listing and inspecting Calendly event types.
"""

from __future__ import annotations

import logging

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.utils.formatting import format_event_type_summary, format_duration

logger = logging.getLogger(__name__)


async def list_event_types(client: CalendlyClient) -> str:
    """List all configured event types for the authenticated user.

    Returns
    -------
    str
        Formatted list of event types.
    """
    try:
        event_types = await client.list_event_types()
    except CalendlyAPIError as exc:
        return f"Error fetching event types: {exc.message}"

    if not event_types:
        return "No event types found. Create one at https://calendly.com/event_types"

    summaries = [format_event_type_summary(et) for et in event_types]
    header = f"Found {len(event_types)} event type(s):\n"
    return header + "\n\n".join(summaries)


async def get_event_type_details(client: CalendlyClient, *, event_type_uuid: str) -> str:
    """Get detailed configuration of a specific event type.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    event_type_uuid:
        UUID of the event type to retrieve.

    Returns
    -------
    str
        Formatted event type details.
    """
    try:
        et = await client.get_event_type(event_type_uuid)
    except CalendlyAPIError as exc:
        return f"Error fetching event type: {exc.message}"

    summary = format_event_type_summary(et)

    # Additional details
    extras: list[str] = []

    description = et.get("description_plain") or et.get("description_html", "")
    if description:
        extras.append(f"  Description: {description[:500]}")

    color = et.get("color")
    if color:
        extras.append(f"  Color: {color}")

    scheduling_url = et.get("scheduling_url")
    if scheduling_url:
        extras.append(f"  Booking URL: {scheduling_url}")

    secret = et.get("secret")
    if secret:
        extras.append("  Visibility: Secret (only accessible via direct link)")
    else:
        extras.append("  Visibility: Public")

    custom_questions = et.get("custom_questions", [])
    if custom_questions:
        q_strs = [q.get("name", "Unnamed question") for q in custom_questions]
        extras.append(f"  Custom questions: {', '.join(q_strs)}")

    if extras:
        summary += "\n" + "\n".join(extras)

    return summary
