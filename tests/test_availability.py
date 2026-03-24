"""Tests for availability MCP tools.

Covers check_availability and get_busy_times.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.tools.availability import check_availability, get_busy_times
from tests.conftest import make_availability_schedule, make_busy_time


# ---------------------------------------------------------------------------
# check_availability
# ---------------------------------------------------------------------------


class TestCheckAvailability:
    """Tests for the check_availability tool."""

    async def test_happy_path_shows_schedules(
        self, mock_client: CalendlyClient
    ) -> None:
        """Availability check returns schedule rules and busy times."""
        result = await check_availability(
            mock_client,
            date_range_start="2026-03-25T00:00:00Z",
            date_range_end="2026-03-26T00:00:00Z",
        )

        assert "Availability Schedules" in result
        assert "Working Hours" in result
        assert "America/New_York" in result
        assert "Monday" in result
        assert "09:00 - 17:00" in result

    async def test_shows_busy_times_within_range(
        self, mock_client: CalendlyClient
    ) -> None:
        """Busy times for the requested range are included in the output."""
        result = await check_availability(
            mock_client,
            date_range_start="2026-03-25T00:00:00Z",
            date_range_end="2026-03-26T00:00:00Z",
        )

        assert "Busy times" in result

    async def test_no_schedules_returns_friendly_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """When no availability schedules exist, a helpful message is shown."""
        mock_client.get_user_availability_schedules = AsyncMock(return_value=[])

        result = await check_availability(
            mock_client,
            date_range_start="2026-03-25T00:00:00Z",
            date_range_end="2026-03-26T00:00:00Z",
        )

        assert result == "No availability schedules found."

    async def test_no_slots_shows_all_busy(
        self, mock_client: CalendlyClient
    ) -> None:
        """When there are no availability intervals (e.g., weekend), 'No availability' is shown."""
        weekend_schedule = make_availability_schedule()
        # Override rules so only a day with no intervals appears
        weekend_schedule["rules"] = [
            {"type": "wday", "wday": "saturday", "intervals": []},
        ]
        mock_client.get_user_availability_schedules = AsyncMock(
            return_value=[weekend_schedule]
        )

        result = await check_availability(
            mock_client,
            date_range_start="2026-03-28T00:00:00Z",
            date_range_end="2026-03-29T00:00:00Z",
        )

        assert "No availability" in result

    async def test_schedule_api_error(self, mock_client: CalendlyClient) -> None:
        """API errors are returned as user-facing error strings."""
        mock_client.get_user_availability_schedules = AsyncMock(
            side_effect=CalendlyAPIError(401, "Unauthorized")
        )

        result = await check_availability(
            mock_client,
            date_range_start="2026-03-25T00:00:00Z",
            date_range_end="2026-03-26T00:00:00Z",
        )

        assert "Error checking availability" in result
        assert "Unauthorized" in result

    async def test_busy_times_fetch_failure_does_not_break(
        self, mock_client: CalendlyClient
    ) -> None:
        """If busy times fetch fails, the schedule info is still returned."""
        mock_client.get_user_busy_times = AsyncMock(
            side_effect=CalendlyAPIError(500, "Internal error")
        )

        result = await check_availability(
            mock_client,
            date_range_start="2026-03-25T00:00:00Z",
            date_range_end="2026-03-26T00:00:00Z",
        )

        # Schedules still present, busy times section missing
        assert "Working Hours" in result
        assert "Busy times" not in result

    async def test_multiple_schedules(self, mock_client: CalendlyClient) -> None:
        """Multiple availability schedules are displayed."""
        schedule1 = make_availability_schedule(name="Working Hours")
        schedule2 = make_availability_schedule(name="After Hours")
        schedule2["timezone"] = "Europe/London"
        mock_client.get_user_availability_schedules = AsyncMock(
            return_value=[schedule1, schedule2]
        )

        result = await check_availability(
            mock_client,
            date_range_start="2026-03-25T00:00:00Z",
            date_range_end="2026-03-26T00:00:00Z",
        )

        assert "Working Hours" in result
        assert "After Hours" in result
        assert "Europe/London" in result


# ---------------------------------------------------------------------------
# get_busy_times
# ---------------------------------------------------------------------------


class TestGetBusyTimes:
    """Tests for the get_busy_times tool."""

    async def test_happy_path_returns_busy_periods(
        self, mock_client: CalendlyClient
    ) -> None:
        """Busy times returns a formatted list of busy periods."""
        result = await get_busy_times(
            mock_client,
            start_time="2026-03-25T00:00:00Z",
            end_time="2026-03-26T00:00:00Z",
        )

        assert "Busy times" in result
        assert "Total busy periods: 1" in result

    async def test_no_busy_times_shows_free_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """When no busy times exist, a 'you are free' message is returned."""
        mock_client.get_user_busy_times = AsyncMock(return_value=[])

        result = await get_busy_times(
            mock_client,
            start_time="2026-03-25T00:00:00Z",
            end_time="2026-03-26T00:00:00Z",
        )

        assert "No busy times found" in result
        assert "free" in result.lower()

    async def test_multiple_busy_periods(self, mock_client: CalendlyClient) -> None:
        """Multiple busy periods are all displayed with a count."""
        busy_times = [
            make_busy_time(start_time="2026-03-25T09:00:00Z", end_time="2026-03-25T09:30:00Z"),
            make_busy_time(start_time="2026-03-25T11:00:00Z", end_time="2026-03-25T12:00:00Z"),
            make_busy_time(start_time="2026-03-25T14:00:00Z", end_time="2026-03-25T15:00:00Z"),
        ]
        mock_client.get_user_busy_times = AsyncMock(return_value=busy_times)

        result = await get_busy_times(
            mock_client,
            start_time="2026-03-25T00:00:00Z",
            end_time="2026-03-26T00:00:00Z",
        )

        assert "Total busy periods: 3" in result

    async def test_api_error_returns_error_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """API errors are returned as user-facing error strings."""
        mock_client.get_user_busy_times = AsyncMock(
            side_effect=CalendlyAPIError(429, "Rate limited")
        )

        result = await get_busy_times(
            mock_client,
            start_time="2026-03-25T00:00:00Z",
            end_time="2026-03-26T00:00:00Z",
        )

        assert "Error fetching busy times" in result
        assert "Rate limited" in result

    async def test_date_range_shown_in_header(
        self, mock_client: CalendlyClient
    ) -> None:
        """The date range is shown in the output header."""
        result = await get_busy_times(
            mock_client,
            start_time="2026-03-25T00:00:00Z",
            end_time="2026-03-26T00:00:00Z",
        )

        assert "2026-03-25" in result
        assert "2026-03-26" in result
