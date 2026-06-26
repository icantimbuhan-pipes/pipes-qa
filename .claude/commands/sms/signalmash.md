# /sms:signalmash

Signalmash SMS deliverability — DLR aggregate CSV format, error code reference.

Portal URL prefix: `/signalmash`

---

## CSV format — required columns + DLR columns

Signalmash exports are **aggregate rows** (not per-message). Each row = one combination of date + from number + carrier + campaign, with DLR code counts as separate columns.

**Required fixed columns** (column name aliases accepted):

| Canonical | Accepted aliases |
|-----------|-----------------|
| `monthnum` | `month_num`, `month` |
| `day` | `day` |
| `year` | `year` |
| `from_number` | `fromnumber`, `from` |
| `operator` | `operator` |
| `mobility` | `mobility` |
| `campaignid` | `campaign_id`, `campaignsid`, `campaign sid` |

**DLR columns**: any column whose header is a number (e.g. `0`, `201`, `45`) is treated as a DLR code with a count value. Rows where the count is 0 or blank are skipped.

Date is built from `monthnum` + `day` + `year` — there is no single date column.

---

## Delivery logic

`dlr_code == "0"` → delivered. All other codes → failed.

---

## DLR error code reference

| Code | Description |
|------|-------------|
| `0` | Delivered to device |
| `1` | Source not found (internal routing error) |
| `6` | Absent subscriber |
| `15` | Screening block |
| `21` | Expired |
| `31` | Subscriber busy for MT SMS |
| `32` | SM delivery failure |
| `34` | Message validity expired |
| `45` | MDN blocked |
| `60` | Campaign not active on AT&T |
| `61` | Destination blocked |
| `64` | Blocked — exceeded quota |
| `66` | Data coding scheme blocked |
| `69` | Sending limit reached |
| `153` | Absent subscriber |
| `201` | Absent subscriber, IMSI detached |
| `300` | Invalid destination address |
| `310` | Invalid source address |
| `321` | ESME receiver reject error |
| `322` | ESME receiver temporary error |
| `349` | Request failed |
| `409` | MC vendor specific errors |

---

## Routes

| Route | What it shows |
|-------|---------------|
| `/signalmash/upload` | Upload form |
| `/signalmash/reports` | Company list with delivery rates |
| `/signalmash/report/<slug>` | Per-company KPIs, failure breakdown by carrier + DLR code, paginated records |
| `/signalmash/report/<slug>/download` | CSV export |

Signalmash does **not** have a Slack send button (Telgorithm and Commio only).

---

## Campaign map

File: `sms_deliverability/signalmash/campaign_map.py`

Same company list as Telgorithm and Commio. Keep all three in sync when adding a new company.

---

## DB schema

Table: `signalmash_records` — `data/sms_signalmash.db`

Key columns: `report_date`, `from_number`, `operator`, `mobility`, `campaign_id`, `company_name`, `dlr_code`, `dlr_description`, `count`, `batch_id`

Note: `count` holds the aggregate message count for that DLR code in that row (not 1 per record).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Missing required columns" | Check that monthnum/day/year/from_number/operator/mobility/campaignid are present |
| No DLR data imported | DLR columns must be numeric headers (e.g. `0`, `201`) — check column names |
| "CSV has no non-zero delivery records" | All DLR counts are 0 or blank in the file |
| Company unmapped | Campaign ID not in `signalmash/campaign_map.py` — add it, then re-upload |
