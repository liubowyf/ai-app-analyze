#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:?ROOT_DIR is required}"
FRONTEND_LOG="${FRONTEND_LOG:?FRONTEND_LOG is required}"
API_BASE_URL="${API_BASE_URL:?API_BASE_URL is required}"
FRONTEND_HOST="${FRONTEND_HOST:?FRONTEND_HOST is required}"
FRONTEND_PORT="${FRONTEND_PORT:?FRONTEND_PORT is required}"

cd "$ROOT_DIR/frontend"

env NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" npm run build >>"$FRONTEND_LOG" 2>&1

standalone_server="$(find .next/standalone -type f -path '*/frontend/server.js' 2>/dev/null | head -n 1)"
if [[ -n "$standalone_server" ]]; then
  standalone_server="$(cd "$(dirname "$standalone_server")" && pwd)/$(basename "$standalone_server")"
  standalone_root="$(cd "$(dirname "$standalone_server")" && pwd)"
  mkdir -p "$standalone_root/.next"
  rm -rf "$standalone_root/.next/static"
  cp -R .next/static "$standalone_root/.next/static"
  if [[ -d public ]]; then
    rm -rf "$standalone_root/public"
    cp -R public "$standalone_root/public"
  fi
  cd "$standalone_root"
  env NODE_ENV=production HOSTNAME="$FRONTEND_HOST" PORT="$FRONTEND_PORT" NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" \
    node "$standalone_server" >>"$FRONTEND_LOG" 2>&1
else
  env NODE_ENV=production HOSTNAME="$FRONTEND_HOST" PORT="$FRONTEND_PORT" NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" \
    npm run start >>"$FRONTEND_LOG" 2>&1
fi
