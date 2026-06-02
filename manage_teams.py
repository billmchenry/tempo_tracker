"""Manage Tempo teams config (teams.json).

Usage:
    python manage_teams.py list
    python manage_teams.py add "Team Name"
    python manage_teams.py add "Team Name" --hub-channel "https://hub.exprealty.com/messages/?conversation=<uuid>"
    python manage_teams.py remove "Team Name"
    python manage_teams.py set-channel "Team Name" "https://hub.exprealty.com/messages/?conversation=<uuid>"
    python manage_teams.py set-channel "Team Name" "<bare-uuid>"
"""

import argparse
import json
import os
import re
import sys

TEAMS_FILE = os.path.join(os.path.dirname(__file__), "teams.json")

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def _extract_uuid(value: str) -> str:
    """Accept a full Hub conversation URL or a bare UUID; return the UUID."""
    m = _UUID_RE.search(value)
    if not m:
        print(f"ERROR: Could not find a UUID in '{value}'.")
        print("Provide a full Hub conversation URL or a bare UUID.")
        sys.exit(1)
    return m.group(0)


def _load():
    with open(TEAMS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(teams):
    with open(TEAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2)
        f.write("\n")


def cmd_list(_args):
    teams = _load()
    if not teams:
        print("No teams configured.")
    else:
        print(f"{len(teams)} team(s) in teams.json:")
        for i, t in enumerate(teams, 1):
            tid     = t.get("tempo_team_id", "(not yet resolved)")
            channel = t.get("hub_conversation_id", "(no Hub channel)")
            print(f"  {i}. {t['name']}")
            print(f"       Tempo ID:    {tid}")
            print(f"       Hub channel: {channel}")


def cmd_add(args):
    teams = _load()
    name = args.name.strip()
    if any(t["name"] == name for t in teams):
        print(f"Team '{name}' is already configured.")
        sys.exit(1)
    entry: dict = {"name": name}
    if args.hub_channel:
        entry["hub_conversation_id"] = _extract_uuid(args.hub_channel)
    teams.append(entry)
    _save(teams)
    print(f"Added: {name}")
    if "hub_conversation_id" in entry:
        print(f"  Hub channel: {entry['hub_conversation_id']}")
    print(f"({len(teams)} team(s) now configured)")


def cmd_remove(args):
    teams = _load()
    name = args.name.strip()
    new = [t for t in teams if t["name"] != name]
    if len(new) == len(teams):
        print(f"Team '{name}' not found in teams.json.")
        print("Run 'python manage_teams.py list' to see configured teams.")
        sys.exit(1)
    _save(new)
    print(f"Removed: {name}")
    print(f"({len(new)} team(s) remaining)")


def cmd_set_channel(args):
    teams = _load()
    name = args.name.strip()
    uuid = _extract_uuid(args.channel)
    for t in teams:
        if t["name"] == name:
            t["hub_conversation_id"] = uuid
            _save(teams)
            print(f"Set Hub channel for '{name}': {uuid}")
            return
    print(f"Team '{name}' not found in teams.json.")
    print("Run 'python manage_teams.py list' to see configured teams.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Manage Tempo teams config")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List configured teams and their Hub channels")

    add_p = sub.add_parser("add", help="Add a team by exact Tempo name")
    add_p.add_argument("name", help="Tempo team name (exact match, case-sensitive)")
    add_p.add_argument("--hub-channel", metavar="URL_OR_UUID",
                       help="Hub conversation URL or UUID to post reports to")

    rm_p = sub.add_parser("remove", help="Remove a team")
    rm_p.add_argument("name", help="Tempo team name to remove")

    sc_p = sub.add_parser("set-channel", help="Set or update the Hub channel for a team")
    sc_p.add_argument("name", help="Tempo team name (exact match)")
    sc_p.add_argument("channel", metavar="URL_OR_UUID",
                      help="Hub conversation URL or bare UUID")

    args = parser.parse_args()
    {
        "list":        cmd_list,
        "add":         cmd_add,
        "remove":      cmd_remove,
        "set-channel": cmd_set_channel,
    }[args.command](args)


if __name__ == "__main__":
    main()
