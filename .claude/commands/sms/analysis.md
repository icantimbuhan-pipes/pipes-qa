# /sms:analysis — SMS Deliverability Analysis & KPI Report

Use this skill to analyze KPI summaries, diagnose failure patterns, identify root causes, and generate action plans for clients. Works across Telgorithm, Commio, and Signalmash.

---

## How to run an analysis

1. Open the portal at `http://localhost:5001`
2. Go to the telco's **Reports** page and pick the date range (Day / Week / Month)
3. Look at the **Delivered Rate** and **Top failure** columns per company
4. Use this skill as the reference to interpret codes and build action plans
5. Click **Send to Slack** — the report will include 🚨 alerts for any client below 94%

For a 3-month baseline: use the **Month** view and compare the last 3 months per company.

---

## Delivery rate thresholds

| Rate | Status | Action |
|------|--------|--------|
| ≥ 95% | ✅ Healthy | Monitor monthly |
| 94–94.9% | ⚠️ Warning | Review top failure, act within the week |
| < 94% | 🚨 Alert | Immediate action — Slack alert fires automatically |
| < 80% | 🔴 Critical | Escalate to client immediately |

The Slack report automatically flags any company below 94% at the top of the message.

---

## Error codes — Telgorithm & Commio

Both use the same 6 status codes.

| Code | Label | Root Cause | Action Plan |
|------|-------|-----------|-------------|
| 200 | Delivered | — | Nothing needed |
| 005 | Undeliverable | Number disconnected, ported out, deactivated SIM, or invalid format | Run number validation/lookup API; remove persistent failures from list |
| 600 | Unregistered Traffic | 10DLC campaign not approved on that carrier, or registration expired | Log into TCR and check campaign status per carrier; resubmit if expired |
| 700 | Opt Out Filtered | Recipient sent STOP; carrier honors it automatically | Add to DNC immediately; never re-contact without fresh consent |
| 800 | Carrier Blocked | Content triggered spam filter OR sender number has high complaint rate | Review message body for blocked phrases (see below); rotate sender if complaints are high |
| 900 | Carrier Disabled | Sender number/account suspended by carrier due to repeated violations | Contact carrier to appeal; audit all campaigns on that number; provision a new sender if needed |

---

## Error codes — Signalmash (DLR codes)

| Code | Label | Root Cause | Action Plan |
|------|-------|-----------|-------------|
| 0 | Delivered | — | Nothing needed |
| 1 | Source not found | FROM number not provisioned in Signalmash or routing misconfigured | Verify FROM number is active and registered |
| 6 | EC_ABSENT_SUBSCRIBER_SM | Device powered off or out of coverage | Retry after 24 h; remove if still failing after 3 attempts |
| 15 | Screening block | Carrier spam filter flagged the content | Review message for blocked phrases; ensure opt-out is present |
| 21 | Expired | Phone was unreachable during validity window | Reduce message validity period; retry once |
| 31 | Subscriber busy (inbox full) | Recipient's SMS storage is full | Retry after a few hours |
| 32 | EC_SM_DELIVERY_FAILURE | Network congestion or carrier-side failure | Retry once; contact Signalmash if > 1% of total volume |
| 34 | Message Validity Expired | Same as 21 — message held past TTL | Same as 21 |
| 45 | MDN BLOCKED | Number is on carrier's MDN blacklist (prior STOP, complaint, or deactivated) | Remove number from ALL campaigns immediately; check against carrier DNC feed |
| 60 | Campaign not active on AT&T | 10DLC campaign not registered or approved on AT&T | Check TCR for AT&T-specific campaign status; resubmit if missing |
| 61 | Destination blocked | Network-level block (similar to 45, carrier-specific) | Remove number; check if a pattern of carrier blocks emerges |
| 64 | Blocked — exceeded quota | Too many messages sent from the campaign too quickly | Throttle sending velocity; stay within campaign daily cap |
| 66 | Data coding scheme blocked | Unicode/emoji characters not supported by recipient carrier | Convert message body to GSM-7 only (remove emoji, smart quotes, em-dashes) |
| 69 | Sending limit reached | Daily campaign cap hit | Request higher limits from Signalmash or spread volume over more days |
| 153 | Absent subscriber | Device unreachable (see code 6) | Same as code 6 |
| 201 | Absent subscriber, IMSI detached | SIM removed or device off for extended period | Remove from list if absent after 72 h |
| 300 | Invalid destination address | Number does not exist, wrong format, or ported with errors | Validate number format (10-digit NANP); remove failed numbers |
| 310 | Invalid source address | FROM number is misconfigured or deregistered | Verify FROM number configuration in Signalmash dashboard |
| 321 | ESME Receiver reject | SMSC-level protocol rejection — possible compliance violation | Review message formatting; contact Signalmash with batch ID |
| 322 | ESME Receiver temporary error | Transient SMSC or network issue | Automatic retry; escalate if > 2% of volume |
| 349 | Request failed | Catch-all; details in SMSC logs | Contact Signalmash support with batch ID from the upload |
| 409 | MC vendor specific error | Carrier proprietary block | Identify which carrier column is highest; contact Signalmash for carrier-specific guidance |

---

## Carrier-specific behavior

### Verizon
- **MDN BLOCKED (45)** — Verizon runs an aggressive MDN blacklist. Once a number receives a STOP or generates a complaint, it is permanently blocked from that sender. This is the most common Verizon failure.
  - Action: Replace the sending DID, ensure 10DLC is compliant, audit opt-out list
- **Carrier Blocked (800)** — Verizon's content filter is strict on debt/financial language.
  - Action: Avoid "debt relief", "consolidation", "pre-approved", "no credit check"

### T-Mobile
- **Invalid destination address (300)** — T-Mobile returns this when the MDN doesn't resolve cleanly in their network, especially for recently ported numbers.
  - Action: Use an LRN lookup to verify portability; remove numbers that fail consistently
- **Unregistered Traffic (600)** — T-Mobile has strict 10DLC enforcement; unregistered campaigns are blocked at the gateway.
  - Action: Verify campaign is active in TCR and approved specifically for T-Mobile

### AT&T
- **Campaign not active on AT&T (60)** — AT&T requires each campaign to be explicitly approved on their network. Approval is separate from TCR registration.
  - Action: Log into TCR → select the campaign → check AT&T status; appeal if rejected

### Other carriers (T-Mobile MVNO, regional)
- Often inherit T-Mobile's blocking rules (Metro, Cricket uses AT&T rules)
- High failure on regional carriers usually points to 10DLC registration gaps

---

## Content that gets automatically blocked

Carriers and SMS spam filters will block messages containing any of the following:

### Profanity / explicit
- Any profanity or sexual content
- Threats or violent language

### SHAFT categories (automatic block)
Carriers have zero tolerance for these without age verification opt-in:
- Sex / adult content
- Hate speech
- Alcohol promotions (to non-opted-in users)
- Firearms sales
- Tobacco / vaping promotions

### Financial spam triggers
- "Guaranteed" / "risk-free" / "risk free"
- "No credit check" / "pre-approved"
- "Debt relief" / "debt consolidation" / "debt settlement"
- "You owe" / "account past due" (without proper context)
- "Click here for $" / "you won" / "claim your prize"
- Excessive urgency: "ACT NOW", "EXPIRES TONIGHT", "LIMITED TIME"

### Format issues that trigger spam scores
- All caps throughout the body
- Excessive punctuation (!!!, ???)
- URL shorteners (bit.ly, tinyurl.com) — use branded short domains or full URLs
- Missing opt-out language — every message needs something like "Reply STOP to opt out"
- Smart quotes ( " " ' ' ) and em-dashes (—) — convert to plain ASCII before sending
- Emojis in high volume → can cause code 66 (data coding scheme blocked)

### What carriers expect to see
- Company name identified in the message body
- Clear call-to-action
- Opt-out instruction ("Reply STOP to unsubscribe")
- No deceptive sender identity

---

## From number hygiene (sending number health)

A "clean" sending number has:
- Active 10DLC campaign registration (not expired, not rejected)
- Opt-out rate below 5% (>5% = yellow flag; >10% = replace the number)
- No active carrier complaints
- Message use case that matches the campaign type
- Not recycled from a high-complaint previous user

Check sending number health:
1. Log into the Telgorithm / Signalmash / Commio portal and check number status
2. Look at opt-out rate over the last 30 days
3. If a number has a high MDN BLOCKED rate → retire it and provision a new DID

---

## To number hygiene (recipient number health)

Before sending, a healthy recipient number should:
- Be a valid 10-digit US NANP format (no country code prefix)
- Be a mobile number — not landline or VoIP (use carrier lookup)
- Not be on your internal DNC / opt-out list
- Not have previously returned STOP to your campaign
- Have an active MDN (use number validation / LRN lookup API)

Signs of a dirty number list:
- > 3% Undeliverable (code 005) → list has many disconnected numbers
- > 2% MDN BLOCKED (code 45) → numbers from a low-quality lead source
- > 5% Opt Out Filtered (code 700) → audience mismatch or over-messaging

---

## 3-month baseline framework

Use the **Month** view in the portal to compare the last 3 months.

For each company, track month over month:

| Metric | What to look for |
|--------|-----------------|
| Delivered rate | Downward trend = worsening problem |
| Top failure code | New codes appearing = new issue category |
| Top failure carrier | Carrier-specific block emerging |
| Volume | Big volume spike can temporarily drag rate down |

**Interpreting trends:**
- Rate dropping + same failure code → the root cause was not fixed
- Rate dropping + new failure code → new problem introduced (content change? new list?)
- Rate stable but volume grew → healthy list growth
- Rate stable but volume dropped → client may have paused sends

---

## How to build an action plan for a client

1. **Find their top 2 failure codes** from the failure breakdown table in the portal
2. **Look them up** in the tables above — get root cause and action
3. **Check which carrier** has the highest failure count (shown in the Top failure column)
4. **Check message content** — ask client to share recent message templates; review against blocked content list
5. **Check number health** — look at Undeliverable rate; if > 3%, their list needs scrubbing
6. **Write the plan:**
   - What the error means (plain English)
   - Why it's happening (carrier-specific cause)
   - What to do this week (immediate fix)
   - What to do this month (structural improvement)

---

## Quick diagnosis cheat sheet

| Symptom | Most likely cause | First action |
|---------|------------------|--------------|
| High 800 / Carrier Blocked | Content spam triggers | Review message templates |
| High 005 / Undeliverable | Dirty number list | Run number validation scrub |
| High 700 / Opt Out | Over-messaging or irrelevant content | Reduce frequency, improve targeting |
| High 600 / Unregistered | 10DLC registration lapsed | Check TCR and renew |
| High 45 / MDN BLOCKED | Sending to opted-out / blacklisted numbers | Audit DNC list and number sources |
| High 60 | AT&T campaign not active | Check AT&T status in TCR |
| High 66 | Unicode characters in message | Strip to GSM-7 ASCII |
| High 300 | Invalid destination numbers | Validate and scrub list |
