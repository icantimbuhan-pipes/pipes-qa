# /ops:status

Check whether the Pipes QA system is ready to run and all providers are healthy.

---

## What to check

1. **Environment** — verify `.env` exists and required vars are set:
   ```bash
   grep -E "HEAVY_KHOMP_API_KEY|QA_PHONE_NUMBER|SLACK_WEBHOOK_URL" .env
   ```
   Report which are set and which are empty.

2. **Active providers** — read `runner/interactive.py` and show the PROVIDERS dict.
   Tell the user which are active vs commented out.

3. **API health** — run a quick connectivity check:
   ```bash
   uv run python -m monitoring.checks.api_health
   ```
   Show the result.

4. **Last run** — check `data/reports/` for the most recent JSON report file.
   Show: provider tested, date/time, pass/fail count.

5. **Dependencies installed** — check if `.venv/` exists:
   ```bash
   uv sync --dry-run 2>&1 | head -5
   ```

---

## Output format

Report as a quick status table:

```
Item                  Status
────────────────────  ──────────────────
HEAVY_KHOMP_API_KEY   ✅ set
QA_PHONE_NUMBER       ✅ set (5122******)
SLACK_WEBHOOK_URL     ⚠️  not set
Active providers      heavy-khomp (1 of 4)
Last run              2026-06-20 09:00 — 22/22 ✅
API health            ✅ ok
Dependencies          ✅ installed
```

If anything is wrong, tell the user exactly how to fix it.
