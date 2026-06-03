"""Hub API client and message builder."""

import requests

import config


def _daily_str(s: dict) -> str:
    if s.get("inaccessible"):
        return "- could not access logs"
    n     = s["days_not_reported"]
    total = s["reporting_work_days"]
    if total == 0:
        return "- period just started"
    if n == 0:
        return "✓ all days logged"
    if n == total:
        return f"✗ all {total} days missed"
    return f"✗ {n} of {total} days missed"


def build_message(team_name: str, run_date: str, period: dict,
                  stats: list) -> str:
    """Format the full plain-text Hub progress message."""
    lines = [
        config.HUB_MESSAGE_HEADER.format(
            team_name=team_name,
            run_date=run_date,
            period_start=period["start"],
            capex_end_date=period["end"],
        ),
        "*TEAM PROGRESS:*\n",
    ]

    for s in stats:
        lines.append(f"• {s['name']}")
        lines.append(f"  {_daily_str(s)}")
        lines.append("")

    lines.extend(config.HUB_MESSAGE_FOOTER.splitlines())
    return "\n".join(lines)


def post_message(api_key: str, conversation_id: str, content: str) -> dict:
    """POST a plain-text message to a Hub conversation."""
    resp = requests.post(
        f"{config.HUB_BASE_URL}/api/v1/messages",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"conversation_id": conversation_id, "content": content},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
