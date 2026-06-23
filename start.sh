#!/bin/bash
# Pipes.QA Portal — background launcher
# Run once: ./start.sh
# Stop:     ./stop.sh
# Logs:     tail -f portal.log / tunnel.log / dnc_bot.log

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.portal.pid"
TUNNEL_PID="$DIR/.tunnel.pid"
DNC_PID="$DIR/.dnc_bot.pid"
LOG_FILE="$DIR/portal.log"
TUNNEL_LOG="$DIR/tunnel.log"
DNC_LOG="$DIR/dnc_bot.log"

# ── Flask portal ──────────────────────────────────────────────────────────────
if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
  echo "Portal already running (PID $(cat $PID_FILE)) → http://localhost:5050"
else
  cd "$DIR"
  nohup python3 -m portal >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "✓ Portal started (PID $!) → http://localhost:5050"
fi

# ── Cloudflare Tunnel ─────────────────────────────────────────────────────────
if [ -f "$TUNNEL_PID" ] && kill -0 "$(cat $TUNNEL_PID)" 2>/dev/null; then
  echo "Tunnel already running (PID $(cat $TUNNEL_PID)) → https://qa.aimagicstuff.com"
else
  nohup cloudflared tunnel run pipes-qa >> "$TUNNEL_LOG" 2>&1 &
  echo $! > "$TUNNEL_PID"
  echo "✓ Tunnel started (PID $!) → https://qa.aimagicstuff.com"
fi

# ── Slack DNC Bot ─────────────────────────────────────────────────────────────
if [ -f "$DNC_PID" ] && kill -0 "$(cat $DNC_PID)" 2>/dev/null; then
  echo "DNC bot already running (PID $(cat $DNC_PID))"
else
  cd "$DIR"
  nohup /Users/iccantimbuhangmail.com/.local/bin/uv run python -m integrations.slack_dnc >> "$DNC_LOG" 2>&1 &
  echo $! > "$DNC_PID"
  echo "✓ DNC bot started (PID $!) — logs: tail -f dnc_bot.log"
fi

# Local network URL
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
if [ -n "$LOCAL_IP" ]; then
  echo "  Local network → http://$LOCAL_IP:5050"
fi
