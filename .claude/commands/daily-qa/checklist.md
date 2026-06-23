# /daily-qa:checklist

Manage QA checklists — the step-by-step sequences used during a Daily QA session.

Two types exist: **hardcoded** (Python files, version-controlled) and **custom** (built in the portal UI, stored in the DB).

---

## Where checklists live

| Type | Location | Edit via |
|------|----------|---------|
| Hardcoded | `checklists/*.py` | Code editor |
| Custom | `data/portal.db` → `custom_checklists` | Portal `/checklists` |

The portal shows both types on the same list at `/checklists`.

---

## Current hardcoded checklists

| File | Sections | Items | Purpose |
|------|----------|-------|---------|
| `heavy_khomp_qa.py` | 12 | 31 | Full daily QA — all providers |
| `hourly_heavy_khomp_qa.py` | — | — | Hourly abbreviated check |
| `retell_ai_qa.py` | — | — | RetellAI / Accident Office only |
| `sms_ai_qa.py` | — | — | SMS AI bot flow |
| `sms_only_qa.py` | — | — | SMS-only campaign |

### heavy_khomp_qa.py — section summary

| # | Section | Items | Provider |
|---|---------|-------|----------|
| 1 | Account Used — IVR check | 1 | heavy_khomp |
| 2 | Test Keypress Actions (Transfer, Schedule ×3, Continue, End Call, DNC) | 7 | heavy_khomp |
| 3 | Dynamic Inserts | 1 | heavy_khomp_dynamic |
| 4 | AMD Detection (4 sub-calls) | 1 | heavy_khomp |
| 5 | Auto-Connect | 1 | heavy_khomp |
| 6 | TBI Khomp OB & IB (Transfer, Schedule, DNC) | 3 | tbi_khomp |
| 7 | TBI Freeswitch OB & IB (Transfer, Schedule, DNC) | 3 | tbi_fs |
| 8 | Signalmash Khomp OB & IB (Transfer, Schedule, DNC) | 3 | signalmash_khomp |
| 9 | Signalmash Freeswitch OB & IB (Transfer, Schedule, DNC) | 3 | signalmash_fs |
| 10 | RetellAI — Accident Office (Connect, Schedule, Stop/DNC) | 3 | accident_office |
| 11 | SMS Only — Signalmash (Sent, Outbound, Inbound, Emoji) | 4 | sms_signalmash |
| 12 | SMS with AI — Signalmash | 1 | sms_ai_signalmash |

---

## Editing a hardcoded checklist

Open the relevant file in `checklists/` and modify the `Section` / `CheckItem` / `SubCall` objects.

### Data types

```python
from checklists.daily_qa import SubCall, CheckItem, Section

Section(
    id="unique_id",             # snake_case, used in DB session
    title="N/12  Section Name", # shown as the step heading
    trigger_call_at_start=True, # fires a call before the first item
    start_instruction="...",    # instructions shown with the trigger button
    provider_key="heavy_khomp", # overrides the session's default provider for this section
    items=[...],
)

CheckItem(
    id="unique_id",
    text="What to check",
    note="Optional sub-text shown below",
    bullets=["bullet 1", "bullet 2"],   # optional checklist within the item
    trigger_call=True,                   # item-level call button
    call_instruction="...",              # instructions for the item call button
    sub_calls=[SubCall(...)],            # individual call button per sub-test (AMD style)
    provider_key="...",                  # overrides section provider
)

SubCall(
    instruction="What to say / do",
    note="Expected result",
)
```

After editing, restart the portal — hardcoded checklists are loaded at startup.

---

## Custom checklists — portal builder

### Routes

| Route | What it does |
|-------|-------------|
| `GET /checklists/` | List all checklists (hardcoded + custom) |
| `GET /checklists/new` | New custom checklist form |
| `POST /checklists/save` | Create new custom checklist |
| `GET /checklists/<id>/edit` | Edit existing custom checklist |
| `POST /checklists/<id>/save` | Save edits |
| `POST /checklists/<id>/delete` | Delete custom checklist |

### Fields per custom checklist

- **Name** — shown in the session picker
- **Report type** — `daily` or other (used for Slack report labeling)
- **Default provider** — which provider key is used for items without a specific `provider_key`
- **Sections** — built interactively in the UI, stored as JSON

---

## Adding a new section to heavy_khomp_qa.py

1. Open `checklists/heavy_khomp_qa.py`
2. Append a new `Section(...)` to `HEAVY_KHOMP_QA`
3. Update the section number in the `title` (e.g. `"13/13  New Section"`)
4. Restart the portal: `./stop.sh && ./start.sh`
5. Start a new Daily QA session — the new section appears at the end

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Section doesn't appear after editing | Restart the portal — checklists load at startup |
| Custom checklist not in session picker | Check it's saved with a non-empty name in `/checklists` |
| Wrong provider triggered for a section | Set `provider_key` on the `Section` or `CheckItem` |
| Sub-call buttons not showing | Item needs `sub_calls=[SubCall(...)]` — not `trigger_call=True` |

---

## Related skills

- `/daily-qa:run` — run a Daily QA session
- `/daily-qa:add-provider` — wire up a new call provider
