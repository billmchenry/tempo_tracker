"""CapEx/Component field audit — daily entry point (Mon-Thu).

Finds "Agent Experience" tickets missing the CapEx Project Type and/or
Component field, groups them by the ticket's CircleN label, and posts a
digest to each Circle's Hub channel. Tickets with no Circle label (or more
than one) go to the fallback channel (Agent Experience Product Team).

Usage:
    python capex_component_audit.py
    python capex_component_audit.py --no-hub   # preview digests, skip posting

CI mode (GitHub Actions):
    Detected automatically via GITHUB_ACTIONS=true env var. Behavior is the
    same as local runs — this job has no file output either way.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
from src import jira_client, hub_client

CI_MODE = os.environ.get("GITHUB_ACTIONS") == "true"

CIRCLE_LABEL_RE = re.compile(r"^circle\s*([1-4])$", re.IGNORECASE)

AUDIT_FIELDS = ["summary", "reporter", "assignee", "labels", "components",
                config.JIRA_CAPEX_FIELD_ID]


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} - {msg}")


def missing_fields(ticket: dict) -> list:
    missing = []
    if not ticket.get("capex_type"):
        missing.append("Capex Project Type")
    if not ticket.get("components"):
        missing.append("Component")
    return missing


def circle_numbers(ticket: dict) -> list:
    matches = []
    for label in ticket.get("labels", []):
        m = CIRCLE_LABEL_RE.match(label.strip())
        if m:
            matches.append(m.group(1))
    return sorted(set(matches))


def build_digest(run_date: str, jira_base_url: str, tickets: list) -> str:
    lines = [f"*CapEx/Component Field Audit — {run_date}*", "",
             "The following Agent Experience tickets are missing required "
             "CapEx and/or Component data:", ""]
    for t in tickets:
        lines.append(f"• *{t['key']}* — {jira_base_url}/browse/{t['key']}")
        lines.append(f"  \"{t['summary']}\"")
        lines.append(f"  Reporter: {t['reporter']} | Assignee: {t['assignee']}")
        lines.append(f"  Missing: {', '.join(missing_fields(t))}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main():
    parser = argparse.ArgumentParser(description="CapEx/Component field audit")
    parser.add_argument("--no-hub", action="store_true",
                        help="Skip posting to Hub (digests still printed)")
    args = parser.parse_args()

    if CI_MODE:
        log("Running in CI mode (GitHub Actions).")

    jira_base_url = os.environ.get("JIRA_BASE_URL",   "").strip().rstrip("/")
    jira_email    = os.environ.get("JIRA_EMAIL",       "").strip()
    capex_token   = os.environ.get("CAPEX_TRACKER",    "").strip()
    hub_api_key   = os.environ.get("HUB_API_KEY",      "").strip()

    missing = [k for k, v in {
        "JIRA_BASE_URL":  jira_base_url,
        "JIRA_EMAIL":     jira_email,
        "CAPEX_TRACKER":  capex_token,
    }.items() if not v]
    if missing:
        log(f"ERROR: Missing environment variables: {', '.join(missing)}")
        log("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    if not jira_client.verify_auth(jira_base_url, jira_email, capex_token):
        log("ERROR: Jira authentication failed (JIRA_EMAIL/CAPEX_TRACKER rejected by /rest/api/3/myself).")
        log("Refusing to run the audit query — a bad token returns 0 issues silently instead of erroring.")
        sys.exit(1)

    log("Running CapEx/Component audit JQL against Jira...")
    tickets = jira_client.search_issues(
        config.CAPEX_COMPONENT_AUDIT_JQL, AUDIT_FIELDS,
        jira_base_url, jira_email, capex_token, config.JIRA_CAPEX_FIELD_ID,
    )
    log(f"Found {len(tickets)} ticket(s) missing CapEx and/or Component.")

    circle_buckets = {num: [] for num in config.CIRCLE_HUB_CHANNELS}
    fallback_bucket = []

    for t in tickets:
        matches = circle_numbers(t)
        if len(matches) == 1 and matches[0] in circle_buckets:
            circle_buckets[matches[0]].append(t)
        else:
            reason = "no Circle label" if not matches else f"multiple Circle labels ({', '.join(matches)})"
            log(f"  {t['key']}: routed to fallback channel ({reason}).")
            fallback_bucket.append(t)

    eastern  = ZoneInfo("America/New_York")
    run_date = datetime.now(eastern).strftime("%Y-%m-%d")

    all_buckets = [(f"Circle {num}", config.CIRCLE_HUB_CHANNELS[num], circle_buckets[num])
                   for num in sorted(circle_buckets)]
    all_buckets.append(("Fallback (Agent Experience Product Team)",
                        config.FALLBACK_HUB_CHANNEL, fallback_bucket))

    for label, conv_id, bucket_tickets in all_buckets:
        if not bucket_tickets:
            log(f"{label}: 0 tickets — no message sent.")
            continue

        log(f"{label}: {len(bucket_tickets)} ticket(s).")
        message = build_digest(run_date, jira_base_url, bucket_tickets)
        log(f"Digest preview for {label}:\n{message}")

        if args.no_hub:
            log(f"{label}: Hub posting skipped (--no-hub).")
        elif not hub_api_key:
            log(f"{label}: Hub posting skipped (HUB_API_KEY not set).")
        elif not conv_id:
            log(f"{label}: WARNING — no hub_conversation_id resolved for this channel. Skipping post.")
        else:
            try:
                hub_client.post_message(hub_api_key, conv_id, message)
                log(f"{label}: Hub message posted successfully.")
            except Exception as e:
                log(f"{label}: WARNING — Hub posting failed ({e}). Run continues.")

    log("Audit run completed.")


if __name__ == "__main__":
    main()
