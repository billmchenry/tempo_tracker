"""Hub API client and message builder."""

import requests

import config


def build_message(team_name: str, run_timestamp: str, period: dict,
                  days_remaining: int, stats: list, elapsed_work_days: int) -> str:
    """Format the full plain-text Hub progress message."""
    lines = [
        config.HUB_MESSAGE_HEADER.format(
            team_name=team_name,
            run_timestamp=run_timestamp,
            period_start=period["start"],
            capex_end_date=period["end"],
            days_remaining=days_remaining,
        ),
        f"TEAM PROGRESS ({elapsed_work_days} working days elapsed):\n",
    ]

    for s in stats:
        pace_str = "✓ on track" if s["on_track"] else "✗ behind pace"
        if s["pto_hours"] > 0:
            pace_str += f" (adj. target: {s['adjusted_target']}h w/ {s['pto_hours']}h PTO)"
        lines.append(
            f"  {s['name']:<15} "
            f"{s['capex_hours']:>5.1f}h CapEx  |  "
            f"{pace_str:<45}  |  "
            f"{s['days_not_reported']} of {s['elapsed_work_days']} days not reported"
        )

    lines.append(
        "\n" + config.HUB_MESSAGE_FOOTER.format(
            capex_target_hours=config.CAPEX_TARGET_HOURS,
            daily_threshold=config.DAILY_HOURS_THRESHOLD,
        )
    )
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
