"""Response formatting helpers.

Converts raw Calendly API responses into human-readable text suitable for
display in Claude Desktop/Code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def format_datetime(iso_string: str | None) -> str:
    """Convert an ISO 8601 string to a friendly format.

    Example: ``2026-03-24T14:30:00.000000Z`` becomes ``Mon Mar 24, 2026 at 2:30 PM UTC``.
    """
    if not iso_string:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%a %b %d, %Y at %-I:%M %p %Z").replace(" 0", " ")
    except (ValueError, AttributeError):
        return iso_string


def format_duration(minutes: int | None) -> str:
    """Format a duration in minutes to a human-readable string."""
    if minutes is None:
        return "N/A"
    if minutes < 60:
        return f"{minutes} min"
    hours, remaining = divmod(minutes, 60)
    if remaining == 0:
        return f"{hours}h"
    return f"{hours}h {remaining}min"


def format_event_summary(event: dict[str, Any], invitees: list[dict[str, Any]] | None = None) -> str:
    """Format a scheduled event into a readable summary block."""
    name = event.get("name", "Untitled Event")
    start = format_datetime(event.get("start_time"))
    end = format_datetime(event.get("end_time"))
    status = event.get("status", "unknown")
    location_info = _format_location(event.get("location", {}))

    lines = [
        f"**{name}**",
        f"  Time: {start} - {end}",
        f"  Status: {status}",
    ]

    if location_info:
        lines.append(f"  Location: {location_info}")

    if invitees:
        invitee_strs = [
            f"{inv.get('name', 'Unknown')} <{inv.get('email', 'N/A')}>"
            for inv in invitees
        ]
        lines.append(f"  Invitees: {', '.join(invitee_strs)}")

    event_uuid = event.get("uri", "").rsplit("/", 1)[-1]
    if event_uuid:
        lines.append(f"  Event ID: {event_uuid}")

    return "\n".join(lines)


def format_event_type_summary(event_type: dict[str, Any]) -> str:
    """Format an event type into a readable summary block."""
    name = event_type.get("name", "Untitled")
    duration = format_duration(event_type.get("duration"))
    slug = event_type.get("slug", "N/A")
    active = "Active" if event_type.get("active") else "Inactive"
    kind = event_type.get("kind", "N/A")

    et_uuid = event_type.get("uri", "").rsplit("/", 1)[-1]

    lines = [
        f"**{name}**",
        f"  Duration: {duration}",
        f"  Slug: {slug}",
        f"  Status: {active}",
        f"  Type: {kind}",
    ]

    if et_uuid:
        lines.append(f"  Event Type ID: {et_uuid}")

    return "\n".join(lines)


def format_availability_slot(slot: dict[str, Any]) -> str:
    """Format a single availability slot."""
    start = format_datetime(slot.get("start_time"))
    end = format_datetime(slot.get("end_time"))
    status = slot.get("status", "available")
    return f"  {start} - {end} ({status})"


def format_busy_time(busy: dict[str, Any]) -> str:
    """Format a single busy time period."""
    start = format_datetime(busy.get("start_time"))
    end = format_datetime(busy.get("end_time"))
    event_type = busy.get("type", "external")
    return f"  {start} - {end} [{event_type}]"


def _format_location(location: dict[str, Any] | None) -> str:
    """Extract a readable location string from the event location object."""
    if not location:
        return ""
    loc_type = location.get("type", "")
    if loc_type == "physical":
        return location.get("location", "In-person")
    if loc_type in ("google_conference", "zoom", "microsoft_teams_conference"):
        join_url = location.get("join_url", "")
        return f"{loc_type.replace('_', ' ').title()} - {join_url}" if join_url else loc_type.replace("_", " ").title()
    if location.get("join_url"):
        return location["join_url"]
    return location.get("location", loc_type)
