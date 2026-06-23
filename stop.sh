#!/bin/bash
# Pipes.QA Portal — stop portal + tunnel
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.portal.pid"
TUNNEL_PID="$DIR/.tunnel.pid"

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
