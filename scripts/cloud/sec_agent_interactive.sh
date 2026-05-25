#!/usr/bin/env bash
set -euo pipefail

cd "${FIN_REPO_ROOT:-/root/autodl-tmp/FIN_Insight_Agent}"

PY="${PY:-/root/miniconda3/bin/python}"
LLM_BACKEND="${LLM_BACKEND:-qwen_vllm}"
if [[ "$LLM_BACKEND" == "deepseek" ]]; then
  BASE_URL="${BASE_URL:-https://api.deepseek.com}"
  CHAT_COMPLETIONS_PATH="${CHAT_COMPLETIONS_PATH:-/chat/completions}"
  MODEL_NAME="${MODEL_NAME:-deepseek-v4-pro}"
  API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  REASONING_EFFORT="${REASONING_EFFORT:-}"
  ENABLE_THINKING="${ENABLE_THINKING:-0}"
else
  BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
  CHAT_COMPLETIONS_PATH="${CHAT_COMPLETIONS_PATH:-/v1/chat/completions}"
  MODEL_NAME="${MODEL_NAME:-qwen9b}"
  API_KEY_ENV="${API_KEY_ENV:-}"
  REASONING_EFFORT="${REASONING_EFFORT:-}"
  ENABLE_THINKING="${ENABLE_THINKING:-0}"
fi

usage() {
  cat <<'EOF'
Usage:
  bash scripts/cloud/sec_agent_interactive.sh chat
  bash scripts/cloud/sec_agent_interactive.sh chat-bge-first
  bash scripts/cloud/sec_agent_interactive.sh ask "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh ask-bge-first "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh chat-deepseek
  bash scripts/cloud/sec_agent_interactive.sh chat-mixed-deepseek
  bash scripts/cloud/sec_agent_interactive.sh chat-mixed-8k-deepseek
  bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh ask-mixed-deepseek "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh ask-mixed-8k-deepseek "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh graph-ask-deepseek "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh session-deepseek
  bash scripts/cloud/sec_agent_interactive.sh session-mixed-deepseek
  bash scripts/cloud/sec_agent_interactive.sh session-mixed-8k-deepseek
  bash scripts/cloud/sec_agent_interactive.sh graph-inspect-state /path/to/sec_agent_state.json
  bash scripts/cloud/sec_agent_interactive.sh graph-resume-state /path/to/sec_agent_state.json
  bash scripts/cloud/sec_agent_interactive.sh plan "your free-form prompt"
  bash scripts/cloud/sec_agent_interactive.sh config

This is the constrained SEC agent, not bare model chat:
  free prompt -> SEC BM25/ObjectBM25 -> BGE-M3 rerank -> runtime exact-value ledger
  -> deterministic Judgment Plan -> LLM synthesis -> deterministic post-gates.

Common overrides:
  TICKERS=ALL YEARS=2023,2024,2025 bash scripts/cloud/sec_agent_interactive.sh chat
  TICKERS=NVDA,MSFT YEARS=2025 bash scripts/cloud/sec_agent_interactive.sh chat
  EVIDENCE_TOP_K=3 OBJECT_TOP_K=4 MAX_TOKENS=8000 bash scripts/cloud/sec_agent_interactive.sh ask "..."
  BGE_FIRST=1 bash scripts/cloud/sec_agent_interactive.sh chat
  USER_OUTPUT=1 bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "..."
  QUERY_PLANNER=llm DEEPSEEK_API_KEY=... bash scripts/cloud/sec_agent_interactive.sh chat-deepseek
  DEEPSEEK_API_KEY=... bash scripts/cloud/sec_agent_interactive.sh chat-deepseek
  DEEPSEEK_API_KEY=... YEARS=2023,2024,2025,2026 bash scripts/cloud/sec_agent_interactive.sh session-mixed-deepseek
  SOURCE_GAP_PATH=data/processed_private/source_gaps/sec_tech_8k_earnings_pilot_source_gaps_merged_2026_2027.jsonl bash scripts/cloud/sec_agent_interactive.sh session-mixed-8k-deepseek

Notes:
  Default scope is TICKERS=ALL, which resolves to all companies in the SEC 10-K manifest.
  BGE-first mode stops Qwen before retrieval, runs BGE-M3 on CUDA by default, then starts Qwen for synthesis.
  Query planner system prompts are injected with a manifest-derived project source inventory.
  DeepSeek mode reads the key from DEEPSEEK_API_KEY; do not store API keys in files.
  Mixed mode uses accepted 2023-2025 10-K plus 2026 10-Q BM25/object-BM25 artifacts.
  Mixed 8-K mode adds pilot SEC 8-K earnings-release evidence and optional source gap reasons.
  The exact-value ledger is built at runtime from retrieved structured SEC objects; it is gate-checked but not human-reviewed gold.
EOF
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

ensure_qwen_server() {
  if server_ready; then
    return 0
  fi
  echo "Qwen server is not ready; starting resident vLLM server ..."
  BASE_URL="$BASE_URL" MODEL_NAME="$MODEL_NAME" bash scripts/cloud/qwen9b_interactive.sh start
}

ensure_min_int_env() {
  local name="$1"
  local minimum="$2"
  local current="${!name:-}"
  if ! [[ "$current" =~ ^[0-9]+$ ]] || (( current < minimum )); then
    export "$name=$minimum"
  fi
}

use_mixed_10k_10q_sources() {
  export MANIFEST_PATH="${MANIFEST_PATH:-data/processed_private/manifests/sec_tech_primary_mixed_10k_latest_10q_manifest_fy2023_2027.jsonl}"
  export BM25_INDEX_DIR="${BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027}"
  export OBJECT_BM25_INDEX_DIR="${OBJECT_BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects}"
  export SEC_AGENT_SOURCE_POLICY="${SEC_AGENT_SOURCE_POLICY:-SEC_PRIMARY_MIXED_RECENT}"
}

use_mixed_10k_10q_8k_sources() {
  export MANIFEST_PATH="${MANIFEST_PATH:-data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_pilot_manifest_fy2023_2027.jsonl}"
  export BM25_INDEX_DIR="${BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_pilot_fy2023_2027}"
  export OBJECT_BM25_INDEX_DIR="${OBJECT_BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects}"
  export SOURCE_GAP_PATH="${SOURCE_GAP_PATH:-data/processed_private/source_gaps/sec_tech_8k_earnings_pilot_source_gaps_merged_2026_2027.jsonl}"
  export SEC_AGENT_SOURCE_POLICY="${SEC_AGENT_SOURCE_POLICY:-SEC_PRIMARY_MIXED_WITH_8K_EARNINGS}"
}

agent_flags() {
  local flags=(--llm-backend "$LLM_BACKEND" --base-url "$BASE_URL" --chat-completions-path "$CHAT_COMPLETIONS_PATH" --model "$MODEL_NAME")
  flags+=(--query-planner "${QUERY_PLANNER:-heuristic}")
  flags+=(--manifest-path "${MANIFEST_PATH:-data/processed_private/manifests/sec_tech_10k_manifest.jsonl}")
  if [[ -n "${SOURCE_GAP_PATH:-}" ]]; then
    flags+=(--source-gap-path "$SOURCE_GAP_PATH")
  fi
  flags+=(--bm25-index-dir "${BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_10k}")
  flags+=(--object-bm25-index-dir "${OBJECT_BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_10k_objects}")
  if [[ -n "${MAX_TOKENS:-}" ]]; then
    flags+=(--max-tokens "$MAX_TOKENS")
  fi
  if [[ -n "${PLANNER_MAX_TOKENS:-}" ]]; then
    flags+=(--planner-max-tokens "$PLANNER_MAX_TOKENS")
  fi
  if [[ -n "$API_KEY_ENV" ]]; then
    flags+=(--api-key-env "$API_KEY_ENV")
  fi
  if [[ -n "$REASONING_EFFORT" ]]; then
    flags+=(--reasoning-effort "$REASONING_EFFORT")
  fi
  if [[ "$ENABLE_THINKING" == "1" || "$ENABLE_THINKING" == "true" ]]; then
    flags+=(--enable-thinking)
  fi
  if [[ "${BGE_FIRST:-0}" == "1" ]]; then
    export BGE_DEVICE="${BGE_DEVICE:-cuda}"
    flags+=(--bge-first --auto-start-qwen --bge-device "$BGE_DEVICE")
  elif [[ -n "${BGE_DEVICE:-}" ]]; then
    flags+=(--bge-device "$BGE_DEVICE")
  fi
  printf '%s\n' "${flags[@]}"
}

run_chat() {
  local flags=()
  mapfile -t flags < <(agent_flags)
  if [[ "$LLM_BACKEND" == "qwen_vllm" && "${BGE_FIRST:-0}" != "1" ]]; then
    ensure_qwen_server
  fi
  exec "$PY" scripts/cloud/sec_agent_interactive.py "${flags[@]}" "$@"
}

run_ask() {
  if [[ $# -eq 0 ]]; then
    echo "Usage: bash scripts/cloud/sec_agent_interactive.sh ask \"your prompt\"" >&2
    exit 2
  fi
  local flags=()
  mapfile -t flags < <(agent_flags)
  if [[ "$LLM_BACKEND" == "qwen_vllm" && "${BGE_FIRST:-0}" != "1" ]]; then
    ensure_qwen_server
  fi
  exec "$PY" scripts/cloud/sec_agent_interactive.py "${flags[@]}" --prompt "$*"
}

run_plan() {
  if [[ $# -eq 0 ]]; then
    echo "Usage: bash scripts/cloud/sec_agent_interactive.sh plan \"your prompt\"" >&2
    exit 2
  fi
  local flags=()
  mapfile -t flags < <(agent_flags)
  exec "$PY" scripts/cloud/sec_agent_interactive.py "${flags[@]}" --plan-only --prompt "$*"
}

run_graph_ask() {
  if [[ $# -eq 0 ]]; then
    echo "Usage: bash scripts/cloud/sec_agent_interactive.sh graph-ask \"your prompt\"" >&2
    exit 2
  fi
  local flags=()
  mapfile -t flags < <(agent_flags)
  if [[ "$LLM_BACKEND" == "qwen_vllm" && "${BGE_FIRST:-0}" != "1" ]]; then
    ensure_qwen_server
  fi
  exec "$PY" scripts/cloud/sec_agent_graph_runner.py --prompt "$*" "${flags[@]}"
}

run_graph_inspect_state() {
  if [[ $# -eq 0 ]]; then
    echo "Usage: bash scripts/cloud/sec_agent_interactive.sh graph-inspect-state /path/to/sec_agent_state.json" >&2
    exit 2
  fi
  exec "$PY" scripts/cloud/sec_agent_graph_runner.py --inspect-state --state-path "$1"
}

run_graph_resume_state() {
  if [[ $# -eq 0 ]]; then
    echo "Usage: bash scripts/cloud/sec_agent_interactive.sh graph-resume-state /path/to/sec_agent_state.json" >&2
    exit 2
  fi
  local flags=()
  mapfile -t flags < <(agent_flags)
  local use_state_route="${SEC_AGENT_RESUME_USE_STATE_ROUTE:-1}"
  if [[ "$LLM_BACKEND" == "qwen_vllm" && "${BGE_FIRST:-0}" != "1" && "$use_state_route" =~ ^(0|false|False|no|NO)$ ]]; then
    ensure_qwen_server
  fi
  exec "$PY" scripts/cloud/sec_agent_graph_runner.py --resume-state --state-path "$1" "${flags[@]}"
}

run_context_session() {
  if [[ -x /root/autodl-tmp/envs/sec-agent-cu128/bin/python && "${PY:-}" == "/root/miniconda3/bin/python" ]]; then
    PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python
  fi
  local session_flags=(--llm-backend "$LLM_BACKEND" --base-url "$BASE_URL" --chat-completions-path "$CHAT_COMPLETIONS_PATH" --model "$MODEL_NAME")
  session_flags+=(--query-planner "${QUERY_PLANNER:-llm}")
  session_flags+=(--bge-device "${BGE_DEVICE:-cuda}")
  session_flags+=(--manifest-path "${MANIFEST_PATH:-data/processed_private/manifests/sec_tech_10k_manifest.jsonl}")
  if [[ -n "${SOURCE_GAP_PATH:-}" ]]; then
    session_flags+=(--source-gap-path "$SOURCE_GAP_PATH")
  fi
  session_flags+=(--bm25-index-dir "${BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_10k}")
  session_flags+=(--object-bm25-index-dir "${OBJECT_BM25_INDEX_DIR:-data/indexes/bm25/sec_tech_10k_objects}")
  session_flags+=(--source-policy "${SEC_AGENT_SOURCE_POLICY:-SEC_ONLY_10K}")
  session_flags+=(--graph-max-tokens "${SYNTHESIS_MAX_TOKENS:-8000}")
  if [[ -n "${CONTROLLER_MAX_TOKENS:-}" ]]; then
    session_flags+=(--max-tokens "$CONTROLLER_MAX_TOKENS")
  fi
  if [[ -n "$API_KEY_ENV" ]]; then
    session_flags+=(--api-key-env "$API_KEY_ENV")
  fi
  exec "$PY" scripts/cloud/sec_agent_context_session_cli.py "${session_flags[@]}" "$@"
}

cmd="${1:-chat}"
case "$cmd" in
  chat|"")
    shift || true
    run_chat "$@"
    ;;
  chat-bge-first|chat-gpu-bge)
    export BGE_FIRST=1
    shift || true
    run_chat "$@"
    ;;
  chat-deepseek|chat-api)
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
  if [[ "$MODEL_NAME" == "qwen9b" ]]; then
    export MODEL_NAME="deepseek-v4-pro"
  fi
  export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_chat "$@"
  ;;
  chat-mixed-deepseek|chat-mixed-api)
    use_mixed_10k_10q_sources
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
  if [[ "$MODEL_NAME" == "qwen9b" ]]; then
    export MODEL_NAME="deepseek-v4-pro"
  fi
  export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_chat "$@"
  ;;
  chat-mixed-8k-deepseek|chat-mixed-8k-api)
    use_mixed_10k_10q_8k_sources
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
  if [[ "$MODEL_NAME" == "qwen9b" ]]; then
    export MODEL_NAME="deepseek-v4-pro"
  fi
  export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_chat "$@"
  ;;
  ask)
    shift || true
    run_ask "$@"
    ;;
  ask-bge-first|ask-gpu-bge)
    export BGE_FIRST=1
    shift || true
    run_ask "$@"
    ;;
  ask-deepseek|ask-api)
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
    export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_ask "$@"
  ;;
  ask-mixed-deepseek|ask-mixed-api)
    use_mixed_10k_10q_sources
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
    export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_ask "$@"
  ;;
  ask-mixed-8k-deepseek|ask-mixed-8k-api)
    use_mixed_10k_10q_8k_sources
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
    export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_ask "$@"
  ;;
  graph-ask)
    shift || true
    run_graph_ask "$@"
    ;;
  graph-ask-deepseek|graph-ask-api)
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
    export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export REASONING_EFFORT="${REASONING_EFFORT:-}"
  export ENABLE_THINKING="${ENABLE_THINKING:-0}"
  export BGE_FIRST="${BGE_FIRST:-1}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export MAX_TOKENS="${MAX_TOKENS:-8000}"
  ensure_min_int_env MAX_TOKENS 8000
  shift || true
  run_graph_ask "$@"
  ;;
  session-deepseek|session-api)
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
  export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export BGE_DEVICE="${BGE_DEVICE:-cuda}"
  export SYNTHESIS_MAX_TOKENS="${SYNTHESIS_MAX_TOKENS:-8000}"
  ensure_min_int_env SYNTHESIS_MAX_TOKENS 8000
  shift || true
  run_context_session "$@"
  ;;
  session-mixed-deepseek|session-mixed-api)
    use_mixed_10k_10q_sources
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
  export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export BGE_DEVICE="${BGE_DEVICE:-cuda}"
  export SYNTHESIS_MAX_TOKENS="${SYNTHESIS_MAX_TOKENS:-8000}"
  ensure_min_int_env SYNTHESIS_MAX_TOKENS 8000
  shift || true
  run_context_session "$@"
  ;;
  session-mixed-8k-deepseek|session-mixed-8k-api)
    use_mixed_10k_10q_8k_sources
    export LLM_BACKEND=deepseek
    if [[ "$BASE_URL" == "http://127.0.0.1:8000" ]]; then
      export BASE_URL="https://api.deepseek.com"
    fi
    if [[ "$CHAT_COMPLETIONS_PATH" == "/v1/chat/completions" ]]; then
      export CHAT_COMPLETIONS_PATH="/chat/completions"
    fi
    if [[ "$MODEL_NAME" == "qwen9b" ]]; then
      export MODEL_NAME="deepseek-v4-pro"
    fi
  export API_KEY_ENV="${API_KEY_ENV:-DEEPSEEK_API_KEY}"
  export QUERY_PLANNER="${QUERY_PLANNER:-llm}"
  export BGE_DEVICE="${BGE_DEVICE:-cuda}"
  export SYNTHESIS_MAX_TOKENS="${SYNTHESIS_MAX_TOKENS:-8000}"
  ensure_min_int_env SYNTHESIS_MAX_TOKENS 8000
  shift || true
  run_context_session "$@"
  ;;
  graph-inspect-state)
    shift || true
    run_graph_inspect_state "$@"
    ;;
  graph-resume-state)
    shift || true
    run_graph_resume_state "$@"
    ;;
  plan|preview)
    shift || true
    run_plan "$@"
    ;;
  config)
    flags=()
    mapfile -t flags < <(agent_flags)
    exec "$PY" scripts/cloud/sec_agent_interactive.py "${flags[@]}" --print-config
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
