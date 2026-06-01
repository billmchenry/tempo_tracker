"""Jira REST API client with local JSON cache.

Issues are looked up by their numeric Jira ID (from Tempo worklogs) or by
issue key. The cache stores data under both the numeric ID and the key so
either can be used as a lookup handle.
"""

import json
import os
import requests
from requests.auth import HTTPBasicAuth

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "issues.json")

_issue_cache: dict = {}


def _auth(email: str, token: str) -> HTTPBasicAuth:
    return HTTPBasicAuth(email, token)


def _load_cache():
    global _issue_cache
    if _issue_cache:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            _issue_cache = json.load(f)


def _save_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(_issue_cache, f, indent=2)


def clear_cache():
    global _issue_cache
    _issue_cache = {}
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def _parse_capex(raw) -> str | None:
    """Extract the string value from various Jira custom field shapes."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return raw.get("value") or raw.get("name")
    if isinstance(raw, list) and raw:
        first = raw[0]
        return first.get("value") or first.get("name") if isinstance(first, dict) else str(first)
    return None


def get_issue(identifier: str, base_url: str, email: str, token: str,
              capex_field_id: str) -> dict:
    """Return issue metadata, using local cache.

    identifier: either a numeric Jira issue ID (e.g. "268993") or a key
                (e.g. "AGX-1072"). Both are stored in cache after first fetch.

    Returns dict with keys:
        key, summary, type, project_key, project_name,
        parent_key, status, capex_type
    """
    _load_cache()
    if identifier in _issue_cache:
        return _issue_cache[identifier]

    fields = f"summary,issuetype,project,parent,status,{capex_field_id}"
    url = f"{base_url}/rest/api/3/issue/{identifier}?fields={fields}"
    resp = requests.get(url, auth=_auth(email, token))

    if resp.status_code == 404:
        result = {
            "key": str(identifier),
            "summary": str(identifier),
            "type": "Unknown",
            "project_key": str(identifier).split("-")[0] if "-" in str(identifier) else "",
            "project_name": "",
            "parent_key": None,
            "status": "Unknown",
            "capex_type": None,
        }
        _issue_cache[identifier] = result
        _save_cache()
        return result

    resp.raise_for_status()
    body = resp.json()
    f = body["fields"]
    issue_key = body["key"]

    parent_key = None
    if f.get("parent"):
        parent_key = f["parent"]["key"]
    elif f.get("issuetype", {}).get("name", "").lower() == "epic":
        parent_key = issue_key  # epics are their own parent in this model

    result = {
        "key": issue_key,
        "summary": f.get("summary", str(identifier)),
        "type": f.get("issuetype", {}).get("name", ""),
        "project_key": f.get("project", {}).get("key", ""),
        "project_name": f.get("project", {}).get("name", ""),
        "parent_key": parent_key,
        "status": f.get("status", {}).get("name", ""),
        "capex_type": _parse_capex(f.get(capex_field_id)),
    }

    # Cache under both the numeric ID and the issue key
    _issue_cache[str(identifier)] = result
    _issue_cache[issue_key] = result
    _save_cache()
    return result


def get_capex_field_id(base_url: str, email: str, token: str) -> str | None:
    """Discover the Jira custom field ID for 'Capex Project Type'."""
    url = f"{base_url}/rest/api/3/field"
    resp = requests.get(url, auth=_auth(email, token))
    resp.raise_for_status()
    for field in resp.json():
        if field.get("name", "").lower() == "capex project type":
            return field["id"]
    return None
