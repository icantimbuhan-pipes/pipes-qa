#!/bin/bash
# Pipes.QA Portal — background launcher
# Run once: ./start.sh
# Stop:     ./stop.sh
# Logs:     tail -f portal.log

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.portal.pid"
LOG_FILE="$DIR/portal.log"

if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
  echo "Portal already running (PID $(cat $PID_FILE)) → http://localhost:5050"
  exit 0
fi

cd "$DIR"
nohup python3 -m portal >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "✓ Portal started (PID $!) → http://localhost:5050"

# Local network URL
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
if [ -n "$LOCAL_IP" ]; then
  echo "  Share on network → http://$LOCAL_IP:5050"
fi
