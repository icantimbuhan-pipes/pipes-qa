# /providers:lite-fs

Reference for the Outbound Lite FS (Freeswitch) provider.

---

## Status: 🔧 Not yet configured

Run `/qa:add-provider` to wire this up.

---

## Identity

| Field | Value |
|-------|-------|
| Name | Outbound Lite FS |
| Key | `lite-fs` |
| File | `providers/lite_fs.py` |
| Env var | `LITE_FS_API_KEY` |

---

## To activate

1. Get API endpoint + params from the team
2. Add `LITE_FS_API_KEY=...` to `.env`
3. Fill in `providers/lite_fs.py`
4. Uncomment `"lite-fs"` in `runner/interactive.py`

---

## Note

Lite FS likely shares the same Freeswitch AMD behavior as Heavy FS.  
See `/providers:heavy-fs` for AMD notes once that provider is confirmed working.
