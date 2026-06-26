# /sms:run

SMS Deliverability reporting workflow. Upload carrier export CSVs, view per-company delivery rates, and send Slack summaries.

---

## Overview

Three providers, each with its own upload format and URL prefix inside the portal:

| Provider | URL prefix | Delivered = | CSV format |
|----------|-----------|-------------|------------|
| Telgorithm | `/telgorithm` | `Status == Delivered` | Row per message (10 cols) |
| Signalmash | `/signalmash` | `dlr_code == 0` | Aggregate rows (DLR cols) |
| Commio | `/commio` | `delivery_status_code == 200` | Row per message (3+ cols) |

---

## Workflow — each provider follows the same steps

1. **Get the CSV export** from the carrier portal for the date(s) you want.
2. **Upload** at the provider's `/upload` route.
3. **View reports** at `/reports` — company list with delivered/failed rates.
4. **Drill into a company** at `/report/<slug>` — KPIs + failure breakdown.
5. **Send to Slack** using the Send to Slack button (Telgorithm and Commio only).
6. **Download CSV** from any company report for offline sharing.

---

## Viewing modes

All three providers support day / week / month views via `?view=day|week|month&date=YYYY-MM-DD`.

---

## Adding a company to the reports

Companies appear automatically when their Campaign ID is in the campaign map.
If a new company's messages show as "unmapped":

1. Find the Campaign ID in the upload (Commio's `/commio/campaigns` shows unmapped IDs).
2. Add the ID → company name entry to all three campaign maps:
   - `sms_deliverability/telgorithm/campaign_map.py`
   - `sms_deliverability/signalmash/campaign_map.py`
   - `sms_deliverability/commio/campaign_map.py`
3. Re-upload — existing records are NOT retroactively re-mapped (re-import needed).

---

## Database files

| Provider | DB path |
|----------|---------|
| Telgorithm | `data/sms_telgorithm.db` |
| Signalmash | `data/sms_signalmash.db` |
| Commio | `data/sms_commio.db` |

Each is SQLite, isolated. WAL mode enabled on all.

---

## Related skills

- `/sms:telgorithm` — Telgorithm CSV format, columns, error codes, Slack setup
- `/sms:signalmash` — Signalmash DLR aggregate format, error code reference
- `/sms:commio` — Commio status codes, campaign checker, Slack setup
