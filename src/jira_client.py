"""Jira REST API client with local JSON cache.

Key design:
- batch_get_issues(): fetches up to 100 issues per JQL call (avoids per-issue hammering)
- get_issue(): single-issue lookup for parent keys (uses same cache)
- get_users(): bulk user profile fetch → display name + timezone, cached in users.json
"""

import json
import os
import time
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
ISSUES_CACHE = os.path.join(CACHE_DIR, "issues.json")
USERS_CACHE = os.path.join(CACHE_DIR, "users.json")

_issue_cache: dict = {}
_user_cache: dict = {}

BATCH_SIZE = 100  # Jira search maxResults limit


def _auth(email: str, token: str) -> HTTPBasicAuth:
    return HTTPBasicAuth(email, token)


def _make_session(email: str, token: str) -> requests.Session:
    """Return a session with auth, connection pooling, and retry logic."""
    session = requests.Session()
    session.auth = _auth(email, token)
    retry = Retry(total=3, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


# --------------------------------------------------------------------------- #
# Cache helpers
# --------------------------------------------------------------------------- #

def _load_issue_cache():
    global _issue_cache
    if _issue_cache:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(ISSUES_CACHE):
        with open(ISSUES_CACHE) as f:
            _issue_cache = json.load(f)


def _save_issue_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(ISSUES_CACHE, "w") as f:
        json.dump(_issue_cache, f, indent=2)


def _load_user_cache():
    global _user_cache
    if _user_cache:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.exists(USERS_CACHE):
        with open(USERS_CACHE) as f:
            _user_cache = json.load(f)


def _save_user_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(USERS_CACHE, "w") as f:
        json.dump(_user_cache, f, indent=2)


def clear_cache():
    global _issue_cache, _user_cache
    _issue_cache = {}
    _user_cache = {}
    for f in (ISSUES_CACHE, USERS_CACHE):
        if os.path.exists(f):
            os.remove(f)


# --------------------------------------------------------------------------- #
# Issue parsing
# --------------------------------------------------------------------------- #

def _parse_capex(raw) -> str | None:
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


def _parse_issue_fields(issue_id: str, body: dict, capex_field_id: str) -> dict:
    """Extract a normalised dict from a Jira issue API response body."""
    f = body["fields"]
    issue_key = body["key"]

    parent_key = None
    if f.get("parent"):
        parent_key = f["parent"]["key"]
    elif f.get("issuetype", {}).get("name", "").lower() == "epic":
        parent_key = issue_key

    return {
        "key": issue_key,
        "summary": f.get("summary", str(issue_id)),
        "type": f.get("issuetype", {}).get("name", ""),
        "project_key": f.get("project", {}).get("key", ""),
        "project_name": f.get("project", {}).get("name", ""),
        "parent_key": parent_key,
        "status": f.get("status", {}).get("name", ""),
        "capex_type": _parse_capex(f.get(capex_field_id)),
    }


def _not_found_result(identifier: str) -> dict:
    return {
        "key": str(identifier),
        "summary": str(identifier),
        "type": "Unknown",
        "project_key": str(identifier).split("-")[0] if "-" in str(identifier) else "",
        "project_name": "",
        "parent_key": None,
        "status": "Unknown",
        "capex_type": None,
    }


# --------------------------------------------------------------------------- #
# Issue fetching
# --------------------------------------------------------------------------- #

def batch_get_issues(ids: list, base_url: str, email: str, token: str,
                     capex_field_id: str) -> dict:
    """Fetch many issues via JQL batching (100 per request).

    ids: list of numeric Jira issue IDs (strings)
    Returns {id: issue_dict} for all requested IDs.
    Also stores results under the issue key for parent lookups.
    """
    _load_issue_cache()

    uncached = [i for i in ids if str(i) not in _issue_cache]
    if not uncached:
        return {str(i): _issue_cache[str(i)] for i in ids}

    fields_str = f"summary,issuetype,project,parent,status,{capex_field_id}"
    session = _make_session(email, token)

    for chunk_start in range(0, len(uncached), BATCH_SIZE):
        chunk = uncached[chunk_start:chunk_start + BATCH_SIZE]
        fetched_ids = set()

        # Try batch JQL search first (new Cloud endpoint, then legacy)
        jql = f"id in ({','.join(str(i) for i in chunk)})"
        payload = {"jql": jql, "fields": fields_str.split(","), "maxResults": BATCH_SIZE}
        batch_ok = False

        for search_url in (
            f"{base_url}/rest/api/3/search/jql",
            f"{base_url}/rest/api/3/search",
        ):
            try:
                resp = session.post(search_url, json=payload)
                if resp.status_code in (200, 201):
                    for issue in resp.json().get("issues", []):
                        iid = str(issue["id"])
                        result = _parse_issue_fields(iid, issue, capex_field_id)
                        _issue_cache[iid] = result
                        _issue_cache[result["key"]] = result
                        fetched_ids.add(iid)
                    batch_ok = True
                    break
            except Exception:
                pass

        # Fall back to individual fetches for anything not returned by batch
        remaining = [i for i in chunk if str(i) not in fetched_ids]
        if remaining and not batch_ok:
            remaining = chunk  # retry everything individually

        for iid in remaining:
            try:
                r = session.get(
                    f"{base_url}/rest/api/3/issue/{iid}?fields={fields_str}"
                )
                if r.status_code == 200:
                    result = _parse_issue_fields(str(iid), r.json(), capex_field_id)
                else:
                    result = _not_found_result(str(iid))
                _issue_cache[str(iid)] = result
                _issue_cache[result["key"]] = result
            except Exception:
                _issue_cache[str(iid)] = _not_found_result(str(iid))
            time.sleep(0.05)

        # Any still-missing IDs → mark not found
        for iid in chunk:
            if str(iid) not in _issue_cache:
                _issue_cache[str(iid)] = _not_found_result(str(iid))

        _save_issue_cache()

        if chunk_start + BATCH_SIZE < len(uncached):
            time.sleep(0.3)

    return {str(i): _issue_cache.get(str(i), _not_found_result(str(i))) for i in ids}


def get_issue(identifier: str, base_url: str, email: str, token: str,
              capex_field_id: str) -> dict:
    """Single-issue lookup (used for parent key resolution). Uses cache."""
    _load_issue_cache()
    if str(identifier) in _issue_cache:
        return _issue_cache[str(identifier)]

    fields = f"summary,issuetype,project,parent,status,{capex_field_id}"
    url = f"{base_url}/rest/api/3/issue/{identifier}?fields={fields}"
    resp = requests.get(url, auth=_auth(email, token))

    if resp.status_code == 404:
        result = _not_found_result(identifier)
    else:
        resp.raise_for_status()
        result = _parse_issue_fields(str(identifier), resp.json(), capex_field_id)

    _issue_cache[str(identifier)] = result
    _issue_cache[result["key"]] = result
    _save_issue_cache()
    return result


# --------------------------------------------------------------------------- #
# User profile fetching
# --------------------------------------------------------------------------- #

def _extract_first_name(display_name: str) -> str:
    """Return a short first name from a Jira display name or username.

    Handles:
      "Sandi Johnston"  -> "Sandi"
      "shruti.vijay"    -> "Shruti"   (dot-separated username)
      "Chaitanya R"     -> "Chaitanya"
    """
    if not display_name:
        return display_name
    parts = display_name.split()
    if len(parts) > 1:
        return parts[0]
    # Single token — try dot-split (username style)
    parts = display_name.split(".")
    return parts[0].capitalize()


def get_users(account_ids: list, base_url: str, email: str, token: str) -> dict:
    """Fetch display name and timezone for a list of account IDs.

    Returns {accountId: {"first_name": str, "display_name": str, "timezone": str}}
    Caches results in cache/users.json. Refreshes on every run (users are few).
    """
    _load_user_cache()
    auth = _auth(email, token)
    result = {}

    for account_id in account_ids:
        if account_id in _user_cache:
            result[account_id] = _user_cache[account_id]
            continue

        url = f"{base_url}/rest/api/3/user?accountId={account_id}"
        resp = requests.get(url, auth=auth)

        if resp.status_code != 200:
            profile = {
                "display_name": account_id,
                "first_name": account_id[:8],
                "timezone": "UTC",
            }
        else:
            data = resp.json()
            display_name = data.get("displayName", account_id)
            first_name = _extract_first_name(display_name)
            timezone = data.get("timeZone", "UTC")
            profile = {
                "display_name": display_name,
                "first_name": first_name,
                "timezone": timezone,
            }

        _user_cache[account_id] = profile
        result[account_id] = profile
        time.sleep(0.05)  # small delay between user lookups

    _save_user_cache()

    # Deduplicate first names: if two members share a first name, append last initial
    seen: dict = {}  # first_name -> account_id of first occurrence
    for aid, prof in result.items():
        fn = prof["first_name"]
        if fn in seen:
            # Disambiguate both entries with last initial
            for dup_aid in (seen[fn], aid):
                parts = result[dup_aid]["display_name"].split()
                if len(parts) > 1:
                    result[dup_aid]["first_name"] = f"{parts[0]} {parts[-1][0]}."
        else:
            seen[fn] = aid

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
