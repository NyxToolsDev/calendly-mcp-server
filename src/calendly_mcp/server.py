"""MCP server setup and tool registration.

Initializes the Calendly MCP server using the official MCP Python SDK,
registers all tools with JSON Schema input definitions, and handles
tool execution with proper error handling and license gating.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from calendly_mcp.client.calendly_api import CalendlyClient
from calendly_mcp.config import Config, load_config
from calendly_mcp.tools import availability, analytics, event_types, events, scheduling
from calendly_mcp.utils.license import LicenseValidator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions with JSON Schema inputs
# ---------------------------------------------------------------------------

FREE_TOOLS: list[Tool] = [
    Tool(
        name="list_upcoming_events",
        description=(
            "List upcoming scheduled Calendly events. "
            "Returns event name, time, invitees, location, and status."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of events to return (1-100)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
                "min_start_time": {
                    "type": "string",
                    "description": "ISO 8601 lower bound for event start time (defaults to now)",
                },
                "max_start_time": {
                    "type": "string",
                    "description": "ISO 8601 upper bound for event start time",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status",
                    "enum": ["active", "canceled"],
                },
            },
        },
    ),
    Tool(
        name="get_event_details",
        description=(
            "Get full details of a specific Calendly event including "
            "invitees, location, conferencing details, and cancellation info."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "event_uuid": {
                    "type": "string",
                    "description": "UUID of the event to retrieve",
                },
            },
            "required": ["event_uuid"],
        },
    ),
    Tool(
        name="search_events",
        description=(
            "Search Calendly events by invitee name or email address. "
            "Performs a case-insensitive partial match."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Name or email to search for",
                },
                "min_start_time": {
                    "type": "string",
                    "description": "ISO 8601 lower bound for event start time",
                },
                "max_start_time": {
                    "type": "string",
                    "description": "ISO 8601 upper bound for event start time",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="check_availability",
        description=(
            "Check available time slots from your Calendly availability "
            "schedules and show busy periods for a date range."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "date_range_start": {
                    "type": "string",
                    "description": "ISO 8601 start of the date range",
                },
                "date_range_end": {
                    "type": "string",
                    "description": "ISO 8601 end of the date range",
                },
            },
            "required": ["date_range_start", "date_range_end"],
        },
    ),
    Tool(
        name="get_busy_times",
        description=(
            "Get busy/unavailable time periods for a date range. "
            "Shows all times when you are not available for meetings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "ISO 8601 start of the date range",
                },
                "end_time": {
                    "type": "string",
                    "description": "ISO 8601 end of the date range",
                },
            },
            "required": ["start_time", "end_time"],
        },
    ),
    Tool(
        name="list_event_types",
        description=(
            "List all configured Calendly event types with name, "
            "duration, slug, and availability status."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_event_type_details",
        description=(
            "Get detailed configuration of a specific Calendly event type "
            "including description, booking URL, custom questions, and visibility."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "event_type_uuid": {
                    "type": "string",
                    "description": "UUID of the event type to retrieve",
                },
            },
            "required": ["event_type_uuid"],
        },
    ),
]

PREMIUM_TOOLS: list[Tool] = [
    Tool(
        name="create_one_off_event",
        description=(
            "[Premium] Create a single-use scheduling link to book a meeting. "
            "Generates a link that the invitee can use to confirm the booking."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "event_type_uuid": {
                    "type": "string",
                    "description": "UUID of the event type to schedule",
                },
                "invitee_email": {
                    "type": "string",
                    "description": "Email address of the invitee",
                },
                "invitee_name": {
                    "type": "string",
                    "description": "Full name of the invitee",
                },
                "start_time": {
                    "type": "string",
                    "description": "Desired start time in ISO 8601 format",
                },
            },
            "required": ["event_type_uuid", "invitee_email", "invitee_name", "start_time"],
        },
    ),
    Tool(
        name="cancel_event",
        description=(
            "[Premium] Cancel an existing scheduled Calendly event. "
            "Invitees will be notified of the cancellation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "event_uuid": {
                    "type": "string",
                    "description": "UUID of the event to cancel",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional cancellation reason shown to invitees",
                },
            },
            "required": ["event_uuid"],
        },
    ),
    Tool(
        name="reschedule_event",
        description=(
            "[Premium] Reschedule an existing event to a new time. "
            "Cancels the original and creates a new booking link."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "event_uuid": {
                    "type": "string",
                    "description": "UUID of the event to reschedule",
                },
                "new_start_time": {
                    "type": "string",
                    "description": "New desired start time in ISO 8601 format",
                },
            },
            "required": ["event_uuid", "new_start_time"],
        },
    ),
    Tool(
        name="get_scheduling_stats",
        description=(
            "[Premium] Get scheduling analytics for a date range including "
            "total meetings, average duration, popular times, and cancellation rate."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "min_start_time": {
                    "type": "string",
                    "description": "ISO 8601 start of the analysis period",
                },
                "max_start_time": {
                    "type": "string",
                    "description": "ISO 8601 end of the analysis period",
                },
            },
            "required": ["min_start_time", "max_start_time"],
        },
    ),
    Tool(
        name="get_invitee_insights",
        description=(
            "[Premium] Analyze meeting patterns with a specific contact. "
            "Shows meeting history, total time spent, frequency, and meeting types."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "invitee_email": {
                    "type": "string",
                    "description": "Email address of the contact to analyze",
                },
            },
            "required": ["invitee_email"],
        },
    ),
]

# Set of premium tool names for quick lookup
PREMIUM_TOOL_NAMES = frozenset(t.name for t in PREMIUM_TOOLS)


# ---------------------------------------------------------------------------
# Tool execution dispatcher
# ---------------------------------------------------------------------------

async def execute_tool(
    name: str,
    arguments: dict[str, Any],
    client: CalendlyClient,
) -> str:
    """Dispatch a tool call to the appropriate handler function.

    Parameters
    ----------
    name:
        The tool name as registered with the MCP server.
    arguments:
        The validated input arguments from the MCP call.
    client:
        Initialized Calendly API client.

    Returns
    -------
    str
        The formatted result text.

    Raises
    ------
    ValueError
        If the tool name is unknown.
    """
    # Free tier tools
    if name == "list_upcoming_events":
        return await events.list_upcoming_events(
            client,
            count=arguments.get("count", 10),
            min_start_time=arguments.get("min_start_time"),
            max_start_time=arguments.get("max_start_time"),
            status=arguments.get("status"),
        )

    if name == "get_event_details":
        return await events.get_event_details(
            client,
            event_uuid=arguments["event_uuid"],
        )

    if name == "search_events":
        return await events.search_events(
            client,
            query=arguments["query"],
            min_start_time=arguments.get("min_start_time"),
            max_start_time=arguments.get("max_start_time"),
        )

    if name == "check_availability":
        return await availability.check_availability(
            client,
            date_range_start=arguments["date_range_start"],
            date_range_end=arguments["date_range_end"],
        )

    if name == "get_busy_times":
        return await availability.get_busy_times(
            client,
            start_time=arguments["start_time"],
            end_time=arguments["end_time"],
        )

    if name == "list_event_types":
        return await event_types.list_event_types(client)

    if name == "get_event_type_details":
        return await event_types.get_event_type_details(
            client,
            event_type_uuid=arguments["event_type_uuid"],
        )

    # Premium tier tools
    if name == "create_one_off_event":
        return await scheduling.create_one_off_event(
            client,
            event_type_uuid=arguments["event_type_uuid"],
            invitee_email=arguments["invitee_email"],
            invitee_name=arguments["invitee_name"],
            start_time=arguments["start_time"],
        )

    if name == "cancel_event":
        return await scheduling.cancel_event(
            client,
            event_uuid=arguments["event_uuid"],
            reason=arguments.get("reason"),
        )

    if name == "reschedule_event":
        return await scheduling.reschedule_event(
            client,
            event_uuid=arguments["event_uuid"],
            new_start_time=arguments["new_start_time"],
        )

    if name == "get_scheduling_stats":
        return await analytics.get_scheduling_stats(
            client,
            min_start_time=arguments["min_start_time"],
            max_start_time=arguments["max_start_time"],
        )

    if name == "get_invitee_insights":
        return await analytics.get_invitee_insights(
            client,
            invitee_email=arguments["invitee_email"],
        )

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def create_server(config: Config) -> tuple[Server, CalendlyClient, LicenseValidator]:
    """Create and configure the MCP server instance.

    Registers tool listing and tool execution handlers. Premium tools
    are only listed and executable when a valid license is present.

    Parameters
    ----------
    config:
        Validated server configuration.

    Returns
    -------
    tuple
        The MCP Server instance, CalendlyClient, and LicenseValidator.
    """
    server = Server("calendly-mcp")
    client = CalendlyClient(config)
    license_validator = LicenseValidator(cache_ttl_seconds=config.license_cache_ttl_seconds)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        """Return the list of available tools based on license status."""
        tools = list(FREE_TOOLS)
        if license_validator.is_premium:
            tools.extend(PREMIUM_TOOLS)
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        """Execute a tool and return the result as text content."""
        arguments = arguments or {}

        # Gate premium tools behind license validation
        if name in PREMIUM_TOOL_NAMES and not license_validator.is_premium:
            return [TextContent(
                type="text",
                text=scheduling.PREMIUM_REQUIRED_MSG,
            )]

        try:
            result = await execute_tool(name, arguments, client)
        except ValueError as exc:
            result = f"Error: {exc}"
        except Exception:
            logger.exception("Unexpected error executing tool '%s'", name)
            result = (
                f"An unexpected error occurred while executing '{name}'. "
                "Please check the server logs for details."
            )

        return [TextContent(type="text", text=result)]

    return server, client, license_validator


async def run_server() -> None:
    """Initialize configuration, validate license, and start the MCP server.

    This is the main entry point called by ``__main__.py``.
    """
    config = load_config()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting Calendly MCP Server v0.1.0")

    server, client, license_validator = create_server(config)

    # Validate license if provided
    if config.license_key:
        logger.info("Validating premium license key...")
        status = await license_validator.validate(config.license_key)
        if status.is_valid:
            logger.info(
                "Premium license active for %s. All tools enabled.",
                status.customer_name or "customer",
            )
        else:
            logger.warning(
                "Premium license validation failed: %s. Only free tools available.",
                status.error,
            )
    else:
        logger.info("No license key provided. Running in free tier mode.")

    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
