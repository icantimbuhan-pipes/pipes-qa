# /dnc:slack-bot — Slack Auto-DNC Bot

Watches a Slack channel for phone numbers.
The moment a number is posted, it fires a DNC postback to Pipes and reacts ✅ or ❌.

## Run it

```bash
uv run python -m integrations.slack_dnc
```

Keep this running in the background (or set up as a launchd service on Mac).

---

## One-time Slack App Setup

### 1. Create a new Slack App

Go to: https://api.slack.com/apps → **Create New App** → **From scratch**
- App Name: `Pipes DNC Bot`
- Workspace: your Pipes workspace

---

### 2. Enable Socket Mode

Left sidebar → **Socket Mode** → toggle ON  
→ Create an App-Level Token:
- Token name: `pipes-dnc-socket`
- Scope: `connections:write`
- Click **Generate**
- Copy the token (starts with `xapp-`) → add to `.env` as `SLACK_APP_TOKEN`

---

### 3. Add Bot Token Scopes

Left sidebar → **OAuth & Permissions** → scroll to **Bot Token Scopes** → Add:

| Scope | Why |
|-------|-----|
| `channels:history` | Read messages in public channels |
| `chat:write` | Post thread replies on failure |
| `reactions:write` | Add ✅ / ❌ reaction |
| `channels:read` | Look up channel IDs |

---

### 4. Subscribe to Events

Left sidebar → **Event Subscriptions** → toggle ON  
→ **Subscribe to bot events** → Add:

| Event | Why |
|-------|-----|
| `message.channels` | Fires when a message is posted in a public channel |

---

### 5. Install to Workspace

Left sidebar → **Install App** → **Install to Workspace** → Allow  
→ Copy **Bot User OAuth Token** (starts with `xoxb-`) → add to `.env` as `SLACK_BOT_TOKEN`

---

### 6. Add bot to the DNC channel

In Slack, open the `#pipes-solomon-sons-relocation` channel → click the channel name → **Integrations** → **Add an App** → find `Pipes DNC Bot`.

Get the channel's ID: click channel name → bottom of the About panel shows the ID (starts with `C`).  
Add to `.env` as `DNC_SLACK_CHANNEL=C0XXXXXXXXX`

---

## .env variables needed

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
DNC_SLACK_CHANNEL=C0XXXXXXXXX
```

---

## How it works

1. Someone posts a phone number in the channel
2. Bot extracts all 10-digit US numbers from the message (handles any format)
3. Fires `POST https://integrations.pipes.ai/api/lead/do-not-call/...` for each number
4. Reacts ✅ if all succeeded, ❌ if any failed
5. If a number fails, posts a thread reply naming the failed number

---

## DNC API

```
POST https://integrations.pipes.ai/api/lead/do-not-call/7l6OaLWvqXoBz9pDVeExbn3JwG2rP8jN
Body: phone=3235551234   (10-digit format)
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot doesn't react | Check it's in the channel and `DNC_SLACK_CHANNEL` is the correct ID |
| `SLACK_BOT_TOKEN` error | Re-install the app to workspace after adding scopes |
| Socket won't connect | Make sure Socket Mode is ON and `SLACK_APP_TOKEN` starts with `xapp-` |
| 11-digit number not caught | Bot strips leading `1` for US numbers — anything else is skipped |
