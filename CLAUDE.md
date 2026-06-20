# Pipes.QA

Daily outbound call monitoring and QA for the Pipes platform.
Triggers calls via API, walks through a 22-item checklist interactively, sends results to Slack.

## Quick start

```bash
uv sync
uv run python -m runner                         # full daily QA
uv run python -m runner --provider heavy-khomp  # one provider
```

## Skills (start here)

| Skill | What it does |
|-------|-------------|
| `/qa:run` | Master daily QA orchestrator — run this |
| `/qa:add-provider` | Wire up Heavy FS, Lite Khomp, or Lite FS |
| `/providers:heavy-khomp` | API reference + AMD behavior + troubleshooting |
| `/providers:heavy-fs` | Heavy FS reference (not yet configured) |
| `/providers:lite-khomp` | Lite Khomp reference (not yet configured) |
| `/providers:lite-fs` | Lite FS reference (not yet configured) |
| `/ops:status` | Check system health before running |
| `/ops:report` | View or resend the last Slack report |

## Project layout

```
providers/          one file per call provider (heavy_khomp, heavy_fs, lite_khomp, lite_fs)
checklists/         22-item QA checklist definition
runner/             interactive CLI engine + Slack reporter
monitoring/checks/  automated API health checks
tests/              pytest unit + integration tests
data/reports/       JSON results from each run (gitignored)
.claude/commands/   skills — the brain of this project
.github/workflows/  optional scheduled GitHub Actions trigger
```

## Providers

| Provider | Status | Skill |
|----------|--------|-------|
| Outbound Heavy Khomp | ✅ Active | `/providers:heavy-khomp` |
| Outbound Heavy FS | 🔧 Configure | `/providers:heavy-fs` |
| Outbound Lite Khomp | 🔧 Configure | `/providers:lite-khomp` |
| Outbound Lite FS | 🔧 Configure | `/providers:lite-fs` |

## Environment

Copy `.env.example` → `.env` and fill in credentials.
Required: `HEAVY_KHOMP_API_KEY`, `QA_PHONE_NUMBER`, `SLACK_WEBHOOK_URL`.
See `/providers:heavy-khomp` for the full variable reference.

## Branch strategy

- `main` — stable, all passing providers
- `dev` — active development
- `provider/<key>` — adding a new provider (one branch per)
