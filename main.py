"""Tempo reporting dashboard — daily entry point.

Usage:
    python main.py
    python main.py --team "Agent Experience Product Team"
    python main.py --from 2025-12-27 --to 2026-01-23
    python main.py --refresh-cache   # clears Jira issue + user cache
"""

import argparse
import os
import re
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


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")


def run_for_team(team_name, output_dir, timestamp, period, effective_to,
                 credentials, log_fn):
    """Run the full pipeline for a single team, writing output to output_dir."""
    tempo_token, jira_base_url, jira_email, jira_token = credentials

    log_fn(f"Looking up Tempo team: {team_name}")
    team_id = tempo_client.get_team_id(tempo_token, team_name)
    log_fn(f"Team ID: {team_id}")

    log_fn("Fetching team members from Tempo...")
    api_members = tempo_client.get_team_members(tempo_token, team_id)
    log_fn(f"Found {len(api_members)} team members.")

    log_fn("Fetching user display names from Jira...")
    account_ids   = list(api_members.keys())
    user_profiles = jira_client.get_users(account_ids, jira_base_url, jira_email, jira_token)
    members       = {aid: prof["first_name"] for aid, prof in user_profiles.items()}
    log_fn("Team: " + ", ".join(sorted(members.values())))

    log_fn(f"Fetching worklogs from {period['start']} to {effective_to}...")
    worklogs = tempo_client.get_worklogs(tempo_token, team_id, period["start"], effective_to)
    log_fn(f"Retrieved {len(worklogs)} worklogs.")

    if not worklogs:
        log_fn("No worklogs found for this period. Nothing to report.")
        return

    log_fn("Processing worklogs...")
    df = processor.process(
        worklogs=worklogs,
        members=members,
        jira_base_url=jira_base_url,
        jira_email=jira_email,
        jira_token=jira_token,
        capex_field_id=config.JIRA_CAPEX_FIELD_ID,
    )
    log_fn(f"Processed {len(df)} rows.")

    csv_path = os.path.join(output_dir, f"Processed_Tempo_{timestamp}.csv")
    df.to_csv(csv_path, index=False)
    log_fn(f"Processed CSV saved to {csv_path}.")

    log_fn("Generating charts...")
    all_member_names = sorted(members.values())
    charts.generate(df, output_dir, period, log_fn, all_members=all_member_names)

    log_fn(f"Team '{team_name}' completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Tempo reporting dashboard")
    parser.add_argument("--team",      dest="team",      help="Run for a single team (exact name from teams.json)")
    parser.add_argument("--from",      dest="from_date", help="Override start date YYYY-MM-DD")
    parser.add_argument("--to",        dest="to_date",   help="Override end date YYYY-MM-DD")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Clear Jira issue + user cache before running")
    args = parser.parse_args()

    # --- Credentials ---
    tempo_token   = os.environ.get("TEMPO_TOKEN",   "").strip()
    jira_base_url = os.environ.get("JIRA_BASE_URL", "").strip().rstrip("/")
    jira_email    = os.environ.get("JIRA_EMAIL",    "").strip()
    jira_token    = os.environ.get("JIRA_TOKEN",    "").strip()

    missing = [k for k, v in {
        "TEMPO_TOKEN":   tempo_token,
        "JIRA_BASE_URL": jira_base_url,
        "JIRA_EMAIL":    jira_email,
        "JIRA_TOKEN":    jira_token,
    }.items() if not v]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    # --- Teams ---
    if not config.TEMPO_TEAMS:
        print("ERROR: No teams configured. Run 'python manage_teams.py add \"Team Name\"'.")
        sys.exit(1)

    if args.team:
        teams_to_run = [t for t in config.TEMPO_TEAMS if t["name"] == args.team]
        if not teams_to_run:
            print(f"ERROR: Team '{args.team}' not found in teams.json.")
            print("Run 'python manage_teams.py list' to see configured teams.")
            sys.exit(1)
    else:
        teams_to_run = config.TEMPO_TEAMS

    # --- Date range ---
    today = date.today()
    if args.from_date and args.to_date:
        period = {
            "name":  f"Custom {args.from_date} to {args.to_date}",
            "start": args.from_date,
            "end":   args.to_date,
        }
    else:
        period = find_active_period(today)
        if not period:
            print(f"ERROR: Today ({today}) doesn't fall in any CAPEX_PERIODS in config.py.")
            print("Add the current period or use --from / --to flags.")
            sys.exit(1)

    effective_to = period["end"]

    # --- Output setup ---
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(config.OUTPUT_BASE, f"Tempo_{timestamp}_final")
    os.makedirs(output_dir, exist_ok=True)
    log_path   = os.path.join(output_dir, f"Tempo_log_{timestamp}.txt")

    def log(msg):
        write_log(log_path, msg)

    log("Script started.")
    log(f"Period: {period['name']} ({period['start']} to {effective_to})")
    log(f"Teams: {', '.join(t['name'] for t in teams_to_run)}")

    if args.refresh_cache:
        jira_client.clear_cache()
        log("Jira issue + user cache cleared.")

    credentials = (tempo_token, jira_base_url, jira_email, jira_token)

    for team_cfg in teams_to_run:
        team_name = team_cfg["name"]
        team_output_dir = os.path.join(output_dir, _slug(team_name))
        os.makedirs(team_output_dir, exist_ok=True)
        log(f"--- Running: {team_name} ---")
        run_for_team(team_name, team_output_dir, timestamp, period,
                     effective_to, credentials, log)

    log("All teams completed.")
    print(f"\nOutput saved to: {output_dir}")


if __name__ == "__main__":
    main()
