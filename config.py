import json
import os

_teams_file = os.path.join(os.path.dirname(__file__), "teams.json")
with open(_teams_file, encoding="utf-8") as _f:
    TEMPO_TEAMS: list[dict] = json.load(_f)

OUTPUT_BASE = r"G:\My Drive\Tempo"

# ── Reporting thresholds ──────────────────────────────────────────────────────
# Change these once and every chart label + Hub message updates automatically.
DAILY_HOURS_THRESHOLD = 6   # ✓ in Daily Hours Table requires > this many hours
CAPEX_TARGET_HOURS    = 80  # target CapEx hours per team member per period

# ── Hub messaging ─────────────────────────────────────────────────────────────
HUB_BASE_URL = "https://oklnqysblyswhbfxurby.supabase.co/functions/v1/hub-api"

# Local/staging override: all messages go here when not running in GitHub Actions
STAGING_CONVERSATION_ID = "4f908a49-822c-4a3f-be96-9450b7f1e698"

HUB_MESSAGE_HEADER = (
    "*{team_name} - CapEx Progress Report as of {run_date}*\n"
    "\n"
    "CapEx Period Start: {period_start}\n"
    "\n"
    "*CapEx Period End: {capex_end_date}*"
)

HUB_MESSAGE_FOOTER = (
    "---\n"
    "\n"
    "*Information about this report*\n"
    "\n"
    f"• Every weekday must have at least {DAILY_HOURS_THRESHOLD}h logged, regardless if it is CapEx time or not.\n"
    "\n"
    "• Team members in earlier time zones (e.g. India IST) who log after midnight local time will have those hours counted on the previous calendar day.\n"
    "\n"
    "• Tempo is aware of US holidays (it shows red in Tempo) - team members do not need to enter holidays if Tempo is aware. If Tempo is not aware, please log as TIME2-1 for eight hours.\n"
    "\n"
    "• If you are anticipating time off, please enter it in Tempo prior to time off."
)

# 2026 CapEx reporting periods (Start Day → Cut Off Day).
# main.py auto-selects the period where today falls.
# Add future years here as needed.
CAPEX_PERIODS = [
    {"name": "2026 Period 01", "start": "2025-12-27", "end": "2026-01-23"},
    {"name": "2026 Period 02", "start": "2026-01-24", "end": "2026-02-20"},
    {"name": "2026 Period 03", "start": "2026-02-21", "end": "2026-03-27"},
    {"name": "2026 Period 04", "start": "2026-03-28", "end": "2026-04-24"},
    {"name": "2026 Period 05", "start": "2026-04-25", "end": "2026-05-22"},
    {"name": "2026 Period 06", "start": "2026-05-23", "end": "2026-06-26"},
    {"name": "2026 Period 07", "start": "2026-06-27", "end": "2026-07-24"},
    {"name": "2026 Period 08", "start": "2026-07-25", "end": "2026-08-21"},
    {"name": "2026 Period 09", "start": "2026-08-22", "end": "2026-09-25"},
    {"name": "2026 Period 10", "start": "2026-09-26", "end": "2026-10-23"},
    {"name": "2026 Period 11", "start": "2026-10-24", "end": "2026-11-20"},
    {"name": "2026 Period 12", "start": "2026-11-21", "end": "2026-12-23"},
]

# Jira custom field ID for "Capex Project Type"
JIRA_CAPEX_FIELD_ID = "customfield_11300"

# ── CapEx/Component field audit ───────────────────────────────────────────────
# Flags "Agent Experience" tickets missing CapEx Project Type and/or Component,
# routed to the reporting Circle's Hub channel.
CAPEX_COMPONENT_AUDIT_JQL = (
    'project = "Agent Experience" AND ('
    '"Capex Project Type[Dropdown]" is EMPTY OR component is EMPTY'
    ') AND status not in (Cancelled, Duplicate, "Not a Bug", "Cannot Reproduce", Backlog, "To Do") '
    'AND type not in (Epic, Sub-task)'
)


def _hub_channel_for_team(team_name: str) -> str | None:
    return next((t["hub_conversation_id"] for t in TEMPO_TEAMS if t["name"] == team_name), None)


# Circle label ("Circle1".."Circle4") -> Hub channel, reusing the conversation
# IDs already assigned to each Circle's team in teams.json.
CIRCLE_HUB_CHANNELS = {
    "1": _hub_channel_for_team("Agent Experience Circle 1"),
    "2": _hub_channel_for_team("Agent Experience Circle 2"),
    "3": _hub_channel_for_team("Agent Experience Circle 3"),
    "4": _hub_channel_for_team("Agent Platform- Circle 4"),
}

# Tickets with no Circle label, or more than one, go here for manual triage.
FALLBACK_HUB_CHANNEL = _hub_channel_for_team("Agent Experience Product Team")
