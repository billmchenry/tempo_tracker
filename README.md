# Tempo Tracker

Automated daily reporting dashboard for the Agent Experience Product Team's Tempo time entries.

Pulls worklogs via the Tempo API, enriches them with Jira issue metadata, and generates
the same four charts/reports that were previously produced manually in Google Colab.

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

Copy `.env.example` to `.env` and fill in your credentials:

```
TEMPO_TOKEN=<your Tempo API token>
JIRA_BASE_URL=https://exprealtyengineering.atlassian.net
JIRA_EMAIL=bill.mchenry@exprealty.net
JIRA_TOKEN=<your Jira API token>
```

**Tempo token**: already in `Documents\tempo.txt`

**Jira API token**: Create one at
https://id.atlassian.com/manage-profile/security/api-tokens
→ Click "Create API token" → copy the value into `JIRA_TOKEN`

### 3. Configure CapEx periods

Open `config.py` and fill in the `CAPEX_PERIODS` list with your actual reporting windows:

```python
CAPEX_PERIODS = [
    {"name": "FY2025 Q2", "start": "2025-04-01", "end": "2025-06-30"},
    # ...
]
```

`main.py` auto-selects whichever period contains today's date.

### 4. Validate the setup

```bat
.venv\Scripts\activate
python setup.py
```

This confirms:
- Tempo API connects and "Agent Experience Product Team" is found (ID=46)
- Jira API connects and `customfield_11300` (Capex Project Type) is accessible

### 5. Run a report

```bat
python main.py
```

Output is saved to a timestamped subfolder under `G:\My Drive\Tempo\`.

Override dates if needed:
```bat
python main.py --from 2025-04-01 --to 2025-06-30
python main.py --refresh-cache   # re-fetches all Jira issue data
```

## Windows Task Scheduler (daily automation)

1. Open Task Scheduler → "Create Basic Task"
2. Trigger: Daily at 8:00 AM
3. Action: Start a program
   - Program: `C:\path\to\tempo_tracker\run_tempo.bat`
   - Start in: `C:\path\to\tempo_tracker`
4. Save

Logs are written to `logs\tempo_YYYYMMDD.log` in the repo directory.

## Output files (per run)

All saved to `G:\My Drive\Tempo\Tempo_<timestamp>_final\`:

| File | Description |
|------|-------------|
| `Processed_Tempo_*.csv` | Full processed worklog data |
| `Cumulative_Capex_Hours_Chart.png` | Running CapEx hours per person over the period |
| `Daily_Hours_Table.png` | Daily ✓/✗ attendance table |
| `Stacked_Proportion_Capex_Chart.png` | Time split by epic (CapEx only) |
| `Stacked_Proportion_Category_Chart.png` | Time split by category (all entries) |
| `Tempo_log_*.txt` | Run log |

## Team members

The team member list is auto-discovered from the "Agent Experience Product Team" Tempo team
on each run and written to `cache/team_members.json`. `config.py` contains a `STATIC_TEAM_MEMBERS`
fallback dict with the known short display names (Sandi, Chaitanya, etc.) that takes precedence
over the Tempo API names.

## Jira issue cache

Issue metadata (type, project, parent, CapEx type) is cached in `cache/issues.json` to avoid
redundant API calls. The cache is never auto-expired (issue CapEx classification rarely changes).
Use `python main.py --refresh-cache` to force a full refresh.
