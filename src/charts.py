import os
import textwrap
from datetime import date as date_type

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def _ensure_all_members(pivot: pd.DataFrame, all_members: list | None) -> pd.DataFrame:
    """Add zero rows for any member in all_members not already in the index."""
    if not all_members:
        return pivot
    for m in all_members:
        if m not in pivot.index:
            pivot.loc[m] = 0
    return pivot.loc[sorted(all_members)]


def generate(df: pd.DataFrame, output_dir: str, period: dict, log_fn,
             all_members: list | None = None):
    """Generate all 4 charts and save to output_dir.

    period     : {"name": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    log_fn     : callable(message) for logging
    all_members: list of all team member first names — every member appears in
                 every chart even if they logged no hours this period
    """
    os.makedirs(output_dir, exist_ok=True)

    first_day = pd.to_datetime(period["start"])
    end_day   = pd.to_datetime(period["end"])

    df["Work date"] = pd.to_datetime(df["Work date"])

    # -------------------------------------------------------------------------
    # Chart 1: Cumulative Capex Logged Hours Per Day
    # -------------------------------------------------------------------------
    today_ts   = pd.Timestamp(date_type.today())
    cutoff     = min(today_ts, end_day)   # lines extend to today (or period end)

    capex_df = df[df["Is Capex"] == True].copy()
    capex_df = capex_df.sort_values("Work date")
    capex_df["Cumulative Hours"] = capex_df.groupby("User name")["Logged Hours"].cumsum()

    capex_period = capex_df[
        (capex_df["Work date"] >= first_day) & (capex_df["Work date"] <= end_day)
    ]

    # Build per-user series, extending the last known value to today
    user_series: dict = {}
    for name, grp in capex_period.groupby("User name"):
        grp = grp.sort_values("Work date")
        dates   = list(grp["Work date"])
        cumvals = list(grp["Cumulative Hours"])
        if dates[-1] < cutoff:          # extend line horizontally to today
            dates.append(cutoff)
            cumvals.append(cumvals[-1])
        user_series[name] = (dates, cumvals)

    # Members with zero capex — flat line at 0 from period start to today
    members_to_plot = sorted(all_members) if all_members else sorted(user_series.keys())
    for m in members_to_plot:
        if m not in user_series:
            user_series[m] = ([first_day, cutoff], [0, 0])

    # Target pace line: 80 hours spread evenly over work days in the period
    work_days   = pd.bdate_range(start=first_day, end=end_day)
    n_work_days = len(work_days)
    target_per_day = 80 / n_work_days if n_work_days else 0
    target_dates  = [first_day] + list(work_days)
    target_values = [0] + [target_per_day * (i + 1) for i in range(n_work_days)]

    # --- Plot ---
    n_series = len(members_to_plot)
    fig, ax = plt.subplots(figsize=(13, 6))

    for name in members_to_plot:
        dates, cumvals = user_series[name]
        ax.plot(dates, cumvals, label=name, marker="o", markersize=3, linewidth=1.8)

    ax.plot(target_dates, target_values,
            color="red", linestyle="--", linewidth=2,
            label=f"Target pace ({n_work_days} work days → 80h)")

    ax.set_xlim(first_day, end_day)
    ax.set_xticks(pd.date_range(start=first_day, end=end_day, freq="W-FRI"))
    ax.set_xticklabels(
        [d.strftime("%b %d") for d in pd.date_range(start=first_day, end=end_day, freq="W-FRI")],
        rotation=30, ha="right"
    )
    ax.set_title("Cumulative CapEx Logged Hours", fontsize=16, weight="bold", pad=10)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Logged Hours")
    ax.grid(True, alpha=0.4)

    # Legend below the chart, spread across columns
    ncols = min(n_series + 1, 5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22),
              ncol=ncols, frameon=True, fontsize=9)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28)   # make room for legend below x-axis

    chart1_path = os.path.join(output_dir, "Cumulative_Capex_Hours_Chart.png")
    fig.savefig(chart1_path, dpi=150, bbox_inches="tight")
    plt.close()
    log_fn(f"Cumulative Capex Chart saved to {chart1_path}.")

    # -------------------------------------------------------------------------
    # Chart 2: Daily Hours Table (✓ / ✗ / Weekend)
    # -------------------------------------------------------------------------
    df["Work_date_only"] = pd.to_datetime(df["Work_date_only"])
    all_dates = pd.date_range(start=first_day, end=end_day)

    daily_hours = (
        df.groupby(["Work_date_only", "User name"])["Logged Hours"]
        .sum()
        .unstack(fill_value=0)
    )
    daily_hours = daily_hours.reindex(index=all_dates, fill_value=0)

    # Ensure every team member has a column
    if all_members:
        for m in all_members:
            if m not in daily_hours.columns:
                daily_hours[m] = 0
        daily_hours = daily_hours[sorted(all_members)]

    table = daily_hours.copy()
    table.index = table.index.date
    table = table.transpose()

    n_members = len(table.index)
    n_dates   = len(table.columns)
    fig_w = max(12, (n_members + 1) * 1.8)
    fig_h = max(4,  n_dates * 0.45 + 1.2)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    # Build table text and a parallel state matrix for cell colouring.
    # States: "past_ok" | "future_ok" | "past_miss" | "future_none" | "weekend"
    COLORS = {
        "past_ok":    "#90EE90",  # lightgreen
        "future_ok":  "#d4f5d4",  # lighter green — logged ahead of time
        "past_miss":  "#F08080",  # lightcoral
        "future_none":"#e8eaf0",  # light blue-gray — not yet due
        "weekend":    "#d3d3d3",  # lightgray
    }

    today = date_type.today()
    table_data   = []
    cell_states  = []  # parallel rows; index 0 = date column placeholder

    for date in table.columns:
        row        = [date.strftime("%Y-%m-%d")]
        state_row  = ["_date"]
        is_future  = pd.Timestamp(date).date() > today
        is_weekend = pd.Timestamp(date).weekday() >= 5

        for member in table.index:
            raw   = table.at[member, date]
            hours = float(raw.sum()) if hasattr(raw, "sum") else float(raw)

            if is_weekend:
                row.append("Weekend");  state_row.append("weekend")
            elif hours > 6:
                row.append("✓")
                state_row.append("future_ok" if is_future else "past_ok")
            elif is_future:
                row.append("-");        state_row.append("future_none")
            else:
                row.append("✗");        state_row.append("past_miss")

        table_data.append(row)
        cell_states.append(state_row)

    col_labels = ["Date"] + list(table.index)
    table_ax = ax.table(cellText=table_data, colLabels=col_labels,
                        cellLoc="center", bbox=[0, 0, 1, 1])
    table_ax.auto_set_font_size(False)
    table_ax.set_fontsize(11)
    table_ax.auto_set_column_width(range(len(col_labels)))

    for (i, j), cell in table_ax.get_celld().items():
        if i == 0 or j == 0:          # header row or Date column
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor("black")
        else:
            state = cell_states[i - 1][j]
            cell.set_facecolor(COLORS.get(state, "white"))

    plt.title("Daily Logged Hours by Team Member", fontsize=14, weight="bold", pad=8)
    table2_path = os.path.join(output_dir, "Daily_Hours_Table.png")
    plt.savefig(table2_path, dpi=150, bbox_inches="tight")
    plt.close()
    log_fn(f"Daily Hours Table saved to {table2_path}.")

    # -------------------------------------------------------------------------
    # Chart 3: Stacked Column — Proportion of Time by Epic (Capex only)
    # -------------------------------------------------------------------------
    def wrap_text(label, width=10):
        return "\n".join(textwrap.wrap(str(label), width=width))

    capex_only = df[df["Is Capex"] == True].copy()
    capex_activities = (
        capex_only.groupby(["User name", "Simple name"])["Logged Hours"]
        .sum()
        .unstack(fill_value=0)
    )
    capex_activities = _ensure_all_members(capex_activities, all_members)
    # Members with 0 capex hours get a single "No CapEx logged" bar for visibility
    zero_rows = capex_activities[capex_activities.sum(axis=1) == 0].index
    if len(zero_rows) > 0 and "No CapEx logged" not in capex_activities.columns:
        capex_activities["No CapEx logged"] = 0
        capex_activities.loc[zero_rows, "No CapEx logged"] = 1  # placeholder for proportion

    capex_prop = capex_activities.div(
        capex_activities.sum(axis=1).replace(0, 1), axis=0
    )

    fig, ax = plt.subplots(figsize=(max(10, n_members * 1.5), 7))
    capex_prop.plot(kind="bar", stacked=True, ax=ax)

    plt.title("Proportion of Time Spent on Activities by User (Capex Only)",
              fontsize=16, weight="bold")
    plt.xlabel("User Name")
    plt.ylabel("Proportion of Logged Hours")
    ax.legend().remove()
    plt.xticks(rotation=30, ha="right")

    for i, container in enumerate(ax.containers):
        col_name = capex_prop.columns[i]
        wrapped = wrap_text(col_name, width=10)
        labels = []
        for rect in container:
            h = rect.get_height()
            labels.append(f"{wrapped}\n{h * 100:.1f}%" if h > 0.01 else "")
        ax.bar_label(container, labels=labels, label_type="center", fontsize=8)

    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "Stacked_Proportion_Capex_Chart.png")
    plt.savefig(chart3_path, dpi=150)
    plt.close()
    log_fn(f"Stacked Capex chart saved to {chart3_path}.")

    # -------------------------------------------------------------------------
    # Chart 4: Stacked Column — Proportion of Time by Category (all)
    # -------------------------------------------------------------------------
    category_activities = (
        df.groupby(["User name", "Category"])["Logged Hours"]
        .sum()
        .unstack(fill_value=0)
    )
    category_activities = _ensure_all_members(category_activities, all_members)
    # Members with 0 hours get an "No time logged" placeholder
    zero_rows = category_activities[category_activities.sum(axis=1) == 0].index
    if len(zero_rows) > 0 and "No time logged" not in category_activities.columns:
        category_activities["No time logged"] = 0
        category_activities.loc[zero_rows, "No time logged"] = 1

    category_prop = category_activities.div(
        category_activities.sum(axis=1).replace(0, 1), axis=0
    )

    fig, ax = plt.subplots(figsize=(max(10, n_members * 1.5), 7))
    category_prop.plot(kind="bar", stacked=True, ax=ax)

    plt.title("Proportion of Time Spent on Activities by User Across Categories",
              fontsize=16, weight="bold")
    plt.xlabel("User Name")
    plt.ylabel("Proportion of Logged Hours")
    ax.legend().remove()
    plt.xticks(rotation=30, ha="right")

    for i, container in enumerate(ax.containers):
        cat_name = category_prop.columns[i]
        wrapped = wrap_text(cat_name, width=10)
        labels = []
        for rect in container:
            h = rect.get_height()
            labels.append(f"{wrapped}\n{h * 100:.1f}%" if h > 0.01 else "")
        ax.bar_label(container, labels=labels, label_type="center", fontsize=8)

    plt.tight_layout()
    chart4_path = os.path.join(output_dir, "Stacked_Proportion_Category_Chart.png")
    plt.savefig(chart4_path, dpi=150)
    plt.close()
    log_fn(f"Stacked Category chart saved to {chart4_path}.")
