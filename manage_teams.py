"""Manage Tempo teams config (teams.json).

Usage:
    python manage_teams.py list
    python manage_teams.py add "Team Name"
    python manage_teams.py remove "Team Name"
"""

import argparse
import json
import os
import sys

TEAMS_FILE = os.path.join(os.path.dirname(__file__), "teams.json")


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
            print(f"  {i}. {t['name']}")


def cmd_add(args):
    teams = _load()
    name = args.name.strip()
    if any(t["name"] == name for t in teams):
        print(f"Team '{name}' is already configured.")
        sys.exit(1)
    teams.append({"name": name})
    _save(teams)
    print(f"Added: {name}")
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


def main():
    parser = argparse.ArgumentParser(description="Manage Tempo teams config")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List configured teams")

    add_p = sub.add_parser("add", help="Add a team by exact Tempo name")
    add_p.add_argument("name", help="Tempo team name (exact match, case-sensitive)")

    rm_p = sub.add_parser("remove", help="Remove a team")
    rm_p.add_argument("name", help="Tempo team name to remove")

    args = parser.parse_args()
    {"list": cmd_list, "add": cmd_add, "remove": cmd_remove}[args.command](args)


if __name__ == "__main__":
    main()
