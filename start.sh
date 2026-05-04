#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

ensure_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR"
}

pid_is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

read_pid() {
  local file="$1"
  [[ -f "$file" ]] && tr -d '[:space:]' < "$file" || true
}

port_pid() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

service_running() {
  local pid_file="$1"
  local port="$2"
  local pid
  pid="$(read_pid "$pid_file")"
  if pid_is_running "$pid"; then
    return 0
  fi
  [[ -n "$(port_pid "$port")" ]]
}

ensure_backend_deps() {
  local stamp="$BACKEND_DIR/.venv/.requirements.stamp"
  if [[ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" || "$BACKEND_DIR/requirements.txt" -nt "$stamp" ]]; then
    echo "Installing backend dependencies..."
    python3 -m venv "$BACKEND_DIR/.venv"
    "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
    touch "$stamp"
  fi
}

ensure_frontend_deps() {
  local stamp="$FRONTEND_DIR/node_modules/.package-lock.stamp"
  if [[ ! -d "$FRONTEND_DIR/node_modules" || "$FRONTEND_DIR/package-lock.json" -nt "$stamp" || "$FRONTEND_DIR/package.json" -nt "$stamp" ]]; then
    echo "Installing frontend dependencies..."
    npm --prefix "$FRONTEND_DIR" install
    touch "$stamp"
  fi
}

start_backend() {
  if service_running "$BACKEND_PID_FILE" "$BACKEND_PORT"; then
    echo "Backend already running on port $BACKEND_PORT"
    return
  fi

  ensure_backend_deps
  echo "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT"
  (
    cd "$BACKEND_DIR"
    nohup .venv/bin/uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )
}

start_frontend() {
  if service_running "$FRONTEND_PID_FILE" "$FRONTEND_PORT"; then
    echo "Frontend already running on port $FRONTEND_PORT"
    return
  fi

  ensure_frontend_deps
  echo "Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT"
  (
    cd "$FRONTEND_DIR"
    nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  local port="$3"
  local pid
  pid="$(read_pid "$pid_file")"

  if pid_is_running "$pid"; then
    echo "Stopping $name pid $pid"
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if pid_is_running "$pid"; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi

  local listener_pid
  listener_pid="$(port_pid "$port")"
  if pid_is_running "$listener_pid"; then
    echo "Stopping $name listener pid $listener_pid on port $port"
    kill "$listener_pid" >/dev/null 2>&1 || true
  fi

  rm -f "$pid_file"
}

start_all() {
  ensure_dirs
  start_backend
  start_frontend
  echo
  echo "Project is running:"
  echo "  Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
  echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
  echo
  echo "Logs:"
  echo "  $BACKEND_LOG"
  echo "  $FRONTEND_LOG"
}

stop_all() {
  ensure_dirs
  stop_pid_file "frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
  stop_pid_file "backend" "$BACKEND_PID_FILE" "$BACKEND_PORT"
  echo "Project stopped"
}

status_all() {
  ensure_dirs
  if service_running "$BACKEND_PID_FILE" "$BACKEND_PORT"; then
    echo "Backend: running on port $BACKEND_PORT"
  else
    echo "Backend: stopped"
  fi

  if service_running "$FRONTEND_PID_FILE" "$FRONTEND_PORT"; then
    echo "Frontend: running on port $FRONTEND_PORT"
  else
    echo "Frontend: stopped"
  fi
}

case "${1:-start}" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  *)
    echo "Usage: ./start.sh [start|stop|restart|status]"
    exit 1
    ;;
esac
