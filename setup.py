"""One-time setup helper.

Run this after cloning to:
1. Validate Tempo credentials and list available teams
2. Confirm the Jira Capex Project Type field ID
3. Test that 'Agent Experience Product Team' exists in Tempo

Usage: python setup.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

import requests
from requests.auth import HTTPBasicAuth

TEMPO_BASE = "https://api.tempo.io/4"


def check_env():
    missing = []
    for k in ("TEMPO_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_TOKEN"):
        if not os.environ.get(k):
            missing.append(k)
    if missing:
        print(f"ERROR: Missing in .env: {', '.join(missing)}")
        sys.exit(1)


def list_tempo_teams(token):
    print("\n--- Tempo Teams ---")
    url = f"{TEMPO_BASE}/teams"
    headers = {"Authorization": f"Bearer {token}"}
    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        for t in data.get("results", []):
            print(f"  ID={t['id']}  Name={t['name']}")
        url = data.get("metadata", {}).get("next")


def check_jira_capex_field(base_url, email, token):
    print("\n--- Jira Fields matching 'capex' ---")
    url = f"{base_url}/rest/api/3/field"
    resp = requests.get(url, auth=HTTPBasicAuth(email, token))
    resp.raise_for_status()
    found = False
    for field in resp.json():
        if "capex" in field.get("name", "").lower():
            print(f"  ID={field['id']}  Name={field['name']}")
            found = True
    if not found:
        print("  (no fields with 'capex' in the name found)")


def main():
    check_env()
    token = os.environ["TEMPO_TOKEN"]
    jira_base = os.environ["JIRA_BASE_URL"].rstrip("/")
    jira_email = os.environ["JIRA_EMAIL"]
    jira_token = os.environ["JIRA_TOKEN"]

    print("Checking Tempo API connection...")
    try:
        list_tempo_teams(token)
    except Exception as e:
        print(f"Tempo API error: {e}")
        sys.exit(1)

    print("\nChecking Jira API connection...")
    try:
        check_jira_capex_field(jira_base, jira_email, jira_token)
    except Exception as e:
        print(f"Jira API error: {e}")
        sys.exit(1)

    print("\nSetup check complete.")
    print("If 'Agent Experience Product Team' appears above, you're good to go.")
    print("Verify JIRA_CAPEX_FIELD_ID in config.py matches what's listed above.")


if __name__ == "__main__":
    main()
