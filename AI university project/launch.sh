#!/bin/bash
# Launches the Personal Learning Agent: starts the backend API and the
# frontend dev server, and opens the app in your default browser.
set -e
cd "$(dirname "$0")"

BACKEND_PORT=8000
FRONTEND_PORT=5173

BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  echo "Shutting down..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

if ! command -v npm >/dev/null 2>&1; then
  echo "npm isn't installed yet — install Node.js first (sudo apt install -y nodejs npm), then try again."
  read -p "Press Enter to close..."
  exit 1
fi

if lsof -i :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "Something is already running on port $BACKEND_PORT — assuming the backend is already up."
else
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT &
  BACKEND_PID=$!
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "First run — installing frontend dependencies (this can take a minute)..."
  (cd frontend && npm install)
fi

if lsof -i :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "Something is already running on port $FRONTEND_PORT — open http://127.0.0.1:$FRONTEND_PORT or stop it first."
  xdg-open "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1 &
  wait
  exit 0
fi

(cd frontend && npm run dev -- --port $FRONTEND_PORT --strictPort) &
FRONTEND_PID=$!

for i in $(seq 1 60); do
  if curl -s -o /dev/null "http://127.0.0.1:$FRONTEND_PORT/"; then
    break
  fi
  sleep 0.5
done
xdg-open "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1 &

echo "Personal Learning Agent is running at http://127.0.0.1:$FRONTEND_PORT"
echo "Close this window (or press Ctrl+C) to stop everything."
wait
