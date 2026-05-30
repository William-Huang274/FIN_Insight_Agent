#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${1:-.tmp_wsl_venv}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
if [[ "$VENV_DIR" = /* ]]; then
  VENV_PATH="$VENV_DIR"
else
  VENV_PATH="$REPO_ROOT/$VENV_DIR"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required in WSL." >&2
  exit 2
fi

python3 -m venv "$VENV_PATH"
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

cat <<EOF

WSL Python environment is ready.

Add these lines to your local Workbench profile:

WORKBENCH_EXECUTION_SHELL=wsl
WORKBENCH_WSL_REPO_ROOT=$REPO_ROOT
PY=$VENV_PATH/bin/python
BGE_DEVICE=cpu

If your Windows Workbench process holds the API key, keep API_KEY_ENV set in the
profile and set the real key only in the Workbench process environment.
EOF
