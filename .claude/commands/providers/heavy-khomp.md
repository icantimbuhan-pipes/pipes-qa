# /providers:heavy-khomp

Full reference for the Outbound Heavy Khomp provider.

---

## Identity

| Field | Value |
|-------|-------|
| Name | Outbound Heavy Khomp |
| Key | `heavy-khomp` |
| File | `providers/heavy_khomp.py` |
| Env var | `HEAVY_KHOMP_API_KEY` |
| Status | ✅ Active |

---

## API Reference

**Endpoint:** `POST https://leads.pipes.ai/api/lead`  
**Auth:** `api_key` sent as a form parameter (no headers required)  
**Content-Type:** `application/x-www-form-urlencoded`

### Parameters

| Param | Value / Source | Notes |
|-------|---------------|-------|
| `api_key` | `$HEAVY_KHOMP_API_KEY` | from `.env` |
| `phone_number` | `$QA_PHONE_NUMBER` | Google Voice number being dialled |
| `ip_address` | `$QA_IP_ADDRESS` | test IP |
| `tcpa_consent` | `1` | always 1 for QA |
| `tcpa_consent_date` | today's date (auto) | set dynamically at runtime |
| `first_name` | `$QA_FIRST_NAME` | default: "Justin Bieber" |
| `email` | `$QA_EMAIL` | |
| `jornaya_leadid` | `$QA_JORNAYA_LEADID` | |
| `postal_code` | `$QA_POSTAL_CODE` | default: 32004 |
| `state` | `$QA_STATE` | default: FL |

### Success response

HTTP `200 OK` — no call ID is returned. A 200 means the call was queued.

### Failure responses

| Code | Meaning | Fix |
|------|---------|-----|
| `401` | Bad API key | Check `HEAVY_KHOMP_API_KEY` in `.env` |
| `422` | Missing/invalid param | Check all required fields are set |
| `5xx` | Server error | Retry once; if it persists, escalate |

---

## AMD Behavior (what to expect)

| Scenario | What Khomp AMD detects | IVR response |
|----------|----------------------|--------------|
| You say "Hello" | Live person | IVR plays |
| You say "Hello this is [Name]" | Live person | IVR plays |
| You say "Hey this is [Name] with Pipes how may I help you?" | Machine/voicemail | IVR stops |
| You say nothing | Live person | IVR plays |

---

## Khomp vs Freeswitch differences

- **Khomp**: hardware-based AMD, generally more reliable on noisy lines
- **Freeswitch (FS)**: software AMD, faster detection but more sensitive to background noise

If Khomp AMD is failing on test 3 (voicemail detection), the phrase may not be long enough to trigger detection — try adding a longer sentence.

---

## Troubleshooting

**Call triggers but IVR never plays:**
- Check that `QA_PHONE_NUMBER` is the correct Google Voice number
- Verify the number can receive calls (not on DND)

**AMD test 3 not detecting voicemail:**
- Speak the full phrase clearly and at a normal pace
- Khomp needs ~3 seconds of continuous speech to classify as machine
- Add a short pause before speaking

**Call triggers but no ring:**
- The API returned 200 but the call may be rate-limited
- Wait 60 seconds and retry

---

## Env vars needed (in `.env`)

```
HEAVY_KHOMP_API_KEY=l6OaLWvqXoBz9pDgz9Rxbn3JwG2rP8jN
QA_PHONE_NUMBER=5122227114
QA_IP_ADDRESS=79.116.129.221
QA_EMAIL=icantimbuhan@pipes.ai
QA_JORNAYA_LEADID=93C30C8C-FA4F-D125-0622-2D176826CBED
QA_POSTAL_CODE=32004
QA_STATE=FL
QA_FIRST_NAME=Justin Bieber
```
