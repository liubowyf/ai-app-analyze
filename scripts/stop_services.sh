#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.runtime_logs"
API_SESSION_NAME="intelligent-app-api"
WORKER_SESSION_NAME="intelligent-app-worker"
FRONTEND_SESSION_NAME="intelligent-app-frontend"
API_COMMAND_PATTERN="./venv/bin/uvicorn api.main:app"
WORKER_COMMAND_PATTERN="./venv/bin/dramatiq workers.task_actor"
FRONTEND_COMMAND_PATTERN="scripts/run_frontend_service.sh"

stop_pidfile() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]]; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

stop_tmux_session() {
  local session_name="$1"
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$session_name" 2>/dev/null; then
    tmux kill-session -t "$session_name"
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

stop_matching_processes() {
  local pattern="$1"
  pkill -f "$pattern" 2>/dev/null || true
  sleep 1
  pkill -9 -f "$pattern" 2>/dev/null || true
}

stop_tmux_session "$API_SESSION_NAME"
stop_tmux_session "$WORKER_SESSION_NAME"
stop_tmux_session "$FRONTEND_SESSION_NAME"
stop_pidfile "$LOG_DIR/frontend.pid"
rm -f "$LOG_DIR/api.pid" "$LOG_DIR/worker.pid" "$LOG_DIR/frontend.pid"
stop_matching_processes "$WORKER_COMMAND_PATTERN"
stop_matching_processes "$API_COMMAND_PATTERN"
stop_matching_processes "$FRONTEND_COMMAND_PATTERN"
stop_port 8000
stop_port 3000

echo "stopped"
