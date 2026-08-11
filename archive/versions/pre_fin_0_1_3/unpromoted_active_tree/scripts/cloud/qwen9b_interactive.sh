#!/usr/bin/env bash
set -euo pipefail

cd "${FIN_REPO_ROOT:-/root/autodl-tmp/FIN_Insight_Agent}"

PY="${PY:-/root/miniconda3/bin/python}"
MODEL_PATH="${MODEL_PATH:-data/models_private/modelscope/Qwen/Qwen3___5-9B}"
MODEL_NAME="${MODEL_NAME:-qwen9b}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.92}"
DTYPE="${DTYPE:-float16}"
MAX_TOKENS="${MAX_TOKENS:-1200}"
TEMPERATURE="${TEMPERATURE:-0.0}"
LOG_DIR="${LOG_DIR:-reports/logs}"
PID_FILE="${PID_FILE:-${LOG_DIR}/qwen9b_interactive_vllm.pid}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/qwen9b_interactive_vllm.log}"

mkdir -p "$LOG_DIR"

export TORCHDYNAMO_DISABLE="${TORCHDYNAMO_DISABLE:-1}"
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/cloud/qwen9b_interactive.sh start
  bash scripts/cloud/qwen9b_interactive.sh chat
  bash scripts/cloud/qwen9b_interactive.sh status
  bash scripts/cloud/qwen9b_interactive.sh tail
  bash scripts/cloud/qwen9b_interactive.sh stop

Common overrides:
  PORT=8001 MAX_MODEL_LEN=32768 MAX_TOKENS=1600 bash scripts/cloud/qwen9b_interactive.sh start
  SYSTEM_PROMPT="你是严谨的SEC财务分析助手..." bash scripts/cloud/qwen9b_interactive.sh chat
  NO_HISTORY=1 bash scripts/cloud/qwen9b_interactive.sh chat
  ENABLE_THINKING=1 bash scripts/cloud/qwen9b_interactive.sh chat
EOF
}

is_alive() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
    return
  fi
  return 1
}

server_ready() {
  "$PY" - "$BASE_URL" <<'PY'
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(base + "/v1/models", timeout=2) as resp:
        raise SystemExit(0 if resp.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
}

wait_ready() {
  echo "waiting for vLLM server at ${BASE_URL} ..."
  for _ in $(seq 1 240); do
    if server_ready; then
      echo "server ready: ${BASE_URL}"
      return 0
    fi
    if [[ -f "$PID_FILE" ]] && ! is_alive; then
      echo "vLLM server process exited before readiness. Last log lines:" >&2
      tail -n 80 "$LOG_FILE" >&2 || true
      return 1
    fi
    sleep 2
  done
  echo "server did not become ready. Check log: ${LOG_FILE}" >&2
  return 1
}

start_server() {
  if server_ready; then
    echo "server already ready: ${BASE_URL}"
    return 0
  fi
  if is_alive; then
    echo "server process exists but health check is not ready. PID=$(cat "$PID_FILE") LOG=${LOG_FILE}"
    wait_ready
    return
  fi

  echo "starting vLLM OpenAI server on ${HOST}:${PORT}"
  echo "model=${MODEL_PATH} max_model_len=${MAX_MODEL_LEN} dtype=${DTYPE} gpu_memory_utilization=${GPU_MEMORY_UTILIZATION}"
  nohup "$PY" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --tokenizer "$MODEL_PATH" \
    --served-model-name "$MODEL_NAME" \
    --host "$HOST" \
    --port "$PORT" \
    --trust-remote-code \
    --dtype "$DTYPE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --enforce-eager \
    --language-model-only \
    --skip-mm-profiling \
    --no-enable-log-requests \
    > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  wait_ready
  echo "PID=$(cat "$PID_FILE") LOG=${LOG_FILE}"
}

stop_server() {
  if is_alive; then
    local pid
    pid="$(cat "$PID_FILE")"
    echo "stopping PID=${pid}"
    kill "$pid" || true
    sleep 2
    kill -9 "$pid" 2>/dev/null || true
  else
    echo "no live server pid found"
  fi
  rm -f "$PID_FILE"
}

chat() {
  if ! server_ready; then
    echo "server is not ready. Start it with: bash scripts/cloud/qwen9b_interactive.sh start" >&2
    return 1
  fi
  local history_flag=()
  if [[ "${NO_HISTORY:-0}" == "1" ]]; then
    history_flag=(--no-history)
  fi
  local thinking_flag=()
  if [[ "${ENABLE_THINKING:-0}" == "1" ]]; then
    thinking_flag=(--enable-thinking)
  fi
  "$PY" scripts/cloud/qwen9b_chat_client.py \
    --base-url "$BASE_URL" \
    --model "$MODEL_NAME" \
    --temperature "$TEMPERATURE" \
    --max-tokens "$MAX_TOKENS" \
    --system "${SYSTEM_PROMPT:-你是一个严谨的中文财务分析助手。回答必须清晰、可核查，不确定时直接说明。}" \
    "${thinking_flag[@]}" \
    "${history_flag[@]}"
}

status() {
  if server_ready; then
    echo "ready: ${BASE_URL}"
  elif is_alive; then
    echo "process alive but not ready: PID=$(cat "$PID_FILE") LOG=${LOG_FILE}"
  else
    echo "stopped"
  fi
}

cmd="${1:-}"
case "$cmd" in
  start) start_server ;;
  chat) chat ;;
  status) status ;;
  tail) tail -n 120 -f "$LOG_FILE" ;;
  stop) stop_server ;;
  restart) stop_server; start_server ;;
  help|-h|--help|"") usage ;;
  *) echo "unknown command: $cmd" >&2; usage; exit 2 ;;
esac
