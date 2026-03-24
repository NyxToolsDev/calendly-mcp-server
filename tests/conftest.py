"""Shared pytest fixtures for calendly-mcp tests.

Provides mock Calendly API responses, a mock CalendlyClient, and sample
data factories for events, event types, invitees, and availability.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from calendly_mcp.client.calendly_api import CalendlyClient
from calendly_mcp.config import Config
from calendly_mcp.utils.license import LicenseStatus, LicenseValidator


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------

USER_URI = "https://api.calendly.com/users/TESTUSER123"


def make_event(
    *,
    uuid: str = "evt-aaa-111",
    name: str = "Discovery Call",
    start_time: str = "2026-03-25T14:00:00.000000Z",
    end_time: str = "2026-03-25T14:30:00.000000Z",
    status: str = "active",
    event_type: str = "https://api.calendly.com/event_types/et-bbb-222",
    location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sample scheduled event dict matching Calendly API shape."""
    return {
        "uri": f"https://api.calendly.com/scheduled_events/{uuid}",
        "name": name,
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "event_type": event_type,
        "location": location or {"type": "zoom", "join_url": "https://zoom.us/j/123"},
        "created_at": "2026-03-20T10:00:00.000000Z",
        "updated_at": "2026-03-20T10:00:00.000000Z",
    }


def make_invitee(
    *,
    name: str = "John Doe",
    email: str = "john@example.com",
    status: str = "active",
) -> dict[str, Any]:
    """Build a sample invitee dict matching Calendly API shape."""
    return {
        "uri": f"https://api.calendly.com/invitees/{email.replace('@', '-at-')}",
        "name": name,
        "email": email,
        "status": status,
        "created_at": "2026-03-20T10:00:00.000000Z",
        "updated_at": "2026-03-20T10:00:00.000000Z",
    }


def make_event_type(
    *,
    uuid: str = "et-bbb-222",
    name: str = "30 Minute Meeting",
    duration: int = 30,
    slug: str = "30-minute-meeting",
    active: bool = True,
    kind: str = "solo",
) -> dict[str, Any]:
    """Build a sample event type dict matching Calendly API shape."""
    return {
        "uri": f"https://api.calendly.com/event_types/{uuid}",
        "name": name,
        "duration": duration,
        "slug": slug,
        "active": active,
        "kind": kind,
        "scheduling_url": f"https://calendly.com/testuser/{slug}",
        "color": "#0069ff",
        "description_plain": "A quick chat to discuss your needs.",
        "custom_questions": [],
        "secret": False,
    }


def make_busy_time(
    *,
    start_time: str = "2026-03-25T09:00:00.000000Z",
    end_time: str = "2026-03-25T09:30:00.000000Z",
    event_type: str = "calendly",
) -> dict[str, Any]:
    """Build a sample busy time dict."""
    return {
        "type": event_type,
        "start_time": start_time,
        "end_time": end_time,
    }


def make_availability_schedule(
    *,
    name: str = "Working Hours",
    timezone: str = "America/New_York",
) -> dict[str, Any]:
    """Build a sample availability schedule dict."""
    return {
        "name": name,
        "timezone": timezone,
        "rules": [
            {
                "type": "wday",
                "wday": "monday",
                "intervals": [{"from": "09:00", "to": "17:00"}],
            },
            {
                "type": "wday",
                "wday": "tuesday",
                "intervals": [{"from": "09:00", "to": "17:00"}],
            },
            {
                "type": "wday",
                "wday": "wednesday",
                "intervals": [{"from": "09:00", "to": "17:00"}],
            },
            {
                "type": "wday",
                "wday": "thursday",
                "intervals": [{"from": "09:00", "to": "17:00"}],
            },
            {
                "type": "wday",
                "wday": "friday",
                "intervals": [{"from": "09:00", "to": "17:00"}],
            },
            {
                "type": "wday",
                "wday": "saturday",
                "intervals": [],
            },
            {
                "type": "wday",
                "wday": "sunday",
                "intervals": [],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_config() -> Config:
    """Return a Config with a dummy access token for testing."""
    return Config(
        calendly_access_token="test-token-12345",
        license_key=None,
        log_level="DEBUG",
        calendly_base_url="https://api.calendly.com",
    )


@pytest.fixture()
def mock_client(test_config: Config) -> CalendlyClient:
    """Return a CalendlyClient with all API methods mocked.

    Each method is an ``AsyncMock`` that returns sensible defaults.
    Override return values in individual tests as needed.
    """
    client = CalendlyClient(test_config)

    # Patch the user URI so we skip the /users/me call
    client._user_uri = USER_URI

    # Mock HTTP-backed methods
    client.list_scheduled_events = AsyncMock(return_value=[make_event()])
    client.get_scheduled_event = AsyncMock(return_value=make_event())
    client.get_event_invitees = AsyncMock(return_value=[make_invitee()])
    client.list_event_types = AsyncMock(return_value=[make_event_type()])
    client.get_event_type = AsyncMock(return_value=make_event_type())
    client.get_user_availability_schedules = AsyncMock(
        return_value=[make_availability_schedule()]
    )
    client.get_user_busy_times = AsyncMock(return_value=[make_busy_time()])
    client.search_events_by_invitee = AsyncMock(
        return_value=[{**make_event(), "_matched_invitees": [make_invitee()]}]
    )
    client.create_scheduling_link = AsyncMock(return_value={
        "booking_url": "https://calendly.com/d/abc-123/30-minute-meeting",
        "owner_type": "EventType",
    })
    client.cancel_event = AsyncMock(return_value={})

    return client


@pytest.fixture()
def sample_events() -> list[dict[str, Any]]:
    """Return a list of sample events for testing."""
    return [
        make_event(uuid="evt-1", name="Standup", start_time="2026-03-25T09:00:00Z"),
        make_event(uuid="evt-2", name="Design Review", start_time="2026-03-25T11:00:00Z"),
        make_event(
            uuid="evt-3",
            name="Canceled Call",
            start_time="2026-03-25T15:00:00Z",
            status="canceled",
        ),
    ]


@pytest.fixture()
def sample_event_types() -> list[dict[str, Any]]:
    """Return a list of sample event types for testing."""
    return [
        make_event_type(uuid="et-1", name="15 Minute Chat", duration=15, slug="15-min"),
        make_event_type(uuid="et-2", name="30 Minute Meeting", duration=30, slug="30-min"),
        make_event_type(uuid="et-3", name="60 Minute Deep Dive", duration=60, slug="60-min"),
    ]


@pytest.fixture()
def premium_license_validator() -> LicenseValidator:
    """Return a LicenseValidator with a valid cached premium license."""
    validator = LicenseValidator(cache_ttl_seconds=86400)
    validator._cached_status = LicenseStatus(
        is_valid=True,
        license_key="premium-test-key",
        customer_name="Test Customer",
        validated_at=time.monotonic(),
    )
    return validator


@pytest.fixture()
def free_license_validator() -> LicenseValidator:
    """Return a LicenseValidator with no premium license."""
    return LicenseValidator(cache_ttl_seconds=86400)
