"""Per-person CapEx stats used in the Hub progress message."""

from datetime import date, timedelta

import pandas as pd

import config


def compute_team_stats(df: pd.DataFrame, period: dict, all_members: list) -> tuple:
    """Return (stats_list, elapsed_work_days).

    stats_list: one dict per member (sorted by name):
        name, capex_hours, on_track, daily_ok, days_not_reported,
        reporting_work_days, elapsed_work_days, pto_hours, adjusted_target

    elapsed_work_days  : working days period-start → today (for header display)
    reporting_work_days: working days period-start → yesterday (daily check
                         excludes today — team may not have logged yet)
    """
    today     = date.today()
    yesterday = today - timedelta(days=1)

    period_start = pd.Timestamp(period["start"])
    period_end   = pd.Timestamp(period["end"])
    cutoff       = min(pd.Timestamp(today), period_end)
    tomorrow     = pd.Timestamp(today + timedelta(days=1))

    total_work_days     = len(pd.bdate_range(period_start, period_end))
    elapsed_work_days   = len(pd.bdate_range(period_start, cutoff))
    remaining_work_days = len(pd.bdate_range(tomorrow, period_end))

    # Daily reporting check: only days through yesterday are expected to have entries
    report_cutoff       = min(pd.Timestamp(yesterday), period_end)
    reporting_work_days = (
        len(pd.bdate_range(period_start, report_cutoff))
        if report_cutoff >= period_start else 0
    )

    stats = []
    for member in sorted(all_members):
        mdf = df[df["User name"] == member]

        capex_hours = float(mdf[mdf["Is Capex"] == True]["Logged Hours"].sum())

        # PTO: weekdays only — weekend PTO entries don't reduce the 80h target
        pto_raw   = mdf[mdf["Category"] == "Time off"]
        pto_hours = float(
            pto_raw[pd.to_datetime(pto_raw["Work_date_only"]).dt.dayofweek < 5]
            ["Logged Hours"].sum()
        )

        # Days logged through yesterday only
        past = mdf[pd.to_datetime(mdf["Work_date_only"]) <= pd.Timestamp(yesterday)]
        days_reported     = int(past["Work_date_only"].nunique())
        days_not_reported = max(0, reporting_work_days - days_reported)

        pace      = capex_hours / elapsed_work_days if elapsed_work_days > 0 else 0.0
        projected = capex_hours + pace * remaining_work_days

        pto_days        = pto_hours / 8
        adjusted_target = (
            config.CAPEX_TARGET_HOURS * (total_work_days - pto_days) / total_work_days
            if total_work_days > 0 else float(config.CAPEX_TARGET_HOURS)
        )

        stats.append({
            "name":                member,
            "capex_hours":         round(capex_hours, 1),
            "on_track":            projected >= adjusted_target,
            "daily_ok":            days_not_reported == 0,
            "days_not_reported":   days_not_reported,
            "reporting_work_days": reporting_work_days,
            "elapsed_work_days":   elapsed_work_days,
            "pto_hours":           round(pto_hours, 1),
            "adjusted_target":     round(adjusted_target, 1),
        })

    return stats, elapsed_work_days
