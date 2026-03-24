"""Availability MCP tools (free tier).

Provides tools for checking available time slots and busy periods.
"""

from __future__ import annotations

import logging
from typing import Any

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.utils.formatting import format_availability_slot, format_busy_time

logger = logging.getLogger(__name__)


async def check_availability(
    client: CalendlyClient,
    *,
    date_range_start: str,
    date_range_end: str,
) -> str:
    """Check available time slots from the user's availability schedules.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    date_range_start:
        ISO 8601 start of the date range to check.
    date_range_end:
        ISO 8601 end of the date range to check.

    Returns
    -------
    str
        Formatted availability information.
    """
    try:
        schedules = await client.get_user_availability_schedules()
    except CalendlyAPIError as exc:
        return f"Error checking availability: {exc.message}"

    if not schedules:
        return "No availability schedules found."

    lines: list[str] = ["**Availability Schedules:**\n"]

    for schedule in schedules:
        name = schedule.get("name", "Unnamed Schedule")
        timezone_str = schedule.get("timezone", "Unknown")
        lines.append(f"**{name}** (Timezone: {timezone_str})")

        rules = schedule.get("rules", [])
        if not rules:
            lines.append("  No rules configured.")
            continue

        for rule in rules:
            rule_type = rule.get("type", "unknown")
            wday = rule.get("wday", "")
            date = rule.get("date", "")
            intervals = rule.get("intervals", [])

            label = wday.capitalize() if wday else date if date else rule_type
            if intervals:
                interval_strs = [
                    f"{iv.get('from', '?')} - {iv.get('to', '?')}"
                    for iv in intervals
                ]
                lines.append(f"  {label}: {', '.join(interval_strs)}")
            else:
                lines.append(f"  {label}: No availability")

        lines.append("")

    # Also fetch busy times for the given range to show what's booked
    try:
        busy_times = await client.get_user_busy_times(date_range_start, date_range_end)
        if busy_times:
            lines.append(f"\n**Busy times ({date_range_start[:10]} to {date_range_end[:10]}):**")
            for bt in busy_times:
                lines.append(format_busy_time(bt))
    except CalendlyAPIError:
        logger.debug("Could not fetch busy times for availability check")

    return "\n".join(lines)


async def get_busy_times(
    client: CalendlyClient,
    *,
    start_time: str,
    end_time: str,
) -> str:
    """Get busy/unavailable time periods for the authenticated user.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    start_time:
        ISO 8601 start of the date range.
    end_time:
        ISO 8601 end of the date range.

    Returns
    -------
    str
        Formatted list of busy periods.
    """
    try:
        busy_times = await client.get_user_busy_times(start_time, end_time)
    except CalendlyAPIError as exc:
        return f"Error fetching busy times: {exc.message}"

    if not busy_times:
        return f"No busy times found between {start_time[:10]} and {end_time[:10]}. You appear to be free!"

    lines = [f"**Busy times ({start_time[:10]} to {end_time[:10]}):**\n"]
    for bt in busy_times:
        lines.append(format_busy_time(bt))

    lines.append(f"\nTotal busy periods: {len(busy_times)}")
    return "\n".join(lines)
