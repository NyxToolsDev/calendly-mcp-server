"""Analytics MCP tools (premium tier).

Provides tools for scheduling statistics and invitee insights.
These require a valid Lemon Squeezy premium license key.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.utils.formatting import format_datetime, format_duration

logger = logging.getLogger(__name__)


async def get_scheduling_stats(
    client: CalendlyClient,
    *,
    min_start_time: str,
    max_start_time: str,
) -> str:
    """Get scheduling analytics for a date range.

    Analyzes events to compute total meetings, average duration,
    most popular booking times, cancellation rate, and more.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    min_start_time:
        ISO 8601 start of the analysis period.
    max_start_time:
        ISO 8601 end of the analysis period.

    Returns
    -------
    str
        Formatted scheduling statistics.
    """
    try:
        # Fetch all events (active + canceled) in the range
        active_events = await client.list_scheduled_events(
            count=100,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
            status="active",
        )
        canceled_events = await client.list_scheduled_events(
            count=100,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
            status="canceled",
        )
    except CalendlyAPIError as exc:
        return f"Error fetching scheduling data: {exc.message}"

    all_events = active_events + canceled_events
    total = len(all_events)
    active_count = len(active_events)
    canceled_count = len(canceled_events)

    if total == 0:
        return f"No events found between {min_start_time[:10]} and {max_start_time[:10]}."

    # Compute average duration
    durations: list[float] = []
    hour_counter: Counter[int] = Counter()
    day_counter: Counter[str] = Counter()

    for event in active_events:
        start_str = event.get("start_time", "")
        end_str = event.get("end_time", "")
        if start_str and end_str:
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                duration_min = (end_dt - start_dt).total_seconds() / 60
                durations.append(duration_min)
                hour_counter[start_dt.hour] += 1
                day_counter[start_dt.strftime("%A")] += 1
            except (ValueError, AttributeError):
                pass

    avg_duration = sum(durations) / len(durations) if durations else 0
    total_hours = sum(durations) / 60

    # Most popular times
    top_hours = hour_counter.most_common(3)
    top_days = day_counter.most_common(3)

    cancellation_rate = (canceled_count / total * 100) if total > 0 else 0

    lines = [
        f"**Scheduling Statistics ({min_start_time[:10]} to {max_start_time[:10]})**\n",
        f"  Total events: {total}",
        f"  Active: {active_count}",
        f"  Canceled: {canceled_count}",
        f"  Cancellation rate: {cancellation_rate:.1f}%",
        "",
        f"  Average duration: {format_duration(int(avg_duration))}",
        f"  Total meeting time: {total_hours:.1f} hours",
    ]

    if top_hours:
        hour_strs = [f"{h}:00 ({c} meetings)" for h, c in top_hours]
        lines.append(f"\n  Most popular hours: {', '.join(hour_strs)}")

    if top_days:
        day_strs = [f"{d} ({c})" for d, c in top_days]
        lines.append(f"  Most popular days: {', '.join(day_strs)}")

    return "\n".join(lines)


async def get_invitee_insights(
    client: CalendlyClient,
    *,
    invitee_email: str,
) -> str:
    """Analyze meeting patterns with a specific contact.

    Searches all recent events for meetings with the given invitee
    and computes summary statistics.

    Parameters
    ----------
    client:
        Initialized Calendly API client.
    invitee_email:
        Email address of the contact to analyze.

    Returns
    -------
    str
        Formatted invitee insights.
    """
    try:
        matches = await client.search_events_by_invitee(invitee_email)
    except CalendlyAPIError as exc:
        return f"Error fetching invitee data: {exc.message}"

    if not matches:
        return f"No events found with invitee '{invitee_email}'."

    # Compute insights
    total_events = len(matches)
    active_events = [e for e in matches if e.get("status") == "active"]
    canceled_events = [e for e in matches if e.get("status") == "canceled"]

    total_duration_min = 0.0
    event_names: Counter[str] = Counter()
    first_meeting: str | None = None
    last_meeting: str | None = None

    sorted_events = sorted(matches, key=lambda e: e.get("start_time", ""))

    for event in sorted_events:
        name = event.get("name", "Untitled")
        event_names[name] += 1

        start_str = event.get("start_time", "")
        end_str = event.get("end_time", "")

        if not first_meeting and start_str:
            first_meeting = start_str
        if start_str:
            last_meeting = start_str

        if start_str and end_str:
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                total_duration_min += (end_dt - start_dt).total_seconds() / 60
            except (ValueError, AttributeError):
                pass

    total_hours = total_duration_min / 60
    cancellation_rate = (len(canceled_events) / total_events * 100) if total_events > 0 else 0

    # Find the invitee name from matched invitees
    invitee_name = invitee_email
    for event in matches:
        for inv in event.get("_matched_invitees", []):
            if (inv.get("email") or "").lower() == invitee_email.lower():
                invitee_name = inv.get("name") or invitee_email
                break

    lines = [
        f"**Invitee Insights: {invitee_name}** ({invitee_email})\n",
        f"  Total meetings: {total_events}",
        f"  Active: {len(active_events)}",
        f"  Canceled: {len(canceled_events)}",
        f"  Cancellation rate: {cancellation_rate:.1f}%",
        f"  Total time spent: {total_hours:.1f} hours ({format_duration(int(total_duration_min))})",
    ]

    if first_meeting:
        lines.append(f"  First meeting: {format_datetime(first_meeting)}")
    if last_meeting:
        lines.append(f"  Most recent: {format_datetime(last_meeting)}")

    if event_names:
        lines.append("\n  Meeting types:")
        for name, count in event_names.most_common(5):
            lines.append(f"    - {name}: {count} time(s)")

    return "\n".join(lines)
