"""Tempo reporting dashboard — daily entry point.

Usage:
    python main.py
    python main.py --team "Agent Experience Product Team"
    python main.py --from 2025-12-27 --to 2026-01-23
    python main.py --refresh-cache   # clears Jira issue + user cache
    python main.py --no-hub          # skip posting to Hub (preview MD still written locally)

CI mode (GitHub Actions):
    Detected automatically via GITHUB_ACTIONS=true env var.
    Skips all file output (no CSV, charts, or Google Drive writes).
    Logs go to stdout only. Hub API is still called.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Ensure stdout handles Unicode (matters on Windows when running in CI simulation)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
from src import tempo_client, jira_client, processor, charts, stats as stats_mod, hub_client

_TEAMS_FILE = os.path.join(os.path.dirname(__file__), "teams.json")

# Automatically true when running inside GitHub Actions
CI_MODE = os.environ.get("GITHUB_ACTIONS") == "true"


def write_log(log_path: str | None, message: str):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - {message}"
    print(line)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def find_active_period(today: date) -> dict | None:
    for p in config.CAPEX_PERIODS:
        start = date.fromisoformat(p["start"])
        end   = date.fromisoformat(p["end"])
        if start <= today <= end:
            return p
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")


def _save_teams(teams: list):
    """Persist teams list back to teams.json (used to cache resolved IDs)."""
    with open(_TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2)
        f.write("\n")


def run_for_team(team_name, team_id, output_dir, timestamp, period, effective_to,
                 credentials, log_fn, ci_mode=False, inaccessible_config=None):
    """Run the full pipeline for a single team. Returns (df, all_member_names, inaccessible_names).

    inaccessible_config: list of first names (from teams.json) whose Tempo logs
                         are known to be inaccessible to the API token.
    """
    tempo_token, jira_base_url, jira_email, jira_token = credentials

    log_fn(f"Fetching team members for: {team_name} (ID={team_id})...")
    api_members = tempo_client.get_team_members(tempo_token, team_id)
    log_fn(f"Found {len(api_members)} team members.")

    log_fn("Fetching user display names from Jira...")
    account_ids   = list(api_members.keys())
    user_profiles = jira_client.get_users(account_ids, jira_base_url, jira_email, jira_token)

    # For inaccessible accounts, use Tempo display name so we get a real name in the report
    for aid, prof in user_profiles.items():
        if not prof.get("accessible", True):
            tempo_display = api_members.get(aid, "")
            if tempo_display:
                parts = tempo_display.split()
                prof["first_name"] = parts[0].capitalize() if parts else prof["first_name"]

    members = {aid: prof["first_name"] for aid, prof in user_profiles.items()}

    # Jira-profile failures + explicitly configured Tempo-inaccessible members
    inaccessible_names = {
        prof["first_name"]
        for aid, prof in user_profiles.items()
        if not prof.get("accessible", True)
    } | set(inaccessible_config or [])

    if inaccessible_names:
        log_fn(f"Inaccessible members (logs cannot be retrieved): {', '.join(sorted(inaccessible_names))}")
    log_fn("Team: " + ", ".join(sorted(members.values())))

    log_fn(f"Fetching worklogs from {period['start']} to {effective_to}...")
    worklogs = tempo_client.get_worklogs(tempo_token, team_id, period["start"], effective_to)
    log_fn(f"Retrieved {len(worklogs)} worklogs.")

    if not worklogs:
        log_fn("No worklogs found for this period. Nothing to report.")
        return None, [], inaccessible_names

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

    all_member_names = sorted(members.values())

    if not ci_mode:
        csv_path = os.path.join(output_dir, f"Processed_Tempo_{timestamp}.csv")
        df.to_csv(csv_path, index=False)
        log_fn(f"Processed CSV saved to {csv_path}.")

        log_fn("Generating charts...")
        charts.generate(df, output_dir, period, log_fn, all_members=all_member_names)
    else:
        log_fn("CI mode: skipping CSV and chart generation.")

    log_fn(f"Team '{team_name}' completed successfully.")
    return df, all_member_names, inaccessible_names


def main():
    parser = argparse.ArgumentParser(description="Tempo reporting dashboard")
    parser.add_argument("--team",         dest="team",      help="Run for a single team (exact name from teams.json)")
    parser.add_argument("--from",         dest="from_date", help="Override start date YYYY-MM-DD")
    parser.add_argument("--to",           dest="to_date",   help="Override end date YYYY-MM-DD")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Clear Jira issue + user cache before running")
    parser.add_argument("--no-hub",       action="store_true",
                        help="Skip posting to Hub (preview MD still written locally)")
    args = parser.parse_args()

    if CI_MODE:
        print("Running in CI mode (GitHub Actions) — file output disabled.")

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

    hub_api_key = os.environ.get("HUB_API_KEY", "").strip()

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if CI_MODE:
        output_dir = None
        log_path   = None
    else:
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

    credentials   = (tempo_token, jira_base_url, jira_email, jira_token)
    teams_modified = False

    for team_cfg in teams_to_run:
        team_name = team_cfg["name"]
        log(f"--- Running: {team_name} ---")

        if CI_MODE:
            team_output_dir = None
        else:
            team_output_dir = os.path.join(output_dir, _slug(team_name))
            os.makedirs(team_output_dir, exist_ok=True)

        # Resolve Tempo team ID — use cached ID if available, otherwise look up by
        # name and save it back to teams.json so future runs are rename-proof.
        team_id = team_cfg.get("tempo_team_id")
        if not team_id:
            try:
                team_id = tempo_client.get_team_id(tempo_token, team_name)
                team_cfg["tempo_team_id"] = team_id
                teams_modified = True
                log(f"Resolved Tempo team ID: {team_id} (saved to teams.json).")
            except ValueError as e:
                log(f"WARNING: Skipping '{team_name}' — {e}")
                continue

        try:
            df, all_member_names, inaccessible_names = run_for_team(
                team_name, team_id, team_output_dir, timestamp, period,
                effective_to, credentials, log, ci_mode=CI_MODE,
                inaccessible_config=team_cfg.get("inaccessible_members", []),
            )
        except Exception as e:
            log(f"WARNING: '{team_name}' failed — {e}. Run continues.")
            continue

        if df is None:
            continue

        # --- Hub message ---
        try:
            eastern        = ZoneInfo("America/New_York")
            run_ts         = datetime.now(eastern).strftime("%Y-%m-%d %H:%M ET")
            days_remaining = (date.fromisoformat(period["end"]) - today).days

            team_stats, elapsed = stats_mod.compute_team_stats(
                df, period, all_member_names, inaccessible_members=inaccessible_names
            )
            message = hub_client.build_message(
                team_name, run_ts, period, days_remaining, team_stats, elapsed
            )

            if CI_MODE:
                log(f"Hub message preview:\n{message}")
            else:
                preview_path = os.path.join(team_output_dir, "Hub_Message_Preview.md")
                with open(preview_path, "w", encoding="utf-8") as f:
                    f.write(f"# Hub Message Preview\n\n```\n{message}\n```\n")
                log(f"Hub message preview saved to {preview_path}.")

            # Local runs → staging channel; CI runs → individual team channel
            if not CI_MODE:
                conv_id = config.STAGING_CONVERSATION_ID
                log(f"Local run: routing Hub message to staging channel.")
            else:
                conv_id = team_cfg.get("hub_conversation_id", "")

            if args.no_hub:
                log("Hub posting skipped (--no-hub).")
            elif not hub_api_key:
                log("Hub posting skipped (HUB_API_KEY not set in .env).")
            elif not conv_id:
                log("Hub posting skipped (no hub_conversation_id in teams.json).")
            else:
                try:
                    hub_client.post_message(hub_api_key, conv_id, message)
                    log("Hub message posted successfully.")
                except Exception as e:
                    log(f"WARNING: Hub posting failed — {e}. Run continues.")
        except Exception as e:
            log(f"WARNING: Hub message for '{team_name}' failed — {e}. Run continues.")

    # Persist any newly resolved team IDs — only meaningful in local mode
    if teams_modified and not CI_MODE:
        _save_teams(config.TEMPO_TEAMS)

    log("All teams completed.")
    if not CI_MODE:
        print(f"\nOutput saved to: {output_dir}")


if __name__ == "__main__":
    main()
