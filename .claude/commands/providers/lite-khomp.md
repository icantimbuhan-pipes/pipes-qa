# /providers:lite-khomp

Reference for the Outbound Lite Khomp provider.

---

## Status: 🔧 Not yet configured

Run `/qa:add-provider` to wire this up.

---

## Identity

| Field | Value |
|-------|-------|
| Name | Outbound Lite Khomp |
| Key | `lite-khomp` |
| File | `providers/lite_khomp.py` |
| Env var | `LITE_KHOMP_API_KEY` |

---

## Heavy vs Lite difference

- **Heavy** accounts: higher concurrency limits, priority routing
- **Lite** accounts: lower concurrency, used for standard volume

The API call structure may be identical to Heavy Khomp — confirm with the team whether Lite uses the same endpoint with a different API key, or a different endpoint entirely.

---

## To activate

1. Confirm API endpoint (same as Heavy or different?)
2. Add `LITE_KHOMP_API_KEY=...` to `.env`
3. Fill in `providers/lite_khomp.py`
4. Uncomment `"lite-khomp"` in `runner/interactive.py`
