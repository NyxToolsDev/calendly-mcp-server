# Calendly MCP Usage Examples

Natural language prompts you can use with Claude once the Calendly MCP server is connected.

---

## Viewing Events

| What you say | Tool called |
|---|---|
| "What meetings do I have this week?" | `list_upcoming_events` |
| "Show me my schedule for tomorrow" | `list_upcoming_events` (with date filter) |
| "List my next 5 meetings" | `list_upcoming_events` (count=5) |
| "What canceled meetings did I have this month?" | `list_upcoming_events` (status=canceled) |

---

## Event Details

| What you say | Tool called |
|---|---|
| "Tell me more about my 3pm meeting" | `get_event_details` |
| "Who's invited to the design review?" | `get_event_details` |
| "What's the Zoom link for my next call?" | `get_event_details` |

---

## Searching Events

| What you say | Tool called |
|---|---|
| "Do I have any meetings with john@example.com?" | `search_events` |
| "Find all meetings with Sarah" | `search_events` |
| "When did I last meet with the Acme team?" | `search_events` |

---

## Checking Availability

| What you say | Tool called |
|---|---|
| "Am I free Thursday afternoon?" | `check_availability` |
| "What does my availability look like next week?" | `check_availability` |
| "When am I available for a meeting on Friday?" | `check_availability` |
| "What times am I busy tomorrow?" | `get_busy_times` |
| "Show me my blocked time slots for this week" | `get_busy_times` |

---

## Event Types

| What you say | Tool called |
|---|---|
| "What event types do I have set up?" | `list_event_types` |
| "Show me the details of my 30-minute meeting type" | `get_event_type_details` |
| "What booking options do I offer?" | `list_event_types` |

---

## Scheduling (Premium)

| What you say | Tool called |
|---|---|
| "Schedule a 30-minute call with john@example.com for Tuesday at 2pm" | `create_one_off_event` |
| "Set up a meeting with Jane Smith (jane@company.com) next Wednesday" | `create_one_off_event` |
| "Create a booking link for a discovery call with the new client" | `create_one_off_event` |

---

## Canceling (Premium)

| What you say | Tool called |
|---|---|
| "Cancel my 3pm meeting tomorrow" | `cancel_event` |
| "Cancel the call with John - I have a conflict" | `cancel_event` (with reason) |
| "Remove the design review from my schedule" | `cancel_event` |

---

## Rescheduling (Premium)

| What you say | Tool called |
|---|---|
| "Move my 2pm meeting to Thursday at 4pm" | `reschedule_event` |
| "Reschedule the call with Sarah to next Monday morning" | `reschedule_event` |
| "Push my 3pm back to 5pm" | `reschedule_event` |

---

## Analytics (Premium)

| What you say | Tool called |
|---|---|
| "How many meetings did I have this month?" | `get_scheduling_stats` |
| "What's my average meeting length?" | `get_scheduling_stats` |
| "What are my busiest days for meetings?" | `get_scheduling_stats` |
| "How often do meetings with jane@example.com happen?" | `get_invitee_insights` |
| "Show me my meeting history with the engineering team lead" | `get_invitee_insights` |
| "How much time have I spent in meetings with John?" | `get_invitee_insights` |

---

## Multi-Step Conversations

Claude can chain multiple tools together in a conversation:

1. **"Am I free for a 30-minute call with Sarah next Tuesday?"**
   - Claude checks availability (`check_availability`), then offers to schedule (`create_one_off_event`)

2. **"I need to reschedule my meeting with John. Move it to whenever I'm free on Thursday."**
   - Claude checks availability (`check_availability`), finds the existing meeting (`search_events`), then reschedules (`reschedule_event`)

3. **"Give me a summary of my meetings with the Acme Corp team this quarter"**
   - Claude searches events (`search_events`), then provides invitee insights (`get_invitee_insights`)
