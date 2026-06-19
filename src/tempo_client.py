import json
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TEMPO_BASE = "https://api.tempo.io/4"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")


def _make_session(token: str) -> requests.Session:
    """Return a session with auth headers, connection pooling, and retry logic.

    Retries up to 3 times on transient server errors (429, 500, 502, 503, 504)
    with exponential backoff: 1s, 2s, 4s between attempts.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    retry = Retry(total=3, backoff_factor=1.0,
                  status_forcelist=[429, 500, 502, 503, 504],
                  respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def get_team_id(token: str, team_name: str) -> str:
    """Return the Tempo team ID for the given team name."""
    session = _make_session(token)
    url = f"{TEMPO_BASE}/teams"
    while url:
        resp = session.get(url)
        resp.raise_for_status()
        data = resp.json()
        for team in data.get("results", []):
            if team["name"] == team_name:
                return str(team["id"])
        url = data.get("metadata", {}).get("next")
    raise ValueError(f"Tempo team '{team_name}' not found. "
                     "Run setup.py to list available teams.")


def get_team_members(token: str, team_id: str) -> dict:
    """Return {accountId: displayName} for all members of a team.
    Writes result to cache/team_members.json."""
    session = _make_session(token)
    url = f"{TEMPO_BASE}/teams/{team_id}/members"
    members = {}
    while url:
        resp = session.get(url)
        resp.raise_for_status()
        data = resp.json()
        for m in data.get("results", []):
            # Tempo v4 returns member info nested under "member" key
            member_obj = m.get("member", m)
            account_id = member_obj.get("accountId", "")
            display_name = member_obj.get("displayName", "")
            if account_id:
                members[account_id] = display_name
        url = data.get("metadata", {}).get("next")

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, f"team_members_{team_id}.json"), "w") as f:
        json.dump(members, f, indent=2)
    return members


def get_user_holiday_scheme(token: str, account_id: str) -> dict | None:
    """Return the Tempo holiday scheme for a user, or None if not found."""
    session = _make_session(token)
    url = f"{TEMPO_BASE}/holiday-schemes/users/{account_id}"
    resp = session.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_holidays_for_scheme(token: str, scheme_id: int, year: int) -> set:
    """Return set of all holiday dates (YYYY-MM-DD) for a scheme and year."""
    session = _make_session(token)
    url = f"{TEMPO_BASE}/holiday-schemes/{scheme_id}/holidays?year={year}"
    resp = session.get(url)
    resp.raise_for_status()
    return {h["date"] for h in resp.json().get("results", [])}


def get_worklogs(token: str, team_id: str, from_date: str, to_date: str) -> list:
    """Return all worklogs for a team between from_date and to_date (YYYY-MM-DD).

    Each returned worklog dict is the raw Tempo API object. The issue is
    identified by issue_id (integer) — issue key must be resolved via Jira.
    """
    session = _make_session(token)
    url = (f"{TEMPO_BASE}/worklogs"
           f"?teamId={team_id}&from={from_date}&to={to_date}&limit=50")
    worklogs = []
    while url:
        resp = session.get(url)
        resp.raise_for_status()
        data = resp.json()
        worklogs.extend(data.get("results", []))
        url = data.get("metadata", {}).get("next")
    return worklogs
