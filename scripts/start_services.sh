#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.runtime_logs"
mkdir -p "$LOG_DIR"

ENV_FILE="$ROOT_DIR/.env"
API_SESSION_NAME="intelligent-app-api"
WORKER_SESSION_NAME="intelligent-app-worker"
FRONTEND_SESSION_NAME="intelligent-app-frontend"

API_PID_FILE="$LOG_DIR/api.pid"
WORKER_PID_FILE="$LOG_DIR/worker.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"

API_LOG="$LOG_DIR/api.log"
WORKER_LOG="$LOG_DIR/worker.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

load_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    return
  fi
  eval "$("$ROOT_DIR/venv/bin/python" - <<'PY' "$ENV_FILE"
import shlex
import sys
from dotenv import dotenv_values

for key, value in dotenv_values(sys.argv[1]).items():
    if value is None:
        continue
    print(f"export {key}={shlex.quote(value)}")
PY
)"
}

load_env_file

API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:${API_PORT}}"

cd "$ROOT_DIR"

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "required command not found: $cmd" >&2
    exit 1
  fi
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

tmux_session_exists() {
  local session_name="$1"
  tmux has-session -t "$session_name" 2>/dev/null
}

kill_tmux_session() {
  local session_name="$1"
  if tmux_session_exists "$session_name"; then
    tmux kill-session -t "$session_name"
  fi
}

write_tmux_pane_pid() {
  local session_name="$1"
  local output_file="$2"
  tmux list-panes -t "$session_name" -F '#{pane_pid}' | head -n 1 > "$output_file"
}

start_api() {
  stop_port "$API_PORT"
  : > "$API_LOG"
  kill_tmux_session "$API_SESSION_NAME"
  tmux new-session -d -s "$API_SESSION_NAME" \
    "cd '$ROOT_DIR' && env PYTHONPATH=. ./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port '$API_PORT' --http httptools --workers 2 >> '$API_LOG' 2>&1"
  write_tmux_pane_pid "$API_SESSION_NAME" "$API_PID_FILE"
}

start_worker() {
  : > "$WORKER_LOG"
  kill_tmux_session "$WORKER_SESSION_NAME"
  tmux new-session -d -s "$WORKER_SESSION_NAME" \
    "cd '$ROOT_DIR' && env PYTHONPATH=. ./venv/bin/dramatiq workers.task_actor >> '$WORKER_LOG' 2>&1"
  write_tmux_pane_pid "$WORKER_SESSION_NAME" "$WORKER_PID_FILE"
}

start_frontend() {
  stop_port "$FRONTEND_PORT"
  : > "$FRONTEND_LOG"
  kill_tmux_session "$FRONTEND_SESSION_NAME"
  # Frontend runtime contract: build first, then execute `node "$standalone_server"` in tmux.
  tmux new-session -d -s "$FRONTEND_SESSION_NAME" \
    "cd '$ROOT_DIR' && env ROOT_DIR='$ROOT_DIR' FRONTEND_LOG='$FRONTEND_LOG' API_BASE_URL='$API_BASE_URL' FRONTEND_HOST='$FRONTEND_HOST' FRONTEND_PORT='$FRONTEND_PORT' bash '$ROOT_DIR/scripts/run_frontend_service.sh'"
  write_tmux_pane_pid "$FRONTEND_SESSION_NAME" "$FRONTEND_PID_FILE"
}

require_command tmux

start_api
start_worker
start_frontend

echo "env_file=$ENV_FILE"
echo "api_session=$API_SESSION_NAME"
echo "worker_session=$WORKER_SESSION_NAME"
echo "frontend_session=$FRONTEND_SESSION_NAME"
echo "api_pid=$(cat "$API_PID_FILE")"
echo "worker_pid=$(cat "$WORKER_PID_FILE")"
echo "frontend_pid=$(cat "$FRONTEND_PID_FILE")"
echo "api_log=$API_LOG"
echo "worker_log=$WORKER_LOG"
echo "frontend_log=$FRONTEND_LOG"
