# Calendly MCP Server

An MCP (Model Context Protocol) server that connects Claude Desktop and Claude Code to your Calendly account, enabling natural-language scheduling management.

## Installation

```bash
pip install calendly-mcp
```

## Getting a Calendly Personal Access Token

1. Log in to [Calendly](https://calendly.com)
2. Go to **Settings** > **Integrations & Apps**
3. Scroll to **API & Connectors** and click **API**
4. Click **Get a token now** (or **Generate New Token**)
5. Give the token a name (e.g., "Claude MCP") and click **Create Token**
6. Copy the token immediately -- it will not be shown again

## Configuration

### Claude Desktop

Add the following to your `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "calendly": {
      "command": "calendly-mcp",
      "env": {
        "CALENDLY_ACCESS_TOKEN": "your-token-here",
        "LICENSE_KEY": "optional-premium-key"
      }
    }
  }
}
```

### Claude Code

Set the environment variable before starting Claude Code:

```bash
export CALENDLY_ACCESS_TOKEN="your-token-here"
export LICENSE_KEY="optional-premium-key"   # only if you have a premium license
```

Then add the MCP server:

```bash
claude mcp add calendly -- calendly-mcp
```

Or add it to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "calendly": {
      "command": "calendly-mcp",
      "env": {
        "CALENDLY_ACCESS_TOKEN": "your-token-here"
      }
    }
  }
}
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CALENDLY_ACCESS_TOKEN` | Yes | Calendly Personal Access Token or OAuth2 token |
| `LICENSE_KEY` | No | Lemon Squeezy premium license key |
| `LOG_LEVEL` | No | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `CALENDLY_BASE_URL` | No | Override the Calendly API base URL (for testing) |

## Tools

### Free Tier (7 tools)

| Tool | Description | Required Parameters |
|---|---|---|
| `list_upcoming_events` | List upcoming scheduled events with optional filters | None (optional: `count`, `min_start_time`, `max_start_time`, `status`) |
| `get_event_details` | Get full details of a specific event including invitees and location | `event_uuid` |
| `search_events` | Search events by invitee name or email (case-insensitive partial match) | `query` (optional: `min_start_time`, `max_start_time`) |
| `check_availability` | Check available time slots from your availability schedules | `date_range_start`, `date_range_end` |
| `get_busy_times` | Get busy/unavailable time periods for a date range | `start_time`, `end_time` |
| `list_event_types` | List all configured event types with name, duration, and status | None |
| `get_event_type_details` | Get detailed configuration of a specific event type | `event_type_uuid` |

### Premium Tier (5 additional tools)

| Tool | Description | Required Parameters |
|---|---|---|
| `create_one_off_event` | Create a single-use scheduling link for a meeting | `event_type_uuid`, `invitee_email`, `invitee_name`, `start_time` |
| `cancel_event` | Cancel an existing scheduled event (invitees are notified) | `event_uuid` (optional: `reason`) |
| `reschedule_event` | Reschedule an event to a new time | `event_uuid`, `new_start_time` |
| `get_scheduling_stats` | Get scheduling analytics: total meetings, avg duration, popular times | `min_start_time`, `max_start_time` |
| `get_invitee_insights` | Analyze meeting patterns with a specific contact | `invitee_email` |

## Free vs Premium

| Feature | Free | Premium |
|---|---|---|
| View upcoming events | Yes | Yes |
| Get event details | Yes | Yes |
| Search events by invitee | Yes | Yes |
| Check availability | Yes | Yes |
| View busy times | Yes | Yes |
| List event types | Yes | Yes |
| Get event type details | Yes | Yes |
| Create scheduling links | -- | Yes |
| Cancel events | -- | Yes |
| Reschedule events | -- | Yes |
| Scheduling analytics | -- | Yes |
| Invitee insights | -- | Yes |
| **Price** | **Free** | **$12/month** |

Upgrade at [nyxtools.lemonsqueezy.com/checkout](https://nyxtools.lemonsqueezy.com/checkout)

## Usage Examples

Once connected, talk to Claude naturally:

### Viewing Your Schedule

- "What meetings do I have this week?"
- "Show me my schedule for tomorrow"
- "List my next 5 meetings"
- "What canceled meetings did I have this month?"

### Event Details

- "Tell me more about my 3pm meeting"
- "Who's invited to the design review?"
- "What's the Zoom link for my next call?"

### Searching Events

- "Do I have any meetings with john@example.com?"
- "Find all meetings with Sarah"
- "When did I last meet with the Acme team?"

### Checking Availability

- "Am I free Thursday afternoon?"
- "What does my availability look like next week?"
- "What times am I busy tomorrow?"

### Event Types

- "What event types do I have set up?"
- "Show me the details of my 30-minute meeting type"

### Scheduling (Premium)

- "Schedule a 30-minute call with john@example.com for Tuesday at 2pm"
- "Set up a meeting with Jane Smith next Wednesday"

### Canceling and Rescheduling (Premium)

- "Cancel my 3pm meeting tomorrow"
- "Cancel the call with John -- I have a conflict"
- "Move my 2pm meeting to Thursday at 4pm"
- "Reschedule the call with Sarah to next Monday morning"

### Analytics (Premium)

- "How many meetings did I have this month?"
- "What's my average meeting length?"
- "How much time have I spent in meetings with John?"

## Development

### Setup

```bash
git clone https://github.com/nyxtools/calendly-mcp-server.git
cd calendly-mcp-server
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
pytest --cov=calendly_mcp    # with coverage
```

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

## Troubleshooting

### "CALENDLY_ACCESS_TOKEN is required"

You have not set the `CALENDLY_ACCESS_TOKEN` environment variable. Make sure it is configured in your `claude_desktop_config.json` (under `env`) or exported in your shell before running Claude Code.

### 401 Unauthorized errors

Your Calendly Personal Access Token is invalid or has been revoked. Generate a new token at **Settings > Integrations & Apps > API** in Calendly and update your configuration.

### 429 Rate limit errors

The Calendly API enforces rate limits. The MCP server automatically retries with exponential backoff, but if you see persistent rate limit errors, reduce the frequency of requests or wait a few minutes.

### Connection errors

- Verify you have internet connectivity
- Check that `api.calendly.com` is reachable from your network
- If behind a proxy, ensure `httpx` can reach the Calendly API

### Premium tools not appearing

- Verify your `LICENSE_KEY` is set correctly in the environment
- Check the server logs for license validation errors (`LOG_LEVEL=DEBUG`)
- Ensure your premium subscription is active at [nyxtools.lemonsqueezy.com](https://nyxtools.lemonsqueezy.com)

### Server not starting in Claude Desktop

- Verify the `command` path is correct (`calendly-mcp` must be on your PATH)
- Try running `calendly-mcp` directly in a terminal to check for errors
- On Windows, you may need to use the full path to the executable

## License

MIT -- see [LICENSE](LICENSE) for details.

Copyright (c) 2026 NyxTools · LEW Enterprises LLC
