#!/bin/bash
# Pipes.QA Portal — stop background server
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.portal.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm "$PID_FILE"
    echo "✓ Portal stopped (PID $PID)"
  else
    rm "$PID_FILE"
    echo "Portal was not running."
  fi
else
  echo "Portal is not running (no PID file found)."
fi
