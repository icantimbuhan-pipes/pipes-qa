# /providers:heavy-fs

Reference for the Outbound Heavy FS (Freeswitch) provider.

---

## Status: 🔧 Not yet configured

This provider needs its API details added before it can be used.  
Run `/qa:add-provider` and follow the steps.

---

## Identity

| Field | Value |
|-------|-------|
| Name | Outbound Heavy FS |
| Key | `heavy-fs` |
| File | `providers/heavy_fs.py` |
| Env var | `HEAVY_FS_API_KEY` |

---

## To activate

1. Paste the API endpoint, method, and params here (update this file)
2. Add `HEAVY_FS_API_KEY=...` to `.env`
3. Fill in `providers/heavy_fs.py`
4. Uncomment `"heavy-fs"` in `runner/interactive.py` PROVIDERS dict
5. Run `/qa:add-provider` for the full walkthrough

---

## Freeswitch AMD notes (once active)

Freeswitch AMD is software-based. Key differences from Khomp:
- Faster initial detection (~1s vs ~2s for Khomp)
- More sensitive to background noise — test in a quiet environment
- Voicemail detection phrase (test 3) may need fewer words than Khomp
- If live-person detection is inconsistent, check the `SILENCE_THRESHOLD` setting on the FS server
