# Tempo Tracker

Automated daily reporting dashboard for the **Agent Experience Product Team**'s Tempo time entries.

Replaces a manual Google Colab workflow where a CSV had to be downloaded by hand, team members were hardcoded, and epic metadata was maintained in a Google Sheet. This tool pulls everything from the Tempo and Jira APIs, runs on a schedule, and writes reports directly to Google Drive.

---

## How it works

1. **Fetches worklogs** from the Tempo API for the current CapEx period (auto-selected from `config.py`)
2. **Resolves display names** for all team members from Jira user profiles (first name, deduplicated)
3. **Enriches each worklog** with Jira issue metadata — type, project, parent epic, status, and CapEx classification — using batched JQL queries with a local cache
4. **Converts timestamps** using Tempo's `startDateTimeUtc` field (no manual timezone config needed)
5. **Generates four charts** and a processed CSV, saved to a timestamped subfolder in `G:\My Drive\Tempo\`

---

## Project structure

```
tempo_tracker/
├── .env                    # Secrets (never committed)
├── .env.example            # Template
├── config.py               # CapEx periods, team name, output path
├── main.py                 # Entry point
├── setup.py                # One-time credential validator
├── run_tempo.bat           # Windows Task Scheduler launcher
├── requirements.txt
├── src/
│   ├── tempo_client.py     # Tempo REST API v4 (worklogs, teams, members)
│   ├── jira_client.py      # Jira REST API (batch issue fetch, user display names)
│   ├── processor.py        # Data transformation pipeline
│   └── charts.py           # All four report charts
└── cache/
    ├── issues.json         # Jira issue metadata cache (auto-populated)
    └── team_members.json   # Tempo team member cache (refreshed each run)
```

---

## Setup

### 1. Clone and create a virtual environment

```bat
git clone https://github.com/billmchenry/tempo_tracker.git
cd tempo_tracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create your `.env` file

Copy `.env.example` to `.env` and fill in:

```
TEMPO_TOKEN=<your Tempo API token>
JIRA_BASE_URL=https://exprealtyengineering.atlassian.net
JIRA_EMAIL=bill.mchenry@exprealty.net
JIRA_TOKEN=<your Jira API token>
```

- **Tempo token**: stored in `Documents\tempo.txt`
- **Jira API token**: create one at https://id.atlassian.com/manage-profile/security/api-tokens → "Create API token" (no scope selection needed — inherits your account permissions)

### 3. Validate the setup

```bat
.venv\Scripts\activate
python setup.py
```

Confirms:
- Tempo API is reachable and "Agent Experience Product Team" (ID=46) exists
- Jira API is reachable and `customfield_11300` (Capex Project Type) is visible

### 4. Run a report

```bat
python main.py
```

Output is saved to `G:\My Drive\Tempo\Tempo_<timestamp>_final\`.

**Override date range:**
```bat
python main.py --from 2026-05-23 --to 2026-06-26
```

**Force a full Jira cache refresh** (use if issue CapEx classifications have changed):
```bat
python main.py --refresh-cache
```

---

## CapEx periods

Periods are defined in `config.py` as a list of named windows:

```python
CAPEX_PERIODS = [
    {"name": "2026 Period 06", "start": "2026-05-23", "end": "2026-06-26"},
    ...
]
```

`main.py` automatically selects whichever period contains today's date. Add new periods here at the start of each year. The full 2026 schedule is already configured (12 periods, ~4 weeks each).

Worklogs are fetched for the **entire period** (including future dates) so advance-logged entries are always captured.

---

## Windows Task Scheduler (daily automation)

The `run_tempo.bat` file activates the virtual environment, runs `main.py`, and appends output to a dated log file.

**To schedule it:**

1. Open **Task Scheduler** → "Create Basic Task"
2. Name: `Tempo Daily Report`
3. Trigger: **Daily** at 8:00 AM
4. Action: Start a program
   - Program: `C:\users\billmchenry\claude_projects\tempo_tracker\run_tempo.bat`
   - Start in: `C:\users\billmchenry\claude_projects\tempo_tracker`
5. Finish

Logs are written to `logs\tempo_YYYYMMDD.log` in the repo directory.

---

## Output files

Each run creates a timestamped folder: `G:\My Drive\Tempo\Tempo_<YYYYMMDD_HHMMSS>_final\`

| File | Description |
|------|-------------|
| `Processed_Tempo_*.csv` | Full processed worklog data with all derived columns |
| `Cumulative_Capex_Hours_Chart.png` | Cumulative CapEx hours per person vs. target pace |
| `Daily_Hours_Table.png` | Per-day logging status for every team member |
| `Stacked_Proportion_Capex_Chart.png` | Share of CapEx time by epic, per person |
| `Stacked_Proportion_Category_Chart.png` | Share of time by category (CapEx / Non-CapEx / Time off / Admin) |
| `Tempo_log_*.txt` | Run log with timestamps |

---

## Chart details

### Cumulative CapEx Hours

- One line per team member showing running total of CapEx-tagged hours
- Lines extend to **today** — if someone hasn't logged recently, their line runs flat to the current date
- Members with zero CapEx entries show a flat line at 0
- **Target pace line** (red dashed): 80 hours divided evenly across the business days in the period, so you can see at a glance whether the team is ahead or behind
- Legend displayed below the chart

### Daily Hours Table

Each cell represents one person on one day:

| Symbol | Colour | Meaning |
|--------|--------|---------|
| ✓ | Green | ≥ 6 hours logged (past date) |
| ✓ | Light green | ≥ 6 hours logged (future date — logged ahead) |
| ✗ | Red | < 6 hours logged on a past weekday |
| `-` | Blue-gray | Future weekday — not yet expected |
| Weekend | Gray | Saturday or Sunday |

All team members appear in the table for the full period, even those with no entries.

### Stacked Proportion Charts

- **CapEx by epic**: proportion of each person's CapEx hours broken down by parent epic (simple name). Members with no CapEx entries are shown with a "No CapEx logged" bar.
- **By category**: proportion of total hours across Time off / Non project time / CapEx Project Time / Non-CapEx Project Time. Members with no entries are shown with a "No time logged" bar.

---

## Team members

Team membership is pulled live from the Tempo API ("Agent Experience Product Team", ID=46) on every run. Display names (first names) are resolved from Jira user profiles. If two members share a first name, a last initial is appended automatically (e.g., two "Josh" accounts become "Josh H.").

The resolved list is written to `cache/team_members.json` after each run.

---

## Jira issue cache

Issue metadata (type, project, parent key, status, CapEx classification) is fetched via batched JQL queries (up to 100 issues per request) and cached in `cache/issues.json`. The cache persists between runs — CapEx classifications rarely change. Use `--refresh-cache` to force a full re-fetch.

---

## Key decisions / design notes

| Topic | Decision |
|-------|----------|
| Timezone handling | Uses Tempo's `startDateTimeUtc` field directly — no per-user timezone config needed |
| CapEx classification | Read from Jira custom field `customfield_11300` ("Capex Project Type") on each issue |
| Parent epic lookup | Resolved via Jira REST API; `Issue Type = Epic` issues are treated as their own parent |
| TIME / TIME2 projects | Entries in these projects are always classified as Non-CapEx; PTO issues map to a `PTO-00` pseudo-parent |
| Batch fetching | Issues fetched via `POST /rest/api/3/search/jql` (100 per request) with fallback to individual GETs |
| Future dates | Worklogs fetched through period end so advance-logged entries are included |
