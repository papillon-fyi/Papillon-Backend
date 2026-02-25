#!/bin/bash

SCRIPT="server.app:app"
PID_FILE="server.pid"
LOG_FILE="server.log"

set -a
source .env
set +a

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

start() {
  if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Bluesky Feed Manager service is already running (PID $(cat "$PID_FILE"))"
    exit 1
  fi

  nohup uvicorn "$SCRIPT" --host "$HOST" --port "$PORT" --reload > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "Started Bluesky Feed Manager service (PID $(cat "$PID_FILE")). Logs: $LOG_FILE"
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found for Bluesky Feed Manager service"
    exit 1
  fi

  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Stopped Bluesky Feed Manager service (PID $PID)"
    rm "$PID_FILE"
  else
    echo "Bluesky Feed Manager service (PID $PID) is not running"
    rm "$PID_FILE"
  fi
}

status() {
  if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Bluesky Feed Manager service is running (PID $(cat "$PID_FILE"))"
  else
    echo "Bluesky Feed Manager service is not running"
  fi
}

case "$1" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|status}" ;;
esac
