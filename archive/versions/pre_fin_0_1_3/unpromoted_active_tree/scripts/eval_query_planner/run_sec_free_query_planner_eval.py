from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_CLOUD = REPO_ROOT / "scripts" / "cloud"
if str(SCRIPTS_CLOUD) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_CLOUD))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import sec_agent_interactive as interactive  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the current SEC free-query planner over planner_eval_v1.")
    parser.add_argument("--eval-path", default="eval_sets/sec_free_query_planner_eval_v1.jsonl")
    parser.add_argument(
        "--output-path",
        default="reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl",
    )
    parser.add_argument("--query-planner", default=os.environ.get("QUERY_PLANNER", "heuristic"), choices=("heuristic", "llm"))
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "qwen_vllm"), choices=("qwen_vllm", "deepseek", "openai_compatible"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", ""))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", ""))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", ""))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", ""))
    parser.add_argument("--reasoning-effort", default=os.environ.get("REASONING_EFFORT", ""))
    parser.add_argument("--enable-thinking", action="store_true", default=interactive._env_bool("ENABLE_THINKING"))
    parser.add_argument("--disable-thinking", action="store_true", default=interactive._env_bool("DISABLE_THINKING"))
    parser.add_argument("--planner-max-tokens", type=int, default=int(os.environ.get("PLANNER_MAX_TOKENS", "1800")))
    parser.add_argument("--planner-timeout-s", type=int, default=int(os.environ.get("PLANNER_TIMEOUT_S", "180")))
    parser.add_argument("--max-cases", type=int, default=0, help="Optional cap for bounded API smoke runs.")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected case_id values. Repeatable.")
    parser.add_argument("--resume", action="store_true", help="Append to an existing JSONL and skip completed case IDs.")
    parser.add_argument("--tickers", default=os.environ.get("TICKERS", interactive.DEFAULT_TICKER_SCOPE))
    parser.add_argument("--years", default=os.environ.get("YEARS", ""))
    parser.add_argument("--manifest-path", default="data/processed_private/manifests/sec_tech_10k_manifest.jsonl")
    parser.add_argument("--source-gap-path", default=os.environ.get("SOURCE_GAP_PATH", ""))
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--object-bm25-index-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument("--bge-model", default=os.environ.get("BGE_MODEL", "/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3"))
    parser.add_argument("--quiet", action="store_true", default=interactive._env_bool("QUIET"))
    args = parser.parse_args()
    _normalize_model_defaults(args)
    return args


def main() -> None:
    args = parse_args()
    eval_rows = interactive._read_jsonl(_resolve(args.eval_path))
    if args.case_id:
        selected = {str(case_id) for case_id in args.case_id}
        eval_rows = [row for row in eval_rows if str(row.get("case_id") or "") in selected]
    if args.max_cases and args.max_cases > 0:
        eval_rows = eval_rows[: args.max_cases]
    manifest_rows = interactive._read_jsonl(_resolve(args.manifest_path))
    available = interactive._available_scope(manifest_rows)
    project_inventory = interactive._project_inventory(args, manifest_rows)

    output_path = _resolve(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed: set[str] = set()
    if args.resume and output_path.exists():
        completed = {
            str(row.get("case_id") or "")
            for row in interactive._read_jsonl(output_path)
            if str(row.get("case_id") or "")
        }
    else:
        output_path.write_text("", encoding="utf-8")

    outputs = []
    started = time.time()
    for index, eval_row in enumerate(eval_rows, start=1):
        case_id = str(eval_row.get("case_id") or "")
        if case_id in completed:
            if not args.quiet:
                print(f"[{index}/{len(eval_rows)}] {case_id} skipped=already_completed", flush=True)
            continue
        query = str(eval_row.get("query") or "")
        tickers = interactive._resolve_tickers(args.tickers, query, available)
        years = interactive._parse_years(args.years) or interactive._infer_years(query) or list(interactive.DEFAULT_YEARS)
        tickers, years = interactive._filter_available(tickers, years, available)
        row_started = time.time()
        status = "ok"
        error = ""
        contract: dict[str, Any] = {}
        try:
            contract = interactive._build_query_contract(args, query, tickers, years, project_inventory)
        except Exception as exc:
            status = "error"
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
        outputs.append(
            {
                "schema_version": "sec_free_query_planner_eval_contract_row_v0.1",
                "case_id": case_id,
                "category": eval_row.get("category"),
                "query": query,
                "status": status,
                "error": error,
                "elapsed_sec": round(time.time() - row_started, 4),
                "query_contract": contract,
            }
        )
        with output_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(outputs[-1], ensure_ascii=False) + "\n")
            fh.flush()
        if not args.quiet:
            print(f"[{index}/{len(eval_rows)}] {case_id} status={status}", flush=True)
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "case_count": len(outputs),
                "ok_count": sum(1 for row in outputs if row.get("status") == "ok"),
                "error_count": sum(1 for row in outputs if row.get("status") != "ok"),
                "elapsed_sec": round(time.time() - started, 4),
                "query_planner": args.query_planner,
                "llm_backend": args.llm_backend,
                "model": args.model,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _normalize_model_defaults(args: argparse.Namespace) -> None:
    if args.llm_backend == "deepseek":
        args.base_url = args.base_url or "https://api.deepseek.com"
        args.chat_completions_path = args.chat_completions_path or "/chat/completions"
        args.model = args.model or "deepseek-v4-pro"
        args.api_key_env = args.api_key_env or "DEEPSEEK_API_KEY"
        return
    args.base_url = args.base_url or "http://127.0.0.1:8000"
    args.chat_completions_path = args.chat_completions_path or "/v1/chat/completions"
    args.model = args.model or "qwen9b"


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


if __name__ == "__main__":
    main()
