"""Scheduling MCP tools (premium tier).

Provides tools for creating, canceling, and rescheduling events.
These require a valid Lemon Squeezy premium license key.
"""

from __future__ import annotations

import logging

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.utils.formatting import format_datetime

logger = logging.getLogger(__name__)

PREMIUM_REQUIRED_MSG = (
    "This is a premium feature. "
    "Upgrade at https://nyxtools.gumroad.com for $12/mo "
    "to unlock scheduling, cancellation, rescheduling, and analytics tools."
)


async def create_one_off_event(
    client: CalendlyClient,
    *,
    event_type_uuid: str,
    invitee_email: str,
    invitee_name: str,
    start_time: str,
) -> str:
    """Create a single-use scheduling link for a meeting.

    This generates a scheduling link pre-configured for the specified event
    type. The invitee can use this link to confirm the booking.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    event_type_uuid:
        UUID of the event type to schedule.
    invitee_email:
        Email address of the invitee.
    invitee_name:
        Full name of the invitee.
    start_time:
        Desired start time in ISO 8601 format.

    Returns
    -------
    str
        Confirmation with the scheduling link.
    """
    # Build the full event type URI
    try:
        et = await client.get_event_type(event_type_uuid)
    except CalendlyAPIError as exc:
        return f"Error fetching event type: {exc.message}"

    event_type_uri = et.get("uri", "")
    if not event_type_uri:
        return "Error: Could not determine event type URI."

    try:
        result = await client.create_scheduling_link(event_type_uri, max_event_count=1)
    except CalendlyAPIError as exc:
        return f"Error creating scheduling link: {exc.message}"

    booking_url = result.get("booking_url", "")
    owner_type = result.get("owner_type", "")

    lines = [
        "**Scheduling Link Created**",
        f"  Event type: {et.get('name', 'Unknown')}",
        f"  For: {invitee_name} <{invitee_email}>",
        f"  Requested time: {format_datetime(start_time)}",
        f"  Booking URL: {booking_url}",
        "",
        "Share this link with the invitee to confirm the booking.",
        "Note: The invitee will select the final time from available slots on the booking page.",
    ]
    return "\n".join(lines)


async def cancel_event(
    client: CalendlyClient,
    *,
    event_uuid: str,
    reason: str | None = None,
) -> str:
    """Cancel an existing scheduled event.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    event_uuid:
        UUID of the event to cancel.
    reason:
        Optional cancellation reason shown to invitees.

    Returns
    -------
    str
        Cancellation confirmation.
    """
    # First fetch the event to show what's being canceled
    try:
        event = await client.get_scheduled_event(event_uuid)
    except CalendlyAPIError as exc:
        return f"Error fetching event: {exc.message}"

    try:
        await client.cancel_event(event_uuid, reason=reason)
    except CalendlyAPIError as exc:
        if exc.status_code == 403:
            return "Error: You don't have permission to cancel this event."
        if exc.status_code == 404:
            return "Error: Event not found. It may have already been canceled."
        return f"Error canceling event: {exc.message}"

    event_name = event.get("name", "Untitled Event")
    start = format_datetime(event.get("start_time"))

    lines = [
        "**Event Canceled**",
        f"  Event: {event_name}",
        f"  Was scheduled for: {start}",
    ]
    if reason:
        lines.append(f"  Reason: {reason}")
    lines.append("\nInvitees will be notified of the cancellation.")

    return "\n".join(lines)


async def reschedule_event(
    client: CalendlyClient,
    *,
    event_uuid: str,
    new_start_time: str,
) -> str:
    """Reschedule an existing event to a new time.

    Note: The Calendly API does not have a direct reschedule endpoint.
    This cancels the existing event with a reschedule note and creates
    a new scheduling link for the same event type.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    event_uuid:
        UUID of the event to reschedule.
    new_start_time:
        New desired start time in ISO 8601 format.

    Returns
    -------
    str
        Rescheduling confirmation with new booking link.
    """
    # Fetch the original event
    try:
        event = await client.get_scheduled_event(event_uuid)
    except CalendlyAPIError as exc:
        return f"Error fetching event: {exc.message}"

    event_name = event.get("name", "Untitled Event")
    old_start = format_datetime(event.get("start_time"))
    event_type_uri = event.get("event_type", "")

    if not event_type_uri:
        return "Error: Could not determine the event type for rescheduling."

    # Cancel the original event with a reschedule reason
    cancel_reason = f"Rescheduling to {format_datetime(new_start_time)}"
    try:
        await client.cancel_event(event_uuid, reason=cancel_reason)
    except CalendlyAPIError as exc:
        return f"Error canceling original event for reschedule: {exc.message}"

    # Create a new scheduling link
    try:
        result = await client.create_scheduling_link(event_type_uri, max_event_count=1)
    except CalendlyAPIError as exc:
        return (
            f"Original event canceled, but failed to create new scheduling link: {exc.message}\n"
            "Please create a new scheduling link manually."
        )

    booking_url = result.get("booking_url", "")

    lines = [
        "**Event Rescheduled**",
        f"  Event: {event_name}",
        f"  Original time: {old_start}",
        f"  Requested new time: {format_datetime(new_start_time)}",
        f"  New booking URL: {booking_url}",
        "",
        "The original event has been canceled. Share the new booking link",
        "with the invitee to confirm the rescheduled time.",
    ]
    return "\n".join(lines)
