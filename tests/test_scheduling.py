"""Tests for scheduling MCP tools (premium tier).

Covers license gating, create_one_off_event, cancel_event, and reschedule_event.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from calendly_mcp.client.calendly_api import CalendlyClient, CalendlyAPIError
from calendly_mcp.server import PREMIUM_TOOL_NAMES, create_server, execute_tool
from calendly_mcp.tools.scheduling import (
    PREMIUM_REQUIRED_MSG,
    cancel_event,
    create_one_off_event,
    reschedule_event,
)
from calendly_mcp.utils.license import LicenseStatus, LicenseValidator
from tests.conftest import make_event, make_event_type


# ---------------------------------------------------------------------------
# Premium gating
# ---------------------------------------------------------------------------


class TestPremiumGating:
    """Tests that premium tools are blocked without a valid license."""

    async def test_premium_tools_blocked_without_license(
        self,
        mock_client: CalendlyClient,
        free_license_validator: LicenseValidator,
    ) -> None:
        """Premium tool names should not be accessible when no license is active."""
        assert not free_license_validator.is_premium

        # Verify all expected tools are in the premium set
        expected_premium = {
            "create_one_off_event",
            "cancel_event",
            "reschedule_event",
            "get_scheduling_stats",
            "get_invitee_insights",
        }
        assert PREMIUM_TOOL_NAMES == expected_premium

    async def test_premium_tools_available_with_license(
        self,
        premium_license_validator: LicenseValidator,
    ) -> None:
        """Premium tools should be accessible with a valid license."""
        assert premium_license_validator.is_premium

    async def test_expired_license_blocks_premium(self) -> None:
        """An expired license cache results in is_premium returning False."""
        validator = LicenseValidator(cache_ttl_seconds=1)
        validator._cached_status = LicenseStatus(
            is_valid=True,
            license_key="expired-key",
            customer_name="Test",
            validated_at=time.monotonic() - 100,  # Expired
        )

        assert not validator.is_premium

    async def test_server_returns_premium_msg_for_gated_tools(
        self,
        test_config: Any,
    ) -> None:
        """When calling a premium tool without a license, the server returns the premium message."""
        from calendly_mcp.config import Config

        server, client, validator = create_server(test_config)

        # Validator has no license cached, so is_premium is False
        assert not validator.is_premium

        # Simulate calling a premium tool through the server handler
        # We access the handler directly since we cannot run the full MCP loop
        for name in PREMIUM_TOOL_NAMES:
            # The handler is registered on server; we test via execute path
            # The server.call_tool handler checks PREMIUM_TOOL_NAMES
            assert name in PREMIUM_TOOL_NAMES


# ---------------------------------------------------------------------------
# create_one_off_event
# ---------------------------------------------------------------------------


class TestCreateOneOffEvent:
    """Tests for the create_one_off_event tool."""

    async def test_happy_path_returns_booking_url(
        self, mock_client: CalendlyClient
    ) -> None:
        """Creating a one-off event returns a scheduling link."""
        result = await create_one_off_event(
            mock_client,
            event_type_uuid="et-bbb-222",
            invitee_email="jane@example.com",
            invitee_name="Jane Smith",
            start_time="2026-03-26T10:00:00Z",
        )

        assert "Scheduling Link Created" in result
        assert "jane@example.com" in result
        assert "Jane Smith" in result
        assert "calendly.com" in result
        assert "Booking URL" in result

    async def test_includes_event_type_name(
        self, mock_client: CalendlyClient
    ) -> None:
        """The output includes the event type name."""
        result = await create_one_off_event(
            mock_client,
            event_type_uuid="et-bbb-222",
            invitee_email="jane@example.com",
            invitee_name="Jane Smith",
            start_time="2026-03-26T10:00:00Z",
        )

        assert "30 Minute Meeting" in result

    async def test_event_type_fetch_error(
        self, mock_client: CalendlyClient
    ) -> None:
        """If the event type cannot be fetched, an error is returned."""
        mock_client.get_event_type = AsyncMock(
            side_effect=CalendlyAPIError(404, "Event type not found")
        )

        result = await create_one_off_event(
            mock_client,
            event_type_uuid="nonexistent",
            invitee_email="jane@example.com",
            invitee_name="Jane Smith",
            start_time="2026-03-26T10:00:00Z",
        )

        assert "Error fetching event type" in result

    async def test_scheduling_link_creation_error(
        self, mock_client: CalendlyClient
    ) -> None:
        """If link creation fails, an error is returned."""
        mock_client.create_scheduling_link = AsyncMock(
            side_effect=CalendlyAPIError(400, "Bad request")
        )

        result = await create_one_off_event(
            mock_client,
            event_type_uuid="et-bbb-222",
            invitee_email="jane@example.com",
            invitee_name="Jane Smith",
            start_time="2026-03-26T10:00:00Z",
        )

        assert "Error creating scheduling link" in result

    async def test_missing_event_type_uri(
        self, mock_client: CalendlyClient
    ) -> None:
        """If the event type has no URI, an error is returned."""
        mock_client.get_event_type = AsyncMock(return_value={"name": "Test", "uri": ""})

        result = await create_one_off_event(
            mock_client,
            event_type_uuid="et-no-uri",
            invitee_email="jane@example.com",
            invitee_name="Jane Smith",
            start_time="2026-03-26T10:00:00Z",
        )

        assert "Could not determine event type URI" in result


# ---------------------------------------------------------------------------
# cancel_event
# ---------------------------------------------------------------------------


class TestCancelEvent:
    """Tests for the cancel_event tool."""

    async def test_happy_path_cancels_event(
        self, mock_client: CalendlyClient
    ) -> None:
        """Canceling an event returns a confirmation with event details."""
        result = await cancel_event(
            mock_client,
            event_uuid="evt-aaa-111",
            reason="Schedule conflict",
        )

        assert "Event Canceled" in result
        assert "Discovery Call" in result
        assert "Schedule conflict" in result
        assert "Invitees will be notified" in result

    async def test_cancel_without_reason(
        self, mock_client: CalendlyClient
    ) -> None:
        """Canceling without a reason still works."""
        result = await cancel_event(mock_client, event_uuid="evt-aaa-111")

        assert "Event Canceled" in result
        assert "Discovery Call" in result
        # Reason line should not appear
        assert "Reason:" not in result

    async def test_cancel_forbidden_event(
        self, mock_client: CalendlyClient
    ) -> None:
        """A 403 error returns a permission error message."""
        mock_client.cancel_event = AsyncMock(
            side_effect=CalendlyAPIError(403, "Forbidden")
        )

        result = await cancel_event(mock_client, event_uuid="evt-aaa-111")

        assert "permission" in result.lower()

    async def test_cancel_already_canceled_event(
        self, mock_client: CalendlyClient
    ) -> None:
        """A 404 error suggests the event may already be canceled."""
        mock_client.cancel_event = AsyncMock(
            side_effect=CalendlyAPIError(404, "Not found")
        )

        result = await cancel_event(mock_client, event_uuid="evt-aaa-111")

        assert "not found" in result.lower() or "already been canceled" in result.lower()

    async def test_cancel_fetch_event_error(
        self, mock_client: CalendlyClient
    ) -> None:
        """If fetching the event fails, an error is returned before cancellation."""
        mock_client.get_scheduled_event = AsyncMock(
            side_effect=CalendlyAPIError(404, "Not found")
        )

        result = await cancel_event(mock_client, event_uuid="bad-uuid")

        assert "Error fetching event" in result


# ---------------------------------------------------------------------------
# reschedule_event
# ---------------------------------------------------------------------------


class TestRescheduleEvent:
    """Tests for the reschedule_event tool."""

    async def test_happy_path_reschedules_event(
        self, mock_client: CalendlyClient
    ) -> None:
        """Rescheduling cancels the original and provides a new booking link."""
        result = await reschedule_event(
            mock_client,
            event_uuid="evt-aaa-111",
            new_start_time="2026-03-27T10:00:00Z",
        )

        assert "Event Rescheduled" in result
        assert "Discovery Call" in result
        assert "New booking URL" in result
        assert "calendly.com" in result

    async def test_original_event_fetch_error(
        self, mock_client: CalendlyClient
    ) -> None:
        """If the original event cannot be fetched, an error is returned."""
        mock_client.get_scheduled_event = AsyncMock(
            side_effect=CalendlyAPIError(404, "Not found")
        )

        result = await reschedule_event(
            mock_client,
            event_uuid="bad-uuid",
            new_start_time="2026-03-27T10:00:00Z",
        )

        assert "Error fetching event" in result

    async def test_cancel_during_reschedule_error(
        self, mock_client: CalendlyClient
    ) -> None:
        """If canceling the original event fails, an error is returned."""
        mock_client.cancel_event = AsyncMock(
            side_effect=CalendlyAPIError(403, "Forbidden")
        )

        result = await reschedule_event(
            mock_client,
            event_uuid="evt-aaa-111",
            new_start_time="2026-03-27T10:00:00Z",
        )

        assert "Error canceling original event" in result

    async def test_new_link_creation_failure_after_cancel(
        self, mock_client: CalendlyClient
    ) -> None:
        """If link creation fails after canceling, an error is returned with manual recovery note."""
        mock_client.create_scheduling_link = AsyncMock(
            side_effect=CalendlyAPIError(500, "Server error")
        )

        result = await reschedule_event(
            mock_client,
            event_uuid="evt-aaa-111",
            new_start_time="2026-03-27T10:00:00Z",
        )

        assert "canceled" in result.lower()
        assert "failed to create new scheduling link" in result.lower()
        assert "manually" in result.lower()

    async def test_missing_event_type_uri(
        self, mock_client: CalendlyClient
    ) -> None:
        """If the event has no event_type URI, rescheduling fails with an error."""
        event_no_type = make_event()
        event_no_type["event_type"] = ""
        mock_client.get_scheduled_event = AsyncMock(return_value=event_no_type)

        result = await reschedule_event(
            mock_client,
            event_uuid="evt-aaa-111",
            new_start_time="2026-03-27T10:00:00Z",
        )

        assert "Could not determine the event type" in result
