# /validator:run

API Validator — fire test leads against the Pipes API to verify rejection logic for specific scenarios.

Portal URL: `/validator`

---

## What it does

Sends a POST to `https://leads.pipes.ai/api/lead` with a real provider API key and controlled param overrides. Checks the response against an expected rejection code and shows pass/fail.

Use it to confirm the API is correctly enforcing rules for invalid Jornaya IDs, expired TCPA consent, bad phone numbers, DNC status, and more.

---

## Before running

Each test uses a provider's API key — you need at least one configured.

Priority order for API key lookup:
1. DB config at `/api-configs` (per-provider saved config)
2. `.env` file (e.g. `HEAVY_KHOMP_API_KEY`)

If no key is found for the selected provider, the API returns a rejection immediately. Check `/api-configs` to confirm the key is saved.

Shared params (phone, IP, email, Jornaya Lead ID) come from:
1. Saved QA settings at `/api-configs` (shared section)
2. `.env` fallback (`QA_PHONE_NUMBER`, `QA_IP_ADDRESS`, `QA_EMAIL`, `QA_JORNAYA_LEADID`)

---

## Providers available

| Key | Name |
|-----|------|
| `heavy_khomp` | Heavy Khomp (ThinQ) |
| `heavy_khomp_dynamic` | Heavy Khomp Dynamic |
| `lite_khomp` | Lite Khomp |
| `tbi_khomp` | TBI Khomp |
| `tbi_fs` | TBI Freeswitch |
| `signalmash_khomp` | Signalmash Khomp |
| `signalmash_fs` | Signalmash Freeswitch |
| `accident_office` | Accident Office (RetellAI) |

---

## Test scenarios

| Scenario | Category | Expected rejection |
|----------|----------|-------------------|
| Valid Jornaya Lead ID | Jornaya | Any (or accepted) |
| Invalid Jornaya Lead ID | Jornaya | `invalid jornaya leadid` |
| Expired TCPA Consent (91 days) | TCPA | `fed DNC 90 safety check` |
| Invalid Phone Number | Phone | `invalid phone number` |
| Invalid Postal Code | Location | `invalid postal code` |
| Invalid State | Location | `invalid state` |
| DNC Status Check | DNC | Any (shows current DNC status) |
| No Jornaya Lead ID | Jornaya | `no jornaya leadid provided` |

Each scenario card shows the editable params — you can change them before running.

---

## Reading results

- **✅ Got expected rejection** — the API rejected with exactly what was expected
- **✅ Accepted** — for scenarios with no specific expected rejection
- **⚠ Accepted — expected a rejection** — the API let the lead through when it shouldn't have
- **⚠ Wrong rejection** — the API rejected, but for a different reason than expected
- **✗ Network error** — couldn't reach `leads.pipes.ai`

Expand "Full Response & Params Sent" on any card to see the raw API response and exactly what was posted.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Button does nothing when clicked | Check browser console for JS errors; ensure the page fully loaded |
| All scenarios show "accepted" | API key may be invalid — check `/api-configs` |
| "Network error" on every test | Portal can't reach `leads.pipes.ai` — check network/VPN |
| Wrong rejection on expired TCPA | Some providers don't enforce the 90-day check — expected behavior |
| DNC Status Check shows "already dnc" | QA phone is suppressed — remove it from DNC, then re-run |

---

## Related skills

- `/validator:add-scenario` — add a new rejection test scenario
- `/providers:heavy-khomp` — Heavy Khomp API reference
