"""Tempo reporting dashboard — daily entry point.

Usage:
    python main.py
    python main.py --from 2025-04-01 --to 2025-06-30
    python main.py --refresh-cache
"""

import argparse
import os
import sys
from datetime import datetime, date

from dotenv import load_dotenv

load_dotenv()

import config
from src import tempo_client, jira_client, processor, charts


def write_log(log_path: str, message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - {message}"
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_active_period(today: date) -> dict | None:
    for p in config.CAPEX_PERIODS:
        start = date.fromisoformat(p["start"])
        end = date.fromisoformat(p["end"])
        if start <= today <= end:
            return p
    return None


def main():
    parser = argparse.ArgumentParser(description="Tempo reporting dashboard")
    parser.add_argument("--from", dest="from_date", help="Override start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", help="Override end date YYYY-MM-DD")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Clear the Jira issue cache before running")
    args = parser.parse_args()

    # --- Credentials ---
    tempo_token = os.environ.get("TEMPO_TOKEN", "").strip()
    jira_base_url = os.environ.get("JIRA_BASE_URL", "").strip().rstrip("/")
    jira_email = os.environ.get("JIRA_EMAIL", "").strip()
    jira_token = os.environ.get("JIRA_TOKEN", "").strip()

    missing = [k for k, v in {
        "TEMPO_TOKEN": tempo_token,
        "JIRA_BASE_URL": jira_base_url,
        "JIRA_EMAIL": jira_email,
        "JIRA_TOKEN": jira_token,
    }.items() if not v]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    # --- Date range ---
    today = date.today()
    if args.from_date and args.to_date:
        period = {
            "name": f"Custom {args.from_date} to {args.to_date}",
            "start": args.from_date,
            "end": args.to_date,
        }
    else:
        period = find_active_period(today)
        if not period:
            print(f"ERROR: Today ({today}) doesn't fall in any CAPEX_PERIODS defined in config.py.")
            print("Add the current period to CAPEX_PERIODS or use --from / --to flags.")
            sys.exit(1)

    # Pull worklogs up to today (not necessarily to period end)
    effective_to = min(today.isoformat(), period["end"])

    # --- Output setup ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(config.OUTPUT_BASE, f"Tempo_{timestamp}_final")
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, f"Tempo_log_{timestamp}.txt")

    def log(msg):
        write_log(log_path, msg)

    log("Script started.")
    log(f"Period: {period['name']} ({period['start']} → {effective_to})")

    # --- Optional cache refresh ---
    if args.refresh_cache:
        jira_client.clear_cache()
        log("Jira issue cache cleared.")

    # --- Tempo: team + worklogs ---
    log(f"Looking up Tempo team: {config.TEMPO_TEAM_NAME}")
    team_id = tempo_client.get_team_id(tempo_token, config.TEMPO_TEAM_NAME)
    log(f"Team ID: {team_id}")

    log("Fetching team members...")
    api_members = tempo_client.get_team_members(tempo_token, team_id)
    # Merge with static fallback so known members always have short display names
    members = {**api_members, **config.STATIC_TEAM_MEMBERS}
    log(f"Team members: {list(members.values())}")

    log(f"Fetching worklogs from {period['start']} to {effective_to}...")
    worklogs = tempo_client.get_worklogs(tempo_token, team_id, period["start"], effective_to)
    log(f"Retrieved {len(worklogs)} worklogs.")

    if not worklogs:
        log("No worklogs found for this period. Nothing to report.")
        sys.exit(0)

    # --- Process ---
    log("Processing worklogs...")
    df = processor.process(
        worklogs=worklogs,
        members=members,
        user_timezones=config.USER_TIMEZONES,
        jira_base_url=jira_base_url,
        jira_email=jira_email,
        jira_token=jira_token,
        capex_field_id=config.JIRA_CAPEX_FIELD_ID,
    )
    log(f"Processed {len(df)} rows.")

    # Save processed CSV
    csv_path = os.path.join(output_dir, f"Processed_Tempo_{timestamp}.csv")
    df.to_csv(csv_path, index=False)
    log(f"Processed CSV saved to {csv_path}.")

    # --- Charts ---
    log("Generating charts...")
    charts.generate(df, output_dir, period, log)

    log("Script completed successfully.")
    print(f"\nOutput saved to: {output_dir}")


if __name__ == "__main__":
    main()
