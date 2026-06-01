TEMPO_TEAM_NAME = "Agent Experience Product Team"
OUTPUT_BASE = r"G:\My Drive\Tempo"

# CapEx reporting periods — add new periods each quarter.
# main.py auto-selects the period where today falls.
# FILL IN actual dates below once confirmed.
CAPEX_PERIODS = [
    # {"name": "FY20XX QX", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
]

# accountId → IANA timezone string.
# Accounts not listed here default to Asia/Kolkata (IST).
USER_TIMEZONES = {
    "62966bbdd9eae9006f351a5b": "America/Los_Angeles",  # Sandi
}

# Jira custom field ID for "Capex Project Type"
JIRA_CAPEX_FIELD_ID = "customfield_11300"

# Display-name overrides keyed by Jira account ID.
# These are used as fallback when a member isn't returned by the Tempo Teams API.
STATIC_TEAM_MEMBERS = {
    "62966bbdd9eae9006f351a5b": "Sandi",
    "6419b4037222b08f3e723215": "Chaitanya",
    "712020:034b7985-956f-4902-9e75-e650579a28c3": "Vaishnavi",
    "712020:07e24850-3942-4a27-89ab-99490614c796": "Bharath",
    "712020:4b6cf577-d552-466e-b86e-fd3c1692fa71": "Arti",
    "712020:8523765b-264f-47a2-9c6a-d01fdd62ebad": "Ayank",
    "712020:797a0310-c342-44ba-9e4b-f13a9471a6ff": "Shruti",
    "712020:1344747e-82b5-44dd-b994-0cbe881f02b6": "Bill",
    "640f1b99407493675d44f31b": "Parth",
}
