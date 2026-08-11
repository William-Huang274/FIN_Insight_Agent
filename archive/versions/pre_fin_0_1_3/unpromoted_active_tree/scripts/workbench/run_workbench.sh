#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="8765"
PYTHON_BIN="${PYTHON:-python}"
RELOAD=0
SKIP_FRONTEND_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --reload)
      RELOAD=1
      shift
      ;;
    --skip-frontend-build)
      SKIP_FRONTEND_BUILD=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FRONTEND_ROOT="$REPO_ROOT/apps/workbench/frontend"

cd "$REPO_ROOT"
mkdir -p data/workbench_private

if [[ "$SKIP_FRONTEND_BUILD" == "0" ]]; then
  if command -v npm >/dev/null 2>&1; then
    pushd "$FRONTEND_ROOT" >/dev/null
    if [[ ! -d node_modules ]]; then
      echo "Installing Workbench frontend dependencies..."
      if [[ -f package-lock.json ]]; then
        npm ci
      else
        npm install
      fi
    fi
    echo "Building Workbench frontend..."
    npm run build
    popd >/dev/null
  else
    echo "npm not found; skipping React/Vite build and using the bundled static page." >&2
  fi
fi

echo
echo "FinSight Workbench:"
echo "  http://$HOST:$PORT/"
echo

ARGS=(scripts/workbench/start_workbench.py --host "$HOST" --port "$PORT")
if [[ "$RELOAD" == "1" ]]; then
  ARGS+=(--reload)
fi
exec "$PYTHON_BIN" "${ARGS[@]}"
