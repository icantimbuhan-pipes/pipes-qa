# /ops:guide — Complete Pipes.QA Project Reference

Everything built in this project — what it is, how it works, how to use it.

---

## What is Pipes.QA?

A private web portal for the Pipes.ai team to run QA checks on outbound call providers, monitor SMS deliverability, manage Do Not Call (DNC) lists, and analyze QA evidence using AI. It runs on your Mac and is accessible over the internet via a Cloudflare tunnel.

**Live URL:** https://qa.aimagicstuff.com
**Local URL:** http://localhost:5050

---

## Starting and stopping

```bash
./start.sh      # start portal + Cloudflare tunnel + Slack DNC bot
./stop.sh       # stop all three

tail -f portal.log     # live portal logs
tail -f tunnel.log     # Cloudflare tunnel logs
tail -f dnc_bot.log    # Slack DNC bot logs
```

The portal runs on port **5050** as a background process. The Cloudflare tunnel makes it reachable at `qa.aimagicstuff.com` without opening firewall ports.

---

## Login & User Accounts

Every page requires login. Go to `qa.aimagicstuff.com/auth/login`.

**Default admin account:**
- Email: `admin@pipes.ai`
- Password: `admin123`
- ⚠️ Change this immediately in Admin → Users → Edit.

### Roles

| Role | What they can see |
|------|-------------------|
| **Admin** | Everything — full access, bypasses all permission checks |
| **Manager** | All features except the Admin panel |
| **QA** | Dashboard, QA runs, Validator, QA Testing Assistant |
| **Viewer** | Dashboard only (no Recent QA Runs, no SMS, no DNC) |

### Managing users

Go to `qa.aimagicstuff.com/admin/users`:
- **Create user** — email, username, password, assign role
- **Edit user** — change role, reset password, activate/deactivate
- **Delete user** — cannot delete your own account

### Managing permissions

Go to `qa.aimagicstuff.com/admin/permissions`:
- Select a role from the tabs
- Check/uncheck **View / Edit / Delete / Admin** per page
- Save Changes
- Admin role permissions cannot be restricted (always has full access)

---

## Daily QA

**URL:** `/daily-qa`
**Skill:** `/daily-qa:run`

Walks through a checklist step by step. For each item you press Pass ✅ or Fail ❌ and optionally add a note. At the end you get a summary you can send to Slack.

### How to run a QA check
1. Click **Start QA →** on the dashboard
2. Pick a checklist (Daily QA — Heavy Khomp, Hourly, etc.)
3. Answer each item — Pass or Fail, add latency notes if needed
4. On the Summary page, click **Send to Slack**

### Checklists
- Built-in checklists are defined in `checklists/`
- Custom checklists can be created at `/checklists`
- Each checklist has sections and items; items have IDs, text, and pass/fail

### Quick Report
**URL:** `/quick-report`
A fast way to send a formatted Slack report without going through the full checklist wizard.

---

## SMS Deliverability

**URL:** `/upload` (main hub) → then pick Telgorithm, Signalmash, or Commio
**Skill:** `/sms:run`

Upload daily CSV exports from each carrier, view per-company KPIs, failure breakdowns, and send summaries to Slack.

### Supported carriers

| Carrier | Upload format | URL |
|---------|--------------|-----|
| **Telgorithm** | CSV with columns: company, carrier, dlr_code, count | `/telgorithm/upload` |
| **Signalmash** | CSV with aggregate DLR codes like `(000)`, `(321)` | `/signalmash/upload` |
| **Commio** | CSV export | `/commio/upload` |

### What the reports show
- **Total / Delivered / Failed** count per company
- **Delivery rate %** with color-coded health status (green ≥94%, yellow ≥85%, red <85%)
- **Top failure code** with root cause label
- **Send to Slack** button to post the report

### Analysis pages
Each carrier has an `/analysis` page showing:
- KPI strip across all companies
- Company health table (expandable rows with failure breakdown)
- Error code intelligence with root cause + action plan
- Per-company analysis at `/telgorithm/analysis/<slug>` or `/signalmash/analysis/<slug>`
- **↗ Slack** button to send per-company analysis to Slack

### Error code knowledge base
File: `sms_deliverability/analysis_kb.py`
Contains root cause, severity, and action for every DLR error code.
Codes automatically get labels and actions in the analysis view.

### 94% delivery rate alert
When overall delivery rate drops below 94%, the Slack message includes a ⚠️ alert section.

---

## QA Testing Assistant

**URL:** `/qa-test`
**Skill:** `/qa:test`

Submit evidence — screenshots, logs, API responses, CSV files — and get structured QA findings back from an AI model.

### AI backends (pick one — all free except Anthropic)

| Option | Cost | Setup |
|--------|------|-------|
| **Groq** | Free | Sign up at `console.groq.com` → create API key → add `GROQ_API_KEY=...` to `.env` |
| **Ollama** | Free | Install from `ollama.com` → `ollama pull llama3.2` → add `OLLAMA_MODEL=llama3.2` to `.env` |
| Anthropic | Paid | Get key at `console.anthropic.com` → add `ANTHROPIC_API_KEY=...` to `.env` |

The portal auto-detects which backend is available (Anthropic → Groq → Ollama priority).

**Note:** Screenshots can only be analyzed by Anthropic (Claude). Groq and Ollama receive text-only evidence — describe screenshots in the notes field.

### Evidence you can submit
- Feature name + user story / requirements
- Test steps, expected vs actual results
- Screenshots (PNG/JPG)
- UI table headers (copy-paste from browser)
- CSV/Excel files
- API response JSON
- Database records
- Error logs / console output

### Output format
Each issue is reported as:
```
Status: ✅ PASS | ⚠️ WARNING | ❌ FAILED
Issue: ...
Expected: ...
Actual: ...
Evidence: ...
Possible Root Cause: ...
Recommendation: ...
```
Ends with a summary: Result PASS/FAIL/PARTIAL + Issues list + Action items.

---

## DNC Portal

**URL:** `/dnc`
**Skill:** `/dnc:portal`

Manually add phone numbers to the Do Not Call list and fire a postback to Pipes.

### Manual DNC
1. Paste phone numbers (one per line, any format)
2. Click Fire DNC Postback
3. Each number gets `✓ success` or `✗ failed`
4. All attempts are logged in the database

### Slack Auto-DNC Bot
**Skill:** `/dnc:slack-bot`

A background process that watches your Slack channel. When someone posts a phone number, the bot:
1. Extracts all 10-digit US numbers from the message
2. Fires the DNC postback automatically
3. Reacts ✅ if all succeeded, ❌ if any failed
4. Posts a thread reply for any failed numbers

Bot runs in background via `start.sh`. Logs: `tail -f dnc_bot.log`

### DNC API endpoint
```
POST https://integrations.pipes.ai/api/lead/do-not-call/{api_key}
Body: phone=3235551234
```

---

## API Validator

**URL:** `/validator`
**Skill:** `/validator:run`

Tests rejection code scenarios against the Pipes API. Each scenario fires a call with specific parameters designed to trigger a particular rejection code, then checks if the API returned the expected code.

### Test scenarios
Defined in `checklists/heavy_khomp_qa.py` (and the validator config).
Each scenario has: name, description, parameters, expected rejection code.

### How to run
1. Go to `/validator`
2. Click **Run All Scenarios** or pick individual tests
3. Results show: Expected code vs Actual code → Pass/Fail

---

## API Configs

**URL:** `/api-configs`

Store and manage API credentials for each call provider.
Instead of hardcoding values in `.env`, you can add/edit provider configs here.

Each config has: provider name, API URL, API key, first/last name, state, postal code.

---

## Checklists Builder

**URL:** `/checklists`
**Skill:** `/daily-qa:checklist`

Create and edit custom QA checklists.

### Checklist structure
```
Checklist
└── Section 1 (e.g. "Call Quality")
    ├── Item 1 (pass/fail question)
    ├── Item 2
    └── Item 3
└── Section 2
    └── ...
```

### Built-in checklists
Located in `checklists/` directory:
- `heavy_khomp_qa.py` — 22-item Daily QA for Heavy Khomp provider
- Hourly monitoring checklist

---

## Environment variables

File: `.env` in the project root.

| Variable | What it does |
|----------|-------------|
| `GROQ_API_KEY` | Free AI backend for QA Testing Assistant (console.groq.com) |
| `GROQ_MODEL` | Groq model name (default: `llama-3.3-70b-versatile`) |
| `OLLAMA_MODEL` | Ollama model name (default: `llama3.2`) — Ollama detected automatically if running |
| `OLLAMA_URL` | Ollama URL (default: `http://localhost:11434`) |
| `ANTHROPIC_API_KEY` | Paid AI backend (console.anthropic.com) — supports screenshots |
| `PIPES_BASE_URL` | Pipes API base URL (`https://api.pipes.ai`) |
| `PIPES_API_KEY` | Pipes platform API key |
| `PIPES_ORG_ID` | Pipes organization ID |
| `SLACK_WEBHOOK_URL` | Slack webhook for Daily QA reports |
| `SMS_SLACK_WEBHOOK_URL` | Slack webhook for SMS deliverability reports |
| `SLACK_BOT_TOKEN` | Slack bot token (xoxb-...) for DNC auto-bot |
| `SLACK_APP_TOKEN` | Slack app token (xapp-...) for DNC auto-bot socket |
| `DNC_SLACK_CHANNEL` | Slack channel ID(s) for DNC bot to watch (comma-separated) |
| `QA_PHONE_NUMBER` | Test phone number for QA calls |
| `QA_IP_ADDRESS` | Test IP address for QA calls |
| `QA_EMAIL` | Test email for QA calls |
| `HEAVY_KHOMP_API_KEY` | API key for Heavy Khomp provider |
| `LITE_KHOMP_API_KEY` | API key for Lite Khomp provider |
| `TBI_KHOMP_API_KEY` | API key for TBI Khomp provider |
| `TBI_FS_API_KEY` | API key for TBI Freeswitch provider |
| `SIGNALMASH_KHOMP_API_KEY` | API key for Signalmash Khomp provider |
| `SIGNALMASH_FS_API_KEY` | API key for Signalmash Freeswitch provider |
| `ACCIDENT_OFFICE_API_KEY` | API key for Accident Office live campaign |

After editing `.env`, always restart: `./stop.sh && ./start.sh`

---

## Database

File: `data/portal_qa.db` (SQLite, auto-created on first start)

| Table | What it stores |
|-------|---------------|
| `qa_sessions` | Each QA run (checklist, start/end time, slack sent flag) |
| `qa_answers` | Each pass/fail answer within a session |
| `custom_checklists` | Checklists created via the builder UI |
| `provider_configs` | API credentials managed via `/api-configs` |
| `qa_settings` | Portal-wide settings (key/value) |
| `dnc_log` | All DNC postback attempts (phone, status, source, timestamp) |
| `users` | Portal user accounts |
| `roles` | User roles (Admin, Manager, QA, Viewer + custom) |
| `pages` | Registered pages/modules for permission control |
| `role_permissions` | View/Edit/Delete/Admin flags per role per page |

SMS databases are separate files in `data/`:
| File | What it stores |
|------|---------------|
| `data/telgorithm.db` | Telgorithm DLR records uploaded via CSV |
| `data/signalmash.db` | Signalmash DLR records |
| `data/commio.db` | Commio delivery records |

---

## Project file structure

```
Pipes.QA/
├── portal/                     ← Main Flask web portal
│   ├── app.py                  ← App factory — blueprints, login, auth guard
│   ├── db.py                   ← QA sessions, answers, DNC log, provider configs
│   ├── templates/
│   │   ├── base.html           ← Layout with dynamic sidebar nav
│   │   ├── dashboard.html      ← Home page
│   │   ├── 403.html            ← Access denied page
│   │   └── upload.html         ← SMS upload hub
│   ├── auth/                   ← Login/logout + RBAC database
│   ├── admin/                  ← User & permission management UI
│   ├── daily_qa/               ← QA checklist wizard
│   ├── qa_test/                ← AI-powered QA Testing Assistant
│   ├── validator/              ← API rejection code tester
│   ├── api_configs/            ← Provider credential management
│   ├── checklist_builder/      ← Custom checklist editor
│   ├── quick_report/           ← Quick Slack report sender
│   ├── dnc/                    ← Manual DNC portal
│   ├── slack_dnc/              ← Slack webhook receiver for DNC bot
│   └── maintenance/            ← Portal maintenance page
│
├── sms_deliverability/         ← SMS reporting module
│   ├── analysis_kb.py          ← Error code knowledge base (root causes + actions)
│   ├── telgorithm/             ← Telgorithm CSV import, reports, analysis, Slack
│   ├── signalmash/             ← Signalmash CSV import, reports, analysis, Slack
│   └── commio/                 ← Commio CSV import, reports
│
├── checklists/                 ← QA checklist definitions (Python)
├── runner/                     ← CLI runner for non-portal QA runs
├── providers/                  ← One file per call provider
├── data/                       ← SQLite databases + CSV uploads (gitignored)
├── .claude/commands/           ← All skills (this file is one of them)
├── .env                        ← Credentials and config (gitignored)
├── start.sh                    ← Start portal + tunnel + DNC bot
├── stop.sh                     ← Stop all
└── portal.log                  ← Portal runtime log
```

---

## All available skills

| Skill | What it does |
|-------|-------------|
| `/ops:guide` | **This file** — complete project reference |
| `/ops:status` | Check system health before running |
| `/ops:push` | Commit and push work to GitHub |
| `/auth:rbac` | Auth & RBAC reference — roles, permissions, adding pages |
| `/daily-qa:run` | Master daily QA orchestrator |
| `/daily-qa:checklist` | View, edit, or add checklist sections |
| `/daily-qa:add-provider` | Wire up a new call provider |
| `/daily-qa:report` | View or resend the last Slack report |
| `/qa:test` | QA Testing Assistant — submit evidence, get findings |
| `/validator:run` | Run API rejection code scenario tests |
| `/validator:add-scenario` | Add a new rejection code test scenario |
| `/dnc:portal` | Manual DNC portal reference |
| `/dnc:report` | Query and export DNC log |
| `/dnc:slack-bot` | Slack Auto-DNC bot setup and reference |
| `/sms:run` | SMS deliverability workflow |
| `/sms:analysis` | KPI analysis — error codes, root causes, action plans |
| `/sms:telgorithm` | Telgorithm CSV format, error codes, Slack setup |
| `/sms:signalmash` | Signalmash DLR codes, aggregate format, Slack setup |
| `/sms:commio` | Commio status codes, campaign checker |
| `/providers:heavy-khomp` | Heavy Khomp API reference + AMD behavior |
| `/providers:heavy-fs` | Heavy FS reference |
| `/providers:lite-khomp` | Lite Khomp reference |
| `/providers:lite-fs` | Lite FS reference |

---

## Git workflow

```bash
# Start new feature
git checkout dev
git pull origin dev
git checkout -b feature/my-feature-name

# Save work
git add <specific files>
git commit -m "feat: describe what you built"
git push origin feature/my-feature-name

# Merge to dev
git checkout dev
git merge feature/my-feature-name
git push origin dev
```

Branches:
- `main` — stable, all passing
- `dev` — active development (current branch)
- `feature/*` — one branch per feature

Current active branch: `dev`

---

## Common tasks quick reference

| Task | How |
|------|-----|
| Start the portal | `./start.sh` |
| Stop the portal | `./stop.sh` |
| See live errors | `tail -f portal.log` |
| Add a new user | `/admin/users` → New User |
| Change permissions | `/admin/permissions` → select role → check boxes |
| Upload SMS report | `/upload` → pick carrier → choose CSV |
| Run daily QA | Dashboard → Start QA → pick checklist |
| Test API rejection codes | `/validator` → Run All |
| Fire DNC for a number | `/dnc` → paste number → Fire DNC |
| Change AI backend | Edit `.env`, set `GROQ_API_KEY` or `OLLAMA_MODEL`, restart |
| Reset portal database | Delete `data/portal_qa.db`, restart (re-seeds defaults) |
| Check if Ollama works | `curl http://localhost:11434/api/version` |
| List Ollama models | `curl http://localhost:11434/api/tags` |
| Pull a new Ollama model | `ollama pull mistral` (or any model name) |
