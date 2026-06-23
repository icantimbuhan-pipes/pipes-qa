#!/bin/bash
# Pipes.QA Portal — stop portal + tunnel + DNC bot
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.portal.pid"
TUNNEL_PID="$DIR/.tunnel.pid"
DNC_PID="$DIR/.dnc_bot.pid"

# ── Flask portal ──────────────────────────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && echo "✓ Portal stopped (PID $PID)"
  else
    echo "Portal was not running."
  fi
  rm "$PID_FILE"
else
  echo "Portal is not running (no PID file found)."
fi

# ── Cloudflare Tunnel ─────────────────────────────────────────────────────────
if [ -f "$TUNNEL_PID" ]; then
  PID=$(cat "$TUNNEL_PID")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && echo "✓ Tunnel stopped (PID $PID)"
  else
    echo "Tunnel was not running."
  fi
  rm "$TUNNEL_PID"
else
  echo "Tunnel is not running (no PID file found)."
fi

# ── Slack DNC Bot ─────────────────────────────────────────────────────────────
if [ -f "$DNC_PID" ]; then
  PID=$(cat "$DNC_PID")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && echo "✓ DNC bot stopped (PID $PID)"
  else
    echo "DNC bot was not running."
  fi
  rm "$DNC_PID"
else
  echo "DNC bot is not running (no PID file found)."
fi
