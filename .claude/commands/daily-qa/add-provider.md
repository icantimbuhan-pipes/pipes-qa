# /daily-qa:add-provider

Step-by-step guide to wiring up a new call provider (Heavy FS, Lite Khomp, Lite FS).

---

## What you'll need from the user

Before starting, ask for:
1. Provider name (e.g. "Outbound Heavy FS")
2. API endpoint URL
3. HTTP method (POST/GET)
4. Auth method (header key? query param? basic auth?)
5. Full list of request parameters and their values
6. What the API returns on success

---

## Step 1 — Create the provider file

Copy `providers/heavy_khomp.py` as a template.

Create `providers/<key>.py` where `<key>` is the snake_case provider key (e.g. `heavy_fs`, `lite_khomp`).

Update:
- `NAME` — human-readable name shown in the terminal and Slack reports
- `PROVIDER_KEY` — snake_case key used in code
- `API_URL` — the endpoint
- `trigger()` — request method, headers, params

---

## Step 2 — Add env vars

Add the API key and any provider-specific variables to `.env`:

```
HEAVY_FS_API_KEY=your_key_here
# any other provider-specific vars
```

Also add them to `.env.example` with empty values.

---

## Step 3 — Register the provider

Open `runner/interactive.py` and find `PROVIDERS`:

```python
PROVIDERS = {
    "heavy-khomp": "providers.heavy_khomp",
    # "heavy-fs": "providers.heavy_fs",     ← uncomment and update
}
```

Uncomment the line for your new provider.

---

## Step 4 — Update the provider skill file

Open `.claude/commands/providers/<provider-key>.md` and fill in:
- The real API URL and params
- The API key env var name
- Expected behavior / common failures

---

## Step 5 — Create a branch and test

```bash
git checkout -b provider/<key>
uv run python -m runner --provider <key>
```

Run just the new provider, verify all 22 items pass, then merge to `dev`.

---

## Provider key reference

| Provider name | File | Env var | Runner key |
|---------------|------|---------|------------|
| Outbound Heavy Khomp | `providers/heavy_khomp.py` | `HEAVY_KHOMP_API_KEY` | `heavy-khomp` |
| Outbound Heavy FS | `providers/heavy_fs.py` | `HEAVY_FS_API_KEY` | `heavy-fs` |
| Outbound Lite Khomp | `providers/lite_khomp.py` | `LITE_KHOMP_API_KEY` | `lite-khomp` |
| Outbound Lite FS | `providers/lite_fs.py` | `LITE_FS_API_KEY` | `lite-fs` |
