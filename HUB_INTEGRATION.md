# Hub Integration — Tempo CapEx Reports

After every run, `main.py` formats a plain-text progress report and posts it to a
configured Hub conversation channel. Because the Hub API is text-only (no file
attachments), the message contains per-person stats that tell the same story as
the charts.

---

## What the message shows

```
Agent Experience Product Team — CapEx progress report as of 2026-06-02 14:30 ET.
Period: 2026-05-23 → 2026-06-26 (24 calendar days remaining). Remember, CapEx period ends on 2026-06-26.

TEAM PROGRESS (8 working days elapsed):

  Alice            32.5h CapEx  |  trend → 64h  |  0 of 8 days not reported
  Bob              28.0h CapEx  |  trend → 56h  |  2 of 8 days not reported  |  8.0h PTO (adj. target: 70.0h)
  Charlie           0.0h CapEx  |  trend →  0h  |  5 of 8 days not reported

---
CapEx hours = all hours logged to CapEx-eligible Jira issues this period. Target: 80h
(reduced proportionally for any PTO taken on weekdays).
Trend = projected CapEx total by period end, extrapolated from current pace.
Days not reported = weekdays (Mon–Fri) from period start through today with zero hours logged.
All times are Eastern. Team members in earlier time zones (e.g. India IST) who log
after midnight local time will have those hours counted on the previous Eastern calendar day.
```

### Column guide

| Column | Meaning |
|--------|---------|
| **CapEx hours** | All hours logged to CapEx-eligible Jira issues since period start |
| **Trend** | Projected total CapEx hours by period end, based on current daily pace |
| **Days not reported** | Weekdays (Mon–Fri) from period start through today with **zero** hours logged |
| **PTO** | Weekday PTO hours logged (weekends excluded — they don't count toward the target) |
| **Adj. target** | 80h reduced proportionally for PTO days taken (e.g. 2 days PTO out of 20 → 72h target) |

---

## Configuring the Hub channel

Each team in `teams.json` can have an optional `hub_conversation_id`. The ID comes
from the conversation URL:

```
https://hub.exprealty.com/messages/?conversation=d3cd64f4-dd9c-49f6-ac0e-589e9f955a3e
                                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                   this is the hub_conversation_id
```

### Add or update a channel

```bash
# Set channel for an existing team
python manage_teams.py set-channel "Agent Experience Product Team" \
  "https://hub.exprealty.com/messages/?conversation=d3cd64f4-dd9c-49f6-ac0e-589e9f955a3e"

# Or pass the bare UUID
python manage_teams.py set-channel "Agent Experience Product Team" \
  "d3cd64f4-dd9c-49f6-ac0e-589e9f955a3e"

# Add a new team with a channel in one step
python manage_teams.py add "Another Team" \
  --hub-channel "https://hub.exprealty.com/messages/?conversation=<uuid>"
```

---

## Getting an API key

1. Ask a Hub administrator to create an API app with the **`messages:write`** scope.
2. Add the key to your `.env` file:
   ```
   HUB_API_KEY=hub_your_key_here
   ```
3. The API key is validated against the Hub on every run. Keep it secret.

---

## Preview before going live

Every run writes `Hub_Message_Preview.md` inside each team's output folder, regardless
of whether `HUB_API_KEY` is set. Open it to review exactly what would be posted.

---

## Skipping Hub posting

Pass `--no-hub` to skip the API call for a run (the preview MD is still written):

```bash
python main.py --no-hub
```

Posting is also automatically skipped if:
- `HUB_API_KEY` is not set in `.env`
- The team has no `hub_conversation_id` in `teams.json`

---

## Thresholds and targets

Both the chart labels and the Hub message text reference config constants — change
them once in `config.py` and everything updates:

| Constant | Default | Used in |
|----------|---------|---------|
| `CAPEX_TARGET_HOURS` | `80` | Cumulative CapEx chart target line; Hub message target |
| `DAILY_HOURS_THRESHOLD` | `6` | Daily Hours Table ✓/✗ cutoff; Hub message footnote |
