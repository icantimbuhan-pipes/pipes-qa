# /dnc:portal

Manual DNC portal — paste phone numbers, fire the DNC postback to Pipes, see the result immediately.

Portal URL: `/dnc`

---

## What it does

Two ways to DNC a number:

| Method | How |
|--------|-----|
| **Manual** | Paste numbers into the form at `/dnc` → click "🚫 DNC Numbers" |
| **Slack bot** | React ✔️ on any Slack message containing a phone number → see `/dnc:slack-bot` |

Both methods call the same DNC API and log to the same DNC Log on the right side of the page.

---

## Manual DNC — step by step

1. Open `/dnc` in the portal
2. Paste one or more numbers into the textarea — any format works (see below)
3. The preview chips appear as you type — confirm the right numbers are detected
4. Click **🚫 DNC Numbers**
5. Each number shows ✅ success or ❌ failed inline, and the row appears in the DNC Log

The button is disabled until at least one valid number is detected.

---

## Phone number formats accepted

The parser handles all of these in the same paste:

```
5122227114
15122227114
+15122227114
(512) 222-7114
(512)2227114
512-222-7114
512.222.7114
512 222 7114
```

Multiple numbers in one paste — one per line, comma-separated, or embedded in text — are all extracted and DNCed together.

---

## DNC API

All submissions (manual and Slack) post to:

```
POST https://integrations.pipes.ai/api/lead/do-not-call/7l6OaLWvqXoBz9pDVeExbn3JwG2rP8jN
     body: phone=<10-digit-number>
```

HTTP < 400 → success. Any other response → failed.

---

## Routes

| Route | What it does |
|-------|-------------|
| `GET /dnc` | Portal page — form + DNC log |
| `POST /dnc/submit` | DNC all numbers in the textarea; returns JSON `{results: [{phone, formatted, status}]}` |
| `POST /dnc/parse` | Preview only — returns parsed numbers without DNCing |

---

## Slack flow (quick reference)

1. Post a phone number in **#test-hihi**
2. React with **✔️ :heavy_check_mark:** (not 👍, not ✅)
3. Bot replies ✅ (DNC'd) or ❌ (API failed)
4. Entry appears in the DNC Log with source = "slack"

See `/dnc:slack-bot` for full bot setup and troubleshooting.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Button stays disabled | No valid 10-digit number detected — check the preview chips |
| Result shows ❌ failed | DNC API returned HTTP ≥ 400 — check that the number is a valid US number |
| Number parsed but wrong format | Paste just the digits (e.g. `5122227114`) to force exact match |
| Slack reactions not DNCing | Bot may not be running — see `/dnc:slack-bot` |
