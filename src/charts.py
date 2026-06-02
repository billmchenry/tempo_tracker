import os
import textwrap
from datetime import timedelta

import matplotlib.pyplot as plt
import pandas as pd


def generate(df: pd.DataFrame, output_dir: str, period: dict, log_fn,
             all_members: list | None = None):
    """Generate all 4 charts and save to output_dir.

    period     : {"name": str, "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    log_fn     : callable(message) for logging
    all_members: optional list of all team member names — ensures every member
                 appears in charts even if they logged no hours this period
    """
    os.makedirs(output_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # Chart 1: Cumulative Capex Logged Hours Per Day
    # -------------------------------------------------------------------------
    df["Work date"] = pd.to_datetime(df["Work date"])
    capex_df = df[df["Is Capex"] == True].copy()
    capex_df = capex_df.sort_values("Work date")
    capex_df["Cumulative Hours"] = capex_df.groupby("User name")["Logged Hours"].cumsum()

    first_day = pd.to_datetime(period["start"])
    end_day = pd.to_datetime(period["end"])

    capex_chart_df = capex_df[
        (capex_df["Work date"] >= first_day) & (capex_df["Work date"] <= end_day)
    ]

    plt.figure(figsize=(12, 6))
    for name, group in capex_chart_df.groupby("User name"):
        plt.plot(group["Work date"], group["Cumulative Hours"], label=name)

    plt.axhline(y=80, color="r", linestyle="--", label="80 Hour Goal")
    plt.xticks(pd.date_range(start=first_day, end=end_day, freq="W-FRI"))
    plt.title("Daily Logged Hours by Team Member", fontsize=20, weight="bold", pad=20)
    plt.xlabel("Date (Fridays)")
    plt.ylabel("Cumulative Logged Hours")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    chart1_path = os.path.join(output_dir, "Cumulative_Capex_Hours_Chart.png")
    plt.savefig(chart1_path)
    plt.close()
    log_fn(f"Cumulative Capex Chart saved to {chart1_path}.")

    # -------------------------------------------------------------------------
    # Chart 2: Daily Hours Table (✓ / ✗ / Weekend)
    # -------------------------------------------------------------------------
    df["Work_date_only"] = pd.to_datetime(df["Work_date_only"])
    # Use full period range so every day appears, not just days with entries
    period_start = pd.to_datetime(period["start"])
    period_end   = pd.to_datetime(period["end"])
    all_dates = pd.date_range(start=period_start, end=period_end)

    daily_hours = (
        df.groupby(["Work_date_only", "User name"])["Logged Hours"]
        .sum()
        .unstack(fill_value=0)
    )
    daily_hours = daily_hours.reindex(index=all_dates, fill_value=0)

    # Ensure every team member has a column even if they logged nothing
    if all_members:
        for m in all_members:
            if m not in daily_hours.columns:
                daily_hours[m] = 0
        daily_hours = daily_hours[sorted(all_members)]

    table = daily_hours.copy()
    table.index = table.index.date
    table = table.transpose()

    fig, ax = plt.subplots(figsize=(15, 15))
    ax.axis("tight")
    ax.axis("off")

    table_data = []
    for date in table.columns:
        row = [date.strftime("%Y-%m-%d")]
        for member in table.index:
            hours = table.at[member, date]
            if pd.Timestamp(date).weekday() >= 5:
                row.append("Weekend")
            elif hours > 6:
                row.append("✓")
            else:
                row.append("✗")
        table_data.append(row)

    col_labels = ["Date"] + list(table.index)
    table_ax = ax.table(cellText=table_data, colLabels=col_labels,
                        loc="center", cellLoc="center")
    table_ax.auto_set_font_size(False)
    table_ax.set_fontsize(18)
    table_ax.scale(1.5, 2)

    for (i, j), cell in table_ax.get_celld().items():
        if i == 0 or j == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor("black")
        elif table_data[i - 1][j] == "Weekend":
            cell.set_facecolor("lightgray")
        elif table_data[i - 1][j] == "✓":
            cell.set_facecolor("lightgreen")
        elif table_data[i - 1][j] == "✗":
            cell.set_facecolor("lightcoral")

    plt.title("Daily Logged Hours by Team Member", fontsize=20, weight="bold")
    table2_path = os.path.join(output_dir, "Daily_Hours_Table.png")
    plt.savefig(table2_path)
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
    capex_prop = capex_activities.div(capex_activities.sum(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=(12, 7))
    capex_prop.plot(kind="bar", stacked=True, ax=ax)

    plt.title("Proportion of Time Spent on Activities by User (Capex Only)",
              fontsize=20, weight="bold")
    plt.xlabel("User Name")
    plt.ylabel("Proportion of Logged Hours")
    ax.legend().remove()

    for i, container in enumerate(ax.containers):
        epic_name = capex_prop.columns[i]
        wrapped = wrap_text(epic_name, width=10)
        labels = []
        for rect in container:
            h = rect.get_height()
            labels.append(f"{wrapped}\n{h * 100:.1f}%" if h > 0.01 else "")
        ax.bar_label(container, labels=labels, label_type="center", fontsize=8)

    plt.tight_layout()
    chart3_path = os.path.join(output_dir, "Stacked_Proportion_Capex_Chart.png")
    plt.savefig(chart3_path)
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
    category_prop = category_activities.div(category_activities.sum(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=(12, 7))
    category_prop.plot(kind="bar", stacked=True, ax=ax)

    plt.title("Proportion of Time Spent on Activities by User Across Categories",
              fontsize=20, weight="bold")
    plt.xlabel("User Name")
    plt.ylabel("Proportion of Logged Hours")
    ax.legend().remove()

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
    plt.savefig(chart4_path)
    plt.close()
    log_fn(f"Stacked Category chart saved to {chart4_path}.")
