"""Hub API client and message builder."""

import requests

import config

# Column widths for plain-text alignment
_W_NAME   = 16
_W_HOURS  = 9   # "  49.2h  "
_W_CAPEX  = 30  # "✓ on track (adj: 48h)"
_W_DAILY  = 24  # "✗ 2 of 6 days missed"
_SEP      = "  |  "


def _capex_col(s: dict) -> str:
    text = "✓ on track" if s["on_track"] else "✗ behind pace"
    if s["pto_hours"] > 0:
        text += f" (adj: {s['adjusted_target']}h)"
    return text


def _daily_col(s: dict) -> str:
    n = s["days_not_reported"]
    total = s["reporting_work_days"]
    if total == 0:
        return "- period just started"
    if n == 0:
        return "✓ all days logged"
    if n == total:
        return f"✗ all {total} days missed"
    return f"✗ {n} of {total} days missed"


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

    # Header row
    h_name  = "NAME".ljust(_W_NAME)
    h_hours = "CAPEX HRS".ljust(_W_HOURS)
    h_capex = "CAPEX GOAL".ljust(_W_CAPEX)
    h_daily = "DAILY LOGGING"
    lines.append(f"  {h_name}{_SEP}{h_hours}{_SEP}{h_capex}{_SEP}{h_daily}")
    lines.append("  " + "-" * (_W_NAME + _W_HOURS + _W_CAPEX + _W_DAILY + len(_SEP) * 3))

    for s in stats:
        name  = s["name"].ljust(_W_NAME)
        hours = f"{s['capex_hours']:.1f}h".ljust(_W_HOURS)
        capex = _capex_col(s).ljust(_W_CAPEX)
        daily = _daily_col(s)
        lines.append(f"  {name}{_SEP}{hours}{_SEP}{capex}{_SEP}{daily}")

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
