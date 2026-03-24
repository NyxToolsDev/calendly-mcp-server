"""Tests for event-related MCP tools.

Covers list_upcoming_events, get_event_details, and search_events.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.tools.events import (
    get_event_details,
    list_upcoming_events,
    search_events,
)
from tests.conftest import make_event, make_invitee


# ---------------------------------------------------------------------------
# list_upcoming_events
# ---------------------------------------------------------------------------


class TestListUpcomingEvents:
    """Tests for the list_upcoming_events tool."""

    async def test_happy_path_returns_formatted_events(
        self, mock_client: CalendlyClient
    ) -> None:
        """Listing events returns a formatted string with event summaries."""
        result = await list_upcoming_events(mock_client, count=10)

        assert "Found 1 upcoming event(s):" in result
        assert "Discovery Call" in result
        assert "evt-aaa-111" in result

    async def test_multiple_events(self, mock_client: CalendlyClient) -> None:
        """Multiple events are all included in the output."""
        events = [
            make_event(uuid="evt-1", name="Morning Standup"),
            make_event(uuid="evt-2", name="Afternoon Review"),
        ]
        mock_client.list_scheduled_events = AsyncMock(return_value=events)

        result = await list_upcoming_events(mock_client, count=10)

        assert "Found 2 upcoming event(s):" in result
        assert "Morning Standup" in result
        assert "Afternoon Review" in result

    async def test_empty_results(self, mock_client: CalendlyClient) -> None:
        """When no events are found, a friendly message is returned."""
        mock_client.list_scheduled_events = AsyncMock(return_value=[])

        result = await list_upcoming_events(mock_client, count=10)

        assert result == "No upcoming events found."

    async def test_status_filter(self, mock_client: CalendlyClient) -> None:
        """The status filter is passed through to the API client."""
        mock_client.list_scheduled_events = AsyncMock(return_value=[])

        await list_upcoming_events(mock_client, count=5, status="canceled")

        mock_client.list_scheduled_events.assert_called_once()
        call_kwargs = mock_client.list_scheduled_events.call_args
        assert call_kwargs.kwargs.get("status") == "canceled" or \
            call_kwargs[1].get("status") == "canceled"

    async def test_time_range_filter(self, mock_client: CalendlyClient) -> None:
        """Time range parameters are passed through to the API client."""
        mock_client.list_scheduled_events = AsyncMock(return_value=[])

        await list_upcoming_events(
            mock_client,
            count=10,
            min_start_time="2026-03-25T00:00:00Z",
            max_start_time="2026-03-26T00:00:00Z",
        )

        call_kwargs = mock_client.list_scheduled_events.call_args[1]
        assert call_kwargs["min_start_time"] == "2026-03-25T00:00:00Z"
        assert call_kwargs["max_start_time"] == "2026-03-26T00:00:00Z"

    async def test_defaults_min_start_to_now(
        self, mock_client: CalendlyClient
    ) -> None:
        """When no min_start_time is provided, it defaults to roughly now."""
        mock_client.list_scheduled_events = AsyncMock(return_value=[])

        await list_upcoming_events(mock_client, count=10)

        call_kwargs = mock_client.list_scheduled_events.call_args[1]
        # min_start_time should be set (defaulted to current time)
        assert call_kwargs["min_start_time"] is not None
        assert "2026" in call_kwargs["min_start_time"]

    async def test_api_error_returns_error_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """API errors are caught and returned as a user-facing error string."""
        mock_client.list_scheduled_events = AsyncMock(
            side_effect=CalendlyAPIError(401, "Unauthorized")
        )

        result = await list_upcoming_events(mock_client, count=10)

        assert "Error fetching events" in result
        assert "Unauthorized" in result

    async def test_invitee_fetch_failure_still_returns_event(
        self, mock_client: CalendlyClient
    ) -> None:
        """If invitee fetching fails, the event is still included without invitees."""
        mock_client.get_event_invitees = AsyncMock(
            side_effect=CalendlyAPIError(500, "Internal error")
        )

        result = await list_upcoming_events(mock_client, count=10)

        assert "Discovery Call" in result
        # Should not contain invitee info since it failed
        assert "John Doe" not in result


# ---------------------------------------------------------------------------
# get_event_details
# ---------------------------------------------------------------------------


class TestGetEventDetails:
    """Tests for the get_event_details tool."""

    async def test_returns_full_details(self, mock_client: CalendlyClient) -> None:
        """Getting event details returns a comprehensive summary."""
        result = await get_event_details(mock_client, event_uuid="evt-aaa-111")

        assert "Discovery Call" in result
        assert "John Doe" in result
        assert "john@example.com" in result
        assert "evt-aaa-111" in result

    async def test_includes_extra_metadata(self, mock_client: CalendlyClient) -> None:
        """Details include created_at and event type ID."""
        result = await get_event_details(mock_client, event_uuid="evt-aaa-111")

        assert "Created:" in result
        assert "Event Type ID:" in result

    async def test_includes_cancellation_info(
        self, mock_client: CalendlyClient
    ) -> None:
        """Canceled events include cancellation reason and canceler."""
        canceled_event = make_event(status="canceled")
        canceled_event["cancellation"] = {
            "reason": "Schedule conflict",
            "canceled_by": "Organizer",
        }
        mock_client.get_scheduled_event = AsyncMock(return_value=canceled_event)

        result = await get_event_details(mock_client, event_uuid="evt-cancel")

        assert "Schedule conflict" in result
        assert "Canceled by:" in result

    async def test_api_error_returns_error_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """API errors are returned as a user-facing error string."""
        mock_client.get_scheduled_event = AsyncMock(
            side_effect=CalendlyAPIError(404, "Not found")
        )

        result = await get_event_details(mock_client, event_uuid="bad-uuid")

        assert "Error fetching event details" in result
        assert "Not found" in result


# ---------------------------------------------------------------------------
# search_events
# ---------------------------------------------------------------------------


class TestSearchEvents:
    """Tests for the search_events tool."""

    async def test_happy_path_finds_matching_events(
        self, mock_client: CalendlyClient
    ) -> None:
        """Searching by invitee returns matching events."""
        result = await search_events(mock_client, query="john@example.com")

        assert "Found 1 event(s) matching" in result
        assert "john@example.com" in result

    async def test_no_matches_returns_friendly_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """When no events match, a friendly message is returned."""
        mock_client.search_events_by_invitee = AsyncMock(return_value=[])

        result = await search_events(mock_client, query="nobody@example.com")

        assert "No events found matching" in result
        assert "nobody@example.com" in result

    async def test_multiple_matches(self, mock_client: CalendlyClient) -> None:
        """Multiple matching events are all displayed."""
        match1 = {**make_event(uuid="evt-1", name="Call 1"), "_matched_invitees": [make_invitee()]}
        match2 = {**make_event(uuid="evt-2", name="Call 2"), "_matched_invitees": [make_invitee()]}
        mock_client.search_events_by_invitee = AsyncMock(return_value=[match1, match2])

        result = await search_events(mock_client, query="john")

        assert "Found 2 event(s) matching" in result
        assert "Call 1" in result
        assert "Call 2" in result

    async def test_time_filters_passed_through(
        self, mock_client: CalendlyClient
    ) -> None:
        """Time range filters are forwarded to the search client method."""
        mock_client.search_events_by_invitee = AsyncMock(return_value=[])

        await search_events(
            mock_client,
            query="test",
            min_start_time="2026-03-01T00:00:00Z",
            max_start_time="2026-03-31T23:59:59Z",
        )

        call_kwargs = mock_client.search_events_by_invitee.call_args[1]
        assert call_kwargs["min_start_time"] == "2026-03-01T00:00:00Z"
        assert call_kwargs["max_start_time"] == "2026-03-31T23:59:59Z"

    async def test_api_error_returns_error_message(
        self, mock_client: CalendlyClient
    ) -> None:
        """API errors during search are returned as user-facing error strings."""
        mock_client.search_events_by_invitee = AsyncMock(
            side_effect=CalendlyAPIError(500, "Server error")
        )

        result = await search_events(mock_client, query="john")

        assert "Error searching events" in result
        assert "Server error" in result

    async def test_partial_name_match(self, mock_client: CalendlyClient) -> None:
        """Search query is forwarded as-is for partial matching."""
        mock_client.search_events_by_invitee = AsyncMock(return_value=[])

        await search_events(mock_client, query="joh")

        mock_client.search_events_by_invitee.assert_called_once_with(
            "joh",
            min_start_time=None,
            max_start_time=None,
        )
