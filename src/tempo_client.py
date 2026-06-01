import json
import os
import requests

TEMPO_BASE = "https://api.tempo.io/4"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_team_id(token: str, team_name: str) -> str:
    """Return the Tempo team ID for the given team name."""
    url = f"{TEMPO_BASE}/teams"
    while url:
        resp = requests.get(url, headers=_headers(token))
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
    url = f"{TEMPO_BASE}/teams/{team_id}/members"
    members = {}
    while url:
        resp = requests.get(url, headers=_headers(token))
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
    with open(os.path.join(CACHE_DIR, "team_members.json"), "w") as f:
        json.dump(members, f, indent=2)
    return members


def get_worklogs(token: str, team_id: str, from_date: str, to_date: str) -> list:
    """Return all worklogs for a team between from_date and to_date (YYYY-MM-DD).

    Each returned worklog dict is the raw Tempo API object. The issue is
    identified by issue_id (integer) — issue key must be resolved via Jira.
    """
    url = (f"{TEMPO_BASE}/worklogs"
           f"?teamId={team_id}&from={from_date}&to={to_date}&limit=50")
    worklogs = []
    while url:
        resp = requests.get(url, headers=_headers(token))
        resp.raise_for_status()
        data = resp.json()
        worklogs.extend(data.get("results", []))
        url = data.get("metadata", {}).get("next")
    return worklogs
