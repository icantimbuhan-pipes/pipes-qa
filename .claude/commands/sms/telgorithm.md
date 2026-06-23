# /sms:telgorithm

Telgorithm SMS deliverability — CSV upload format, error codes, Slack reporting.

Portal URL prefix: `/telgorithm`

---

## CSV format — required columns

Telgorithm exports are row-per-message. All 10 columns are required:

| Column | Notes |
|--------|-------|
| `CreatedOn` | Timestamp of the message |
| `From` | Sender DID |
| `To` | Recipient number |
| `TextSegmentCount` | Number of SMS segments |
| `Status` | `Delivered` or `Undelivered` |
| `ErrorCode` | Blank when delivered |
| `ErrorDescription` | Blank when delivered |
| `Campaign ID` | Matched against campaign map |
| `RecipientCarrierName` | Carrier name |
| `Text` | Message body |

**Delivery logic**: `Status == "Delivered"` → delivered; anything else → failed.

Column names are fuzzy-matched — common aliases like `campaign_id`, `carrier`, `created_on` are accepted.

---

## Upload

`POST /telgorithm/upload` — upload the CSV and set a report date (defaults to today).

After upload, you land on `/telgorithm/reports?date=YYYY-MM-DD`.

---

## Routes

| Route | What it shows |
|-------|---------------|
| `/telgorithm/upload` | Upload form |
| `/telgorithm/reports` | Company list with delivery rates + avg msgs/min |
| `/telgorithm/report/<slug>` | Per-company KPIs, failure breakdown, message rows |
| `/telgorithm/report/<slug>/download` | CSV export of the report |
| `/telgorithm/records` | Raw message log, all companies |
| `/telgorithm/send-slack` | POST — send Slack report for a date |

---

## Slack report

Sent via `SLACK_WEBHOOK_URL` env var. Triggered by the "Send to Slack" button on the reports page or by posting to `/telgorithm/send-slack` with `date=YYYY-MM-DD`.

Report includes: company name, total / delivered / failed / rate / avg msgs per min + top failure reasons.

---

## Campaign map

File: `sms_deliverability/telgorithm/campaign_map.py`

Maps Campaign ID → company name. Same IDs as Signalmash and Commio — keep all three in sync.

Current companies: HTM Primary, NextGen Leads, Roadway Moving, Bold Moving and Storage, Bravo Moving, Joyce Van Lines, Property Leads, Safeway Moving, Solomon & Sons Relocation Service Inc, Good Greek Moving & Storage, Universal Accounting Center, Choice Tax Relief, ACA Helpline LLC, NSP, SailsFlow, Vivint, Lagoon Media, Apollo Interactive, LeadScorz, Pipes Website Followup.

---

## DB schema

Table: `telgorithm_records` — `data/sms_telgorithm.db`

Key columns: `created_on`, `from_number`, `to_number`, `text_segment_count`, `status`, `error_code`, `error_description`, `campaign_id`, `recipient_carrier_name`, `company_name`, `report_date`, `batch_id`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Missing required columns" | Check CSV headers match expected names (see table above) |
| Company shows no data | Campaign ID not in `telgorithm/campaign_map.py` — add it |
| Avg msgs/min shows `—` | Only one timestamp in the upload; normal for small batches |
| Slack didn't send | Check `SLACK_WEBHOOK_URL` is set in `.env` |
