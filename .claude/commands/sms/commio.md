# /sms:commio

Commio SMS deliverability — CSV upload format, status codes, campaign checker, Slack reporting.

Portal URL prefix: `/commio`

---

## CSV format — required columns

Commio exports are row-per-message. Three columns are required; others are optional but imported when present:

**Required:**

| Column | Notes |
|--------|-------|
| `delivery_status_code` | Numeric status (see table below) |
| `created` | Timestamp of the message |
| `campaign_id` | Matched against campaign map |

**Optional but used if present:**

| Column | Notes |
|--------|-------|
| `from_did` | Sender DID |
| `to_did` | Recipient number |
| `msg_count` | Number of segments |
| `carrier` | Carrier name |
| `direction` | Message direction |

Column names are fuzzy-matched — common aliases accepted.

---

## Delivery status codes

| Code | Meaning |
|------|---------|
| `200` | Delivered ✅ |
| `005` | Undeliverable |
| `600` | Unregistered traffic |
| `700` | Opt-out filtered |
| `800` | Carrier blocked |
| `900` | Carrier disabled |

**Delivery logic**: `delivery_status_code == "200"` → delivered; anything else → failed.

---

## Routes

| Route | What it shows |
|-------|---------------|
| `/commio/upload` | Upload form + report date selector |
| `/commio/reports` | Company list with delivery rates + avg msgs/min |
| `/commio/report/<slug>` | Per-company KPIs, failure breakdown, message rows |
| `/commio/report/<slug>/download` | CSV export |
| `/commio/campaigns` | Cross-provider campaign ID checker (see below) |
| `/commio/send-slack` | POST — send Slack report for a period |

---

## Campaign checker — `/commio/campaigns`

Shows every campaign ID across all three providers (Telgorithm, Signalmash, Commio) in one table:

- **Complete**: ID exists in all 3 providers
- **Incomplete**: ID missing from one or more providers
- **Conflict**: Same ID maps to different company names across providers
- **Unmapped**: IDs found in uploaded Commio data that aren't in any campaign map

Use this page to diagnose missing companies and find IDs to add.

---

## Slack report

Sent via `SLACK_WEBHOOK_URL` env var. Triggered by the "Send to Slack" button on the reports page.

Supports day / week / month views — the Slack report matches whichever view is active.

---

## Campaign map

File: `sms_deliverability/commio/campaign_map.py`

Same company list as Telgorithm and Signalmash. When adding a new company:
1. Find the Campaign ID on `/commio/campaigns` (unmapped section)
2. Add it to all three campaign maps
3. Re-upload the CSV — existing unmapped records need re-import to pick up the company name

---

## DB schema

Table: `commio_records` — `data/sms_commio.db`

Key columns: `created`, `from_did`, `to_did`, `msg_count`, `delivery_status_code`, `status_description`, `campaign_id`, `carrier`, `direction`, `company_name`, `report_date`, `batch_id`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Missing required columns" | CSV must have `delivery_status_code`, `created`, `campaign_id` |
| Company missing from reports | Check `/commio/campaigns` for the Campaign ID — add to map and re-upload |
| Conflict shown in campaign checker | Same Campaign ID maps to different names across providers — check all 3 maps |
| Slack didn't send | Verify `SLACK_WEBHOOK_URL` is set in `.env` |
