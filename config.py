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

HUB_MESSAGE_HEADER = (
    "{team_name} — CapEx progress report as of {run_timestamp}.\n"
    "Period: {period_start} → {capex_end_date} ({days_remaining} calendar days remaining). "
    "Remember, CapEx period ends on {capex_end_date}.\n"
)

HUB_MESSAGE_FOOTER = (
    "---\n"
    "CapEx hours = all hours logged to CapEx-eligible Jira issues this period. "
    "Target: {capex_target_hours}h (reduced proportionally for any weekday PTO logged).\n"
    "On track = current pace projects to meeting the (PTO-adjusted) target by period end.\n"
    "Days not reported = weekdays (Mon–Fri) from period start through today with zero hours logged.\n"
    "All times are Eastern. Team members in earlier time zones (e.g. India IST) who log "
    "after midnight local time will have those hours counted on the previous Eastern calendar day."
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
