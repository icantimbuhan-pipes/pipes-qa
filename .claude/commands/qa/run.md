# /qa:run

Master orchestrator for the Pipes Daily Monitoring QA. Run this every day (or every hour) to verify all outbound call flows are working.

---

## What this does

Triggers outbound calls via the Pipes API, walks you through a 22-item checklist while you answer on Google Voice, then sends a full pass/fail report to Slack.

5 total calls per provider:
- 1 call at the start (IVR Quality + Dispositions)
- 4 calls for AMD Detection Tests (one per scenario)

---

## Providers

| Key | Name | Status |
|-----|------|--------|
| `heavy-khomp` | Outbound Heavy Khomp | ✅ Active |
| `heavy-fs` | Outbound Heavy FS | 🔧 Run `/qa:add-provider` |
| `lite-khomp` | Outbound Lite Khomp | 🔧 Run `/qa:add-provider` |
| `lite-fs` | Outbound Lite FS | 🔧 Run `/qa:add-provider` |

---

## Before running — checklist

1. `.env` exists and has:
   - `HEAVY_KHOMP_API_KEY` — set
   - `QA_PHONE_NUMBER` — the Google Voice number being dialled
   - `SLACK_WEBHOOK_URL` — where the report goes
2. Google Voice is on and you can answer calls
3. You are in the `Pipes.QA` directory

If anything is missing, tell the user what to fix and stop.

---

## Run command

```bash
# All active providers
uv run python -m runner

# One specific provider
uv run python -m runner --provider heavy-khomp
```

---

## Checklist sections (know this cold)

### Section 1 — IVR Quality Check
*One call triggered at the start. Stay on the call for all 4 items.*

1. IVR outbound greeting and prompts are clear and complete
2. IVR repeats once and drops if there's no keypress
3. IVR inbound greeting and prompts are clear and complete
4. IVR inbound repeats once and drops if there's no keypress

### Section 2 — Outbound Dispositions
*Same call, test each menu option.*

5. Transfer Call Destination → verify call is transferred
6. Schedule Tomorrow Morning
7. Schedule Tomorrow Afternoon
8. Schedule Tomorrow Evening
9. Continue
10. End Call → verify call ends after pressing End Call
11. DNC → verify number is suppressed, then remove suppression

### Section 3 — Inbound Dispositions
*Test the inbound IVR flow.*

12. Transfer Call Destination → verify call is transferred
13. Schedule Tomorrow Morning
14. Schedule Tomorrow Afternoon
15. Schedule Tomorrow Evening
16. Continue
17. End Call → verify call ends
18. DNC → verify suppression + removal

### Section 4 — AMD Detection Tests
*Each item triggers a FRESH outbound call.*

| # | What to say | Expected result |
|---|-------------|-----------------|
| 19 | `"Hello"` | IVR plays (live-person detected) |
| 20 | `"Hello this is [your name]"` | IVR plays (live-person detected) |
| 21 | `"Hey this is [Name] with Pipes how may I help you?"` | IVR STOPS (voicemail detected) |
| 22 | Say nothing — complete silence | IVR plays (live-person detected) |

---

## Handling failures during the run

- **Call didn't trigger (API error)**: Check `HEAVY_KHOMP_API_KEY` and `QA_PHONE_NUMBER` in `.env`. See `/providers:heavy-khomp` for full API reference.
- **IVR not playing**: Mark fail, add a note with what happened. Continue the rest of the checklist.
- **AMD test wrong result**: Mark fail. Note what the IVR did vs what was expected.
- **Slack report didn't send**: Run `/ops:report` to resend manually.

---

## After the run

- Slack report is sent automatically with pass/fail per item
- All results are saved to `data/reports/` as JSON
- If any item failed, file a note in the relevant provider skill for tracking

---

## Related skills

- `/providers:heavy-khomp` — full API reference + troubleshooting for Heavy Khomp
- `/qa:add-provider` — wire up Heavy FS, Lite Khomp, or Lite FS
- `/ops:report` — resend or view the last report
- `/ops:status` — check system health before running
