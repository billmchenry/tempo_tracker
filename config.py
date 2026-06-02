TEMPO_TEAM_NAME = "Agent Experience Product Team"
OUTPUT_BASE = r"G:\My Drive\Tempo"

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
