import pandas as pd
import pytz
from datetime import timedelta, datetime

from src import jira_client


def _convert_to_eastern(work_date_str: str, account_id: str,
                         user_timezones: dict):
    """Convert a naive work datetime string to an Eastern-time Timestamp."""
    est = pytz.timezone("America/New_York")
    tz_name = user_timezones.get(account_id, "Asia/Kolkata")
    local_tz = pytz.timezone(tz_name)
    dt = pd.to_datetime(work_date_str, errors="coerce")
    if pd.isna(dt):
        return None
    return local_tz.localize(dt.to_pydatetime()).astimezone(est)


def _next_friday(d):
    """Return the date of the next Friday (inclusive of today if Friday)."""
    days_ahead = (4 - d.weekday()) % 7
    return (d + timedelta(days=days_ahead)).date()


def process(worklogs: list, members: dict, user_timezones: dict,
            jira_base_url: str, jira_email: str, jira_token: str,
            capex_field_id: str) -> pd.DataFrame:
    """Transform raw Tempo worklogs into the processed DataFrame used by charts.

    Parameters
    ----------
    worklogs       : raw worklog dicts from Tempo API
    members        : {accountId: displayName}
    user_timezones : {accountId: tz_string}; unlisted accounts default to IST
    jira_*         : Jira connection params for issue lookup
    capex_field_id : Jira custom field ID for Capex Project Type
    """
    if not worklogs:
        return pd.DataFrame()

    # --- Build base rows from Tempo worklogs ---
    rows = []
    for wl in worklogs:
        issue_id = str(wl["issue"]["id"])   # numeric Jira ID
        account_id = wl["author"]["accountId"]
        hours = wl["timeSpentSeconds"] / 3600
        start_date = wl["startDate"]            # "YYYY-MM-DD"
        start_time = wl.get("startTime", "00:00:00")  # "HH:MM:SS"
        work_date_str = f"{start_date} {start_time[:5]}"  # "YYYY-MM-DD HH:MM"
        rows.append({
            "_issue_id": issue_id,
            "Logged Hours": hours,
            "User Account ID": account_id,
            "Work date": work_date_str,
        })

    t = pd.DataFrame(rows)

    # --- Resolve every unique issue ID via Jira (cached) ---
    unique_ids = t["_issue_id"].unique()
    print(f"  Fetching {len(unique_ids)} unique issues from Jira...")
    issue_data = {}
    for issue_id in unique_ids:
        issue_data[issue_id] = jira_client.get_issue(
            issue_id, jira_base_url, jira_email, jira_token, capex_field_id
        )

    # Map issue fields onto DataFrame
    t["Issue Key"] = t["_issue_id"].map(lambda i: issue_data[i]["key"])
    t["Full name"] = t["User Account ID"].map(members).fillna("")
    t["Issue Type"] = t["_issue_id"].map(lambda i: issue_data[i]["type"])
    t["Project Key"] = t["_issue_id"].map(lambda i: issue_data[i]["project_key"])
    t["Project Name"] = t["_issue_id"].map(lambda i: issue_data[i]["project_name"])
    t["Issue Status"] = t["_issue_id"].map(lambda i: issue_data[i]["status"])
    t["Capex Project Type"] = t["_issue_id"].map(lambda i: issue_data[i]["capex_type"])
    t["Parent Key"] = t["_issue_id"].map(lambda i: issue_data[i]["parent_key"])
    t.drop(columns=["_issue_id"], inplace=True)

    # --- Parent Key fixup ---
    def fix_parent(row):
        pk = row["Parent Key"]
        ik = row["Issue Key"]
        it = str(row["Issue Type"]).lower()
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

    # --- Time conversion to Eastern ---
    t["Time Conversion"] = t.apply(
        lambda row: _convert_to_eastern(row["Work date"], row["User Account ID"],
                                        user_timezones),
        axis=1,
    )
    t["Time Conversion"] = t["Time Conversion"].apply(
        lambda dt: pd.Timestamp(dt).floor("D") if dt is not None else None
    )

    # --- Work date columns ---
    t["Work date"] = pd.to_datetime(t["Work date"], errors="coerce")
    t["Work_date_only"] = t["Work date"].dt.date
    t["Work week"] = t["Work date"].apply(
        lambda d: _next_friday(d) if not pd.isna(d) else None
    )

    # --- Is Capex ---
    t["Is Capex"] = t["Capex Project Type"].apply(
        lambda x: False if pd.isna(x) or x == "Not Capex" else True
    )

    # --- Category ---
    t["Category"] = t.apply(
        lambda row: "Time off" if row["Parent Key"] == "PTO-00"
        else ("Non project time" if row["Parent Key"] == "TIME-00"
              else ("Capex Project Time" if row["Is Capex"]
                    else "Non Capex Project Time")),
        axis=1,
    )

    # --- User name (short display name) ---
    t["User name"] = t["User Account ID"].map(members)

    # --- Epic enrichment: Name, Simple name, Active Project ---
    unique_parents = t["Parent Key"].dropna().unique()
    print(f"  Fetching {len(unique_parents)} unique parent issues from Jira...")
    parent_data = {}
    for pk in unique_parents:
        if pk in ("PTO-00", "TIME-00"):
            parent_data[pk] = {"key": pk, "summary": "", "status": ""}
            continue
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
