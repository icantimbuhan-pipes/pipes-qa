# /dnc:report

View, query, and export the DNC log — all manual and Slack-triggered DNC actions.

---

## Where to view it

**In the portal:** The DNC Log panel on the right side of `/dnc` shows the last 100 entries with phone, status, source, and timestamp. New entries appear live after a manual submission without a page reload.

**In the database:** All entries are in the `dnc_log` table in `data/portal.db`.

---

## DNC log schema

Table: `dnc_log` in `data/portal.db`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment PK |
| `phone` | TEXT | 10-digit number |
| `status` | TEXT | `success` or `failed` |
| `source` | TEXT | `manual` (portal form) or `slack` (bot reaction) |
| `slack_channel` | TEXT | Channel ID when source = slack; blank otherwise |
| `created_at` | TEXT | ISO timestamp (UTC) |

---

## Query examples

```bash
# Open the DB
sqlite3 data/portal.db

# All entries, newest first
SELECT phone, status, source, created_at FROM dnc_log ORDER BY created_at DESC LIMIT 50;

# Only failures
SELECT phone, source, created_at FROM dnc_log WHERE status = 'failed' ORDER BY created_at DESC;

# Count by source
SELECT source, COUNT(*) AS total, SUM(status='success') AS ok, SUM(status='failed') AS failed
FROM dnc_log GROUP BY source;

# Check if a specific number was DNC'd
SELECT * FROM dnc_log WHERE phone = '5122227114' ORDER BY created_at DESC;

# Today's entries
SELECT * FROM dnc_log WHERE created_at >= date('now') ORDER BY created_at DESC;
```

---

## Export to CSV

```bash
sqlite3 -header -csv data/portal.db \
  "SELECT phone, status, source, slack_channel, created_at FROM dnc_log ORDER BY created_at DESC" \
  > dnc_export.csv
```

---

## Clearing the log

The portal UI shows the last 100 entries — it does not have a delete function. To clear old entries from the DB:

```bash
sqlite3 data/portal.db "DELETE FROM dnc_log WHERE created_at < date('now', '-30 days');"
```

---

## Related skills

- `/dnc:portal` — how to DNC a number manually via the portal form
- `/dnc:slack-bot` — how the Slack bot works and how to set it up
