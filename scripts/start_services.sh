#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.runtime_logs"
mkdir -p "$LOG_DIR"

API_PID_FILE="$LOG_DIR/api.pid"
WORKER_PID_FILE="$LOG_DIR/worker.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"

API_LOG="$LOG_DIR/api.log"
WORKER_LOG="$LOG_DIR/worker.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:${API_PORT}}"

cd "$ROOT_DIR"

is_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill $pids 2>/dev/null || true
    sleep 1
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

start_api() {
  stop_port "$API_PORT"
  : > "$API_LOG"
  nohup env PYTHONPATH=. ./venv/bin/uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "$API_PORT" \
    --http httptools \
    --workers 2 \
    >>"$API_LOG" 2>&1 &
  echo $! > "$API_PID_FILE"
}

start_worker() {
  : > "$WORKER_LOG"
  nohup env PYTHONPATH=. ./venv/bin/dramatiq workers.task_actor \
    >>"$WORKER_LOG" 2>&1 &
  echo $! > "$WORKER_PID_FILE"
}

start_frontend() {
  stop_port "$FRONTEND_PORT"
  : > "$FRONTEND_LOG"
  (
    cd "$ROOT_DIR/frontend"
    env NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" npm run build >>"$FRONTEND_LOG" 2>&1
    local standalone_server
    standalone_server="$(find .next/standalone -path '*/frontend/server.js' -o -path '.next/standalone/server.js' 2>/dev/null | head -n 1)"
    if [[ -n "$standalone_server" ]]; then
      nohup env NODE_ENV=production HOSTNAME="$FRONTEND_HOST" PORT="$FRONTEND_PORT" NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" \
        node "$standalone_server" >>"$FRONTEND_LOG" 2>&1 &
    else
      nohup env NODE_ENV=production HOSTNAME="$FRONTEND_HOST" PORT="$FRONTEND_PORT" NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" \
        npm run start >>"$FRONTEND_LOG" 2>&1 &
    fi
    echo $! > "$FRONTEND_PID_FILE"
  )
}

start_api
start_worker
start_frontend

echo "api_pid=$(cat "$API_PID_FILE")"
echo "worker_pid=$(cat "$WORKER_PID_FILE")"
echo "frontend_pid=$(cat "$FRONTEND_PID_FILE")"
echo "api_log=$API_LOG"
echo "worker_log=$WORKER_LOG"
echo "frontend_log=$FRONTEND_LOG"
