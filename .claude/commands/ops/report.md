# /ops:report

View, resend, or export the last QA monitoring report.

---

## Usage

```
/ops:report [--resend] [--provider <key>] [--last <n>]
```

- `--resend` — resend the last report to Slack
- `--provider <key>` — filter to a specific provider
- `--last <n>` — show the last N reports (default: 1)

---

## What to do

1. List JSON files in `data/reports/` sorted by most recent:
   ```bash
   ls -lt data/reports/*.json 2>/dev/null | head -10
   ```

2. Load the requested report(s) and display:
   - Provider name
   - Date/time
   - Pass/fail per section
   - Any failure notes
   - Overall result

3. If `--resend` was passed:
   ```bash
   uv run python -c "
   import json
   from runner.report import send_slack_report
   data = json.load(open('data/reports/<latest>.json'))
   sent = send_slack_report(data)
   print('Sent' if sent else 'SLACK_WEBHOOK_URL not set')
   "
   ```

4. If no reports exist yet, say so and suggest running `/qa:run`.

---

## Report file format

Reports are saved as `data/reports/<provider_key>_<YYYYMMDD_HHMM>.json`:

```json
{
  "provider": "Outbound Heavy Khomp",
  "started_at": "2026-06-20T09:00:00",
  "finished_at": "2026-06-20T09:15:00",
  "passed": 22,
  "total": 22,
  "sections": [
    {
      "title": "IVR Quality Check",
      "items": [
        { "id": "ivr_ob_clarity", "text": "...", "passed": true, "note": "" }
      ]
    }
  ]
}
```
