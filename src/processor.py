import pandas as pd
import pytz
from datetime import datetime, timedelta

from src import jira_client

_EST = pytz.timezone("America/New_York")


def _utc_to_eastern(utc_str: str):
    """Convert Tempo's startDateTimeUtc (e.g. '2026-05-01T14:00:00Z') to Eastern."""
    if not utc_str:
        return None
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    return dt.astimezone(_EST)


def _next_friday(d):
    days_ahead = (4 - d.weekday()) % 7
    return (d + timedelta(days=days_ahead)).date()


def process(worklogs: list, members: dict,
            jira_base_url: str, jira_email: str, jira_token: str,
            capex_field_id: str) -> pd.DataFrame:
    """Transform raw Tempo worklogs into the processed DataFrame used by charts.

    Parameters
    ----------
    worklogs       : raw worklog dicts from Tempo API
    members        : {accountId: first_name}
    jira_*         : Jira connection params for issue lookup
    capex_field_id : Jira custom field ID for Capex Project Type
    """
    if not worklogs:
        return pd.DataFrame()

    # --- Build base rows ---
    rows = []
    for wl in worklogs:
        rows.append({
            "_issue_id":       str(wl["issue"]["id"]),
            "Logged Hours":    wl["timeSpentSeconds"] / 3600,
            "User Account ID": wl["author"]["accountId"],
            # startDate is the user-chosen date; keep for Work date / Work week
            "Work date":       f"{wl['startDate']} {wl.get('startTime', '00:00:00')[:5]}",
            # startDateTimeUtc already encodes the user's timezone — use directly
            "_utc_str":        wl.get("startDateTimeUtc", ""),
        })

    t = pd.DataFrame(rows)

    # --- Batch-fetch all unique issues from Jira ---
    unique_ids = t["_issue_id"].unique().tolist()
    print(f"  Fetching {len(unique_ids)} unique issues from Jira (batched)...")
    issue_data = jira_client.batch_get_issues(
        unique_ids, jira_base_url, jira_email, jira_token, capex_field_id
    )

    t["Issue Key"]          = t["_issue_id"].map(lambda i: issue_data[i]["key"])
    t["Full name"]          = t["User Account ID"].map(members).fillna("")
    t["Issue Type"]         = t["_issue_id"].map(lambda i: issue_data[i]["type"])
    t["Project Key"]        = t["_issue_id"].map(lambda i: issue_data[i]["project_key"])
    t["Project Name"]       = t["_issue_id"].map(lambda i: issue_data[i]["project_name"])
    t["Issue Status"]       = t["_issue_id"].map(lambda i: issue_data[i]["status"])
    t["Capex Project Type"] = t["_issue_id"].map(lambda i: issue_data[i]["capex_type"])
    t["Parent Key"]         = t["_issue_id"].map(lambda i: issue_data[i]["parent_key"])
    t.drop(columns=["_issue_id"], inplace=True)

    # --- Parent Key fixup ---
    def fix_parent(row):
        pk   = row["Parent Key"]
        ik   = row["Issue Key"]
        it   = str(row["Issue Type"]).lower()
        proj = row["Project Key"]
        if (pd.isna(pk) or pk is None) and it == "epic":
            return ik
        if ik in ("TIME2-1", "TIME-1"):
            return "PTO-00"
        if proj in ("TIME", "TIME2"):
            return "TIME-00"
        return pk

    t["Parent Key"] = t.apply(fix_parent, axis=1)

    # --- Capex Project Type fixup ---
    t["Capex Project Type"] = t.apply(
        lambda row: "Not Capex"
        if (pd.isna(row["Capex Project Type"]) and row["Project Key"] in ("TIME", "TIME2"))
        else row["Capex Project Type"],
        axis=1,
    )

    # --- Time Conversion: use Tempo's UTC timestamp, convert to Eastern ---
    t["Time Conversion"] = t["_utc_str"].apply(
        lambda s: pd.Timestamp(_utc_to_eastern(s)).floor("D") if s else None
    )
    t.drop(columns=["_utc_str"], inplace=True)

    # --- Work date columns (based on user-chosen startDate) ---
    t["Work date"]      = pd.to_datetime(t["Work date"], errors="coerce")
    t["Work_date_only"] = t["Work date"].dt.date
    t["Work week"]      = t["Work date"].apply(
        lambda d: _next_friday(d) if not pd.isna(d) else None
    )

    # --- Is Capex ---
    t["Is Capex"] = t["Capex Project Type"].apply(
        lambda x: False if pd.isna(x) or x == "Not Capex" else True
    )

    # --- Category ---
    t["Category"] = t.apply(
        lambda row: "Time off"            if row["Parent Key"] == "PTO-00"
        else ("Non project time"          if row["Parent Key"] == "TIME-00"
        else ("Capex Project Time"        if row["Is Capex"]
        else  "Non Capex Project Time")),
        axis=1,
    )

    # --- User name ---
    t["User name"] = t["User Account ID"].map(members)

    # --- Epic enrichment: Name, Simple name, Active Project ---
    unique_parents = [
        pk for pk in t["Parent Key"].dropna().unique()
        if pk not in ("PTO-00", "TIME-00")
    ]
    print(f"  Fetching {len(unique_parents)} unique parent issues from Jira (batched)...")
    parent_data: dict = {
        "PTO-00":  {"summary": "", "status": ""},
        "TIME-00": {"summary": "", "status": ""},
    }
    for pk in unique_parents:
        parent_data[pk] = jira_client.get_issue(
            pk, jira_base_url, jira_email, jira_token, capex_field_id
        )

    t["Name"] = t["Parent Key"].map(
        lambda pk: parent_data.get(pk, {}).get("summary", "") if pk else ""
    )
    t["Simple name"] = t["Name"].apply(
        lambda s: (s[:40] + "...") if isinstance(s, str) and len(s) > 40 else s
    )
    t["Active Project"] = t["Parent Key"].map(
        lambda pk: 0.0
        if parent_data.get(pk, {}).get("status", "").lower() in ("done", "closed", "resolved")
        else 1.0
    )

    return t
