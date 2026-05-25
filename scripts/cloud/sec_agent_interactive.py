from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SRC_ROOT = REPO_ROOT / "src"
for path in (SCRIPTS_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import run_sec_benchmark_vllm_synthesis_from_traces as vllm_runner  # noqa: E402
import run_sec_eval_synthesis_qwen9b_backend as qwen_adapter  # noqa: E402
from sec_agent.claim_verifier import verify_answer_claims  # noqa: E402
from sec_agent.coverage_matrix import build_coverage_matrix  # noqa: E402
from sec_agent.graph_nodes import state_resume_report  # noqa: E402
from sec_agent.graph_state import SecAgentState  # noqa: E402
from sec_agent.llm_gateway import chat_completion_content as gateway_chat_completion_content  # noqa: E402
from sec_agent.model_routes import public_routes_for_backend, route_for_role  # noqa: E402
from sec_agent.project_inventory import build_project_inventory, inventory_brief, inventory_prompt  # noqa: E402
from sec_agent.query_contract import METRIC_FAMILY_ONTOLOGY, QUERY_TASK_TYPES, validate_query_contract  # noqa: E402


KNOWN_COMPANIES: dict[str, tuple[str, ...]] = {
    "AAPL": ("AAPL", "Apple", "苹果"),
    "ADBE": ("ADBE", "Adobe"),
    "ADP": ("ADP", "Automatic Data Processing"),
    "AMD": ("AMD", "Advanced Micro Devices"),
    "AMAT": ("AMAT", "Applied Materials"),
    "AMZN": ("AMZN", "Amazon", "AWS", "亚马逊"),
    "AVGO": ("AVGO", "Broadcom"),
    "CAT": ("CAT", "Caterpillar"),
    "CRM": ("CRM", "Salesforce"),
    "CRWD": ("CRWD", "CrowdStrike"),
    "CSCO": ("CSCO", "Cisco"),
    "CVX": ("CVX", "Chevron"),
    "GE": ("GE", "General Electric"),
    "GOOGL": ("GOOGL", "Alphabet", "Google", "YouTube"),
    "INTC": ("INTC", "Intel"),
    "INTU": ("INTU", "Intuit", "Credit Karma"),
    "JNJ": ("JNJ", "Johnson & Johnson"),
    "JPM": ("JPM", "JPMorgan", "JPMorgan Chase"),
    "LLY": ("LLY", "Eli Lilly", "Lilly"),
    "META": ("META", "Meta", "Facebook", "Instagram", "Reality Labs"),
    "MSFT": ("MSFT", "Microsoft", "Azure", "微软"),
    "MU": ("MU", "Micron"),
    "NVDA": ("NVDA", "NVIDIA", "Nvidia", "英伟达"),
    "PANW": ("PANW", "Palo Alto", "Palo Alto Networks"),
    "PG": ("PG", "Procter", "P&G"),
    "QCOM": ("QCOM", "Qualcomm"),
    "SNOW": ("SNOW", "Snowflake"),
    "TXN": ("TXN", "Texas Instruments"),
    "V": ("V", "Visa"),
    "WMT": ("WMT", "Walmart"),
    "XOM": ("XOM", "Exxon", "ExxonMobil"),
}

DEFAULT_TICKER_SCOPE = "ALL"
DEFAULT_YEARS = (2023, 2024, 2025)
DEFAULT_SECTIONS = (
    "Item 1. Business",
    "Item 1A. Risk Factors",
    "Item 7. Management's Discussion and Analysis",
    "Item 8. Financial Statements and Supplementary Data",
)
VALID_UNITS = {"usd_millions", "usd_billions", "usd_thousands", "percent"}
AI_FOCUS_TICKERS = (
    "NVDA",
    "AMD",
    "AVGO",
    "AMAT",
    "MU",
    "INTC",
    "QCOM",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "ADBE",
    "SNOW",
)
AI_METRIC_FAMILIES = {
    "data_center_revenue",
    "cloud_revenue",
    "advertising_revenue",
    "semiconductor_systems",
    "semiconductor_solutions",
    "infrastructure_software",
    "operating_income",
    "operating_cash_flow",
    "product_revenue",
    "capital_expenditure_proxy",
    "revenue",
    "services_revenue",
    "gross_margin",
    "research_and_development",
    "arr_or_recurring_proxy",
    "deferred_revenue",
    "free_cash_flow_proxy",
    "rpo",
    "subscription_revenue",
    "total_revenue",
}
BANKING_METRIC_FAMILIES = {
    "allowance_for_credit_losses",
    "asset_quality",
    "capital_ratio",
    "credit_quality",
    "credit_risk",
    "deposits",
    "loans",
    "net_charge_offs",
    "net_interest_income",
    "net_interest_margin",
    "nonperforming_assets",
    "nonperforming_loans",
    "provision_for_credit_losses",
    "total_assets",
}
BANKING_INTENT_TERMS = (
    "bank",
    "banking",
    "net interest",
    "interest margin",
    "credit risk",
    "credit quality",
    "credit losses",
    "charge-off",
    "charge offs",
    "allowance for credit",
    "provision for credit",
    "nonperforming",
    "non-performing",
    "nonaccrual",
    "deposits",
    "loans",
    "cet1",
    "净利息",
    "净息差",
    "信用风险",
    "信用质量",
    "信贷损失",
    "信用损失",
    "拨备",
    "不良贷款",
    "不良资产",
    "存款",
    "贷款",
    "资本充足",
)
RESUME_NODE_ORDER = (
    "retrieve_context",
    "build_runtime_ledger",
    "build_coverage_matrix",
    "build_judgment_plan",
    "synthesize_memo",
    "run_deterministic_gates",
    "render_answer",
)
SUPPORTED_RESUME_NODES = set(RESUME_NODE_ORDER)
PEER_INTENT_TERMS = (
    "competitor",
    "competitors",
    "competition",
    "competitive",
    "peer",
    "peers",
    "rival",
    "rivals",
    "竞争",
    "竞争对手",
    "竞品",
    "同行",
    "同行业",
    "对手",
)
COMPARISON_INTENT_TERMS = (
    "compare",
    "comparison",
    "versus",
    "vs",
    "对比",
    "比较",
    "相比",
    "差异",
    "不同",
)
DOMAIN_CATEGORY_TOKENS = {
    "semiconductor",
    "chip",
    "gpu",
    "cloud",
    "software",
    "cybersecurity",
    "financial",
    "banking",
    "pharma",
    "healthcare",
    "energy",
    "consumer",
    "retail",
    "industrial",
    "payments",
    "advertising",
    "ai",
}
def parse_args() -> argparse.Namespace:
    llm_backend_default = os.environ.get("LLM_BACKEND", "qwen_vllm").strip() or "qwen_vllm"
    base_url_default = os.environ.get("BASE_URL") or (
        "https://api.deepseek.com" if llm_backend_default == "deepseek" else "http://127.0.0.1:8000"
    )
    chat_path_default = os.environ.get("CHAT_COMPLETIONS_PATH") or (
        "/chat/completions" if llm_backend_default == "deepseek" else "/v1/chat/completions"
    )
    model_default = os.environ.get("MODEL_NAME") or (
        "deepseek-v4-pro" if llm_backend_default == "deepseek" else "qwen9b"
    )
    api_key_env_default = os.environ.get("API_KEY_ENV") or (
        "DEEPSEEK_API_KEY" if llm_backend_default == "deepseek" else ""
    )
    parser = argparse.ArgumentParser(description="Free-prompt SEC-grounded interactive agent using BGE context + ledger + Judgment Plan + Qwen.")
    parser.add_argument("--llm-backend", default=llm_backend_default, choices=("qwen_vllm", "deepseek", "openai_compatible"))
    parser.add_argument("--base-url", default=base_url_default)
    parser.add_argument("--chat-completions-path", default=chat_path_default)
    parser.add_argument("--model", default=model_default)
    parser.add_argument("--api-key-env", default=api_key_env_default)
    parser.add_argument("--reasoning-effort", default=os.environ.get("REASONING_EFFORT", ""))
    parser.add_argument("--enable-thinking", action="store_true", default=_env_bool("ENABLE_THINKING"))
    parser.add_argument("--disable-thinking", action="store_true", default=_env_bool("DISABLE_THINKING"))
    parser.add_argument("--prompt", default="")
    parser.add_argument("--tickers", default=os.environ.get("TICKERS", DEFAULT_TICKER_SCOPE))
    parser.add_argument("--years", default=os.environ.get("YEARS", ""))
    parser.add_argument(
        "--manifest-path",
        default=os.environ.get("MANIFEST_PATH", "data/processed_private/manifests/sec_tech_10k_manifest.jsonl"),
    )
    parser.add_argument(
        "--source-gap-path",
        default=os.environ.get("SOURCE_GAP_PATH", ""),
        help="Optional JSONL with structured source coverage gaps, for example 8-K earnings-release missing reasons.",
    )
    parser.add_argument("--bm25-index-dir", default=os.environ.get("BM25_INDEX_DIR", "data/indexes/bm25/sec_tech_10k"))
    parser.add_argument(
        "--object-bm25-index-dir",
        default=os.environ.get("OBJECT_BM25_INDEX_DIR", "data/indexes/bm25/sec_tech_10k_objects"),
    )
    parser.add_argument("--bge-model", default=os.environ.get("BGE_MODEL", "/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3"))
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", ""))
    parser.add_argument("--evidence-top-k", type=int, default=int(os.environ.get("EVIDENCE_TOP_K", "4")))
    parser.add_argument("--object-top-k", type=int, default=int(os.environ.get("OBJECT_TOP_K", "4")))
    parser.add_argument("--max-context-rows", type=int, default=int(os.environ.get("MAX_CONTEXT_ROWS", "120")))
    parser.add_argument("--reranker-top-k", type=int, default=int(os.environ.get("RERANKER_TOP_K", "120")))
    parser.add_argument("--ledger-max-rows", type=int, default=int(os.environ.get("LEDGER_MAX_ROWS", "80")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "4000")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TEMPERATURE", "0.0")))
    parser.add_argument("--query-planner", default=os.environ.get("QUERY_PLANNER", "heuristic"), choices=("heuristic", "llm"))
    parser.add_argument("--planner-max-tokens", type=int, default=int(os.environ.get("PLANNER_MAX_TOKENS", "1800")))
    parser.add_argument("--planner-timeout-s", type=int, default=int(os.environ.get("PLANNER_TIMEOUT_S", "180")))
    parser.add_argument("--output-root", default="eval/sec_cases/outputs/interactive_sec_agent")
    parser.add_argument("--print-config", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--auto-start-qwen", action="store_true", default=_env_bool("AUTO_START_QWEN"))
    parser.add_argument("--bge-first", action="store_true", default=_env_bool("BGE_FIRST"))
    parser.add_argument("--quiet", "--user-output", dest="quiet", action="store_true", default=_env_bool("USER_OUTPUT") or _env_bool("QUIET"))
    args = parser.parse_args()
    if args.llm_backend == "deepseek" and not args.api_key_env:
        args.api_key_env = "DEEPSEEK_API_KEY"
    if (
        args.llm_backend == "deepseek"
        and "BASE_URL" not in os.environ
        and str(args.base_url).rstrip("/") == "http://127.0.0.1:8000"
    ):
        args.base_url = "https://api.deepseek.com"
    if args.llm_backend == "deepseek" and "MODEL_NAME" not in os.environ and args.model == "qwen9b":
        args.model = "deepseek-v4-pro"
    if (
        args.llm_backend == "deepseek"
        and "CHAT_COMPLETIONS_PATH" not in os.environ
        and str(args.chat_completions_path) == "/v1/chat/completions"
    ):
        args.chat_completions_path = "/chat/completions"
    if not args.bge_device:
        args.bge_device = "cuda" if args.bge_first else "cpu"
    return args


def main() -> int:
    args = parse_args()
    if args.print_config:
        print(json.dumps(_config_summary(args), ensure_ascii=False, indent=2))
        return 0
    if args.prompt and args.plan_only:
        run_plan_preview(args, args.prompt)
        return 0
    if args.prompt:
        run_one(args, args.prompt)
        return 0

    print("SEC Agent interactive mode. Type /exit to quit.")
    print("Commands: /scope ALL 2023,2024,2025 | /scope NVDA,MSFT 2023,2024,2025 | /config | /clear")
    print("Each prompt runs SEC retrieval, BGE rerank, runtime ledger, Judgment Plan, LLM synthesis, and deterministic gates.")
    if args.quiet:
        print("User-output mode: showing compact progress only; detailed stage logs are saved with each run.")
    while True:
        try:
            prompt = input("\nuser> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        if prompt in {"/exit", "/quit"}:
            return 0
        if prompt.startswith("/scope "):
            parts = prompt.split(maxsplit=2)
            args.tickers = parts[1] if len(parts) >= 2 else ""
            args.years = parts[2] if len(parts) >= 3 else ""
            print(f"scope set: tickers={args.tickers or '<infer>'} years={args.years or '<infer>'}")
            continue
        if prompt == "/config":
            print(json.dumps(_config_summary(args), ensure_ascii=False, indent=2))
            continue
        if prompt.startswith("/plan "):
            run_plan_preview(args, prompt[6:])
            continue
        if prompt == "/clear":
            print("This agent is single-turn per prompt; no conversation history is retained.")
            continue
        run_one(args, prompt)
    return 0


def run_plan_preview(args: argparse.Namespace, prompt: str) -> None:
    manifest_rows = _read_jsonl(REPO_ROOT / args.manifest_path)
    available = _available_scope(manifest_rows)
    tickers = _resolve_tickers(args.tickers, prompt, available)
    years = _parse_years(args.years) or _infer_years(prompt) or _default_years_for_runtime_source_policy()
    tickers, years = _filter_available(tickers, years, available)
    project_inventory = _project_inventory(args, manifest_rows)
    contract = _build_query_contract(args, prompt, tickers, years, project_inventory)
    _detach_planner_trace(contract)
    _print_project_inventory(project_inventory, tickers, years)
    _print_query_contract(contract)
    print(json.dumps(contract, ensure_ascii=False, indent=2))


def run_one(args: argparse.Namespace, prompt: str) -> Path:
    started = time.time()
    console_events: list[str] = []

    def progress(message: str, *, user_message: str | None = None) -> None:
        console_events.append(message)
        if not args.quiet:
            print(message, flush=True)
        elif user_message:
            print(user_message, flush=True)

    progress("[0/5] building inventory-aware Query Contract ...", user_message="[0/5] planning query scope ...")
    manifest_rows = _read_jsonl(REPO_ROOT / args.manifest_path)
    available = _available_scope(manifest_rows)
    tickers = _resolve_tickers(args.tickers, prompt, available)
    years = _parse_years(args.years) or _infer_years(prompt) or _default_years_for_runtime_source_policy()
    tickers, years = _filter_available(tickers, years, available)
    if not tickers or not years:
        raise RuntimeError("No available SEC filings matched inferred scope. Use /scope TICKERS YEARS.")
    project_inventory = _project_inventory(args, manifest_rows)
    query_contract = _build_query_contract(args, prompt, tickers, years, project_inventory)
    planner_trace = _detach_planner_trace(query_contract)
    if query_contract.get("task_type") == "ai_industry_financial_trend":
        args.reranker_top_k = max(args.reranker_top_k, int(os.environ.get("AI_RERANKER_TOP_K", "360")))

    run_id = _run_id(prompt)
    run_root = REPO_ROOT / args.output_root / run_id
    trace_dir = run_root / "trace"
    qwen_dir = run_root / "qwen"
    gate_dir = run_root / "post_gates"
    ledger_path = run_root / "runtime_exact_value_ledger.json"
    coverage_matrix_path = run_root / "runtime_evidence_coverage_matrix.json"
    plan_path = run_root / "runtime_judgment_plan.json"
    plan_report_path = run_root / "runtime_judgment_plan_report.json"
    cases_path = run_root / "case.jsonl"
    run_root.mkdir(parents=True, exist_ok=True)
    state = _create_sec_agent_state(
        args=args,
        prompt=prompt,
        run_id=run_id,
        run_root=run_root,
        tickers=tickers,
        years=years,
        project_inventory=project_inventory,
    )
    state.source_policy = str(query_contract.get("source_policy") or _runtime_source_policy() or "SEC_ONLY")
    _write_sec_agent_state(state)

    case = _build_case(prompt, tickers, years, run_id, query_contract)
    _write_jsonl(cases_path, [case])
    _write_json(run_root / "query_contract.json", query_contract)
    if planner_trace:
        _write_json(run_root / "planner_trace.json", planner_trace)
    _write_json(run_root / "project_inventory.json", project_inventory)
    _add_state_artifact(
        state,
        "query_contract",
        run_root / "query_contract.json",
        metadata={
            "planner": query_contract.get("planner"),
            "task_type": query_contract.get("task_type"),
            "validation": query_contract.get("validation"),
            "planner_trace_path": str((run_root / "planner_trace.json").resolve()) if planner_trace else "",
        },
    )
    state.mark_stage(
        "plan_query",
        "completed",
        metadata={
            "focus_tickers": query_contract.get("focus_tickers") or [],
            "metric_families": query_contract.get("metric_families") or [],
            "task_count": len([task for task in query_contract.get("decomposed_tasks") or [] if isinstance(task, dict)]),
        },
    )
    state.mark_stage("validate_query_contract", "completed", metadata={"validation": query_contract.get("validation")})
    _write_sec_agent_state(state)

    if not args.quiet:
        _print_project_inventory(project_inventory, tickers, years)
        _print_query_contract(query_contract)
    _run_from_planned_state(args=args, state=state, case=case, run_root=run_root, started=started, console_events=console_events)
    return run_root


def resume_from_state(args: argparse.Namespace, state_path: Path | str) -> Path:
    started = time.time()
    state = SecAgentState.read_json(state_path)
    _apply_state_synthesis_route(args, state)
    run_root = Path(state.output_dir)
    query_contract_ref = state.artifacts.get("query_contract")
    if query_contract_ref is None:
        raise RuntimeError("Cannot resume: state has no query_contract artifact.")
    query_contract = _read_json(Path(query_contract_ref.path))
    if query_contract.get("task_type") == "ai_industry_financial_trend":
        args.reranker_top_k = max(args.reranker_top_k, int(os.environ.get("AI_RERANKER_TOP_K", "360")))
    cases_path = run_root / "case.jsonl"
    if cases_path.exists():
        case = _single_jsonl(cases_path)
    else:
        case = _build_case(state.user_query, state.selected_tickers, state.selected_years, state.run_id, query_contract)
        _write_jsonl(cases_path, [case])
    report = state_resume_report(state)
    next_node = str(report.get("next_ready_node") or "")
    if not next_node:
        _write_json(run_root / "graph_resume_report.json", report)
        return run_root
    if next_node not in SUPPORTED_RESUME_NODES:
        raise RuntimeError(f"Unsupported resume node: {next_node}")
    console_events = [f"[resume] state={Path(state_path).resolve()} next={next_node}"]
    _run_from_resume_node(
        args=args,
        state=state,
        case=case,
        run_root=run_root,
        started=started,
        console_events=console_events,
        start_node=next_node,
    )
    return run_root


def _run_from_planned_state(
    *,
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    run_root: Path,
    started: float,
    console_events: list[str],
) -> None:
    _run_from_resume_node(
        args=args,
        state=state,
        case=case,
        run_root=run_root,
        started=started,
        console_events=console_events,
        start_node="retrieve_context",
    )


def _run_from_resume_node(
    *,
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    run_root: Path,
    started: float,
    console_events: list[str],
    start_node: str,
) -> None:
    prompt = state.user_query
    tickers = state.selected_tickers
    years = state.selected_years
    query_contract = case.get("query_contract") or _read_json(Path(state.artifacts["query_contract"].path))
    paths = _interactive_paths(run_root)
    start_index = _resume_node_index(start_node)

    def progress(message: str, *, user_message: str | None = None) -> None:
        console_events.append(message)
        if not args.quiet:
            print(message, flush=True)
        elif user_message:
            print(user_message, flush=True)

    progress(
        f"[scope] companies={','.join(tickers)} years={','.join(str(y) for y in years)}",
        user_message=f"[scope] {len(tickers)} companies; years={','.join(str(y) for y in years)}",
    )
    trace = None
    context_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    coverage_matrix: dict[str, Any] = {}
    judgment_plan = None
    qwen_result: dict[str, Any] | None = None

    if _resume_should_run(start_index, "retrieve_context"):
        trace, context_rows = _stage_retrieve_context(args, state, paths, progress)
    else:
        trace, context_rows = _load_trace_context(paths)

    if _resume_should_run(start_index, "build_runtime_ledger"):
        ledger_rows = _stage_build_runtime_ledger(args, state, case, paths, context_rows, progress)
    else:
        ledger_rows = _load_ledger_rows(paths)

    if _resume_should_run(start_index, "build_coverage_matrix"):
        coverage_matrix = _stage_build_coverage_matrix(state, case, query_contract, paths, context_rows, ledger_rows, progress)
    else:
        coverage_matrix = _read_json(paths["coverage_matrix_path"])

    if _resume_should_run(start_index, "build_judgment_plan"):
        judgment_plan = _stage_build_judgment_plan(state, case, paths, ledger_rows, progress)
    else:
        judgment_plan = _load_judgment_plan(case, paths["plan_path"])

    if _resume_should_run(start_index, "synthesize_memo"):
        qwen_result = _stage_synthesize_memo(
            args,
            state,
            case,
            paths,
            trace,
            context_rows,
            ledger_rows,
            coverage_matrix,
            judgment_plan,
            progress,
            started,
        )
    else:
        qwen_result = _load_qwen_result(paths["qwen_dir"])

    post_gate_ok = True
    if _resume_should_run(start_index, "run_deterministic_gates"):
        post_gate_ok = _stage_run_deterministic_gates(state, case, paths, judgment_plan, progress)
    elif paths["gate_summary_path"].exists():
        gate_summary = _read_json(paths["gate_summary_path"])
        fail_keys = [key for key, value in gate_summary.items() if key.endswith("_gate_pass") and value is False]
        post_gate_ok = not fail_keys

    if _resume_should_run(start_index, "render_answer"):
        _stage_render_answer(state, paths)

    state.status = "completed" if post_gate_ok else "completed_with_gate_failures"
    state.metadata["total_elapsed_sec"] = round(time.time() - started, 4)
    _write_sec_agent_state(state)
    _write_text(run_root / "console_events.log", "\n".join(console_events) + ("\n" if console_events else ""))
    _print_answer(qwen_result, ledger_rows, context_rows, coverage_matrix, paths["gate_dir"], run_root, post_gate_ok, started)


def _interactive_paths(run_root: Path) -> dict[str, Path]:
    trace_dir = run_root / "trace"
    qwen_dir = run_root / "qwen"
    gate_dir = run_root / "post_gates"
    return {
        "trace_dir": trace_dir,
        "qwen_dir": qwen_dir,
        "gate_dir": gate_dir,
        "cases_path": run_root / "case.jsonl",
        "ledger_path": run_root / "runtime_exact_value_ledger.json",
        "coverage_matrix_path": run_root / "runtime_evidence_coverage_matrix.json",
        "evidence_pack_path": run_root / "runtime_evidence_pack.json",
        "plan_path": run_root / "runtime_judgment_plan.json",
        "plan_report_path": run_root / "runtime_judgment_plan_report.json",
        "gate_summary_path": gate_dir / "sec_benchmark_post_gates_summary.json",
        "rendered_path": qwen_dir / "rendered_answer.md",
    }


def _resume_node_index(node: str) -> int:
    if node not in RESUME_NODE_ORDER:
        raise RuntimeError(f"Unsupported resume node: {node}")
    return RESUME_NODE_ORDER.index(node)


def _resume_should_run(start_index: int, node: str) -> bool:
    return RESUME_NODE_ORDER.index(node) >= start_index


def _stage_retrieve_context(
    args: argparse.Namespace,
    state: SecAgentState,
    paths: dict[str, Path],
    progress: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if args.bge_first and _uses_local_qwen(args):
        progress(
            "[setup] BGE-first mode: stopping Qwen server before retrieval to free GPU memory ...",
            user_message="[setup] freeing GPU memory for BGE rerank ...",
        )
        _qwen_control(args, "stop", quiet=True)
    progress(
        f"[1/5] retrieving SEC context with BM25 + BGE-M3 rerank on {args.bge_device} ...",
        user_message=f"[1/5] retrieving and reranking SEC evidence on {args.bge_device} ...",
    )
    _run_context(args, paths["cases_path"], paths["trace_dir"])
    progress("[1/5] retrieval complete.", user_message="[1/5] retrieval complete.")
    trace, context_rows = _load_trace_context(paths)
    _add_state_artifact(
        state,
        "retrieved_context",
        paths["trace_dir"] / "trace_logs.jsonl",
        row_count=len(context_rows),
        metadata={
            "trace_dir": str(paths["trace_dir"].resolve()),
            "bge_device": args.bge_device,
            "context_row_count": len(context_rows),
            "reranker_top_k": args.reranker_top_k,
        },
    )
    state.mark_stage(
        "retrieve_context",
        "completed",
        metadata={"context_row_count": len(context_rows), "trace_dir": str(paths["trace_dir"].resolve())},
    )
    state.mark_stage(
        "rerank_context",
        "completed",
        metadata={"bge_device": args.bge_device, "reranker_top_k": args.reranker_top_k},
    )
    _write_sec_agent_state(state)
    return trace, context_rows


def _stage_build_runtime_ledger(
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    context_rows: list[dict[str, Any]],
    progress: Any,
) -> list[dict[str, Any]]:
    progress(
        "[2/5] building runtime exact-value ledger from retrieved structured objects ...",
        user_message="[2/5] building exact-value ledger ...",
    )
    ledger_rows = _build_runtime_ledger(case, context_rows, args)
    _write_json(
        paths["ledger_path"],
        {
            "schema_version": "sec_agent_runtime_exact_value_ledger_v0.1",
            "source": "interactive_pipeline_structured_objects",
            "case_id": case["case_id"],
            "row_count": len(ledger_rows),
            "rows": ledger_rows,
        },
    )
    _add_state_artifact(state, "runtime_exact_value_ledger", paths["ledger_path"], row_count=len(ledger_rows))
    state.mark_stage("build_runtime_ledger", "completed", metadata={"ledger_row_count": len(ledger_rows)})
    _write_sec_agent_state(state)
    return ledger_rows


def _stage_build_coverage_matrix(
    state: SecAgentState,
    case: dict[str, Any],
    query_contract: dict[str, Any],
    paths: dict[str, Path],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    progress: Any,
) -> dict[str, Any]:
    progress(
        "[3/6] building deterministic evidence coverage matrix ...",
        user_message="[3/6] building evidence coverage matrix ...",
    )
    coverage_matrix = build_coverage_matrix(
        case=case,
        query_contract=query_contract,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
        run_id=state.run_id,
    )
    _write_json(paths["coverage_matrix_path"], coverage_matrix)
    coverage_summary = coverage_matrix.get("summary") or {}
    _add_state_artifact(
        state,
        "evidence_coverage_matrix",
        paths["coverage_matrix_path"],
        row_count=len(coverage_matrix.get("tasks") or []),
        metadata={"summary": coverage_summary},
    )
    state.mark_stage(
        "build_coverage_matrix",
        "completed",
        metadata={
            "coverage_complete": coverage_summary.get("coverage_complete"),
            "primary_task_support_complete": coverage_summary.get("primary_task_support_complete"),
            "answer_status": coverage_summary.get("answer_status"),
        },
    )
    _write_sec_agent_state(state)
    return coverage_matrix


def _stage_build_judgment_plan(
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    ledger_rows: list[dict[str, Any]],
    progress: Any,
) -> dict[str, Any] | None:
    progress("[4/6] building deterministic Judgment Plan ...", user_message="[4/6] building Judgment Plan ...")
    judgment_plan = None
    if ledger_rows:
        _run(
            [
                sys.executable,
                "scripts/build_sec_benchmark_judgment_plan.py",
                "--cases-path",
                str(paths["cases_path"]),
                "--ledger-path",
                str(paths["ledger_path"]),
                "--trace-run-dir",
                str(paths["trace_dir"]),
                "--output-path",
                str(paths["plan_path"]),
                "--report-path",
                str(paths["plan_report_path"]),
            ]
        )
        plan_payload = _read_json(paths["plan_path"])
        plan_payload = _compact_plan_payload_for_interactive(plan_payload, case, ledger_rows)
        _write_json(paths["plan_path"], plan_payload)
        judgment_plan = next((item for item in plan_payload.get("plans") or [] if item.get("case_id") == case["case_id"]), None)
    else:
        _write_json(
            paths["plan_path"],
            {
                "schema_version": "sec_agent_runtime_judgment_plan_empty_v0.1",
                "plans": [],
                "skipped": [{"case_id": case["case_id"], "reason": "no_runtime_ledger_rows"}],
            },
        )
    _add_state_artifact(
        state,
        "judgment_plan",
        paths["plan_path"],
        row_count=len(((_read_json(paths["plan_path"]) if paths["plan_path"].exists() else {}).get("plans") or [])),
        metadata={"report_path": str(paths["plan_report_path"].resolve()) if paths["plan_report_path"].exists() else ""},
    )
    state.mark_stage("build_judgment_plan", "completed", metadata={"has_plan": bool(judgment_plan)})
    _write_sec_agent_state(state)
    return judgment_plan


def _stage_synthesize_memo(
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    trace: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    coverage_matrix: dict[str, Any],
    judgment_plan: dict[str, Any] | None,
    progress: Any,
    started: float,
) -> dict[str, Any]:
    prompt = state.user_query
    progress(
        f"[5/6] asking {_llm_display_name(args)} with SEC context + ledger + Judgment Plan ...",
        user_message=f"[5/6] asking {_llm_display_name(args)} ...",
    )
    _ensure_llm_ready(args)
    case_for_synthesis = dict(case)
    case_for_synthesis["evidence_coverage_matrix"] = _compact_coverage_matrix_for_prompt(coverage_matrix)
    selected_context_rows, evidence_pack = _select_synthesis_evidence_pack(
        args=args,
        case=case_for_synthesis,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
        coverage_matrix=coverage_matrix,
    )
    case_for_synthesis["prompt_context_max_rows"] = evidence_pack["selection"]["max_rows"]
    _write_json(paths["evidence_pack_path"], evidence_pack)
    _add_state_artifact(
        state,
        "evidence_pack",
        paths["evidence_pack_path"],
        row_count=len(selected_context_rows),
        metadata=evidence_pack["selection"],
    )
    raw_output, llm_gateway_result = _ask_llm_server(args, case_for_synthesis, selected_context_rows, ledger_rows, judgment_plan)
    answer, parse_status, raw_answer = _normalize_or_fallback(
        raw_output,
        case_for_synthesis,
        selected_context_rows,
        ledger_rows,
        judgment_plan,
        llm_gateway_result=llm_gateway_result,
    )
    qwen_result = vllm_runner._qwen_result(
        answer,
        selected_context_rows,
        [f"{args.llm_backend}:{args.model} synthesis", "backend_mode:sec_agent_interactive"],
    )
    if args.llm_backend != "qwen_vllm":
        if qwen_result.get("answer_status") == "answered_qwen9b_ledger_repair" or "ledger_repair" in parse_status:
            qwen_result["answer_status"] = "answered_api_model_ledger_repair"
        elif parse_status == "parsed_after_truncation_repair":
            qwen_result["answer_status"] = "answered_api_model_truncation_repair"
        else:
            qwen_result["answer_status"] = "answered_api_model"
        qwen_result["limitations"] = [f"{args.llm_backend} API synthesis backend"]
    claim_first_report = verify_answer_claims(
        answer=qwen_result["answer"],
        raw_answer=raw_answer,
        ledger_rows=ledger_rows,
        context_rows=selected_context_rows,
        judgment_plan=judgment_plan,
    )
    qwen_result["answer"] = claim_first_report["answer"]
    qwen_result["claims"] = claim_first_report["claims"]
    qwen_result["claim_status"] = claim_first_report["claim_status"]
    qwen_result["unsupported_claim_count"] = claim_first_report["unsupported_claim_count"]
    qwen_result["score_notes"] = [
        *qwen_result.get("score_notes", []),
        f"claim_first_candidate_count:{claim_first_report['summary']['candidate_count']}",
        f"claim_first_promoted_count:{claim_first_report['summary']['promoted_count']}",
        f"claim_first_downgraded_count:{claim_first_report['summary']['downgraded_count']}",
        f"claim_first_rejected_count:{claim_first_report['summary']['rejected_count']}",
    ]
    if claim_first_report["unsupported_claim_count"]:
        qwen_result["failure_types"] = [*qwen_result.get("failure_types", []), "claim_first_unsupported_candidates_removed"]
    qwen_result["debug"] = {
        "user_query": prompt,
        "parse_status": parse_status,
        "raw_output_chars": len(raw_output),
        "raw_output": raw_output,
        "llm_gateway": _gateway_debug(llm_gateway_result),
        "claim_first": claim_first_report["summary"],
    }
    _write_run_outputs(paths["qwen_dir"], _trace_with_context_rows(trace, selected_context_rows), qwen_result, args, started, ledger_rows)
    _add_state_artifact(state, "memo_answer", paths["qwen_dir"] / "agent_outputs.jsonl", row_count=1)
    _add_state_artifact(
        state,
        "claim_verification",
        paths["qwen_dir"] / "claim_verification.jsonl",
        row_count=len(qwen_result.get("claims") or []),
        metadata={"unsupported_claim_count": qwen_result.get("unsupported_claim_count")},
    )
    state.mark_stage(
        "synthesize_memo",
        "completed",
        metadata={
            "answer_status": qwen_result.get("answer_status"),
            "parse_status": parse_status,
            "llm_backend": args.llm_backend,
            "model": args.model,
        },
    )
    state.mark_stage(
        "verify_claims",
        "completed",
        metadata={
            "claim_status": qwen_result.get("claim_status"),
            "unsupported_claim_count": qwen_result.get("unsupported_claim_count"),
        },
    )
    _write_sec_agent_state(state)
    return qwen_result


def _stage_run_deterministic_gates(
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    judgment_plan: dict[str, Any] | None,
    progress: Any,
) -> bool:
    progress("[6/6] running deterministic gates ...", user_message="[6/6] running deterministic gates ...")
    post_gate_ok = True
    try:
        _run_post_gates(
            paths["cases_path"],
            paths["qwen_dir"],
            paths["ledger_path"],
            paths["plan_path"],
            paths["gate_dir"],
            has_plan=bool(judgment_plan),
        )
    except subprocess.CalledProcessError as exc:
        post_gate_ok = False
        progress(f"[gate] post-gates returned non-zero: {exc.returncode}")
    gate_summary = _read_json(paths["gate_summary_path"]) if paths["gate_summary_path"].exists() else {}
    fail_keys = [key for key, value in gate_summary.items() if key.endswith("_gate_pass") and value is False]
    if paths["gate_summary_path"].exists():
        _add_state_artifact(
            state,
            "deterministic_gates",
            paths["gate_summary_path"],
            metadata={"ok": bool(post_gate_ok and not fail_keys), "fail_keys": fail_keys},
        )
    state.mark_stage(
        "run_deterministic_gates",
        "completed" if post_gate_ok else "completed_with_failures",
        metadata={"ok": bool(post_gate_ok and not fail_keys), "fail_keys": fail_keys},
    )
    _write_sec_agent_state(state)
    return bool(post_gate_ok and not fail_keys)


def _stage_render_answer(state: SecAgentState, paths: dict[str, Path]) -> None:
    if paths["rendered_path"].exists():
        _add_state_artifact(state, "rendered_answer", paths["rendered_path"])
    state.mark_stage("render_answer", "completed", metadata={"rendered_answer_path": str(paths["rendered_path"].resolve())})
    _write_sec_agent_state(state)


def _load_trace_context(paths: dict[str, Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trace = _single_jsonl(paths["trace_dir"] / "trace_logs.jsonl")
    return trace, trace.get("context_rows") or []


def _load_ledger_rows(paths: dict[str, Path]) -> list[dict[str, Any]]:
    return _read_json(paths["ledger_path"]).get("rows") or []


def _load_judgment_plan(case: dict[str, Any], plan_path: Path) -> dict[str, Any] | None:
    if not plan_path.exists():
        return None
    plan_payload = _read_json(plan_path)
    return next((item for item in plan_payload.get("plans") or [] if item.get("case_id") == case["case_id"]), None)


def _load_qwen_result(qwen_dir: Path) -> dict[str, Any]:
    agent_rows = _read_jsonl(qwen_dir / "agent_outputs.jsonl")
    claim_rows = _read_jsonl(qwen_dir / "claim_verification.jsonl")
    score_rows = _read_jsonl(qwen_dir / "scores.jsonl")
    if not agent_rows:
        raise RuntimeError(f"Cannot load memo answer from {qwen_dir}")
    agent = agent_rows[0]
    claim = claim_rows[0] if claim_rows else {}
    score = score_rows[0] if score_rows else {}
    return {
        "agent_status": agent.get("status"),
        "answer_status": agent.get("answer_status"),
        "answer": agent.get("answer") or {},
        "limitations": agent.get("limitations") or [],
        "claim_status": claim.get("status", "unknown"),
        "claims": claim.get("claims") or [],
        "unsupported_claim_count": claim.get("unsupported_claim_count", 0),
        "score_status": score.get("status", "unknown"),
        "score_total": score.get("score_total", 0),
        "failure_types": score.get("failure_types") or [],
        "score_notes": score.get("notes") or [],
    }


def _create_sec_agent_state(
    *,
    args: argparse.Namespace,
    prompt: str,
    run_id: str,
    run_root: Path,
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
) -> SecAgentState:
    return SecAgentState.create(
        run_id=run_id,
        user_query=prompt,
        output_dir=run_root,
        selected_tickers=tickers,
        selected_years=years,
        inventory_digest=str(project_inventory.get("inventory_digest") or ""),
        model_routes=public_routes_for_backend(
            roles=["planner", "synthesizer"],
            llm_backend=args.llm_backend,
            model=args.model,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
        ),
        metadata={
            "runner": "scripts/cloud/sec_agent_interactive.py",
            "llm_backend": args.llm_backend,
            "model": args.model,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "api_key_env": args.api_key_env,
            "query_planner": args.query_planner,
            "bge_device": args.bge_device,
            "bge_first": bool(args.bge_first),
            "max_context_rows": args.max_context_rows,
            "ledger_max_rows": args.ledger_max_rows,
            "output_root": args.output_root,
        },
    )


def _add_state_artifact(
    state: SecAgentState,
    key: str,
    path: Path,
    *,
    row_count: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    state.with_artifact(
        key,
        path.resolve(),
        row_count=row_count,
        metadata=metadata or {},
    )


def _apply_state_synthesis_route(args: argparse.Namespace, state: SecAgentState) -> None:
    if not _env_bool("SEC_AGENT_RESUME_USE_STATE_ROUTE", default=True):
        return
    route = {}
    if isinstance(state.model_routes, dict):
        route = state.model_routes.get("synthesizer") or {}
    metadata = state.metadata if isinstance(state.metadata, dict) else {}
    backend = str(route.get("backend") or metadata.get("llm_backend") or "").strip()
    if not backend:
        return
    args.llm_backend = backend
    args.model = str(route.get("model") or metadata.get("model") or args.model)
    args.base_url = str(route.get("base_url") or metadata.get("base_url") or _default_base_url_for_backend(backend))
    args.chat_completions_path = str(
        metadata.get("chat_completions_path")
        or _default_chat_completions_path_for_backend(backend)
    )
    api_key_env = route.get("api_key_env")
    if api_key_env is None:
        api_key_env = metadata.get("api_key_env")
    if api_key_env is None:
        api_key_env = _default_api_key_env_for_backend(backend)
    args.api_key_env = str(api_key_env or "")
    if backend == "qwen_vllm":
        args.auto_start_qwen = True


def _default_base_url_for_backend(backend: str) -> str:
    if str(backend or "") == "deepseek":
        return "https://api.deepseek.com"
    return "http://127.0.0.1:8000"


def _default_chat_completions_path_for_backend(backend: str) -> str:
    if str(backend or "") == "deepseek":
        return "/chat/completions"
    return "/v1/chat/completions"


def _default_api_key_env_for_backend(backend: str) -> str:
    if str(backend or "") == "deepseek":
        return "DEEPSEEK_API_KEY"
    return ""


def _write_sec_agent_state(state: SecAgentState) -> None:
    state.write_json(Path(state.output_dir) / "sec_agent_state.json")


def _run_context(args: argparse.Namespace, cases_path: Path, trace_dir: Path) -> None:
    _run(
        [
            sys.executable,
            "scripts/run_sec_benchmark_eval.py",
            "--cases-path",
            str(cases_path),
            "--mode",
            "pipeline_context",
            "--output-dir",
            str(trace_dir),
            "--manifest-path",
            args.manifest_path,
            "--bm25-index-dir",
            args.bm25_index_dir,
            "--object-bm25-index-dir",
            args.object_bm25_index_dir,
            "--object-top-k",
            str(args.object_top_k),
            "--evidence-top-k",
            str(args.evidence_top_k),
            "--max-context-rows",
            str(args.max_context_rows),
            "--context-reranker",
            "bge",
            "--context-reranker-model",
            args.bge_model,
            "--context-reranker-device",
            args.bge_device,
            "--context-reranker-top-k",
            str(args.reranker_top_k),
            "--context-reranker-batch-size",
            "8",
            "--context-reranker-max-length",
            "2048",
            "--context-reranker-doc-max-chars",
            "6000",
        ],
        stream=not args.quiet,
    )


def _ask_llm_server(
    args: argparse.Namespace,
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    judgment_plan: dict[str, Any] | None,
    coverage_matrix: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    prompt_case = dict(case)
    if coverage_matrix:
        prompt_case["evidence_coverage_matrix"] = _compact_coverage_matrix_for_prompt(coverage_matrix)
    api_insight_mode = _uses_api_backend(args)
    synthesis_profile = ""
    if api_insight_mode:
        synthesis_profile = os.environ.get("SYNTHESIS_PROFILE", "api_memo_v1")
        prompt_case["synthesis_profile"] = synthesis_profile
    user_prompt = qwen_adapter._build_prompt(prompt_case, context_rows, ledger_rows, judgment_plan)
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    focus_tickers = [str(item).upper() for item in (query_contract.get("focus_tickers") or case.get("companies") or [])]
    is_broad_ai = str(query_contract.get("task_type") or case.get("task_type") or "") == "ai_industry_financial_trend" or (
        len(focus_tickers) >= 8
        and _contains_any(str(case.get("prompt") or "").lower(), ("ai", "人工智能", "算力", "数据中心", "芯片"))
    )
    driver_cap = 8 if is_broad_ai else (6 if api_insight_mode else 4)
    point_cap = 8 if is_broad_ai else (7 if api_insight_mode else 5)
    if synthesis_profile == "api_memo_v1":
        system_content = (
            "你是SEC证据约束下的财务分析师，输出目标是高质量投研memo，而不是审计清单。"
            "必须只基于给定证据回答；所有精确数值只能来自 Exact-Value Ledger。"
            "必须输出 valid JSON object，只包含 memo schema：direct_answer、investment_thesis、what_changed、why_it_matters、"
            "peer_readthrough、counterarguments、watch_items、source_limitations、not_found、limitations。"
            "不要输出 legacy summary、decision_drivers 或 key_points；系统会从 memo 字段派生 gate 字段。"
            "direct_answer/investment_thesis/summary 不得写精确数字或metric_id。"
            "what_changed/why_it_matters/peer_readthrough/counterarguments 每条都必须绑定当前 metric_ids/evidence_ids；无ID支撑的判断不要写入这些数组。"
            "peer_readthrough 仅在明确涉及同行/竞争对手且有当前证据ID支撑时使用；单公司跨期比较或无同行证据时必须输出空数组。"
            "counterarguments 只能写当前证据支持的反向证据；未来可能削弱 thesis 的待观察事项必须放入 watch_items 或 source_limitations。"
            "watch_items 要说明未来SEC披露中该看什么。"
            "watch_items.source_to_watch 必须使用枚举 future_10k、future_10q、future_sec_filing 或 not_available_current_policy，不要写 SEC-only 等自由文本。"
            "watch_items 不要写 Direct Customer A/B 等匿名客户标签；应写 major customers 或 customer concentration 这类指标族观察项。"
            "why_it_matters 只解释 focus_tickers 的核心 Judgment Plan drivers；同行或竞争对手的定量指标必须放在 peer_readthrough，不要放进 why_it_matters。"
            "不得把 cloud_revenue、services_revenue 或普通服务收入推断为 ARR、订阅收入、经常性收入特征、续费质量或高粘性订阅模式；"
            "只有当前 metric_ids/evidence_ids 明确支持 subscription_revenue、ARR、递延收入或 RPO 时才可这样表述。"
            "涉及竞争对手时必须区分直接竞争、间接替代、供应商/客户/云厂商自研或证据不足，不能只列公司名。"
            "不要写当前引用证据未明确支持的产品代号、竞品产品名或公司名；若没有 evidence_ids 支撑，用泛化描述。"
            "长度控制：what_changed最多3条，why_it_matters最多3条，peer_readthrough最多3条，counterarguments最多1条，watch_items最多2条。"
            "每条对象的 metric_ids 和 evidence_ids 各最多保留2个代表性ID，不能把全部支持ID塞入答案。"
            "每个对象的主文本字段最多80个中文字符；不要输出 confidence 或 schema 之外的字段。"
            "source_limitations最多4条，避免重复同一句限制。"
            "direct_answer 最多2句，investment_thesis 最多3句；优先给结论和分化逻辑，不要展开审计明细。"
            "不能使用股价、估值、新闻、电话会、分析师预期或source policy外信息。"
        )
    elif api_insight_mode:
        system_content = (
            "你是SEC证据约束下的财务分析师。必须只基于给定证据回答。"
            "所有精确数值只能来自 Exact-Value Ledger；不能自由补数。"
            "summary 要写成有观点的 analyst thesis：解释这些指标合在一起意味着什么、为什么重要、还缺什么证据，而不是只复述事实。"
            "但 summary 不得写精确数字、不得使用SEC证据外事实、不得给投资建议。"
            "每个 driver 要回答 what changed、why it matters、so what、what could weaken it；证据不足必须降级。"
            "涉及竞争对手时，要区分直接GPU/加速器竞争、ASIC/网络/半导体解决方案竞争、CPU/Foundry/平台型竞争等角色，不能只列公司名。"
            "不要写当前引用证据未明确支持的产品代号、竞品产品名或公司名；若没有 evidence_ids 支撑，用泛化描述。"
            "先形成可验证的 claim_candidates；每条候选 claim 必须带 metric_ids/evidence_ids，无法举证的候选不要写入最终 key_points。"
            f"最多输出{driver_cap}个decision_drivers和{point_cap}个key_points；优先沿用Judgment Plan的最高rank drivers。"
            "最终只输出 valid JSON object。"
        )
    else:
        system_content = (
            "你是SEC财务分析助手。必须只基于给定证据回答。"
            "所有精确数值只能来自 Exact-Value Ledger；不能自由补数。"
            "先形成可验证的 claim_candidates；每条候选 claim 必须带 metric_ids/evidence_ids，无法举证的候选不要写入最终 key_points。"
            f"最多输出{driver_cap}个decision_drivers和{point_cap}个key_points；优先沿用Judgment Plan的最高rank drivers。"
            "最终只输出 valid JSON object。"
        )
    payload = {
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ],
    }
    return _chat_completion_content(
        args,
        payload["messages"],
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout_s=900,
        role="synthesizer",
        trace_tags={
            "case_id": str(case.get("case_id") or ""),
            "query_contract_digest": str((case.get("query_contract") or {}).get("project_inventory_digest") or ""),
        },
    )


def _compact_coverage_matrix_for_prompt(coverage_matrix: dict[str, Any]) -> dict[str, Any]:
    tasks = []
    for task in coverage_matrix.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        tasks.append(
            {
                "task_id": task.get("task_id"),
                "question_zh": task.get("question_zh"),
                "priority": task.get("priority"),
                "support_level": task.get("support_level"),
                "allowed_answer_strength": task.get("allowed_answer_strength"),
                "required_tickers": task.get("required_tickers") or [],
                "peer_tickers": task.get("peer_tickers") or [],
                "covered_tickers": task.get("covered_tickers") or [],
                "covered_peer_tickers": task.get("covered_peer_tickers") or [],
                "covered_metric_families": task.get("covered_metric_families") or [],
                "covered_filing_types": task.get("covered_filing_types") or [],
                "covered_source_tiers": task.get("covered_source_tiers") or [],
                "missing_tickers": task.get("missing_tickers") or [],
                "missing_peer_tickers": task.get("missing_peer_tickers") or [],
                "missing_metric_families": task.get("missing_metric_families") or [],
                "missing_years": task.get("missing_years") or [],
                "missing_filing_types": task.get("missing_filing_types") or [],
                "missing_source_tiers": task.get("missing_source_tiers") or [],
                "ledger_row_count": task.get("ledger_row_count"),
                "context_row_count": task.get("context_row_count"),
                "must_caveat": task.get("must_caveat") or [],
                "sample_metric_ids": (task.get("sample_metric_ids") or [])[:6],
                "sample_evidence_ids": (task.get("sample_evidence_ids") or [])[:6],
            }
        )
    return {
        "schema_version": coverage_matrix.get("schema_version"),
        "source_policy": coverage_matrix.get("source_policy"),
        "filing_types": coverage_matrix.get("filing_types") or [],
        "source_tiers": coverage_matrix.get("source_tiers") or [],
        "source_coverage_gaps": (coverage_matrix.get("source_coverage_gaps") or [])[:10],
        "summary": coverage_matrix.get("summary") or {},
        "tasks": tasks,
    }


def _select_synthesis_evidence_pack(
    *,
    args: argparse.Namespace,
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    coverage_matrix: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    default_rows = 48
    max_rows = _clamped_int_env("EVIDENCE_PACK_CONTEXT_ROWS", default_rows, 8, 96)
    selected_rows = qwen_adapter._select_prompt_context_rows(
        context_rows,
        ledger_rows,
        coverage_matrix=_compact_coverage_matrix_for_prompt(coverage_matrix),
        max_rows=max_rows,
    )
    selected_ids = [_context_row_stable_id(row) for row in selected_rows]
    coverage_ids = _coverage_sample_ids(coverage_matrix, ledger_rows)
    coverage_id_set = set(coverage_ids)
    coverage_hit_count = sum(1 for row in selected_rows if _context_row_ids(row) & coverage_id_set)
    return selected_rows, {
        "schema_version": "sec_agent_evidence_pack_v0.1",
        "case_id": case.get("case_id"),
        "source": "coverage_matrix_prioritized_context_selection",
        "selection": {
            "policy": "coverage_matrix_sample_ids_then_ledger_ids_then_balanced_context",
            "max_rows": max_rows,
            "input_context_rows": len(context_rows),
            "selected_context_rows": len(selected_rows),
            "coverage_sample_id_count": len(coverage_ids),
            "coverage_matched_row_count": coverage_hit_count,
        },
        "coverage_summary": (coverage_matrix.get("summary") or {}),
        "selected_context_row_ids": selected_ids,
        "coverage_sample_ids": coverage_ids[:80],
    }


def _clamped_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _coverage_sample_ids(coverage_matrix: dict[str, Any], ledger_rows: list[dict[str, Any]]) -> list[str]:
    ledger_ids_by_metric_id = _ledger_source_ids_by_metric_id(ledger_rows)
    ids: list[str] = []
    tasks = [task for task in coverage_matrix.get("tasks") or [] if isinstance(task, dict)]
    tasks.sort(key=lambda task: (0 if str(task.get("priority") or "") == "primary" else 1, str(task.get("task_id") or "")))
    for task in tasks:
        for metric_id in task.get("sample_metric_ids") or []:
            ids.extend(ledger_ids_by_metric_id.get(str(metric_id), []))
        ids.extend(str(item) for item in task.get("sample_evidence_ids") or [] if str(item))
    return _unique_compact_strings(ids)


def _context_row_stable_id(row: dict[str, Any]) -> str:
    for key in ("object_id", "evidence_id", "source_evidence_id"):
        value = str(row.get(key) or "")
        if value:
            return value
    return "|".join(str(row.get(key) or "") for key in ("ticker", "fiscal_year", "section")) or "context_row"


def _context_row_ids(row: dict[str, Any]) -> set[str]:
    ids = set()
    for key in ("object_id", "evidence_id", "source_evidence_id"):
        value = str(row.get(key) or "")
        if value:
            ids.add(value)
    return ids


def _trace_with_context_rows(trace: dict[str, Any], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(trace)
    out["context_rows"] = context_rows
    summary = dict(out.get("context_summary") or {})
    summary["context_row_count"] = len(context_rows)
    summary["selection_policy"] = "coverage_matrix_prioritized_evidence_pack"
    out["context_summary"] = summary
    out["context_preview"] = [
        {
            "source_kind": row.get("source_kind"),
            "ticker": row.get("ticker"),
            "fiscal_year": row.get("fiscal_year"),
            "section": row.get("section"),
            "object_id": row.get("object_id"),
            "evidence_id": row.get("evidence_id"),
        }
        for row in context_rows[:12]
    ]
    return out


def _uses_api_backend(args: argparse.Namespace) -> bool:
    return str(args.llm_backend or "") in {"deepseek", "openai_compatible"}


def _chat_completion_content(
    args: argparse.Namespace,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    timeout_s: int,
    role: str,
    trace_tags: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    route = route_for_role(
        role=role,
        llm_backend=args.llm_backend,
        model=args.model,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
    )
    route_tags = dict(trace_tags or {})
    route_tags["model_call_mode"] = route.call_mode
    route_tags["model_route_role"] = route.role
    route_tags["model_route_backend"] = route.backend
    route_tags["requested_max_tokens"] = max_tokens
    return gateway_chat_completion_content(
        llm_backend=args.llm_backend,
        base_url=args.base_url,
        chat_completions_path=args.chat_completions_path,
        model=args.model,
        messages=messages,
        api_key_env=args.api_key_env,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
        stream=False,
        enable_thinking=bool(args.enable_thinking),
        reasoning_effort=args.reasoning_effort,
        role=role,
        profile=route.profile,
        trace_tags=route_tags,
    )


def _normalize_or_fallback(
    raw_output: str,
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    judgment_plan: dict[str, Any] | None,
    llm_gateway_result: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    try:
        parsed = qwen_adapter._extract_json_object(raw_output)
        if not parsed:
            raise ValueError("no_json_object")
        return qwen_adapter._normalize_answer(parsed, ledger_rows, context_rows, judgment_plan, case), "parsed", parsed
    except Exception:
        repaired = _extract_truncated_json_object(raw_output)
        if repaired:
            answer = qwen_adapter._normalize_answer(repaired, ledger_rows, context_rows, judgment_plan, case)
            note = (
                f"{_model_output_label(llm_gateway_result)} output was truncated before valid JSON closure; "
                "parsed the complete JSON prefix and dropped the incomplete tail."
            )
            answer["limitations"] = _unique_compact_strings([*(answer.get("limitations") or []), note])
            return answer, "parsed_after_truncation_repair", repaired

        answer = qwen_adapter._fallback_answer_from_ledger(raw_output, ledger_rows, context_rows)
        parse_status = "parse_error_ledger_repair"
        if _looks_truncated(llm_gateway_result, raw_output):
            parse_status = "parse_error_truncated_ledger_repair"
            note = (
                f"{_model_output_label(llm_gateway_result)} output hit the synthesis token limit before closing JSON; "
                "only Exact-Value Ledger fallback content is shown."
            )
            answer["limitations"] = _unique_compact_strings([note, *(answer.get("limitations") or [])])
        return answer, parse_status, None


def _extract_truncated_json_object(raw_output: str) -> dict[str, Any] | None:
    text = str(raw_output or "")
    start = text.find("{")
    if start < 0:
        return None
    jsonish = text[start:]
    for candidate in _json_prefix_repair_candidates(jsonish):
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict) and any(
            key in parsed
            for key in (
                "direct_answer",
                "investment_thesis",
                "what_changed",
                "why_it_matters",
                "summary",
                "decision_drivers",
                "key_points",
            )
        ):
            return parsed
    return None


def _json_prefix_repair_candidates(text: str) -> list[str]:
    stack: list[str] = []
    in_string = False
    escape = False
    candidates: list[tuple[int, tuple[str, ...]]] = []
    for idx, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            stack.append("}")
            continue
        if char == "[":
            stack.append("]")
            continue
        if char in ("}", "]"):
            if not stack or stack[-1] != char:
                break
            stack.pop()
            candidates.append((idx + 1, tuple(stack)))
            continue
        if char == "," and stack:
            candidates.append((idx, tuple(stack)))

    # Longest valid repaired prefix wins. Comma candidates intentionally cut
    # before the comma so an incomplete next field/list item can be discarded.
    out: list[str] = []
    for end, remaining_stack in reversed(candidates):
        prefix = text[:end].rstrip()
        while prefix.endswith(","):
            prefix = prefix[:-1].rstrip()
        if not prefix or prefix.endswith(":"):
            continue
        out.append(prefix + "".join(reversed(remaining_stack)))
    return out


def _looks_truncated(llm_gateway_result: dict[str, Any] | None, raw_output: str) -> bool:
    if isinstance(llm_gateway_result, dict):
        if str(llm_gateway_result.get("finish_reason") or "").lower() == "length":
            return True
        output_tokens = _int_or_none(llm_gateway_result.get("output_tokens"))
        requested = _int_or_none((llm_gateway_result.get("trace_tags") or {}).get("requested_max_tokens"))
        if output_tokens is not None and requested is not None and output_tokens >= max(1, requested - 1):
            return True
    text = str(raw_output or "").rstrip()
    return bool(text.startswith("{") and not text.endswith("}"))


def _model_output_label(llm_gateway_result: dict[str, Any] | None) -> str:
    if not isinstance(llm_gateway_result, dict):
        return "Model"
    provider = str(llm_gateway_result.get("provider") or "").strip()
    model = str(llm_gateway_result.get("model") or "").strip()
    if provider and model:
        return f"{provider}/{model}"
    return provider or model or "Model"


def _compact_plan_payload_for_interactive(
    plan_payload: dict[str, Any],
    case: dict[str, Any],
    ledger_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    if query_contract.get("task_type") != "ai_industry_financial_trend":
        return plan_payload

    source_ids_by_metric_id = _ledger_source_ids_by_metric_id(ledger_rows or [])
    driver_limit = int(query_contract.get("judgment_plan_driver_limit") or 8)
    driver_limit = max(4, min(driver_limit, 8))
    for plan in plan_payload.get("plans") or []:
        if not isinstance(plan, dict) or plan.get("case_id") != case.get("case_id"):
            continue
        drivers = [driver for driver in plan.get("drivers") or [] if isinstance(driver, dict)]
        selected_drivers = _select_interactive_plan_drivers(drivers, query_contract, driver_limit)
        compact_drivers = []
        for rank, driver in enumerate(selected_drivers, start=1):
            compact = dict(driver)
            compact["rank"] = rank
            metric_ids = [str(item) for item in compact.get("supporting_metric_ids") or []][:8]
            compact["supporting_metric_ids"] = metric_ids
            evidence_ids = []
            for metric_id in metric_ids:
                evidence_ids.extend(source_ids_by_metric_id.get(metric_id, []))
            evidence_ids.extend(str(item) for item in compact.get("supporting_evidence_ids") or [])
            compact["supporting_evidence_ids"] = _unique_compact_strings(evidence_ids)[:12]
            compact["covered_companies"] = [str(item) for item in compact.get("covered_companies") or []][:6]
            years = []
            for item in compact.get("covered_years") or []:
                year = _int_or_none(item)
                if year is not None:
                    years.append(year)
            compact["covered_years"] = years[:3]
            compact["metric_families"] = [str(item) for item in compact.get("metric_families") or []][:6]
            compact["caveats"] = [str(item) for item in compact.get("caveats") or []][:2]
            compact_drivers.append(compact)
        plan["drivers"] = compact_drivers
        plan["must_downgrade_because"] = [str(item) for item in plan.get("must_downgrade_because") or []][:8]
        plan["do_not_overstate"] = [str(item) for item in plan.get("do_not_overstate") or []][:4]
        plan.setdefault("interactive_compaction", {})
        plan["interactive_compaction"] = {
            "reason": "free_query_ai_full30_task_family_balanced_prompt_budget",
            "driver_limit": driver_limit,
            "metric_ids_per_driver": 8,
            "evidence_ids_per_driver": 12,
            "selection": "decomposed_task_metric_family_diversity_then_original_rank",
        }
    return plan_payload


def _select_interactive_plan_drivers(
    drivers: list[dict[str, Any]],
    query_contract: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    if len(drivers) <= limit:
        return drivers

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()

    def add(driver: dict[str, Any] | None) -> None:
        if not driver:
            return
        key = id(driver)
        if key in selected_ids or len(selected) >= limit:
            return
        selected.append(driver)
        selected_ids.add(key)

    decomposed_tasks = query_contract.get("decomposed_tasks") if isinstance(query_contract.get("decomposed_tasks"), list) else []
    for task in decomposed_tasks:
        if len(selected) >= limit:
            break
        if not isinstance(task, dict):
            continue
        required = {str(item) for item in task.get("required_metric_families") or [] if item}
        if not required:
            continue
        add(_best_driver_for_family_set(drivers, selected_ids, required))

    covered_families = {
        str(family)
        for driver in selected
        for family in driver.get("metric_families") or []
        if family
    }
    requested_families = [str(item) for item in query_contract.get("metric_families") or [] if item]
    for family in requested_families:
        if len(selected) >= limit:
            break
        if family in covered_families:
            continue
        driver = _best_driver_for_family_set(drivers, selected_ids, {family})
        add(driver)
        if driver:
            covered_families.update(str(item) for item in driver.get("metric_families") or [] if item)

    for driver in drivers:
        if len(selected) >= limit:
            break
        add(driver)
    return selected


def _best_driver_for_family_set(
    drivers: list[dict[str, Any]],
    selected_ids: set[int],
    required_families: set[str],
) -> dict[str, Any] | None:
    best: tuple[int, int, int, int, dict[str, Any]] | None = None
    strength_score = {"strong": 3, "medium": 2, "weak": 1}
    for position, driver in enumerate(drivers):
        if id(driver) in selected_ids:
            continue
        families = {str(item) for item in driver.get("metric_families") or [] if item}
        overlap = families & required_families
        if not overlap:
            continue
        year_count = len({int(year) for year in driver.get("covered_years") or [] if _int_or_none(year) is not None})
        metric_count = len([item for item in driver.get("supporting_metric_ids") or [] if item])
        score = (
            len(overlap),
            year_count,
            strength_score.get(str(driver.get("conclusion_strength") or "").lower(), 0),
            metric_count,
        )
        candidate = (*score, driver)
        if best is None or candidate[:4] > best[:4] or (candidate[:4] == best[:4] and position < drivers.index(best[4])):
            best = candidate
    return best[4] if best else None


def _ledger_source_ids_by_metric_id(ledger_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for row in ledger_rows:
        metric_id = str(row.get("metric_id") or "")
        if not metric_id:
            continue
        candidates = [
            str(row.get("source_evidence_id") or ""),
            str(row.get("evidence_id") or ""),
            str(row.get("object_id") or ""),
        ]
        mapping[metric_id] = _unique_compact_strings([*mapping.get(metric_id, []), *candidates])
    return mapping


def _unique_compact_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _run_post_gates(
    cases_path: Path,
    qwen_dir: Path,
    ledger_path: Path,
    plan_path: Path,
    gate_dir: Path,
    *,
    has_plan: bool,
) -> None:
    cmd = [
        sys.executable,
        "scripts/run_sec_benchmark_post_gates.py",
        "--gold-run-dir",
        str(qwen_dir),
        "--pipeline-run-dir",
        str(qwen_dir),
        "--cases-path",
        str(cases_path),
        "--output-dir",
        str(gate_dir),
        "--ledger-path",
        str(ledger_path),
        "--skip-trap-gate",
        "--skip-gold-vs-pipeline-gate",
        "--min-qwen-answer-ratio",
        "1.0",
    ]
    if has_plan:
        cmd.extend(["--judgment-plan-path", str(plan_path)])
    else:
        cmd.append("--skip-answer-vs-judgment-plan-gate")
    _run(cmd)


def _build_runtime_ledger(
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    object_ids = [
        str(row.get("object_id") or "")
        for row in context_rows
        if row.get("source_kind") == "structured_object" and row.get("object_id")
    ]
    records = _load_object_records(REPO_ROOT / args.object_bm25_index_dir)
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    context_by_object_id = {
        str(row.get("object_id") or ""): row
        for row in context_rows
        if row.get("object_id")
    }
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for object_id in object_ids:
        record = records.get(object_id)
        if not record:
            continue
        if record.get("object_type") == "metric":
            row = _ledger_row_from_metric(case["case_id"], record)
            if row and _ledger_row_allowed(row, query_contract, context_by_object_id.get(object_id)):
                for candidate in [row, *_ledger_growth_rate_rows_from_metric(case["case_id"], record, row)]:
                    if not _ledger_row_allowed(candidate, query_contract, context_by_object_id.get(object_id)):
                        continue
                    key = _ledger_dedupe_key(candidate)
                    if key not in seen:
                        rows.append(candidate)
                        seen.add(key)
        elif record.get("object_type") == "table":
            for row in _ledger_rows_from_table(case["case_id"], record, set(case["years"])):
                if not _ledger_row_allowed(row, query_contract, context_by_object_id.get(object_id)):
                    continue
                key = _ledger_dedupe_key(row)
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
    _supplement_ai_focus_ledger(case, records, rows, seen, query_contract)
    _supplement_contract_metric_family_ledger(case, records, rows, seen, query_contract)
    _supplement_banking_context_ledger(case, context_rows, rows, seen, query_contract)
    _supplement_free_cash_flow_proxy(case, rows, seen, query_contract)
    rows.sort(key=lambda row: _ledger_row_rank(row, query_contract, context_by_object_id.get(str(row.get("object_id") or ""))), reverse=True)
    rows = _cap_ledger_rows(rows, query_contract, args.ledger_max_rows)
    _dedupe_metric_ids(rows)
    return rows[: args.ledger_max_rows]


def _filing_year_from_source_id(value: Any) -> int | None:
    match = re.search(r"_(20\d{2})_(?:10K|10Q)_", str(value or ""))
    return int(match.group(1)) if match else None


def _metric_sentence_year(record: dict[str, Any], raw: str, default_year: int | None) -> int | None:
    source_year = _filing_year_from_source_id(record.get("source_evidence_id"))
    context = str(record.get("context") or "").lower()
    raw_text = str(raw or "").strip().lower()
    if source_year and context and raw_text and "compared to" in context:
        compare_idx = context.find("compared to")
        raw_idx = context.find(raw_text)
        if raw_idx < 0:
            raw_idx = context.find(raw_text.replace("$", "").strip())
        if 0 <= raw_idx < compare_idx:
            return source_year
    return default_year


def _ledger_source_fields(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    source_type = str(record.get("source_type") or metadata.get("source_type") or "").upper().strip()
    form_type = str(record.get("form_type") or metadata.get("form_type") or source_type).upper().strip()
    if not form_type:
        form_type = _form_type_from_source_id(record.get("source_evidence_id") or record.get("object_id"))
    source_tier = str(record.get("source_tier") or metadata.get("source_tier") or "").strip()
    return {
        "source_type": _normalize_form_type(source_type or form_type),
        "form_type": _normalize_form_type(form_type),
        "source_tier": source_tier or "primary_sec_filing",
        "period_end": record.get("period_end") or metadata.get("period_end"),
        "period_type": record.get("period_type") or metadata.get("period_type"),
        "duration_months": record.get("duration_months") or metadata.get("duration_months"),
        "fiscal_period": record.get("fiscal_period") or metadata.get("fiscal_period"),
    }


def _ledger_period_role(record: dict[str, Any], cell: dict[str, Any] | None = None) -> str | None:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    cell = cell or {}
    explicit = cell.get("period_role") or record.get("period_role") or metadata.get("period_role")
    if explicit:
        return str(explicit)
    repaired = _period_role_from_10q_cash_flow_column(record, cell)
    if repaired:
        return repaired
    for value in (
        cell.get("column_label"),
        record.get("column_label"),
        cell.get("row_label"),
        record.get("row_label"),
        record.get("context"),
        record.get("title"),
        record.get("text_before"),
        record.get("text_after"),
    ):
        role = _period_role_from_text(value)
        if role:
            return role
    source_fields = _ledger_source_fields(record)
    form_type = str(source_fields.get("form_type") or "")
    period_type = str(source_fields.get("period_type") or "").lower()
    duration = _int_or_none(source_fields.get("duration_months"))
    if form_type == "10-K" or period_type == "annual" or duration == 12:
        return "annual"
    if form_type == "10-Q" and (period_type == "quarterly" or duration == 3):
        return "qtd"
    return None


def _period_role_from_10q_cash_flow_column(record: dict[str, Any], cell: dict[str, Any] | None = None) -> str | None:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    cell = cell or {}
    source_fields = _ledger_source_fields(record)
    form_type = str(source_fields.get("form_type") or "").upper()
    if form_type != "10-Q":
        return None
    text = " ".join(
        str(part or "")
        for part in (
            record.get("subsection"),
            record.get("section"),
            record.get("title"),
            record.get("context"),
            record.get("metric_name"),
            record.get("row_label"),
            cell.get("row_label"),
        )
    ).lower()
    if "cash flow" not in text and "cash flows" not in text and "net cash" not in text and "property and equipment" not in text:
        return None
    column_index = _int_or_none(cell.get("column_index") or metadata.get("column_index"))
    logical_index = _int_or_none(cell.get("logical_column_index") or metadata.get("logical_column_index"))
    index = column_index if column_index is not None else logical_index
    if index is None:
        return None
    if _is_legacy_parenthesized_cash_flow_column(record, cell):
        if index in {1, 3}:
            return "qtd"
        if index in {5, 7}:
            return "ytd"
        return None
    # Some legacy parsed rows keep standalone ")" cells as columns, so capex
    # cash-flow cells land at 1/3/5/7 instead of 1/2/3/4.
    if index in {1, 2}:
        return "qtd"
    if index in {3, 4}:
        return "ytd"
    if index in {5, 6}:
        return "ytd"
    return None


def _period_year_from_10q_cash_flow_column(record: dict[str, Any], cell: dict[str, Any] | None = None) -> int | None:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    source_fields = _ledger_source_fields(record)
    if str(source_fields.get("form_type") or "").upper() != "10-Q":
        return None
    source_year = _year_from_value(record.get("fiscal_year"))
    if source_year is None:
        return None
    text = " ".join(
        str(part or "")
        for part in (
            record.get("subsection"),
            record.get("section"),
            record.get("title"),
            record.get("context"),
            record.get("metric_name"),
            record.get("row_label"),
            (cell or {}).get("row_label"),
        )
    ).lower()
    if "cash flow" not in text and "cash flows" not in text and "net cash" not in text and "property and equipment" not in text:
        return None
    column_index = _int_or_none((cell or {}).get("column_index") or metadata.get("column_index"))
    logical_index = _int_or_none((cell or {}).get("logical_column_index") or metadata.get("logical_column_index"))
    index = column_index if column_index is not None else logical_index
    if index is None:
        return None
    if _is_legacy_parenthesized_cash_flow_column(record, cell):
        if index in {1, 5}:
            return source_year
        if index in {3, 7}:
            return source_year - 1
        return None
    if index in {1, 3, 5}:
        return source_year
    if index in {2, 4, 6, 7}:
        return source_year - 1
    return None


def _is_legacy_parenthesized_cash_flow_column(record: dict[str, Any], cell: dict[str, Any] | None = None) -> bool:
    cell = cell or {}
    raw = str(cell.get("raw_value") or record.get("raw_value") or "").strip()
    if not raw.startswith("("):
        return False
    text = " ".join(
        str(part or "")
        for part in (
            record.get("subsection"),
            record.get("context"),
            record.get("metric_name"),
            record.get("row_label"),
            cell.get("row_label"),
        )
    ).lower()
    return "cash flow" in text or "cash flows" in text or "property and equipment" in text


def _period_role_from_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").lower()).strip()
    if not text:
        return None
    patterns = {
        "ttm": (
            r"\bttm\b",
            r"trailing\s+twelve\s+months",
            r"twelve\s+months\s+ended",
            r"12\s+months\s+ended",
        ),
        "ytd": (
            r"\bytd\b",
            r"year[-\s]?to[-\s]?date",
            r"six\s+months\s+ended",
            r"nine\s+months\s+ended",
            r"6\s+months\s+ended",
            r"9\s+months\s+ended",
        ),
        "qtd": (
            r"three\s+months\s+ended",
            r"3\s+months\s+ended",
            r"quarter\s+ended",
            r"for\s+the\s+quarter",
            r"\bquarterly\b",
        ),
        "annual": (
            r"year\s+ended",
            r"fiscal\s+year",
            r"for\s+the\s+year",
            r"\bannual\b",
        ),
        "instant": (
            r"as\s+of\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            r"\bat\s+(?:the\s+)?(?:period|quarter|year)[-\s]?end\b",
        ),
    }
    matches = {
        role
        for role, role_patterns in patterns.items()
        if any(re.search(pattern, text, flags=re.I) for pattern in role_patterns)
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


def _form_type_from_source_id(value: Any) -> str:
    text = str(value or "").upper()
    if "_10Q_" in text:
        return "10-Q"
    if "_10K_" in text:
        return "10-K"
    return ""


def _normalize_form_type(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")


def _ledger_row_from_metric(case_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
    unit = str(record.get("unit") or "")
    raw = str(record.get("raw_value") or "")
    if unit not in VALID_UNITS or not raw or _is_bad_numeric_raw(raw, unit):
        return None
    ticker = str(record.get("ticker") or "").upper()
    year = (
        _period_year_from_10q_cash_flow_column(record)
        or _year_from_value(record.get("period"))
        or _year_from_value(record.get("fiscal_year"))
    )
    year = _metric_sentence_year(record, raw, year)
    if not ticker or year is None:
        return None
    metric_name = str(record.get("metric_name") or record.get("row_label") or "metric")
    if _is_low_signal_metric(metric_name, unit):
        return None
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    metric_context = str(record.get("context") or "")
    family = _metric_family(metric_name, metric_context)
    role = _metric_role(" ".join(part for part in (metric_name, metric_context) if part), unit)
    period_role = _ledger_period_role(record)
    value = _normalized_ledger_value(record.get("value"), raw, family)
    return {
        "metric_id": _ledger_metric_id(case_id, ticker, year, family, role, period_role=period_role),
        "case_id": case_id,
        "ticker": ticker,
        "fiscal_year": year,
        "source_fiscal_year": _year_from_value(record.get("fiscal_year")),
        "period": str(record.get("period") or year),
        "period_role": period_role,
        **_ledger_source_fields(record),
        "metric_family": family,
        "metric_role": role,
        "metric_name": metric_name,
        "raw_value_text": raw,
        "display_value_zh": _display_value_zh(raw, unit),
        "value": value,
        "unit": unit,
        "object_id": record.get("object_id"),
        "source_evidence_id": record.get("source_evidence_id"),
        "section": record.get("section"),
        "row_label": record.get("row_label"),
        "column_label": record.get("column_label"),
        "cell_kind": record.get("cell_kind") or metadata.get("cell_kind"),
        "table_object_id": record.get("table_object_id") or metadata.get("table_object_id"),
        "source_text": record.get("context"),
        "record_title": record.get("title"),
    }


def _ledger_growth_rate_rows_from_metric(
    case_id: str,
    record: dict[str, Any],
    base_row: dict[str, Any],
) -> list[dict[str, Any]]:
    context = str(record.get("context") or "")
    family = str(base_row.get("metric_family") or "")
    if family not in {
        "advertising_revenue",
        "cloud_revenue",
        "data_center_revenue",
        "infrastructure_software",
        "operating_income",
        "product_revenue",
        "revenue",
        "semiconductor_solutions",
        "semiconductor_systems",
        "services_revenue",
        "subscription_revenue",
        "total_revenue",
    }:
        return []
    if not _contains_any(context.lower(), ("increase", "increased", "decrease", "decreased", "grew", "growth", "declined")):
        return []
    rows = []
    for match in re.finditer(r"\bor\s+(-?\d+(?:\.\d+)?)\s*%", context, flags=re.I):
        value = float(match.group(1))
        raw = f"{match.group(1)}%"
        row = dict(base_row)
        period_role = str(base_row.get("period_role") or "")
        row.update(
            {
                "metric_id": _ledger_metric_id(
                    case_id,
                    str(base_row.get("ticker") or ""),
                    base_row.get("fiscal_year"),
                    family,
                    "percentage_rate",
                    period_role=period_role,
                ),
                "metric_role": "percentage_rate",
                "metric_name": f"{base_row.get('metric_name') or family} growth rate",
                "raw_value_text": raw,
                "display_value_zh": raw,
                "value": value,
                "unit": "percent",
            }
        )
        rows.append(row)
    return rows[:2]


def _ledger_rows_from_table(case_id: str, record: dict[str, Any], years: set[int]) -> list[dict[str, Any]]:
    rows = []
    ticker = str(record.get("ticker") or "").upper()
    for cell in record.get("cells") or []:
        unit = str(cell.get("unit") or "")
        raw = str(cell.get("raw_value") or "")
        year = (
            _period_year_from_10q_cash_flow_column(record, cell)
            or _year_from_value(cell.get("period"))
            or _year_from_value(cell.get("column_label"))
        )
        if unit not in VALID_UNITS or not raw or _is_bad_numeric_raw(raw, unit) or year is None or (years and year not in years):
            continue
        metric_name = " ".join(str(part) for part in (cell.get("active_group"), cell.get("row_label")) if part)
        if not metric_name.strip():
            metric_name = str(record.get("title") or "table_metric")
        if _is_low_signal_metric(metric_name, unit):
            continue
        family = _metric_family(metric_name, str(record.get("title") or ""))
        role = _metric_role(metric_name, unit)
        period_role = _ledger_period_role(record, cell)
        value = _normalized_ledger_value(cell.get("value"), raw, family)
        rows.append(
            {
                "metric_id": _ledger_metric_id(
                    case_id,
                    ticker,
                    year,
                    family,
                    role,
                    period_role=period_role,
                    suffix=_slug(str(cell.get("row_label") or "row")),
                ),
                "case_id": case_id,
                "ticker": ticker,
                "fiscal_year": year,
                "source_fiscal_year": _year_from_value(record.get("fiscal_year")),
                "period": str(cell.get("period") or year),
                "period_role": period_role,
                **_ledger_source_fields(record),
                "metric_family": family,
                "metric_role": role,
                "metric_name": metric_name,
                "raw_value_text": raw,
                "display_value_zh": _display_value_zh(raw, unit),
                "value": value,
                "unit": unit,
                "object_id": record.get("object_id"),
                "source_evidence_id": record.get("source_evidence_id"),
                "section": record.get("section"),
                "row_label": cell.get("row_label"),
                "column_label": cell.get("column_label"),
                "table_title": record.get("title"),
                "active_group": cell.get("active_group"),
                "cell_kind": cell.get("cell_kind"),
                "row_index": cell.get("row_index"),
            }
        )
    return rows


def _normalized_ledger_value(value: Any, raw: str, family: str) -> Any:
    if not isinstance(value, (int, float)):
        return value
    raw_text = str(raw or "").strip()
    if raw_text.startswith("(") and family in {"capital_expenditure_proxy"}:
        return -abs(float(value))
    return value


def _supplement_ai_focus_ledger(
    case: dict[str, Any],
    records: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    if query_contract.get("task_type") != "ai_industry_financial_trend":
        return
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    target_labels = ("compute & networking", "data center")
    for record in records.values():
        if record.get("object_type") != "table":
            continue
        ticker = str(record.get("ticker") or "").upper()
        if ticker not in focus:
            continue
        title = str(record.get("title") or "").lower()
        if not any(term in title for term in ("revenue by reportable segments", "revenue by segment", "segment revenue")):
            continue
        for row in _ledger_rows_from_table(str(case.get("case_id") or ""), record, years):
            label = " ".join(str(row.get(key) or "") for key in ("metric_name", "row_label")).lower()
            if not any(term in label for term in target_labels):
                continue
            row["metric_family"] = "data_center_revenue"
            if ticker == "NVDA" and "compute & networking" in label:
                row["metric_name"] = "NVIDIA 计算与网络分部收入"
            else:
                row["metric_name"] = str(row.get("row_label") or row.get("metric_name") or "Data Center revenue")
            row["metric_role"] = "total_value"
            row["metric_id"] = _ledger_metric_id(
                str(case.get("case_id") or ""),
                ticker,
                row.get("fiscal_year"),
                "data_center_revenue",
                "total_value",
                period_role=row.get("period_role"),
                suffix=_slug(str(row.get("row_label") or "segment")),
            )
            if not _ledger_row_allowed(row, query_contract, None):
                continue
            key = _ledger_dedupe_key(row)
            if key in seen:
                continue
            rows.append(row)
            seen.add(key)


def _supplement_contract_metric_family_ledger(
    case: dict[str, Any],
    records: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    desired_families = _contract_required_metric_families(query_contract)
    if not focus or not desired_families:
        return
    family_ticker_periods: set[tuple[str, str, str, str, str]] = set(
        (
            str(row.get("metric_family") or ""),
            str(row.get("ticker") or "").upper(),
            str(row.get("fiscal_year") or ""),
            str(row.get("form_type") or row.get("source_type") or ""),
            str(row.get("period_role") or ""),
        )
        for row in rows
    )
    supplement_limit = int(os.environ.get("AI_LEDGER_SUPPLEMENT_SCAN_LIMIT", "400"))
    added = 0
    for record in records.values():
        ticker = str(record.get("ticker") or "").upper()
        if ticker not in focus:
            continue
        candidate_rows: list[dict[str, Any]]
        if record.get("object_type") == "metric":
            row = _ledger_row_from_metric(str(case.get("case_id") or ""), record)
            candidate_rows = [row] if row else []
        elif record.get("object_type") == "table":
            candidate_rows = _ledger_rows_from_table(str(case.get("case_id") or ""), record, years)
        else:
            continue
        for row in candidate_rows:
            if years and _int_or_none(row.get("fiscal_year")) not in years:
                continue
            family = str(row.get("metric_family") or "")
            if family not in desired_families:
                continue
            force_segment_add = _is_high_value_segment_metric(row)
            row_year = str(row.get("fiscal_year") or "")
            key_by_family_ticker_period = (
                family,
                ticker,
                row_year,
                str(row.get("form_type") or row.get("source_type") or ""),
                str(row.get("period_role") or ""),
            )
            if key_by_family_ticker_period in family_ticker_periods and not force_segment_add:
                continue
            if not _ledger_row_allowed(row, query_contract, None):
                continue
            key = _ledger_dedupe_key(row)
            if key in seen:
                continue
            rows.append(row)
            seen.add(key)
            family_ticker_periods.add(key_by_family_ticker_period)
            added += 1
            if added >= supplement_limit:
                return


def _is_high_value_segment_metric(row: dict[str, Any]) -> bool:
    family = str(row.get("metric_family") or "")
    if family not in {"cloud_revenue", "data_center_revenue", "operating_income"}:
        return False
    label = " ".join(str(row.get(key) or "") for key in ("metric_name", "row_label", "active_group", "table_title", "source_text")).lower()
    return any(
        term in label
        for term in (
            "aws",
            "azure",
            "cloud",
            "data center",
            "compute & networking",
            "intelligent cloud",
            "server products and cloud services",
        )
    )


def _supplement_banking_context_ledger(
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    if not _contract_has_banking_intent(query_contract):
        return
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    desired_families = _contract_required_metric_families(query_contract) & BANKING_METRIC_FAMILIES
    if not focus or not desired_families:
        return
    existing_family_ticker_years = {
        (
            str(row.get("metric_family") or ""),
            str(row.get("ticker") or "").upper(),
            str(row.get("fiscal_year") or ""),
        )
        for row in rows
        if str(row.get("metric_family") or "") in desired_families
    }
    added = 0
    limit = int(os.environ.get("BANKING_LEDGER_CONTEXT_SUPPLEMENT_LIMIT", "60"))
    for context_row in context_rows:
        ticker = str(context_row.get("ticker") or "").upper()
        year = _int_or_none(context_row.get("fiscal_year"))
        if ticker not in focus or (years and year not in years):
            continue
        text = str(context_row.get("text") or context_row.get("preview") or "")
        if not text:
            continue
        for row in _banking_ledger_rows_from_context(case, context_row, text, desired_families):
            row_year = str(row.get("fiscal_year") or "")
            family = str(row.get("metric_family") or "")
            key_by_family_ticker_year = (family, ticker, row_year)
            if key_by_family_ticker_year in existing_family_ticker_years:
                continue
            if not _ledger_row_allowed(row, query_contract, context_row):
                continue
            key = _ledger_dedupe_key(row)
            if key in seen:
                continue
            rows.append(row)
            seen.add(key)
            existing_family_ticker_years.add(key_by_family_ticker_year)
            added += 1
            if added >= limit:
                return


def _supplement_free_cash_flow_proxy(
    case: dict[str, Any],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    desired_families = _contract_required_metric_families(query_contract)
    if "free_cash_flow_proxy" not in desired_families:
        return
    by_key: dict[tuple[str, int, str, str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        family = str(row.get("metric_family") or "")
        if family not in {"operating_cash_flow", "capital_expenditure_proxy"}:
            continue
        year = _int_or_none(row.get("fiscal_year"))
        if year is None:
            continue
        role = str(row.get("period_role") or "")
        if role not in {"qtd", "ytd", "annual", "ttm"}:
            continue
        key = (
            str(row.get("ticker") or "").upper(),
            int(year),
            str(row.get("form_type") or row.get("source_type") or ""),
            role,
            str(row.get("period_end") or ""),
        )
        current = by_key.setdefault(key, {})
        if family not in current or _free_cash_flow_input_rank(row) > _free_cash_flow_input_rank(current[family]):
            current[family] = row
    for (ticker, year, form_type, role, period_end), family_rows in by_key.items():
        ocf = family_rows.get("operating_cash_flow")
        capex = family_rows.get("capital_expenditure_proxy")
        if not ocf or not capex:
            continue
        ocf_value = _numeric_value(ocf.get("value"))
        capex_value = _numeric_value(capex.get("value"))
        if ocf_value is None or capex_value is None:
            continue
        if capex_value > 0:
            capex_value = -capex_value
        derived = ocf_value + capex_value
        unit = str(ocf.get("unit") or capex.get("unit") or "usd_millions")
        row = {
            "metric_id": _ledger_metric_id(
                str(case.get("case_id") or ""),
                ticker,
                year,
                "free_cash_flow_proxy",
                "derived_value",
                period_role=role,
                suffix="ocf_less_capex",
            ),
            "case_id": str(case.get("case_id") or ""),
            "ticker": ticker,
            "fiscal_year": year,
            "source_fiscal_year": ocf.get("source_fiscal_year") or capex.get("source_fiscal_year"),
            "period": str(ocf.get("period") or capex.get("period") or year),
            "period_role": role,
            "source_type": ocf.get("source_type") or capex.get("source_type"),
            "form_type": form_type,
            "source_tier": ocf.get("source_tier") or capex.get("source_tier"),
            "period_end": period_end or ocf.get("period_end") or capex.get("period_end"),
            "period_type": ocf.get("period_type") or capex.get("period_type"),
            "duration_months": ocf.get("duration_months") or capex.get("duration_months"),
            "fiscal_period": ocf.get("fiscal_period") or capex.get("fiscal_period"),
            "metric_family": "free_cash_flow_proxy",
            "metric_role": "derived_value",
            "metric_name": "operating cash flow less additions to property and equipment",
            "raw_value_text": f"{derived:,.0f}",
            "display_value_zh": _display_number_value_zh(derived, unit),
            "value": derived,
            "unit": unit,
            "object_id": ocf.get("object_id") or capex.get("object_id"),
            "source_evidence_id": ocf.get("source_evidence_id") or capex.get("source_evidence_id"),
            "section": ocf.get("section") or capex.get("section"),
            "row_label": "Net cash from operations less additions to property and equipment",
            "column_label": ocf.get("column_label") or capex.get("column_label"),
            "source_text": "Derived from current Exact-Value Ledger rows; not a separately reported SEC line item.",
            "input_metric_ids": [ocf.get("metric_id"), capex.get("metric_id")],
            "input_evidence_ids": [ocf.get("source_evidence_id"), capex.get("source_evidence_id")],
        }
        if not _ledger_row_allowed(row, query_contract, None):
            continue
        key = _ledger_dedupe_key(row)
        if key in seen:
            continue
        rows.append(row)
        seen.add(key)


def _free_cash_flow_input_rank(row: dict[str, Any]) -> tuple[int, int]:
    role_score = {"ytd": 4, "annual": 3, "qtd": 2, "ttm": 1}.get(str(row.get("period_role") or ""), 0)
    value = _numeric_value(row.get("value"))
    return (role_score, int(abs(value or 0)))


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def _banking_ledger_rows_from_context(
    case: dict[str, Any],
    context_row: dict[str, Any],
    text: str,
    desired_families: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ticker = str(context_row.get("ticker") or "").upper()
    default_year = _int_or_none(context_row.get("fiscal_year"))
    case_id = str(case.get("case_id") or "")
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines()]
    recent_periods: list[int] = []
    for index, line in enumerate(lines):
        if not line:
            continue
        years_in_line: list[int] = []
        seen_years: set[int] = set()
        for match in re.finditer(r"\b20\d{2}\b", line):
            year = int(match.group(0))
            if year not in seen_years:
                years_in_line.append(year)
                seen_years.add(year)
        if len(years_in_line) >= 2:
            recent_periods = years_in_line
        value_text = line
        family = _metric_family(line)
        if family not in desired_families or family not in BANKING_METRIC_FAMILIES:
            continue
        periods = recent_periods or years_in_line or ([default_year] if default_year else [])
        value_tokens = _numeric_tokens_for_banking_line(value_text, family)
        if not value_tokens:
            value_text = " ".join(lines[index : min(len(lines), index + 2)])
            value_tokens = _numeric_tokens_for_banking_line(value_text, family)[: len(periods) or 1]
            periods = [default_year] if default_year else periods
        if not value_tokens or not periods:
            continue
        for value_index, token in enumerate(value_tokens[: len(periods)]):
            fiscal_year = periods[value_index] if value_index < len(periods) else default_year
            if fiscal_year is None:
                continue
            raw, value, unit = _normalize_banking_numeric_token(token, family, value_text)
            if unit not in VALID_UNITS or _is_bad_numeric_raw(raw, unit):
                continue
            row = _banking_context_ledger_row(
                case_id=case_id,
                ticker=ticker,
                fiscal_year=int(fiscal_year),
                family=family,
                raw=raw,
                value=value,
                unit=unit,
                source_line=line,
                context_row=context_row,
            )
            rows.append(row)
    return rows


def _numeric_tokens_for_banking_line(line: str, family: str) -> list[str]:
    tokens = []
    for match in re.finditer(r"[$(]?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:%|million|billion)?\)?", line, re.I):
        raw = match.group(0).strip()
        if _is_standalone_year_text(raw):
            continue
        tokens.append(raw)
    if family in {"net_interest_margin", "capital_ratio"}:
        return [token for token in tokens if "%" in token or re.search(r"\b\d+(?:\.\d+)?\b", token)]
    return tokens


def _normalize_banking_numeric_token(token: str, family: str, context: str) -> tuple[str, float | None, str]:
    raw = re.sub(r"\s+", " ", str(token or "").strip())
    negative = raw.startswith("(") and raw.endswith(")")
    value_text = re.sub(r"[$,%()]", "", raw, flags=re.I).strip()
    value_text = re.sub(r"\b(million|billion)\b", "", value_text, flags=re.I).strip()
    try:
        value = float(value_text.replace(",", ""))
    except ValueError:
        value = None
    if value is not None and negative:
        value = -value
    lower = f"{raw} {context}".lower()
    if "%" in raw or family in {"net_interest_margin", "capital_ratio"}:
        return raw if "%" in raw else f"{raw}%", value, "percent"
    if "billion" in lower:
        return raw, value, "usd_billions"
    return raw, value, "usd_millions"


def _banking_context_ledger_row(
    *,
    case_id: str,
    ticker: str,
    fiscal_year: int,
    family: str,
    raw: str,
    value: float | None,
    unit: str,
    source_line: str,
    context_row: dict[str, Any],
) -> dict[str, Any]:
    role = "percentage_rate" if unit == "percent" else "total_value"
    evidence_id = str(context_row.get("evidence_id") or context_row.get("source_evidence_id") or "")
    metric_name = _banking_metric_label(family)
    period_role = "annual"
    return {
        "metric_id": _ledger_metric_id(
            case_id,
            ticker,
            fiscal_year,
            family,
            role,
            period_role=period_role,
            suffix="context",
        ),
        "case_id": case_id,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "period": str(fiscal_year),
        "period_role": period_role,
        "metric_family": family,
        "metric_role": role,
        "metric_name": metric_name,
        "raw_value_text": raw,
        "display_value_zh": _display_value_zh(raw, unit),
        "value": value,
        "unit": unit,
        "object_id": str(context_row.get("object_id") or ""),
        "source_evidence_id": evidence_id,
        "section": context_row.get("section"),
        "row_label": metric_name,
        "column_label": str(fiscal_year),
        "source_text": source_line,
        "record_title": context_row.get("preview"),
        "extraction_method": "banking_context_runtime_heuristic",
    }


def _banking_metric_label(family: str) -> str:
    labels = {
        "allowance_for_credit_losses": "Allowance for credit losses",
        "asset_quality": "Asset quality",
        "capital_ratio": "Capital ratio",
        "credit_quality": "Credit quality",
        "credit_risk": "Credit risk",
        "deposits": "Deposits",
        "loans": "Loans",
        "net_charge_offs": "Net charge-offs",
        "net_interest_income": "Net interest income",
        "net_interest_margin": "Net interest margin",
        "nonperforming_assets": "Nonperforming assets",
        "nonperforming_loans": "Nonperforming loans",
        "provision_for_credit_losses": "Provision for credit losses",
        "total_assets": "Total assets",
    }
    return labels.get(family, family.replace("_", " "))


def _is_standalone_year_text(raw: str) -> bool:
    return bool(re.fullmatch(r"[\s$()]*20\d{2}[\s$()]*", str(raw or "").strip()))


def _contract_required_metric_families(query_contract: dict[str, Any]) -> set[str]:
    families = {str(item) for item in query_contract.get("metric_families") or [] if str(item)}
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families.update(str(item) for item in task.get("required_metric_families") or [] if str(item))
    rules = query_contract.get("ledger_rules") or {}
    families.update(str(item) for item in rules.get("allowed_metric_families") or [] if str(item))
    return families


def _contract_has_peer_scope(query_contract: dict[str, Any]) -> bool:
    peer_terms = (
        "peer",
        "competitor",
        "competition",
        "competitive",
        "rival",
        "竞争",
        "竞争对手",
        "竞品",
        "同行",
        "同行业",
        "对手",
    )
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        if task.get("peer_tickers"):
            return True
        task_text = " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question")).lower()
        if _contains_any(task_text, peer_terms):
            return True
    return False


def _contract_has_banking_intent(query_contract: dict[str, Any]) -> bool:
    families = _contract_required_metric_families(query_contract)
    if families & BANKING_METRIC_FAMILIES:
        return True
    text_parts = [
        query_contract.get("task_type"),
        " ".join(str(item) for item in query_contract.get("facets") or []),
        " ".join(str(item) for item in query_contract.get("analysis_axes") or []),
        " ".join(str(item) for item in query_contract.get("metric_queries") or []),
        " ".join(str(item) for item in query_contract.get("qualitative_queries") or []),
    ]
    for task in query_contract.get("decomposed_tasks") or []:
        if isinstance(task, dict):
            text_parts.append(str(task.get("question_zh") or task.get("question") or ""))
    return _has_banking_intent(" ".join(str(part or "") for part in text_parts), query_contract.get("focus_tickers") or [])


def _build_case(
    prompt: str,
    tickers: list[str],
    years: list[int],
    run_id: str,
    query_contract: dict[str, Any],
) -> dict[str, Any]:
    query_contract = dict(query_contract)
    query_task_type = str(query_contract.get("task_type") or "")
    filing_types = [str(item).upper() for item in (query_contract.get("filing_types") or ["10-K"])]
    source_tiers = [str(item) for item in (query_contract.get("source_tiers") or ["primary_sec_filing"]) if str(item)]
    source_policy = str(query_contract.get("source_policy") or "SEC_ONLY")
    is_ai_industry = query_task_type == "ai_industry_financial_trend"
    is_peer = not is_ai_industry and _contract_has_peer_scope(query_contract)
    query_contract["semantic_gate"] = _semantic_gate_policy_for_prompt(prompt, query_contract, is_peer)
    failure_types = ["source_policy_violation", "proxy_as_direct_metric"]
    if is_peer:
        failure_types.append("entity_bleed_between_peers")
    if re.search(r"margin|profit|毛利|利润", prompt, re.I):
        failure_types.append("non_comparable_metric_comparison")
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "interactive_sec_agent_v0",
        "case_id": f"INTERACTIVE_{run_id}",
        "origin": "interactive_free_prompt",
        "case_group": "interactive",
        "level": "interactive",
        "companies": tickers,
        "years": years,
        "filing_types": filing_types,
        "task_type": query_task_type if is_ai_industry else ("peer_comparison_interactive" if is_peer else "single_or_multi_company_interactive"),
        "prompt": prompt,
        "allowed_sources": ["SEC"],
        "source_policy": source_policy,
        "source_tiers": source_tiers,
        "source_coverage_gaps": query_contract.get("source_coverage_gaps") or [],
        "query_contract": query_contract,
        "semantic_gate": query_contract.get("semantic_gate") or {},
        "prompt_context_max_rows": 64 if is_ai_industry else 32,
        "prompt_context_excerpt_chars": 1800 if is_ai_industry else 2200,
        "required_caveats": _required_caveat_specs(query_contract.get("required_caveats") or []),
        "evaluation_modes": ["pipeline_context"],
        "expected_sections": list(DEFAULT_SECTIONS),
        "gold_points": [
            "Answer only from retrieved SEC filing evidence.",
            "All precise numeric values must come from the runtime Exact-Value Ledger.",
            "State not_found when SEC context or ledger does not support a requested exact metric.",
            "Caveat segment-definition, proxy-metric, and source-boundary limitations.",
            *_source_policy_gold_points(source_policy),
        ],
        "numeric_checks": _generic_numeric_checks(prompt, tickers, years, query_contract),
        "hard_gates": [
            "query_contract",
            "exact_value_ledger",
            "citation_validator",
            "judgment_plan",
            "source_policy_gate",
        ],
        "hallucination_traps": [
            "Do not use non-SEC sources.",
            "Do not infer exact values or market share when the ledger does not provide them.",
            "Do not attribute another company's segment or product metric to the scoped companies.",
            *_source_policy_hallucination_traps(source_policy),
        ],
        "failure_types": failure_types,
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
    }


def _source_policy_gold_points(source_policy: str) -> list[str]:
    if source_policy == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS":
        return [
            "Label 8-K earnings-release evidence as company-authored unaudited material.",
            "Do not use 8-K earnings-release values as audited Exact-Value Ledger facts.",
        ]
    if source_policy == "SEC_PRIMARY_MIXED_RECENT":
        return ["Label 10-Q evidence as unaudited quarterly material when relevant."]
    return []


def _source_policy_hallucination_traps(source_policy: str) -> list[str]:
    if source_policy == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS":
        return [
            "Do not treat company-authored 8-K earnings-release evidence as audited 10-K/10-Q financial statement evidence."
        ]
    return []


def _semantic_gate_policy_for_prompt(
    prompt: str,
    query_contract: dict[str, Any],
    is_peer: bool,
) -> dict[str, Any]:
    gate = dict(query_contract.get("semantic_gate") or {})
    if gate.get("company_coverage"):
        return gate
    prompt_text = str(prompt or "")
    focus = [str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)]
    asks_all = re.search(r"\b(all|each|every)\b|全部|所有|每家|逐一|全量|完整覆盖", prompt_text, re.I)
    asks_direct_compare = re.search(r"compare|comparison|versus|\bvs\b|对比|比较|相比", prompt_text, re.I)
    asks_competitor_discovery = re.search(r"competitor|peer|竞争对手|同行|同行业|主要对手|对手是谁", prompt_text, re.I)
    if asks_all:
        gate["company_coverage"] = "all_companies"
        gate["require_company_coverage"] = True
    elif asks_competitor_discovery and len(focus) > 2:
        gate["company_coverage"] = "selected_companies"
        gate["require_company_coverage"] = False
    elif is_peer and asks_direct_compare:
        gate["company_coverage"] = "all_focus"
        gate["require_company_coverage"] = True
    else:
        gate["company_coverage"] = "selected_companies"
        gate["require_company_coverage"] = False
    return gate


def _required_caveat_specs(caveats: list[Any]) -> list[dict[str, Any]]:
    specs = []
    for item in caveats:
        text = str(item or "").strip()
        if not text:
            continue
        specs.append(
            {
                "id": _slug(text),
                "description": text,
                "where": "caveats",
                "required": True,
                "all_of_any": [[text]],
            }
        )
    return specs


def _project_inventory(args: argparse.Namespace, manifest_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_gap_rows = _read_jsonl(_repo_path(args.source_gap_path)) if args.source_gap_path else []
    return build_project_inventory(
        manifest_rows,
        manifest_path=args.manifest_path,
        bm25_index_dir=args.bm25_index_dir,
        object_bm25_index_dir=args.object_bm25_index_dir,
        bge_model=args.bge_model,
        sections=DEFAULT_SECTIONS,
        source_gap_rows=source_gap_rows,
    )


def _print_project_inventory(inventory: dict[str, Any], tickers: list[str], years: list[int]) -> None:
    forms = inventory.get("form_types") or {}
    categories = inventory.get("categories") or []
    selected = {ticker.upper() for ticker in tickers}
    selected_categories = [
        str(item.get("category") or "")
        for item in categories
        if any(str(ticker).upper() in selected for ticker in item.get("tickers") or [])
    ]
    category_text = ",".join(selected_categories[:6]) + (f",...(+{len(selected_categories)-6})" if len(selected_categories) > 6 else "")
    print(
        "[inventory] "
        f"digest={inventory.get('inventory_digest')} "
        f"companies={len(tickers)}/{inventory.get('company_count')} "
        f"years={','.join(str(year) for year in years)} "
        f"forms={','.join(sorted(forms)) or '<none>'}"
    )
    if category_text:
        print(f"[inventory] categories={category_text}")


def _build_query_contract(
    args: argparse.Namespace,
    prompt: str,
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
) -> dict[str, Any]:
    fallback = _build_heuristic_query_contract(prompt, tickers, years, project_inventory)
    fallback = _repair_query_contract_from_prompt(fallback, prompt, tickers, years, project_inventory)
    if args.query_planner != "llm":
        fallback["planner_backend"] = "heuristic"
        fallback["planner_status"] = "ok"
        return _validate_query_contract(fallback, tickers, years, project_inventory)
    raw = ""
    planner_gateway_result: dict[str, Any] = {}
    planner_trace: dict[str, Any] = {
        "schema_version": "sec_agent_query_planner_trace_v0.1",
        "planner_backend": f"llm:{args.llm_backend}",
        "planner_model": args.model,
        "user_query": prompt,
        "selected_tickers": tickers,
        "selected_years": years,
        "project_inventory_digest": project_inventory.get("inventory_digest"),
        "status": "started",
    }
    try:
        _ensure_llm_ready(args)
        raw, planner_gateway_result = _ask_query_contract_planner(args, prompt, tickers, years, project_inventory, fallback)
        planner_trace.update(
            {
                "status": "raw_returned",
                "raw_output": raw,
                "raw_output_chars": len(raw),
                "llm_gateway": _gateway_debug(planner_gateway_result),
            }
        )
        parsed = _extract_planner_json_object(raw)
        if not parsed:
            planner_trace["status"] = "parse_failed"
            planner_trace["parse_error"] = "planner_returned_no_contract_json_object"
            raise ValueError("planner_returned_no_json_object")
        planner_trace["status"] = "parsed"
        planner_trace["parsed_contract"] = parsed
        contract = _normalize_llm_query_contract(parsed, fallback, tickers, years, project_inventory)
        contract = _repair_query_contract_from_prompt(contract, prompt, tickers, years, project_inventory)
        contract["planner_backend"] = f"llm:{args.llm_backend}"
        contract["planner_status"] = "ok"
        contract["planner_model"] = args.model
        contract["planner_raw_chars"] = len(raw)
        contract["planner_gateway"] = _gateway_debug(planner_gateway_result)
        validated = _validate_query_contract(contract, tickers, years, project_inventory)
        planner_trace["validated_contract_summary"] = _planner_contract_summary(validated)
        validated["_planner_trace"] = planner_trace
        return validated
    except Exception as exc:
        if not args.quiet:
            print(f"[plan] llm planner failed; using heuristic contract: {type(exc).__name__}: {exc}")
        fallback["planner_backend"] = f"llm:{args.llm_backend}"
        fallback["planner_status"] = "fallback_after_error"
        fallback["planner_model"] = args.model
        fallback["planner_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        fallback = _repair_query_contract_from_prompt(fallback, prompt, tickers, years, project_inventory)
        planner_trace.update(
            {
                "status": "fallback_after_error",
                "error": fallback["planner_error"],
                "raw_output": raw,
                "raw_output_chars": len(raw),
                "llm_gateway": _gateway_debug(planner_gateway_result) if planner_gateway_result else {},
            }
        )
        validated = _validate_query_contract(fallback, tickers, years, project_inventory)
        planner_trace["validated_contract_summary"] = _planner_contract_summary(validated)
        validated["_planner_trace"] = planner_trace
        return validated


def _detach_planner_trace(contract: dict[str, Any]) -> dict[str, Any] | None:
    trace = contract.pop("_planner_trace", None)
    return trace if isinstance(trace, dict) else None


def _planner_contract_summary(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": contract.get("task_type"),
        "focus_tickers": contract.get("focus_tickers") or [],
        "task_count": len([task for task in contract.get("decomposed_tasks") or [] if isinstance(task, dict)]),
        "task_ids": [str(task.get("task_id") or "") for task in contract.get("decomposed_tasks") or [] if isinstance(task, dict)],
        "peer_tickers": sorted(
            {
                str(ticker).upper()
                for task in contract.get("decomposed_tasks") or []
                if isinstance(task, dict)
                for ticker in task.get("peer_tickers") or []
                if str(ticker)
            }
        ),
        "validation_status": ((contract.get("query_contract_validation") or {}).get("status")),
    }


def _extract_planner_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    first_dict: dict[str, Any] | None = None
    for idx, char in enumerate(str(text or "")):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(str(text)[idx:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        if first_dict is None:
            first_dict = value
        if _looks_like_query_contract_json(value):
            return value
    return first_dict if first_dict and _looks_like_query_contract_json(first_dict, relaxed=True) else None


def _looks_like_query_contract_json(value: dict[str, Any], *, relaxed: bool = False) -> bool:
    strict_keys = {"task_type", "focus_tickers", "years", "decomposed_tasks"}
    if strict_keys.issubset(value):
        return True
    relaxed_keys = {"task_type", "metric_families", "facets", "rewritten_question_zh", "decomposed_tasks"}
    threshold = 2 if relaxed else 3
    return len(relaxed_keys & set(value)) >= threshold


def _validate_query_contract(
    contract: dict[str, Any],
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
) -> dict[str, Any]:
    result = validate_query_contract(
        contract,
        selected_tickers=tickers,
        selected_years=years,
        project_inventory=project_inventory,
        sections=DEFAULT_SECTIONS,
    )
    clean = result["contract"]
    status = str((result.get("report") or {}).get("status") or "")
    if status != "pass":
        raise RuntimeError(f"Query Contract validation failed: {json.dumps(result.get('report'), ensure_ascii=False)[:600]}")
    return clean


def _build_heuristic_query_contract(
    prompt: str,
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
) -> dict[str, Any]:
    prompt_text = str(prompt or "")
    lowered = prompt_text.lower()
    has_peer_intent = _has_peer_intent(prompt_text)
    is_ai = bool(
        re.search(r"(?<![a-z])ai(?![a-z])|人工智能|算力|大模型|数据中心|gpu|accelerator|hyperscale|cloud|云|芯片", lowered, re.I)
    )
    if is_ai:
        available_for_scope = {(ticker, year) for ticker in tickers for year in years}
        mentioned = _infer_tickers(prompt_text, available_for_scope)
        focus = [ticker for ticker in mentioned if ticker in set(tickers)]
        if not focus:
            focus = [ticker for ticker in AI_FOCUS_TICKERS if ticker in set(tickers)]
        if not focus:
            focus = tickers
        peer_tickers = _infer_peer_tickers_for_prompt(prompt_text, focus, tickers, project_inventory)
        decomposed_tasks = [
            {
                "task_id": "ai_demand_monetization",
                "question_zh": "AI需求是否反映在云、数据中心和半导体相关收入增长中？",
                "priority": "primary",
                "required_metric_families": ["data_center_revenue", "cloud_revenue", "semiconductor_systems", "semiconductor_solutions"],
                "required_tickers": focus,
            },
            {
                "task_id": "investment_and_cash_capacity",
                "question_zh": "AI基础设施投入是否改变资本开支、研发支出和现金流压力？",
                "priority": "primary",
                "required_metric_families": ["capital_expenditure_proxy", "research_and_development", "operating_cash_flow"],
                "required_tickers": focus,
            },
            {
                "task_id": "profitability_and_risk",
                "question_zh": "AI扩张对利润率、供应链和风险披露有什么影响？",
                "priority": "supporting",
                "required_metric_families": ["gross_margin", "operating_income"],
                "required_tickers": focus,
            },
        ]
        if has_peer_intent and peer_tickers:
            decomposed_tasks.append(
                {
                    "task_id": "peer_competition_mapping",
                    "question_zh": "识别与核心公司相关的直接竞争、替代和供应链/客户关系，并用可取得的 SEC 指标说明竞争读通。",
                    "priority": "supporting",
                    "required_metric_families": ["revenue", "gross_margin", "operating_income"],
                    "required_tickers": focus[:1],
                    "peer_tickers": peer_tickers,
                }
            )
        filing_types = _selected_form_types(project_inventory, tickers, years)
        return {
            "schema_version": "interactive_query_contract_v0.2",
            "task_type": "ai_industry_financial_trend",
            "source_policy": "SEC_ONLY",
            "search_scope_tickers": tickers,
            "focus_tickers": focus,
            "years": years,
            "filing_types": filing_types,
            "source_tiers": ["primary_sec_filing"],
            "scope": _contract_scope(tickers, focus, years, filing_types),
            "analysis_axes": ["growth", "profitability", "cash_flow", "capital_intensity", "segment_mix", "risk", "comparability"],
            "decomposed_tasks": decomposed_tasks,
            "facets": [
                "ai_infrastructure_demand",
                "data_center_and_cloud_monetization",
                "semiconductor_supply_chain",
                "capex_and_cash_flow_capacity",
                "profitability_and_margin_pressure",
                "risk_factors",
            ],
            "metric_families": [
                "data_center_revenue",
                "cloud_revenue",
                "semiconductor_systems",
                "semiconductor_solutions",
                "infrastructure_software",
                "operating_income",
                "operating_cash_flow",
                "capital_expenditure_proxy",
                "gross_margin",
                "research_and_development",
                "advertising_revenue",
            ],
            "metric_queries": [
                "AI data center revenue GPU accelerator revenue cloud AI infrastructure revenue",
                "capital expenditures purchases of property and equipment AI infrastructure data centers operating cash flow",
                "operating income gross margin profitability AI infrastructure cloud data center segment",
                "semiconductor systems semiconductor solutions infrastructure software AI accelerator revenue",
                "research and development AI initiatives infrastructure costs",
            ],
            "qualitative_queries": [
                "AI infrastructure demand data center GPU accelerator cloud customer demand",
                "supply constraints customer concentration export controls risk factors AI infrastructure",
            ],
            "forbidden_claims": [
                "Do not claim geopolitical risk unless retrieved SEC risk-factor evidence supports it.",
                "Do not compare non-comparable segment labels as the same metric.",
                "Do not use market prices, news, earnings calls, or macro data outside the project inventory.",
            ],
            "ledger_rules": {
                "allowed_metric_families": sorted(AI_METRIC_FAMILIES),
                "drop_generic_percentage_of_revenue": True,
                "drop_geographic_revenue_breakdowns": True,
                "drop_dates_as_values": True,
                "prefer_focus_tickers": True,
            },
            "semantic_gate": {
                "company_coverage": "focus_tickers_for_peer_only",
                "decomposed_task_coverage": "diagnostic",
                "strict_decomposed_task_coverage": False,
            },
            "required_caveats": [
                "SEC-only evidence boundary.",
                "AI exposure differs by company; segment labels are not always directly comparable.",
                "Precise values must come from runtime Exact-Value Ledger only.",
            ],
            "project_inventory": inventory_brief(project_inventory),
            "project_inventory_digest": project_inventory.get("inventory_digest"),
        }
    filing_types = _selected_form_types(project_inventory, tickers, years)
    available_for_scope = {(ticker, year) for ticker in tickers for year in years}
    mentioned = _infer_tickers(prompt_text, available_for_scope)
    focus = [ticker for ticker in mentioned if ticker in set(tickers)] or tickers
    if _has_banking_intent(prompt_text, focus):
        banking_families = [
            "net_interest_income",
            "net_interest_margin",
            "provision_for_credit_losses",
            "net_charge_offs",
            "allowance_for_credit_losses",
            "credit_quality",
            "credit_risk",
            "asset_quality",
            "nonperforming_assets",
            "nonperforming_loans",
            "deposits",
            "loans",
            "capital_ratio",
            "total_assets",
        ]
        return {
            "schema_version": "interactive_query_contract_v0.2",
            "task_type": "general_sec_financial_question",
            "source_policy": "SEC_ONLY",
            "search_scope_tickers": tickers,
            "focus_tickers": focus,
            "years": years,
            "filing_types": filing_types,
            "source_tiers": ["primary_sec_filing"],
            "scope": _contract_scope(tickers, focus, years, filing_types),
            "analysis_axes": ["growth", "profitability", "funding_mix", "asset_quality", "credit_risk", "capital", "comparability"],
            "decomposed_tasks": [
                {
                    "task_id": "bank_net_interest_income_driver",
                    "question_zh": "提取银行净利息收入、净息差、存款和贷款规模变化，判断利率和负债成本对盈利质量的影响。",
                    "priority": "primary",
                    "required_metric_families": ["net_interest_income", "net_interest_margin", "deposits", "loans"],
                    "required_tickers": focus[:3],
                },
                {
                    "task_id": "bank_credit_quality",
                    "question_zh": "提取信用损失拨备、净核销、信用损失准备和不良资产/贷款指标，判断信用风险是否恶化或缓和。",
                    "priority": "primary",
                    "required_metric_families": [
                        "provision_for_credit_losses",
                        "net_charge_offs",
                        "allowance_for_credit_losses",
                        "nonperforming_assets",
                        "nonperforming_loans",
                    ],
                    "required_tickers": focus[:3],
                },
                {
                    "task_id": "bank_balance_sheet_and_capital",
                    "question_zh": "结合总资产、存贷款和资本充足率披露，说明资产负债表扩张与资本约束。",
                    "priority": "supporting",
                    "required_metric_families": ["total_assets", "deposits", "loans", "capital_ratio"],
                    "required_tickers": focus[:3],
                },
            ],
            "facets": ["net_interest_income", "net_interest_margin", "credit_quality", "asset_quality", "funding_liquidity", "capital_ratio"],
            "metric_families": banking_families,
            "metric_queries": [
                "net interest income net interest margin taxable-equivalent net interest income",
                "provision for credit losses allowance for credit losses net charge-offs nonperforming assets nonperforming loans",
                "average deposits total deposits average loans total loans CET1 common equity tier 1 capital ratio total assets",
            ],
            "qualitative_queries": [
                "interest rate risk deposit pricing loan demand net interest margin",
                "credit risk allowance for credit losses net charge-offs delinquencies nonperforming assets",
                "liquidity capital regulatory capital CET1 risk-weighted assets",
            ],
            "ledger_rules": {
                "allowed_metric_families": sorted(BANKING_METRIC_FAMILIES),
                "drop_dates_as_values": True,
                "drop_human_capital_tables": True,
                "prefer_focus_tickers": True,
            },
            "forbidden_claims": [
                "Do not use market prices, news, earnings calls, or macro data outside the project inventory.",
                "Do not infer bank asset quality or net interest margin without retrieved SEC evidence.",
                "Do not use employee-diversity, human-capital, tax, or generic investment fair-value tables as bank quality metrics.",
            ],
            "required_caveats": [
                "SEC-only evidence boundary.",
                "Precise bank metric values must come from runtime Exact-Value Ledger only.",
                "Bank segment labels, taxable-equivalent measures, and credit metrics are not always comparable across periods without source context.",
            ],
            "project_inventory": inventory_brief(project_inventory),
            "project_inventory_digest": project_inventory.get("inventory_digest"),
        }
    filing_types = _selected_form_types(project_inventory, tickers, years)
    available_for_scope = {(ticker, year) for ticker in tickers for year in years}
    mentioned = _infer_tickers(prompt_text, available_for_scope)
    focus = [ticker for ticker in mentioned if ticker in set(tickers)] or tickers
    peer_tickers = _infer_peer_tickers_for_prompt(prompt_text, focus, tickers, project_inventory)
    task_type = "company_comparison" if has_peer_intent and peer_tickers else "general_sec_financial_question"
    decomposed_tasks = [
        {
            "task_id": "focus_growth_driver",
            "question_zh": "围绕用户问题提取核心公司的财务趋势和增长驱动。",
            "priority": "primary",
            "required_metric_families": ["revenue", "operating_income", "operating_cash_flow", "gross_margin"],
            "required_tickers": focus[:3],
        }
    ]
    if has_peer_intent:
        decomposed_tasks.append(
            {
                "task_id": "peer_competition_mapping",
                "question_zh": "识别用户问题中的同行、竞争对手或替代关系，并在证据允许时拉入可比财务指标。",
                "priority": "supporting",
                "required_metric_families": ["revenue", "gross_margin", "operating_income"],
                "required_tickers": focus[:1],
                "peer_tickers": peer_tickers,
            }
        )
    return {
        "schema_version": "interactive_query_contract_v0.2",
        "task_type": task_type,
        "source_policy": "SEC_ONLY",
        "search_scope_tickers": tickers,
        "focus_tickers": focus,
        "years": years,
        "filing_types": filing_types,
        "scope": _contract_scope(tickers, focus, years, filing_types),
        "analysis_axes": ["growth", "profitability", "cash_flow", "capital_intensity", "risk", "comparability"],
        "decomposed_tasks": decomposed_tasks,
        "facets": ["revenue", "profitability", "cash_flow", "risk_factors"],
        "metric_families": ["revenue", "operating_income", "operating_cash_flow", "gross_margin", "capital_expenditure_proxy"],
        "metric_queries": [
            prompt_text,
            "revenue net sales operating income gross margin segment revenue",
            "capital expenditures purchases of property and equipment operating cash flow free cash flow",
        ],
        "qualitative_queries": ["risk factors business trends management discussion"],
        "ledger_rules": {
            "allowed_metric_families": [],
            "drop_dates_as_values": True,
        },
        "forbidden_claims": [
            "Do not use market prices, news, earnings calls, or macro data outside the project inventory.",
            "Do not make a risk or industry claim without retrieved SEC evidence.",
        ],
        "required_caveats": [
            "SEC-only evidence boundary.",
            "Precise values must come from runtime Exact-Value Ledger only.",
        ],
        "project_inventory": inventory_brief(project_inventory),
        "project_inventory_digest": project_inventory.get("inventory_digest"),
    }


def _ask_query_contract_planner(
    args: argparse.Namespace,
    prompt: str,
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
    fallback: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    system_content = _query_planner_system_prompt(project_inventory, tickers, years)
    user_content = (
        "用户原始问题：\n"
        f"{prompt}\n\n"
        "已解析的候选 scope：\n"
        f"- tickers: {', '.join(tickers)}\n"
        f"- years: {', '.join(str(year) for year in years)}\n\n"
        "当前 heuristic seed，仅供参考；你可以改写 task/facets/focus，但不能越过 PROJECT SOURCE INVENTORY：\n"
        f"{json.dumps(_planner_seed_for_prompt(fallback), ensure_ascii=False, indent=2)}\n\n"
        "请只返回一个 JSON object，不要 markdown。"
    )
    return _chat_completion_content(
        args,
        [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        max_tokens=args.planner_max_tokens,
        temperature=0.0,
        timeout_s=args.planner_timeout_s,
        role="planner",
        trace_tags={
            "inventory_digest": str(project_inventory.get("inventory_digest") or ""),
            "selected_ticker_count": len(tickers),
            "selected_years": ",".join(str(year) for year in years),
        },
    )


def _query_planner_system_prompt(project_inventory: dict[str, Any], tickers: list[str], years: list[int]) -> str:
    inv = inventory_prompt(project_inventory, selected_tickers=tickers, selected_years=years)
    ontology = ", ".join(METRIC_FAMILY_ONTOLOGY)
    task_types = ", ".join(sorted(QUERY_TASK_TYPES))
    runtime_policy = _runtime_source_policy() or "SEC_ONLY_10K"
    return (
        "你是 FIN Insight Agent 的 Query Contract planner。你的任务不是回答用户问题，而是把自由问题改写成后续 SEC 检索、"
        "Exact-Value Ledger、Judgment Plan 和 synthesis 都能执行的任务协议。\n\n"
        f"{inv}\n\n"
        f"ACTIVE SOURCE POLICY: {runtime_policy}\n"
        "CONTRACT RULES\n"
        f"- task_type 必须属于：{task_types}\n"
        f"- required_metric_families / metric_families 只能优先使用这些 ontology 名称：{ontology}\n"
        "- focus_tickers 必须来自 SELECTED COMPANY FILINGS；如果用户问全局趋势，可以选择一个 evidence-relevant 子集，但 search_scope 仍由系统保留。\n"
        "- years 必须来自候选 scope；不要规划项目没有的年份。\n"
        "- filing_types 必须来自 SELECTED COMPANY FILINGS；如 ACTIVE SOURCE POLICY 是 SEC_PRIMARY_MIXED_RECENT 且 10-Q 可用，必须保留 10-Q 及其未经审计季报边界；如 ACTIVE SOURCE POLICY 是 SEC_PRIMARY_MIXED_WITH_8K_EARNINGS 且 8-K 可用，必须保留 8-K 但标注公司未审计管理层口径。\n"
        "- source_tiers 只能来自 PROJECT SOURCE INVENTORY；10-K/10-Q 使用 primary_sec_filing，8-K earnings release 使用 company_authored_unaudited_sec_filing。\n"
        "- decomposed_tasks 要服务于用户问题，避免机械套用行业模板；宽问题至少拆成 2 个任务。\n"
        "- 如果用户问银行盈利质量、净息差、存贷款或信用风险，优先使用银行指标族："
        "net_interest_income、net_interest_margin、provision_for_credit_losses、net_charge_offs、"
        "allowance_for_credit_losses、nonperforming_assets、nonperforming_loans、deposits、loans、capital_ratio、total_assets。\n"
        "- 如果用户问题包含同行、竞争对手、peer、替代、自研、对比等意图，必须新增 peer_competition_mapping 或 peer_comparison 任务；"
        "该任务必须写 required_tickers 和 peer_tickers，peer_tickers 只能来自 PROJECT SOURCE INVENTORY。\n"
        "- forbidden_claims 必须覆盖所有超出当前材料的常见风险，例如 market price/news/macro/earnings-call/未列出的 filing type。\n"
        "- 如果用户问到项目资料没有的来源，写入 required_caveats 或 evidence_gaps，不要把它当成已有证据。\n"
        "- 不能输出最终答案、精确数字、metric_id、evidence_id 或 SEC 原文长引用。\n\n"
        "RETURN JSON SCHEMA\n"
        "{\n"
        '  "schema_version": "interactive_query_contract_planner_v0.1",\n'
        '  "rewritten_question_zh": "...",\n'
        '  "task_type": "...",\n'
        '  "focus_tickers": ["..."],\n'
        '  "years": [2023],\n'
        '  "filing_types": ["10-K", "10-Q", "8-K"],\n'
        '  "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],\n'
        '  "analysis_axes": ["growth", "profitability"],\n'
        '  "facets": ["..."],\n'
        '  "metric_families": ["..."],\n'
        '  "metric_queries": ["..."],\n'
        '  "qualitative_queries": ["..."],\n'
        '  "decomposed_tasks": [{"task_id": "...", "question_zh": "...", "priority": "primary|supporting|caveat", "required_tickers": ["..."], "peer_tickers": ["..."], "required_metric_families": ["..."]}],\n'
        '  "required_caveats": ["..."],\n'
        '  "forbidden_claims": ["..."],\n'
        '  "evidence_gaps": [{"task_id": "...", "gap": "..."}],\n'
        '  "planner_confidence": "high|medium|low"\n'
        "}"
    )


def _normalize_llm_query_contract(
    planned: dict[str, Any],
    fallback: dict[str, Any],
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
) -> dict[str, Any]:
    clean = dict(fallback)
    clean["schema_version"] = "interactive_query_contract_v0.2"
    task_type = str(planned.get("task_type") or fallback.get("task_type") or "").strip()
    if task_type not in QUERY_TASK_TYPES:
        task_type = str(fallback.get("task_type") or "general_sec_financial_question")
    if fallback.get("task_type") == "ai_industry_financial_trend" and task_type in {"open_analysis", "general_sec_financial_question"}:
        task_type = "ai_industry_financial_trend"
    focus = _clamp_tickers(planned.get("focus_tickers"), tickers) or list(fallback.get("focus_tickers") or tickers)
    filing_types = _clamp_form_types(
        planned.get("filing_types") or planned.get("source_types"),
        _selected_form_types(project_inventory, tickers, years),
    ) or list(fallback.get("filing_types") or ["10-K"])
    allowed_source_tiers = _selected_source_tiers(project_inventory, tickers, years, filing_types)
    source_tiers = _merge_source_tiers(
        _clamp_source_tiers(planned.get("source_tiers") or (planned.get("scope") or {}).get("source_tiers"), allowed_source_tiers)
        or _clamp_source_tiers(fallback.get("source_tiers") or (fallback.get("scope") or {}).get("source_tiers"), allowed_source_tiers)
        or [],
        _source_policy_source_tiers(filing_types, allowed_source_tiers),
    )
    clean.update(
        {
            "task_type": task_type,
            "rewritten_question_zh": _short_text(planned.get("rewritten_question_zh"), 500),
            "search_scope_tickers": tickers,
            "focus_tickers": focus,
            "years": years,
            "filing_types": filing_types,
            "source_tiers": source_tiers,
            "source_policy": _source_policy_for_scope(filing_types, source_tiers),
            "scope": _contract_scope(tickers, focus, years, filing_types, source_tiers),
            "analysis_axes": _string_list(planned.get("analysis_axes"), max_items=10) or clean.get("analysis_axes") or [],
            "facets": _string_list(planned.get("facets"), max_items=10) or clean.get("facets") or [],
            "metric_families": _metric_family_list(planned.get("metric_families")) or clean.get("metric_families") or [],
            "metric_queries": _string_list(planned.get("metric_queries"), max_items=8, max_chars=180) or clean.get("metric_queries") or [],
            "qualitative_queries": _string_list(planned.get("qualitative_queries"), max_items=8, max_chars=180) or clean.get("qualitative_queries") or [],
            "required_caveats": _string_list(planned.get("required_caveats"), max_items=10, max_chars=240)
            or clean.get("required_caveats")
            or [],
            "forbidden_claims": _string_list(planned.get("forbidden_claims"), max_items=10, max_chars=240)
            or clean.get("forbidden_claims")
            or [],
            "evidence_gaps": _normalize_evidence_gaps(planned.get("evidence_gaps")),
            "planner_confidence": _planner_confidence(planned.get("planner_confidence")),
            "project_inventory": inventory_brief(project_inventory),
            "project_inventory_digest": project_inventory.get("inventory_digest"),
        }
    )
    clean["decomposed_tasks"] = _normalize_decomposed_tasks(planned.get("decomposed_tasks"), clean)
    if not clean.get("decomposed_tasks"):
        clean["decomposed_tasks"] = fallback.get("decomposed_tasks") or []
    if task_type == "ai_industry_financial_trend":
        clean.setdefault("ledger_rules", {})
        task_families = {
            str(family)
            for task in clean.get("decomposed_tasks") or []
            if isinstance(task, dict)
            for family in task.get("required_metric_families") or []
        }
        clean["ledger_rules"]["allowed_metric_families"] = sorted(
            set(AI_METRIC_FAMILIES) | set(clean.get("metric_families") or []) | task_families
        )
        clean["ledger_rules"]["prefer_focus_tickers"] = True
        clean["semantic_gate"] = {
            "company_coverage": "focus_tickers_for_peer_only",
            "decomposed_task_coverage": "diagnostic",
            "strict_decomposed_task_coverage": False,
        }
    elif _contract_has_banking_intent(clean):
        clean.setdefault("ledger_rules", {})
        task_families = {
            str(family)
            for task in clean.get("decomposed_tasks") or []
            if isinstance(task, dict)
            for family in task.get("required_metric_families") or []
        }
        clean["ledger_rules"]["allowed_metric_families"] = sorted(
            set(BANKING_METRIC_FAMILIES) | set(clean.get("metric_families") or []) | task_families
        )
        clean["ledger_rules"]["drop_human_capital_tables"] = True
        clean["ledger_rules"]["prefer_focus_tickers"] = True
    return clean


def _repair_query_contract_from_prompt(
    contract: dict[str, Any],
    prompt: str,
    tickers: list[str],
    years: list[int],
    project_inventory: dict[str, Any],
) -> dict[str, Any]:
    repaired = dict(contract)
    prompt_text = str(prompt or "")
    lowered = prompt_text.lower()
    available_for_scope = {(ticker, year) for ticker in tickers for year in years}
    mentioned = _infer_tickers(prompt_text, available_for_scope)
    focus = _clamp_tickers(repaired.get("focus_tickers"), tickers) or [ticker for ticker in mentioned if ticker in set(tickers)]
    if not focus:
        focus = list(repaired.get("focus_tickers") or tickers)
    focus = _clamp_tickers(focus, tickers) or tickers
    has_peer_intent = _has_peer_intent(prompt_text)
    comparative_intent = has_peer_intent or (
        len(mentioned) >= 2
        and _contains_any(
            lowered,
            ("和", "与", "哪个", "谁", "更", *COMPARISON_INTENT_TERMS),
        )
    )
    broad_ai_prompt = _is_broad_ai_scope_prompt(prompt_text, mentioned)
    offscope_terms = _offscope_gap_terms(prompt_text, years=years)
    risk_dominant_prompt = _contains_any(lowered, ("风险", "risk", "出口管制", "export control", "客户集中", "customer concentration", "供应风险"))

    if broad_ai_prompt:
        repaired["task_type"] = "ai_industry_financial_trend"
    elif not mentioned and _contains_any(lowered, ("30家公司", "三十家公司", "这些公司", "哪些公司", "全公司", "universe")):
        repaired["task_type"] = "open_analysis"
    elif risk_dominant_prompt and not comparative_intent:
        repaired["task_type"] = "risk_summary"
    elif comparative_intent and len(mentioned) >= 2 and not offscope_terms:
        repaired["task_type"] = "company_comparison"
    elif offscope_terms and repaired.get("task_type") == "company_comparison":
        repaired["task_type"] = "risk_summary" if _contains_any(lowered, ("风险", "risk", "rate", "利率", "credit", "信用")) else "general_sec_financial_question"
    elif len(mentioned) <= 1 and not has_peer_intent:
        if repaired.get("task_type") == "company_comparison":
            repaired["task_type"] = "general_sec_financial_question"
        if repaired.get("task_type") == "ai_industry_financial_trend" and not broad_ai_prompt:
            repaired["task_type"] = "general_sec_financial_question"
    repaired["focus_tickers"] = focus
    repaired["search_scope_tickers"] = tickers
    repaired["years"] = years
    allowed_filing_types = _selected_form_types(project_inventory, tickers, years)
    filing_types = _clamp_form_types(repaired.get("filing_types"), allowed_filing_types)
    repaired["filing_types"] = _source_policy_filing_types(filing_types or allowed_filing_types, allowed_filing_types)
    allowed_source_tiers = _selected_source_tiers(project_inventory, tickers, years, repaired["filing_types"])
    repaired["source_tiers"] = _merge_source_tiers(
        _clamp_source_tiers(repaired.get("source_tiers") or (repaired.get("scope") or {}).get("source_tiers"), allowed_source_tiers)
        or [],
        _source_policy_source_tiers(repaired["filing_types"], allowed_source_tiers),
    )
    repaired["source_policy"] = _source_policy_for_scope(repaired["filing_types"], repaired["source_tiers"])
    repaired["scope"] = _contract_scope(tickers, focus, years, repaired["filing_types"], repaired["source_tiers"])

    _append_contract_task(repaired, _user_question_anchor_task(prompt_text, focus, repaired))
    for task in _prompt_driven_repair_tasks(prompt_text, focus, tickers):
        _append_contract_task(repaired, task)
    if has_peer_intent:
        _ensure_peer_mapping_task(repaired, prompt_text, focus, tickers, project_inventory)
    if offscope_terms:
        _apply_offscope_repairs(repaired, offscope_terms)

    repaired["metric_families"] = _dedupe_metric_families(
        [
            *(repaired.get("metric_families") or []),
            *[
                family
                for task in repaired.get("decomposed_tasks") or []
                if isinstance(task, dict)
                for family in task.get("required_metric_families") or []
            ],
        ]
    )[:16]
    repaired.setdefault("required_caveats", [])
    repaired.setdefault("forbidden_claims", [])
    if "SEC-only evidence boundary." not in repaired["required_caveats"]:
        repaired["required_caveats"].append("SEC-only evidence boundary.")
    if "Precise values must come from runtime Exact-Value Ledger only." not in repaired["required_caveats"]:
        repaired["required_caveats"].append("Precise values must come from runtime Exact-Value Ledger only.")
    task_families = {
        str(family)
        for task in repaired.get("decomposed_tasks") or []
        if isinstance(task, dict)
        for family in task.get("required_metric_families") or []
        if str(family)
    }
    rules = repaired.get("ledger_rules") if isinstance(repaired.get("ledger_rules"), dict) else {}
    existing_allowed = {str(item) for item in rules.get("allowed_metric_families") or [] if str(item)}
    if existing_allowed or task_families:
        rules["allowed_metric_families"] = sorted(existing_allowed | task_families | set(repaired.get("metric_families") or []))
        repaired["ledger_rules"] = rules
    repaired["project_inventory"] = inventory_brief(project_inventory)
    repaired["project_inventory_digest"] = project_inventory.get("inventory_digest")
    return repaired


def _runtime_source_policy() -> str:
    value = str(os.environ.get("SEC_AGENT_SOURCE_POLICY") or "").strip()
    if value in {"SEC_ONLY_10K", "SEC_PRIMARY_MIXED_RECENT", "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"}:
        return value
    return ""


def _source_policy_filing_types(current: list[str], allowed: list[str]) -> list[str]:
    allowed_set = {str(form or "").upper().strip() for form in allowed if str(form or "").strip()}
    current_set = {str(form or "").upper().strip() for form in current if str(form or "").strip()}
    if _runtime_source_policy() == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS":
        mixed = [form for form in ("10-K", "10-Q", "8-K") if form in allowed_set]
        if mixed:
            return mixed
    if _runtime_source_policy() == "SEC_PRIMARY_MIXED_RECENT":
        mixed = [form for form in ("10-K", "10-Q") if form in allowed_set]
        if mixed:
            return mixed
    if _runtime_source_policy() == "SEC_ONLY_10K" and "10-K" in allowed_set:
        return ["10-K"]
    return sorted(current_set & allowed_set) or sorted(allowed_set)


def _source_policy_for_filing_types(filing_types: list[str]) -> str:
    forms = {str(form or "").upper().strip() for form in filing_types if str(form or "").strip()}
    if "8-K" in forms:
        return "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    if forms == {"10-K"}:
        return "SEC_ONLY_10K"
    if forms and forms <= {"10-K", "10-Q"} and "10-Q" in forms:
        return "SEC_PRIMARY_MIXED_RECENT"
    return "SEC_ONLY"


def _source_policy_for_scope(filing_types: list[str], source_tiers: list[str]) -> str:
    forms = {str(form or "").upper().strip() for form in filing_types if str(form or "").strip()}
    tiers = {str(tier or "").strip() for tier in source_tiers if str(tier or "").strip()}
    if "8-K" in forms and "company_authored_unaudited_sec_filing" in tiers:
        return "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    return _source_policy_for_filing_types(filing_types)


def _source_policy_source_tiers(filing_types: list[str], allowed: list[str]) -> list[str]:
    forms = {str(form or "").upper().strip() for form in filing_types if str(form or "").strip()}
    allowed_set = {str(tier or "").strip() for tier in allowed if str(tier or "").strip()}
    if "8-K" in forms and "company_authored_unaudited_sec_filing" in allowed_set:
        return [
            tier
            for tier in ("primary_sec_filing", "company_authored_unaudited_sec_filing")
            if tier in allowed_set
        ]
    if "primary_sec_filing" in allowed_set:
        return ["primary_sec_filing"]
    return list(allowed)


def _merge_source_tiers(primary: list[str], required: list[str]) -> list[str]:
    merged = []
    for tier in [*primary, *required]:
        value = str(tier or "").strip()
        if value and value not in merged:
            merged.append(value)
    return merged


def _is_broad_ai_scope_prompt(prompt: str, mentioned_tickers: list[str]) -> bool:
    text = str(prompt or "").lower()
    has_ai = bool(
        re.search(r"(?<![a-z])ai(?![a-z])|人工智能|算力|大模型|数据中心|gpu|accelerator|hyperscale|cloud|云|芯片", text, re.I)
    )
    if not has_ai:
        return False
    broad_terms = ("ai行业", "ai 行业", "这些财报", "30家公司", "三十家公司", "产业链", "哪些公司", "这些公司", "行业", "industry")
    return _contains_any(text, broad_terms) or len(mentioned_tickers) >= 4


def _prompt_driven_repair_tasks(prompt: str, focus_tickers: list[str], search_tickers: list[str]) -> list[dict[str, Any]]:
    text = str(prompt or "")
    lowered = text.lower()
    tasks: list[dict[str, Any]] = []
    focus = [ticker for ticker in focus_tickers if ticker in set(search_tickers)] or search_tickers
    if _contains_any(lowered, ("云", "cloud", "aws", "azure", "google cloud", "copilot")):
        tasks.append(
            _repair_task(
                "cloud_commercialization_compare",
                "比较云/cloud商业化、profit/operating income 和资本开支/capex 对增长质量的影响。",
                ["cloud_revenue", "operating_income", "capital_expenditure_proxy", "operating_cash_flow"],
                focus,
            )
        )
    if _contains_any(lowered, ("资本开支", "capex", "property and equipment", "现金流", "cash flow", "投资")):
        tasks.append(
            _repair_task(
                "capex_cash_flow_pressure",
                "提取资本开支/capex/property and equipment 与经营现金流/operating cash flow，判断投资压力和现金流质量。",
                ["capital_expenditure_proxy", "operating_cash_flow", "operating_income", "revenue"],
                focus,
            )
        )
    if _contains_any(lowered, ("服务", "services", "硬件", "hardware", "iphone", "product")):
        tasks.append(
            _repair_task(
                "services_product_margin_mix",
                "比较服务/services、硬件/product/iPhone 相关收入与 gross margin/margin，对利润率变化做 SEC 证据内解释。",
                ["services_revenue", "product_revenue", "revenue", "gross_margin", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("手机", "mobile", "handset", "edge", "边缘")):
        tasks.append(
            _repair_task(
                "mobile_edge_ai_revenue",
                "提取手机/mobile/handset、AI/edge 芯片相关收入/revenue 与利润指标，避免把未披露 AI 收入说成直接指标。",
                ["revenue", "product_revenue", "semiconductor_solutions", "gross_margin", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("广告", "advertising", "ads")):
        tasks.append(
            _repair_task(
                "advertising_ai_investment",
                "覆盖广告/advertising revenue、AI/研发/research 和资本开支/capex 对经营利润/operating income 的影响。",
                ["advertising_revenue", "research_and_development", "capital_expenditure_proxy", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("研发", "r&d", "research", "管线", "pipeline", "产品收入", "product revenue")):
        tasks.append(
            _repair_task(
                "rd_pipeline_product_growth",
                "覆盖研发/R&D/research、管线/pipeline、产品收入/product revenue 和增长/revenue 的财报证据。",
                ["research_and_development", "pipeline", "product_revenue", "revenue", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("能源", "energy", "commodity", "cycle", "周期")):
        tasks.append(
            _repair_task(
                "cycle_revenue_profitability",
                "覆盖能源/commodity/cycle 或行业周期下的收入/revenue、利润/operating income、现金流/cash flow 与资本开支/capex。",
                ["revenue", "operating_income", "operating_cash_flow", "capital_expenditure_proxy", "gross_margin"],
                focus,
            )
        )
    if _contains_any(lowered, ("工业", "industrial", "orders", "订单")):
        tasks.append(
            _repair_task(
                "industrial_orders_revenue_profit",
                "覆盖工业/industrial cycle、orders/订单、收入/revenue 和利润/operating income 的变化。",
                ["revenue", "operating_income", "operating_cash_flow", "gross_margin"],
                focus,
            )
        )
    if _contains_any(lowered, ("存储", "memory", "亏损", "loss", "恢复", "recovery", "模拟芯片", "analog", "转型", "turnaround", "manufacturing")):
        tasks.append(
            _repair_task(
                "cycle_pressure_margin_recovery",
                "覆盖存储/memory、模拟芯片/analog、转型/turnaround/manufacturing 等周期压力下的收入、亏损/operating income、margin 和 recovery。",
                ["revenue", "gross_margin", "operating_income", "capital_expenditure_proxy", "operating_cash_flow"],
                focus,
            )
        )
    if _contains_any(lowered, ("基础设施软件", "infrastructure software", "半导体解决方案", "semiconductor solutions")):
        tasks.append(
            _repair_task(
                "infrastructure_software_semis_mix",
                "比较基础设施软件/infrastructure software 与半导体解决方案/semiconductor solutions 对 revenue、gross margin 和 operating income 的贡献。",
                ["infrastructure_software", "semiconductor_solutions", "revenue", "gross_margin", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("半导体", "semiconductor", "设备", "equipment", "内存", "memory", "networking", "supply", "供应")):
        tasks.append(
            _repair_task(
                "semiconductor_supply_demand_mapping",
                "覆盖半导体/semiconductor、设备/semiconductor systems、内存/memory、networking/supply 与 AI需求/data center 的证据。",
                ["data_center_revenue", "semiconductor_solutions", "semiconductor_systems", "revenue", "gross_margin", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("增长", "growth", "盈利", "profit", "改善", "improve", "margin", "rpo")):
        tasks.append(
            _repair_task(
                "growth_profitability_quality",
                "覆盖增长/revenue/RPO、盈利/operating income/loss 和改善/improve/margin，区分增长质量与利润改善。",
                ["revenue", "subscription_revenue", "rpo", "operating_income", "operating_cash_flow", "gross_margin"],
                focus,
            )
        )
    if _contains_any(lowered, ("出口管制", "export control", "客户集中", "customer concentration", "供应风险", "supply risk", "风险", "risk")):
        tasks.append(
            _repair_task(
                "risk_factor_evidence_boundary",
                "检索风险/risk、出口管制/export control、客户集中/customer concentration 和供应/supply risk 的 SEC 证据。",
                ["customer_concentration", "revenue", "data_center_revenue", "semiconductor_solutions", "operating_income"],
                focus,
                priority="supporting",
            )
        )
    if _contains_any(lowered, ("股东回报", "回报股东", "shareholder", "dividend", "buyback", "回购")):
        tasks.append(
            _repair_task(
                "shareholder_return_cash_support",
                "用经营现金流/operating cash flow、资本开支/capex 和利润指标判断股东回报/shareholder/dividend/buyback 的财务支撑。",
                ["operating_cash_flow", "capital_expenditure_proxy", "revenue", "operating_income"],
                focus,
            )
        )
    if _contains_any(lowered, ("利率", "rate", "净利息", "net interest", "存款", "贷款", "降息", "美联储", "fed")):
        tasks.append(
            _repair_task(
                "rate_sensitive_bank_metrics",
                "覆盖利率/rate、净利息收入/net interest income、收入/revenue 和 operating income，区分 SEC 内银行披露与外部宏观假设不支持/unsupported。",
                ["net_interest_income", "revenue", "operating_income", "deposits", "loans"],
                focus,
            )
        )
    return tasks


def _user_question_anchor_task(prompt: str, focus_tickers: list[str], contract: dict[str, Any]) -> dict[str, Any]:
    families = _dedupe_metric_families(contract.get("metric_families") or ["revenue", "operating_income", "operating_cash_flow", "gross_margin"])
    return _repair_task(
        "user_question_anchor",
        f"围绕用户原始问题拆解并保持任务不跑题：{_short_text(prompt, 160)}；只使用 SEC evidence 和 Exact-Value Ledger。",
        families[:6] or ["revenue", "operating_income"],
        focus_tickers,
        priority="primary",
    )


def _ensure_peer_mapping_task(
    contract: dict[str, Any],
    prompt: str,
    focus_tickers: list[str],
    tickers: list[str],
    project_inventory: dict[str, Any],
) -> None:
    peer_tickers = _infer_peer_tickers_for_prompt(prompt, focus_tickers, tickers, project_inventory)
    if not peer_tickers and len(focus_tickers) > 1:
        peer_tickers = [ticker for ticker in focus_tickers[1:] if ticker in set(tickers)]
    if not peer_tickers:
        return
    task = _repair_task(
        "peer_competition_mapping",
        "识别竞争/competitor/peer/同行和对比/compare 关系，并用 SEC 财务指标说明直接竞争、间接替代或证据不足。"
        f" Candidate peers: {', '.join(peer_tickers[:8])}.",
        ["revenue", "gross_margin", "operating_income", "research_and_development"],
        focus_tickers[:1],
        priority="supporting",
    )
    task["peer_tickers"] = peer_tickers[:8]
    _append_contract_task(contract, task)


def _repair_task(
    task_id: str,
    question_zh: str,
    families: list[str],
    required_tickers: list[str],
    *,
    priority: str = "primary",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "question_zh": question_zh,
        "priority": priority,
        "required_metric_families": _dedupe_metric_families(families),
        "required_tickers": required_tickers[:8],
        "peer_tickers": [],
    }


def _append_contract_task(contract: dict[str, Any], task: dict[str, Any]) -> None:
    tasks = [item for item in contract.get("decomposed_tasks") or [] if isinstance(item, dict)]
    existing_ids = {str(item.get("task_id") or "") for item in tasks}
    if task["task_id"] in existing_ids:
        for existing in tasks:
            if str(existing.get("task_id") or "") != task["task_id"]:
                continue
            existing["question_zh"] = _short_text(
                f"{existing.get('question_zh') or ''} {task.get('question_zh') or ''}",
                240,
            )
            existing["required_metric_families"] = _dedupe_metric_families(
                [*(existing.get("required_metric_families") or []), *(task.get("required_metric_families") or [])]
            )
            existing["required_tickers"] = _unique_compact_strings(
                [*(existing.get("required_tickers") or []), *(task.get("required_tickers") or [])]
            )[:8]
            existing["peer_tickers"] = _unique_compact_strings(
                [*(existing.get("peer_tickers") or []), *(task.get("peer_tickers") or [])]
            )[:8]
        return
    task_families = set(task.get("required_metric_families") or [])
    task_tickers = set(task.get("required_tickers") or [])
    for existing in tasks:
        existing_families = set(existing.get("required_metric_families") or [])
        existing_tickers = set(existing.get("required_tickers") or [])
        if task_families and task_families <= existing_families and (not task_tickers or task_tickers <= existing_tickers):
            existing["question_zh"] = _short_text(
                f"{existing.get('question_zh') or ''} {task.get('question_zh') or ''}",
                240,
            )
            return
    tasks.append(task)
    contract["decomposed_tasks"] = tasks[:8]


def _offscope_gap_terms(prompt: str, *, years: Iterable[int] | None = None) -> list[str]:
    text = str(prompt or "").lower()
    terms = []
    available_years = {int(year) for year in years or [] if _int_or_none(year) is not None}
    checks = {
        "市场预期": ("市场预期", "consensus", "forecast", "预测"),
        "forecast": ("forecast", "预测"),
        "stock": ("股价", "stock price", "share price"),
        "valuation": ("估值", "valuation", "p/e"),
        "macro": ("美联储", "降息", "macro", "fed", "federal reserve"),
    }
    if 2026 not in available_years and _contains_any(text, ("2026", "二零二六")):
        terms.append("2026")
    for label, aliases in checks.items():
        if _contains_any(text, aliases):
            terms.append(label)
    explicit_terms = ("美联储", "降息", "股价", "估值", "市场预期")
    for term in explicit_terms:
        if term.lower() in text:
            terms.append(term)
    return _unique_compact_strings(terms)


def _apply_offscope_repairs(contract: dict[str, Any], gap_terms: list[str]) -> None:
    gaps = [item for item in contract.get("evidence_gaps") or [] if isinstance(item, dict)]
    for term in gap_terms:
        gap_text = f"{term} is outside the current SEC-only project source inventory; treat it as unsupported, not as evidence."
        if not any(term.lower() in str(item.get("gap") or "").lower() for item in gaps):
            gaps.append({"task_id": "source_policy_gap", "gap": gap_text})
    contract["evidence_gaps"] = gaps[:8]
    caveats = [str(item) for item in contract.get("required_caveats") or [] if str(item)]
    caveat = "外部来源/未来年份/市场预期/股价估值/macro 假设不在当前 SEC-only source policy 内；只能作为 evidence gap。"
    if caveat not in caveats:
        caveats.append(caveat)
    contract["required_caveats"] = caveats[:10]
    forbidden = [str(item) for item in contract.get("forbidden_claims") or [] if str(item)]
    allowed_forms = {str(item).upper() for item in contract.get("filing_types") or [] if str(item)}
    blocked_forms = [form for form in ("10-K", "10-Q", "8-K") if form not in allowed_forms]
    blocked_form_text = f", {', '.join(blocked_forms)} evidence" if blocked_forms else ""
    forbidden_claim = (
        "Do not answer with stock price, valuation, analyst consensus, macro scenario, "
        f"forecast, news, earnings calls{blocked_form_text}."
    )
    if forbidden_claim not in forbidden:
        forbidden.append(forbidden_claim)
    contract["forbidden_claims"] = forbidden[:10]
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        question = str(task.get("question_zh") or "")
        if _contains_any(question.lower(), tuple(term.lower() for term in gap_terms)):
            task["question_zh"] = _short_text(
                f"{question}（该外部假设当前不支持/unsupported；只检索 SEC 内相关财务或风险披露。）",
                240,
            )
    for key in ("metric_queries", "qualitative_queries", "facets", "analysis_axes"):
        repaired_values = []
        for item in contract.get(key) or []:
            text = str(item)
            if _contains_any(text.lower(), tuple(term.lower() for term in gap_terms)):
                text = f"unsupported under SEC-only source policy: {text}"
            repaired_values.append(text)
        if repaired_values:
            contract[key] = repaired_values


def _dedupe_metric_families(values: Iterable[Any]) -> list[str]:
    allowed = set(METRIC_FAMILY_ONTOLOGY)
    out = []
    for value in values:
        family = str(value or "").strip()
        if family in allowed and family not in out:
            out.append(family)
    return out


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = str(text or "").lower()
    return any(str(term or "").lower() in lowered for term in terms if str(term or ""))


def _planner_seed_for_prompt(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": contract.get("task_type"),
        "focus_tickers": contract.get("focus_tickers"),
        "years": contract.get("years"),
        "filing_types": contract.get("filing_types"),
        "source_tiers": contract.get("source_tiers"),
        "analysis_axes": contract.get("analysis_axes"),
        "facets": contract.get("facets"),
        "metric_families": contract.get("metric_families"),
        "required_caveats": contract.get("required_caveats"),
    }


def _contract_scope(
    search_tickers: list[str],
    focus_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str] | None = None,
) -> dict[str, Any]:
    scope = {
        "universe_tickers": list(search_tickers),
        "focus_tickers": list(focus_tickers),
        "years": list(years),
        "filing_types": list(filing_types),
        "sec_sections": list(DEFAULT_SECTIONS),
    }
    if source_tiers:
        scope["source_tiers"] = list(source_tiers)
    return scope


def _clamp_tickers(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {ticker.upper() for ticker in allowed}
    out = []
    for item in value or []:
        ticker = str(item or "").upper().strip()
        if ticker in allowed_set and ticker not in out:
            out.append(ticker)
    return out


def _selected_form_types(project_inventory: dict[str, Any], tickers: list[str], years: list[int]) -> list[str]:
    selected = {ticker.upper() for ticker in tickers}
    selected_years = {int(year) for year in years}
    forms = set()
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            if selected_years and year not in selected_years:
                continue
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if form_type:
                forms.add(form_type)
    return sorted(forms) or ["10-K"]


def _selected_source_tiers(
    project_inventory: dict[str, Any],
    tickers: list[str],
    years: list[int],
    form_types: list[str],
) -> list[str]:
    selected = {ticker.upper() for ticker in tickers}
    selected_years = {int(year) for year in years}
    selected_forms = {str(form or "").upper().strip() for form in form_types if str(form or "").strip()}
    tiers = set()
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            if selected_years and year not in selected_years:
                continue
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if selected_forms and form_type not in selected_forms:
                continue
            source_tier = str(filing.get("source_tier") or "primary_sec_filing").strip()
            if source_tier:
                tiers.add(source_tier)
    return sorted(tiers) or ["primary_sec_filing"]


def _clamp_form_types(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {str(item).upper() for item in allowed}
    out = []
    for item in value or []:
        form_type = str(item or "").upper().strip()
        if form_type in allowed_set and form_type not in out:
            out.append(form_type)
    return out


def _clamp_source_tiers(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {str(item or "").strip() for item in allowed if str(item or "").strip()}
    out = []
    for item in value or []:
        source_tier = str(item or "").strip()
        if source_tier in allowed_set and source_tier not in out:
            out.append(source_tier)
    return out


def _string_list(value: Any, *, max_items: int, max_chars: int = 80) -> list[str]:
    out = []
    for item in value or []:
        text = _short_text(item, max_chars)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _metric_family_list(value: Any) -> list[str]:
    allowed = set(METRIC_FAMILY_ONTOLOGY)
    out = []
    for item in value or []:
        family = str(item or "").strip()
        if family in allowed and family not in out:
            out.append(family)
    return out[:16]


def _normalize_decomposed_tasks(value: Any, contract: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    allowed_tickers = [str(item).upper() for item in contract.get("search_scope_tickers") or contract.get("focus_tickers") or []]
    for idx, item in enumerate(value or [], start=1):
        if not isinstance(item, dict):
            continue
        task_id = _slug(str(item.get("task_id") or f"task_{idx}"))[:64] or f"task_{idx}"
        priority = str(item.get("priority") or "supporting").strip().lower()
        if priority not in {"primary", "supporting", "caveat"}:
            priority = "supporting"
        families = _metric_family_list(item.get("required_metric_families"))
        if not families:
            families = [str(family) for family in (contract.get("metric_families") or [])[:4]]
        required_tickers = _clamp_tickers(item.get("required_tickers"), allowed_tickers)
        peer_tickers = [ticker for ticker in _clamp_tickers(item.get("peer_tickers"), allowed_tickers) if ticker not in set(required_tickers)]
        tasks.append(
            {
                "task_id": task_id,
                "question_zh": _short_text(item.get("question_zh") or item.get("question") or "", 240),
                "priority": priority,
                "required_metric_families": families,
                "required_tickers": required_tickers,
                "peer_tickers": peer_tickers,
            }
        )
        if len(tasks) >= 8:
            break
    return tasks


def _normalize_evidence_gaps(value: Any) -> list[dict[str, str]]:
    gaps = []
    for item in value or []:
        if isinstance(item, dict):
            task_id = _slug(str(item.get("task_id") or "gap"))[:64] or "gap"
            gap = _short_text(item.get("gap") or item.get("description") or "", 240)
        else:
            task_id = "gap"
            gap = _short_text(item, 240)
        if gap:
            gaps.append({"task_id": task_id, "gap": gap})
        if len(gaps) >= 8:
            break
    return gaps


def _planner_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low"} else "medium"


def _short_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_chars]


def _print_query_contract(contract: dict[str, Any]) -> None:
    focus = contract.get("focus_tickers") or []
    scope = contract.get("search_scope_tickers") or []
    validation = contract.get("query_contract_validation") if isinstance(contract.get("query_contract_validation"), dict) else {}
    focus_text = ",".join(focus[:18]) + (f",...(+{len(focus)-18})" if len(focus) > 18 else "")
    print(
        "[plan] "
        f"task={contract.get('task_type')} "
        f"planner={contract.get('planner_backend', '<unset>')}:{contract.get('planner_status', '<unset>')} "
        f"validation={validation.get('status', '<unset>')} "
        f"scope={len(scope)} companies "
        f"focus={focus_text or '<none>'} "
        f"years={','.join(str(y) for y in contract.get('years') or [])} "
        f"forms={','.join(str(item) for item in contract.get('filing_types') or [])}"
    )
    peer_tickers = sorted(
        {
            str(ticker).upper()
            for task in contract.get("decomposed_tasks") or []
            if isinstance(task, dict)
            for ticker in task.get("peer_tickers") or []
            if str(ticker)
        }
    )
    if peer_tickers:
        print(f"[plan] peer_tickers={','.join(peer_tickers[:12])}")
    print(f"[plan] facets={','.join(str(item) for item in (contract.get('facets') or [])[:8])}")
    print(f"[plan] metric_families={','.join(str(item) for item in (contract.get('metric_families') or [])[:12])}")


def _generic_numeric_checks(
    prompt: str,
    tickers: list[str],
    years: list[int],
    query_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    focus_tickers = [str(item).upper() for item in query_contract.get("focus_tickers") or tickers]
    metric_queries = [str(item) for item in query_contract.get("metric_queries") or []]
    if not metric_queries:
        metric_queries = [
            prompt,
            "revenue net sales operating income gross margin segment revenue",
            "capital expenditures purchases of property and equipment operating cash flow free cash flow",
        ]
    checks = []
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families = [str(item) for item in task.get("required_metric_families") or [] if str(item)]
        if not families:
            continue
        task_companies = _task_company_scope(task, focus_tickers)
        task_query = " ".join(
            part
            for part in [
                str(task.get("question_zh") or ""),
                " ".join(_family_search_alias(family) for family in families),
            ]
            if part
        ).strip()
        if not task_query:
            continue
        checks.append(
            {
                "metric": task_query,
                "companies": task_companies,
                "years": years,
                "metric_families": families,
                "task_id": str(task.get("task_id") or ""),
                "task_priority": str(task.get("priority") or ""),
                "selection_policy": "decomposed_task_metric_family",
            }
        )
    for query in metric_queries:
        checks.append(
            {
                "metric": query,
                "companies": focus_tickers,
                "years": years,
                "metric_families": [],
                "selection_policy": "planner_metric_query",
            }
        )
    return checks


def _task_company_scope(task: dict[str, Any], fallback_tickers: list[str]) -> list[str]:
    out = []
    for key in ("required_tickers", "peer_tickers"):
        for ticker in task.get(key) or []:
            ticker_text = str(ticker or "").upper().strip()
            if ticker_text and ticker_text not in out:
                out.append(ticker_text)
    return out or fallback_tickers


def _family_search_alias(family: str) -> str:
    aliases = {
        "advertising_revenue": "advertising revenue ads revenue",
        "arr_or_recurring_proxy": "annual recurring revenue ARR recurring revenue",
        "capital_expenditure_proxy": "capital expenditures purchases of property and equipment data center infrastructure capex",
        "capex": "capital expenditures purchases of property and equipment data center infrastructure capex",
        "cloud_revenue": "cloud revenue AWS Azure cloud services",
        "data_center_revenue": "data center revenue compute networking AI accelerator",
        "deferred_revenue": "deferred revenue unearned revenue contract liabilities",
        "free_cash_flow_proxy": "free cash flow operating cash flow capital expenditures purchases of property and equipment",
        "gross_margin": "gross margin gross profit margin",
        "infrastructure_software": "infrastructure software security software platform revenue",
        "asset_quality": "asset quality nonperforming assets nonperforming loans charge-offs credit quality",
        "allowance_for_credit_losses": "allowance for credit losses allowance for loan losses allowance for expected credit losses",
        "capital_ratio": "CET1 common equity tier 1 tier 1 capital capital ratio",
        "credit_quality": "credit quality asset quality credit losses nonperforming loans net charge-offs allowance for credit losses",
        "credit_risk": "credit risk credit losses allowance for credit losses net charge-offs delinquencies",
        "deposits": "deposits average deposits total deposits deposit balances",
        "loans": "loans average loans total loans loan portfolio",
        "net_interest_income": "net interest income taxable-equivalent net interest income interest income interest expense",
        "net_interest_margin": "net interest margin NIM net yield on interest-earning assets",
        "net_charge_offs": "net charge-offs net charge offs charge-offs charge offs",
        "nonperforming_assets": "nonperforming assets non-performing assets nonaccrual assets",
        "nonperforming_loans": "nonperforming loans non-performing loans nonaccrual loans",
        "operating_cash_flow": "net cash provided by operating activities operating cash flow",
        "operating_income": "operating income income from operations segment operating income",
        "product_revenue": "product revenue product net sales",
        "provision_for_credit_losses": "provision for credit losses credit loss provision provision for loan losses",
        "research_and_development": "research and development R&D AI infrastructure costs",
        "revenue": "revenue net sales total revenue",
        "rpo": "remaining performance obligations RPO contracted backlog revenue visibility",
        "semiconductor_solutions": "semiconductor solutions revenue",
        "semiconductor_systems": "semiconductor systems revenue",
        "services_revenue": "services revenue service revenue",
        "subscription_revenue": "subscription revenue subscription and support revenue",
        "total_assets": "total assets consolidated assets",
        "total_revenue": "total revenue net sales revenue",
    }
    return aliases.get(str(family), str(family).replace("_", " "))


def _write_run_outputs(
    qwen_dir: Path,
    trace: dict[str, Any],
    synthesis: dict[str, Any],
    args: argparse.Namespace,
    started: float,
    ledger_rows: list[dict[str, Any]] | None = None,
) -> None:
    qwen_dir.mkdir(parents=True, exist_ok=True)
    case_id = str(trace.get("case_id") or "")
    mode = str(trace.get("mode") or "pipeline_context")
    agent = {
        "schema_version": "sec_benchmark_agent_output_v0.1",
        "case_id": case_id,
        "mode": mode,
        "status": synthesis["agent_status"],
        "answer_status": synthesis["answer_status"],
        "answer": synthesis["answer"],
        "limitations": synthesis["limitations"],
        "context_row_count": trace.get("context_summary", {}).get("context_row_count", 0),
    }
    claim = {
        "schema_version": "sec_benchmark_claim_verification_v0.1",
        "case_id": case_id,
        "mode": mode,
        "status": synthesis["claim_status"],
        "claims": synthesis["claims"],
        "unsupported_claim_count": synthesis["unsupported_claim_count"],
    }
    score = {
        "schema_version": "sec_benchmark_score_v0.1",
        "case_id": case_id,
        "mode": mode,
        "status": synthesis["score_status"],
        "score_total": synthesis["score_total"],
        "scores": None,
        "failure_types": synthesis["failure_types"],
        "notes": synthesis["score_notes"],
    }
    raw = {"case_id": case_id, "mode": mode, **synthesis.get("debug", {})}
    llm_gateway = _gateway_debug((synthesis.get("debug") or {}).get("llm_gateway") or {})
    _write_jsonl(qwen_dir / "agent_outputs.jsonl", [agent])
    _write_jsonl(qwen_dir / "claim_verification.jsonl", [claim])
    _write_jsonl(qwen_dir / "scores.jsonl", [score])
    _write_jsonl(qwen_dir / "trace_logs.jsonl", [trace])
    _write_jsonl(qwen_dir / "raw_model_outputs.jsonl", [raw])
    _write_json(qwen_dir / "run_summary.json", {
        "schema_version": "sec_agent_interactive_summary_v0.1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(qwen_dir.resolve()),
        "llm_backend": args.llm_backend,
        "base_url": args.base_url,
        "chat_completions_path": args.chat_completions_path,
        "model": args.model,
        "trace_count": 1,
        "agent_output_count": 1,
        "answer_status_counts": dict(Counter([synthesis["answer_status"]])),
        "llm_gateway": llm_gateway,
        "timings": {"total_elapsed_sec": round(time.time() - started, 4)},
    })
    _write_text(
        qwen_dir / "input_output.md",
        _input_output_markdown(
            user_query=str((synthesis.get("debug") or {}).get("user_query") or ""),
            raw_output=str((synthesis.get("debug") or {}).get("raw_output") or ""),
            answer=synthesis.get("answer") or {},
        ),
    )
    _write_text(
        qwen_dir / "rendered_answer.md",
        _rendered_answer_markdown(
            user_query=str((synthesis.get("debug") or {}).get("user_query") or ""),
            answer=synthesis.get("answer") or {},
            metric_rows={str(row.get("metric_id") or ""): row for row in (ledger_rows or []) if row.get("metric_id")},
            evidence_rows=_evidence_rows_by_id(trace.get("context_rows") or []),
        ),
    )


def _print_answer(
    synthesis: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    coverage_matrix: dict[str, Any] | None,
    gate_dir: Path,
    run_root: Path,
    post_gate_ok: bool,
    started: float,
) -> None:
    answer = synthesis.get("answer") or {}
    metric_rows = {str(row.get("metric_id") or ""): row for row in ledger_rows if row.get("metric_id")}
    evidence_rows = _evidence_rows_by_id(context_rows)
    print("\nassistant>")
    if answer.get("direct_answer") or answer.get("investment_thesis"):
        _print_memo_answer(answer, metric_rows, evidence_rows)
        show_legacy_sections = False
    else:
        print(_clean_display_text(answer.get("summary") or ""))
        show_legacy_sections = True
    if show_legacy_sections:
        for idx, driver in enumerate(answer.get("decision_drivers") or [], start=1):
            print(f"\nDriver {idx}. {_clean_display_text(driver.get('driver_claim') or '')}")
            why = _clean_display_text(driver.get("why_it_matters") or "")
            if why:
                print(f"   why: {why}")
            mids = driver.get("supporting_metric_ids") or []
            eids = driver.get("supporting_evidence_ids") or []
            metric_refs = _format_metric_refs([str(item) for item in mids], metric_rows)
            evidence_refs = _format_evidence_refs([str(item) for item in eids], evidence_rows)
            if metric_refs:
                print(f"   依据数值: {'；'.join(metric_refs)}")
            if evidence_refs:
                print(f"   SEC证据: {'；'.join(evidence_refs)}")
        for idx, point in enumerate(answer.get("key_points") or [], start=1):
            print(f"\n{idx}. {_clean_display_text(point.get('point') or '')}")
            mids = point.get("metric_ids") or []
            eids = point.get("evidence_ids") or []
            metric_refs = _format_metric_refs([str(item) for item in mids], metric_rows)
            evidence_refs = _format_evidence_refs([str(item) for item in eids], evidence_rows)
            if metric_refs:
                print(f"   依据数值: {'；'.join(metric_refs)}")
            if evidence_refs:
                print(f"   SEC证据: {'；'.join(evidence_refs)}")
    limitations = answer.get("limitations") or []
    if limitations:
        print("\nlimitations:")
        for item in limitations[:5]:
            print(f"- {_clean_display_text(item)}")
    gate_summary_path = gate_dir / "sec_benchmark_post_gates_summary.json"
    if gate_summary_path.exists():
        summary = _read_json(gate_summary_path)
        pass_keys = [key for key, value in summary.items() if key.endswith("_gate_pass") and value is True]
        fail_keys = [key for key, value in summary.items() if key.endswith("_gate_pass") and value is False]
        print(f"\n[gates] ok={post_gate_ok and not fail_keys} pass={len(pass_keys)} fail={fail_keys}")
    else:
        print(f"\n[gates] ok={post_gate_ok} summary_not_available")
    coverage_summary = (coverage_matrix or {}).get("summary") or {}
    if coverage_summary:
        print(
            "[coverage] "
            f"complete={coverage_summary.get('coverage_complete')} "
            f"primary_complete={coverage_summary.get('primary_task_support_complete')} "
            f"answer_status={coverage_summary.get('answer_status')} "
            f"support={coverage_summary.get('support_counts')}"
        )
    print(f"[ledger] rows={len(ledger_rows)} [context] rows={len(context_rows)}")
    print(f"[artifacts] {run_root}")
    print(f"[elapsed] {round(time.time() - started, 2)} sec")


def _print_memo_answer(
    answer: dict[str, Any],
    metric_rows: dict[str, dict[str, Any]],
    evidence_rows: dict[str, dict[str, Any]] | None = None,
) -> None:
    direct = _clean_display_text(answer.get("direct_answer") or answer.get("summary") or "")
    thesis = _clean_display_text(answer.get("investment_thesis") or "")
    if direct:
        print("直接回答")
        print(direct)
    if thesis:
        print("\n投资判断")
        print(thesis)
    evidence_rows = evidence_rows or {}
    _print_memo_items("关键变化", answer.get("what_changed") or [], ("claim",), metric_rows, evidence_rows)
    _print_memo_items("为什么重要", answer.get("why_it_matters") or [], ("insight", "business_implication"), metric_rows, evidence_rows)
    _print_memo_items("同行/竞争映射", answer.get("peer_readthrough") or [], ("peer_or_group", "role", "readthrough", "caveat"), metric_rows, evidence_rows)
    _print_memo_items("反证与风险", answer.get("counterarguments") or [], ("claim", "why_it_could_weaken_thesis"), metric_rows, evidence_rows)
    watch_items = [item for item in answer.get("watch_items") or [] if isinstance(item, dict)]
    if watch_items:
        print("\n后续观察项")
        for idx, item in enumerate(watch_items, start=1):
            text = " - ".join(
                _clean_display_text(item.get(key) or "")
                for key in ("item", "why_it_matters", "source_to_watch")
                if _clean_display_text(item.get(key) or "")
            )
            if text:
                print(f"{idx}. {text}")
    source_limitations = [_clean_display_text(item) for item in answer.get("source_limitations") or [] if _clean_display_text(item)]
    if source_limitations:
        print("\n证据边界")
        for item in source_limitations[:5]:
            print(f"- {item}")


def _print_memo_items(
    title: str,
    rows: list[Any],
    text_keys: tuple[str, ...],
    metric_rows: dict[str, dict[str, Any]],
    evidence_rows: dict[str, dict[str, Any]] | None = None,
) -> None:
    items = [item for item in rows if isinstance(item, dict)]
    if not items:
        return
    print(f"\n{title}")
    for idx, item in enumerate(items, start=1):
        parts = [_clean_display_text(item.get(key) or "") for key in text_keys]
        text = " ".join(part for part in parts if part)
        if text:
            print(f"{idx}. {text}")
        metric_refs = _format_metric_refs([str(mid) for mid in item.get("metric_ids") or []], metric_rows)
        evidence_refs = _format_evidence_refs([str(eid) for eid in item.get("evidence_ids") or []], evidence_rows or {})
        if metric_refs:
            print(f"   依据数值: {'；'.join(metric_refs)}")
        if evidence_refs:
            print(f"   SEC证据: {'；'.join(evidence_refs)}")


def _clean_display_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s*\(INTERACTIVE_[^)]+\)", "", text)
    text = re.sub(r"\bINTERACTIVE_\d{8}_\d{6}_[0-9a-f]+::[^\s,;，。)）]+", "", text)
    text = re.sub(r"\s+([,.;，。；])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _format_metric_refs(metric_ids: list[str], metric_rows: dict[str, dict[str, Any]]) -> list[str]:
    refs = []
    seen = set()
    for metric_id in metric_ids:
        row = metric_rows.get(metric_id)
        if not row:
            continue
        key = (
            str(row.get("ticker") or ""),
            str(row.get("fiscal_year") or ""),
            str(row.get("metric_family") or ""),
            str(row.get("period_role") or ""),
            str(row.get("display_value_zh") or row.get("raw_value_text") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        ticker = str(row.get("ticker") or "").upper()
        year_label = _display_metric_ref_year(row)
        period_label = _display_period_role(row)
        label = _display_metric_label(row)
        value = str(row.get("display_value_zh") or row.get("raw_value_text") or "").strip()
        refs.append(f"{ticker} {year_label} {period_label} {label}: {value}")
        if len(refs) >= 4:
            break
    return refs


def _display_metric_ref_year(row: dict[str, Any]) -> str:
    value_year = _int_or_none(row.get("fiscal_year"))
    source_year = _int_or_none(row.get("source_fiscal_year"))
    if value_year is not None and source_year is not None and value_year != source_year:
        return f"FY{value_year} comparable in FY{source_year} filing"
    if value_year is not None:
        return f"FY{value_year}"
    return str(row.get("fiscal_year") or "").strip()


def _display_period_role(row: dict[str, Any]) -> str:
    role = str(row.get("period_role") or "").strip().lower()
    form_type = str(row.get("form_type") or row.get("source_type") or "").strip()
    fiscal_period = str(row.get("fiscal_period") or "").strip()
    period_end = str(row.get("period_end") or "").strip()
    labels = {
        "annual": "annual",
        "qtd": "QTD",
        "ytd": "YTD",
        "ttm": "TTM",
        "instant": "point-in-time",
    }
    label = labels.get(role, "period-role-unknown")
    prefix = " ".join(part for part in (form_type, fiscal_period) if part)
    suffix = f" period_end={period_end}" if period_end and role in {"qtd", "ytd", "ttm", "instant"} else ""
    return " ".join(part for part in (prefix, label) if part).strip() + suffix


def _display_metric_label(row: dict[str, Any]) -> str:
    family = str(row.get("metric_family") or "")
    name = str(row.get("metric_name") or row.get("row_label") or "").strip()
    family_labels = {
        "data_center_revenue": "数据中心/计算收入",
        "cloud_revenue": "云业务收入",
        "advertising_revenue": "广告收入",
        "semiconductor_systems": "半导体系统收入",
        "semiconductor_solutions": "半导体解决方案收入",
        "infrastructure_software": "基础设施软件收入",
        "operating_income": "营业利润",
        "operating_cash_flow": "经营现金流",
        "capital_expenditure_proxy": "资本开支 proxy",
        "gross_margin": "毛利率",
        "research_and_development": "研发支出",
        "allowance_for_credit_losses": "信用损失准备",
        "asset_quality": "资产质量",
        "capital_ratio": "资本充足率",
        "credit_quality": "信用质量",
        "credit_risk": "信用风险",
        "deposits": "存款",
        "loans": "贷款",
        "net_charge_offs": "净核销",
        "net_interest_income": "净利息收入",
        "net_interest_margin": "净息差",
        "nonperforming_assets": "不良资产",
        "nonperforming_loans": "不良贷款",
        "provision_for_credit_losses": "信用损失拨备",
        "total_assets": "总资产",
    }
    label = family_labels.get(family, family or "指标")
    if name and len(name) <= 42 and name.lower() not in {"total", "revenue", "net sales"}:
        return f"{name} ({label})"
    return label


def _evidence_rows_by_id(context_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in context_rows:
        if not isinstance(row, dict):
            continue
        for key in ("evidence_id", "source_evidence_id", "object_id", "chunk_id"):
            value = str(row.get(key) or "").strip()
            if value and value not in rows:
                rows[value] = row
    return rows


def _format_evidence_refs(
    evidence_ids: list[str],
    evidence_rows: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    refs = []
    seen = set()
    evidence_rows = evidence_rows or {}
    for evidence_id in evidence_ids:
        text = _short_evidence_ref(evidence_id, evidence_rows.get(str(evidence_id or "").strip()))
        if not text or text in seen:
            continue
        refs.append(text)
        seen.add(text)
        if len(refs) >= 3:
            break
    return refs


def _short_evidence_ref(evidence_id: str, row: dict[str, Any] | None = None) -> str:
    evidence_id = str(evidence_id or "").strip()
    row = row or {}
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source_tier = str(row.get("source_tier") or metadata.get("source_tier") or "").strip()
    boundary = _source_boundary_label(source_tier)

    if evidence_id.startswith("8K_EARNINGS::"):
        parts = evidence_id.split("::")
        ticker = (parts[1] if len(parts) > 1 else str(row.get("ticker") or "")).upper()
        exhibit = _display_8k_exhibit(parts[3] if len(parts) > 3 else row.get("exhibit") or metadata.get("exhibit"))
        period = _display_evidence_period(row)
        label = " ".join(part for part in (ticker, period, "8-K earnings release", exhibit) if part).strip()
        return f"{label} ({boundary or 'company-authored unaudited'})"

    match = re.match(r"^([A-Z]+)_(\d{4})_(10K|10Q|8K)_(ITEM\d+[A-Z]?)", evidence_id)
    if match:
        ticker, year, form, item = match.groups()
        item_text = item.replace("ITEM", "Item ")
        form_text = form.replace("10K", "10-K").replace("10Q", "10-Q").replace("8K", "8-K")
        suffix = f" ({boundary})" if boundary else ""
        return f"{ticker} {year} {form_text} {item_text}{suffix}"

    if row:
        ticker = str(row.get("ticker") or "").upper()
        year = str(row.get("fiscal_year") or metadata.get("fiscal_year") or "").strip()
        form = _normalize_form_type(row.get("form_type") or row.get("source_type") or metadata.get("form_type") or "")
        suffix = f" ({boundary})" if boundary else ""
        label = " ".join(part for part in (ticker, year, form) if part).strip()
        if label:
            return f"{label}{suffix}"
    return evidence_id[:80]


def _source_boundary_label(source_tier: str) -> str:
    labels = {
        "primary_sec_filing": "SEC primary filing",
        "company_authored_unaudited_sec_filing": "company-authored unaudited",
    }
    return labels.get(str(source_tier or "").strip(), "")


def _display_8k_exhibit(value: Any) -> str:
    text = str(value or "").upper().replace(".", "")
    if "991" in text:
        return "Exhibit 99.1"
    if text.startswith("EX"):
        return text
    return ""


def _display_evidence_period(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    fiscal_year = row.get("fiscal_year") or metadata.get("reported_fiscal_year") or metadata.get("fiscal_year")
    fiscal_period = row.get("fiscal_period") or metadata.get("reported_fiscal_period") or metadata.get("fiscal_period")
    parts = [str(part).strip() for part in (fiscal_year, fiscal_period) if str(part or "").strip()]
    return " ".join(parts)


def _gateway_debug(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    return {
        "status": result.get("status"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "role": result.get("role"),
        "profile": result.get("profile"),
        "finish_reason": result.get("finish_reason"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "cost_estimate": result.get("cost_estimate"),
        "failure_reason": result.get("failure_reason"),
        "trace_tags": result.get("trace_tags") or {},
    }


def _server_ready(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/v1/models", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _uses_local_qwen(args: argparse.Namespace) -> bool:
    return str(args.llm_backend or "") == "qwen_vllm"


def _llm_display_name(args: argparse.Namespace) -> str:
    if str(args.llm_backend or "") == "deepseek":
        return f"DeepSeek API ({args.model})"
    if str(args.llm_backend or "") == "openai_compatible":
        return f"OpenAI-compatible API ({args.model})"
    return f"Qwen local vLLM ({args.model})"


def _ensure_llm_ready(args: argparse.Namespace) -> None:
    if not _uses_local_qwen(args):
        if not str(args.api_key_env or ""):
            raise RuntimeError(f"{args.llm_backend} backend requires --api-key-env")
        if not os.environ.get(str(args.api_key_env)):
            raise RuntimeError(f"{args.llm_backend} backend requires API key env var: {args.api_key_env}")
        return
    _ensure_qwen_ready(args)


def _ensure_qwen_ready(args: argparse.Namespace) -> None:
    if _server_ready(args.base_url):
        return
    if args.auto_start_qwen or args.bge_first:
        if not args.quiet:
            print("[setup] starting Qwen server for synthesis ...")
        _qwen_control(args, "start", quiet=bool(args.quiet))
    if _server_ready(args.base_url):
        return
    try:
        with urllib.request.urlopen(args.base_url.rstrip("/") + "/v1/models", timeout=3) as resp:
            if resp.status != 200:
                raise RuntimeError(f"server health returned HTTP {resp.status}")
    except Exception as exc:
        raise RuntimeError(
            "Qwen server is not ready. Start it first with: bash scripts/cloud/qwen9b_interactive.sh start"
        ) from exc


def _qwen_control(args: argparse.Namespace, command: str, *, quiet: bool) -> None:
    env = os.environ.copy()
    env["BASE_URL"] = args.base_url
    env["MODEL_NAME"] = args.model
    proc = subprocess.run(
        ["bash", "scripts/cloud/qwen9b_interactive.sh", command],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr)
    if not quiet and proc.stdout.strip():
        print(proc.stdout.strip())


def _available_scope(manifest_rows: list[dict[str, Any]]) -> set[tuple[str, int]]:
    out = set()
    for row in manifest_rows:
        ticker = str(row.get("ticker") or "").upper()
        year = _int_or_none(row.get("fiscal_year"))
        if ticker and year is not None:
            out.add((ticker, year))
    return out


def _resolve_tickers(value: str, prompt: str, available: set[tuple[str, int]]) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return _infer_tickers(prompt, available) or _all_available_tickers(available)
    if raw.lower() in {"all", "full", "full30", "*"}:
        if _looks_like_broad_ai_scope(prompt, available):
            available_tickers = {ticker for ticker, _year in available}
            ai_tickers = [ticker for ticker in AI_FOCUS_TICKERS if ticker in available_tickers]
            if ai_tickers:
                return ai_tickers
        return _all_available_tickers(available)
    return _parse_tickers(raw)


def _all_available_tickers(available: set[tuple[str, int]]) -> list[str]:
    return sorted({ticker for ticker, _year in available})


def _parse_tickers(value: str) -> list[str]:
    return [item.upper() for item in re.split(r"[,，\s]+", str(value or "")) if item.strip()]


def _parse_years(value: str) -> list[int]:
    years = []
    for item in re.split(r"[,，\s]+", str(value or "")):
        if not item:
            continue
        if "-" in item:
            start, end = item.split("-", 1)
            if start.isdigit() and end.isdigit():
                years.extend(range(int(start), int(end) + 1))
        elif item.isdigit():
            years.append(int(item))
    return sorted(set(years))


def _default_years_for_runtime_source_policy() -> list[int]:
    if _runtime_source_policy() in {"SEC_PRIMARY_MIXED_RECENT", "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"}:
        return [2023, 2024, 2025, 2026, 2027]
    return list(DEFAULT_YEARS)


def _infer_tickers(prompt: str, available: set[tuple[str, int]]) -> list[str]:
    lowered = prompt.lower()
    found = []
    for ticker, aliases in KNOWN_COMPANIES.items():
        if ticker not in {item[0] for item in available}:
            continue
        for alias in aliases:
            if re.fullmatch(r"[A-Za-z.]+", alias):
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias.lower())}(?![A-Za-z0-9])", lowered):
                    found.append(ticker)
                    break
            elif alias.lower() in lowered:
                found.append(ticker)
                break
    return list(dict.fromkeys(found))


def _looks_like_broad_ai_scope(prompt: str, available: set[tuple[str, int]]) -> bool:
    text = str(prompt or "").lower()
    has_ai = bool(
        re.search(r"(?<![a-z])ai(?![a-z])|人工智能|算力|大模型|数据中心|gpu|accelerator|hyperscale|cloud|云|芯片", text, re.I)
    )
    if not has_ai:
        return False
    has_group_word = any(term in text for term in ("行业", "相关", "这些公司", "公司", "sector", "industry", "peers", "basket"))
    return has_group_word or not _infer_tickers(prompt, available)


def _has_peer_intent(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return any(term.lower() in lowered for term in PEER_INTENT_TERMS)


def _has_banking_intent(prompt: str, focus_tickers: list[str] | None = None) -> bool:
    lowered = str(prompt or "").lower()
    if any(term.lower() in lowered for term in BANKING_INTENT_TERMS):
        return True
    return bool({"JPM"} & {str(ticker).upper() for ticker in focus_tickers or []})


def _infer_peer_tickers_for_prompt(
    prompt: str,
    focus_tickers: list[str],
    tickers: list[str],
    project_inventory: dict[str, Any],
) -> list[str]:
    if not _has_peer_intent(prompt):
        return []
    allowed = [str(ticker).upper() for ticker in tickers]
    focus = [str(ticker).upper() for ticker in focus_tickers if str(ticker).upper() in set(allowed)]
    available_for_scope = {(ticker, year) for ticker in allowed for year in DEFAULT_YEARS}
    mentioned = [ticker for ticker in _infer_tickers(prompt, available_for_scope) if ticker not in set(focus)]
    if mentioned:
        return mentioned[:8]

    category_by_ticker = _inventory_category_by_ticker(project_inventory)
    focus_tokens = set()
    for ticker in focus:
        focus_tokens |= _category_tokens(category_by_ticker.get(ticker, ""))
    prompt_tokens = _category_tokens(prompt)
    seed_tokens = (focus_tokens | prompt_tokens) & DOMAIN_CATEGORY_TOKENS
    if not seed_tokens and focus:
        seed_tokens = _category_tokens(category_by_ticker.get(focus[0], ""))

    scored: list[tuple[int, str]] = []
    for ticker in allowed:
        if ticker in set(focus):
            continue
        category = category_by_ticker.get(ticker, "")
        tokens = _category_tokens(" ".join([category, ticker, " ".join(KNOWN_COMPANIES.get(ticker, ())) ]))
        overlap = len(seed_tokens & tokens)
        if "semiconductor" in seed_tokens and "semiconductor" in tokens:
            overlap += 2
        if "cloud" in seed_tokens and "cloud" in tokens:
            overlap += 1
        if overlap:
            scored.append((overlap, ticker))
    scored.sort(key=lambda item: (-item[0], allowed.index(item[1]) if item[1] in allowed else 999))
    return [ticker for _, ticker in scored[:8]]


def _inventory_category_by_ticker(project_inventory: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in project_inventory.get("categories") or []:
        category = str(item.get("category") or "")
        for ticker in item.get("tickers") or []:
            ticker_text = str(ticker or "").upper()
            if ticker_text and ticker_text not in out:
                out[ticker_text] = category
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        category = str(company.get("category") or company.get("industry") or "")
        if ticker and category and ticker not in out:
            out[ticker] = category
    return out


def _category_tokens(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
    aliases = {
        "gpu": {"gpu", "semiconductor", "chip", "ai"},
        "nvidia": {"gpu", "semiconductor", "chip", "ai"},
        "nvda": {"gpu", "semiconductor", "chip", "ai"},
        "aws": {"cloud", "ai"},
        "azure": {"cloud", "ai"},
        "google": {"cloud", "advertising", "ai"},
    }
    tokens = set(raw)
    for token in list(raw):
        tokens |= aliases.get(token, set())
    return tokens


def _infer_years(prompt: str) -> list[int]:
    years = sorted({int(match.group(1)) for match in re.finditer(r"(?<!\d)(20\d{2})(?!\d)", prompt)})
    if len(years) >= 2:
        return list(range(min(years), max(years) + 1))
    return years


def _filter_available(tickers: list[str], years: list[int], available: set[tuple[str, int]]) -> tuple[list[str], list[int]]:
    filtered_tickers = [ticker for ticker in dict.fromkeys(tickers) if any((ticker, year) in available for year in years)]
    filtered_years = [year for year in sorted(set(years)) if any((ticker, year) in available for ticker in filtered_tickers)]
    return filtered_tickers, filtered_years


def _load_object_records(index_dir: Path) -> dict[str, dict[str, Any]]:
    path = index_dir / "records.jsonl"
    return {
        str(row.get("object_id") or ""): row
        for row in _read_jsonl(path)
        if str(row.get("object_id") or "")
    }


def _metric_family(name: str, context: str = "") -> str:
    text = f"{name} {context}".lower()
    rules = [
        (
            "provision_for_credit_losses",
            (
                "provision for credit losses",
                "credit loss provision",
                "provision for loan losses",
                "provision for loan lease and other losses",
            ),
        ),
        ("allowance_for_credit_losses", ("allowance for credit losses", "allowance for loan losses", "allowance for expected credit losses")),
        ("net_charge_offs", ("net charge-offs", "net charge offs", "charge-offs", "charge offs")),
        ("net_interest_margin", ("net interest margin", "net yield on interest-earning assets")),
        ("net_interest_income", ("net interest income", "taxable-equivalent net interest income")),
        ("nonperforming_assets", ("nonperforming assets", "non-performing assets", "nonaccrual assets", "non-accrual assets")),
        ("nonperforming_loans", ("nonperforming loans", "non-performing loans", "nonaccrual loans", "non-accrual loans")),
        ("capital_ratio", ("cet1", "common equity tier 1", "tier 1 capital", "capital ratio")),
        ("deposits", ("average deposits", "total deposits", "deposit balances", "deposits")),
        ("loans", ("average loans", "total loans", "loan portfolio", "loans retained", "loans")),
        ("total_assets", ("total assets",)),
        ("capital_expenditure_proxy", ("capital expenditure", "capex", "property and equipment", "ppe")),
        ("operating_cash_flow", ("operating cash", "cash provided by operating", "net cash from operations")),
        ("free_cash_flow_proxy", ("free cash flow",)),
        ("research_and_development", ("research and development", "r&d")),
        ("operating_income", ("operating income", "income from operations", "operating profit")),
        ("gross_margin", ("gross margin", "gross profit")),
        ("data_center_revenue", ("data center", "compute & networking")),
        ("cloud_revenue", ("cloud", "aws", "azure")),
        ("advertising_revenue", ("advertising", "ads")),
        ("semiconductor_systems", ("semiconductor systems",)),
        ("semiconductor_solutions", ("semiconductor solutions",)),
        ("infrastructure_software", ("infrastructure software",)),
        ("rpo", ("remaining performance obligation", "rpo")),
        ("deferred_revenue", ("deferred revenue",)),
        ("subscription_revenue", ("subscription and support", "subscription revenue", "subscription")),
        ("services_revenue", ("services revenue", "service revenue", "services net sales")),
        ("product_revenue", ("product revenue", "product net sales")),
        ("total_revenue", ("total revenue", "total net sales")),
        ("customer_concentration", ("customer", "concentration")),
        ("revenue", ("revenue", "net sales", "sales")),
    ]
    for family, terms in rules:
        if any(term in text for term in terms):
            return family
    return _slug(name)[:60] or "metric"


def _is_low_signal_metric(name: str, unit: str) -> bool:
    text = re.sub(r"\s+", " ", str(name or "").strip().lower())
    if unit == "percent" and text in {"% of net revenue", "of net revenue", "percentage of net revenue"}:
        return True
    if unit == "percent" and text in {
        "% of revenue",
        "of revenue",
        "as a percent of revenue",
        "percentage of revenue",
        "percentage of product revenue",
        "percentage of total revenue",
    }:
        return True
    if text in {"years ended", "year ended", "three months ended", "july 26, 2025", "july 27, 2024", "july 29, 2023"}:
        return True
    low_signal_terms = (
        "balance as of",
        "sales of businesses",
        "acquisition of",
        "business combinations",
        "purchase price",
        "pro forma net income",
        "goodwill",
        "intangible assets",
        "sales and marketing",
        "marketing and sales",
        "cost of revenue",
        "cost of sales",
        "general and administrative",
        "total cost",
        "as a percent of revenue",
    )
    if any(term in text for term in low_signal_terms):
        return True
    return False


def _is_bad_numeric_raw(raw: str, unit: str) -> bool:
    text = str(raw or "").strip()
    if not text:
        return True
    if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b", text, re.I):
        return True
    if unit.startswith("usd") and not re.search(r"\d", text):
        return True
    return False


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def _ledger_row_text(row: dict[str, Any], context_row: dict[str, Any] | None = None) -> str:
    parts = [
        row.get("metric_name"),
        row.get("row_label"),
        row.get("column_label"),
        row.get("table_title"),
        row.get("record_title"),
        row.get("active_group"),
        row.get("source_text"),
        (context_row or {}).get("text"),
    ]
    return " ".join(str(part) for part in parts if part)


def _is_percentage_basis_table(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return any(
        term in normalized
        for term in (
            "expressed as a percentage of revenue",
            "expressed as a percent of revenue",
            "as a percentage of revenue",
            "as a percent of revenue",
            "as a percentage of total revenue",
            "as a percent of total revenue",
        )
    )


def _is_excluded_ledger_topic(family: str, text: str) -> bool:
    if family in BANKING_METRIC_FAMILIES:
        return False
    finance_statement_noise = (
        "income tax",
        "tax expense",
        "tax benefit",
        "tax credit",
        "unrecognized tax",
        "valuation allowance",
        "foreign-derived intangible income",
        "global intangible low-taxed income",
        "goodwill",
        "intangible asset",
        "intangible assets",
        "business combination",
        "purchase price",
        "fair value",
        "derivative",
        "debt",
        "lease",
        "interest income",
        "interest expense",
        "non-operating",
        "segment assets",
        "total assets",
        "unearned revenue",
        "deferred revenue",
        "remaining performance obligation",
        "carrying amount",
        "acquisition-related",
        "acquisitions",
        "amortization",
    )
    if family in {
        "advertising_revenue",
        "cloud_revenue",
        "data_center_revenue",
        "infrastructure_software",
        "product_revenue",
        "revenue",
        "semiconductor_solutions",
        "semiconductor_systems",
        "services_revenue",
        "subscription_revenue",
        "total_revenue",
    }:
        return _has_any(text, finance_statement_noise)
    if family in {"operating_income", "operating_cash_flow", "capital_expenditure_proxy"}:
        return _has_any(
            text,
            (
                "income tax",
                "tax expense",
                "tax benefit",
                "business combination",
                "purchase price",
                "goodwill",
                "intangible asset",
                "fair value",
                "derivative",
                "interest income",
                "interest expense",
                "non-operating",
                "acquisition-related",
            ),
        )
    return False


def _is_human_capital_ledger_topic(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    human_terms = (
        "self-identified",
        "gender",
        "race/ethnicity",
        "race and ethnicity",
        "lgbtq",
        "veteran",
        "disability",
        "women",
        "men",
        "white",
        "black",
        "hispanic",
        "asian",
        "employees",
        "workforce",
        "operating committee",
        "board of directors",
    )
    return any(term in normalized for term in human_terms)


def _banking_ledger_row_allowed(row: dict[str, Any], text: str, name_lower: str, source_signal_lower: str) -> bool:
    family = str(row.get("metric_family") or "")
    if family not in BANKING_METRIC_FAMILIES:
        return True
    if _is_human_capital_ledger_topic(text):
        return False
    if any(term in text for term in ("income tax", "tax expense", "tax benefit", "provision for income taxes")):
        return False
    required_terms = {
        "allowance_for_credit_losses": ("allowance for credit losses", "allowance for loan losses", "allowance for expected credit losses"),
        "capital_ratio": ("cet1", "common equity tier 1", "tier 1 capital", "capital ratio"),
        "deposits": ("average deposits", "total deposits", "deposit balances", "deposits"),
        "loans": ("average loans", "total loans", "loan portfolio", "loans"),
        "net_charge_offs": ("net charge-off", "net charge offs", "charge-off", "charge offs"),
        "net_interest_income": ("net interest income", "taxable-equivalent net interest income"),
        "net_interest_margin": ("net interest margin", "net yield on interest-earning assets"),
        "nonperforming_assets": ("nonperforming assets", "non-performing assets", "nonaccrual assets", "non-accrual assets"),
        "nonperforming_loans": ("nonperforming loans", "non-performing loans", "nonaccrual loans", "non-accrual loans"),
        "provision_for_credit_losses": (
            "provision for credit losses",
            "credit loss provision",
            "provision for loan losses",
            "provision for loan lease and other losses",
        ),
        "total_assets": ("total assets",),
    }
    probes = required_terms.get(family, ())
    if probes and not any(term in text for term in probes):
        return False
    if family == "deposits" and any(term in text for term in ("fdic deposit insurance fund", "deposit insurance assessment", "insurance coverage for certain deposits")):
        return False
    if family == "loans" and any(term in text for term in ("student loans", "loan-to-value", "loan to value")) and not any(
        term in text for term in ("total loans", "average loans", "loan portfolio")
    ):
        return False
    if family == "capital_ratio" and row.get("unit") != "percent":
        return False
    if family == "net_interest_margin" and row.get("unit") != "percent":
        return False
    if family in {"net_interest_income", "provision_for_credit_losses", "allowance_for_credit_losses", "deposits", "loans", "total_assets"} and row.get("unit") == "percent":
        return False
    return bool(source_signal_lower or name_lower)


def _has_revenue_measure_signal(family: str, text: str) -> bool:
    revenue_terms = ("revenue", "net sales", "sales", "收入")
    has_revenue = _has_any(text, revenue_terms)
    if family == "cloud_revenue":
        return has_revenue and _has_any(text, ("cloud", "aws", "azure", "云"))
    if family == "data_center_revenue":
        return has_revenue and _has_any(text, ("data center", "compute", "networking", "数据中心", "计算", "网络"))
    if family == "advertising_revenue":
        return has_revenue and _has_any(text, ("advertising", "ads", "广告"))
    if family == "infrastructure_software":
        return has_revenue and _has_any(text, ("infrastructure software", "software", "security", "platform", "软件", "安全"))
    if family == "product_revenue":
        return has_revenue and _has_any(text, ("product", "产品"))
    if family == "services_revenue":
        return has_revenue and _has_any(text, ("service", "services", "服务"))
    if family == "subscription_revenue":
        return has_revenue and _has_any(text, ("subscription", "订阅"))
    if family == "total_revenue":
        return has_revenue and _has_any(text, ("total", "consolidated", "总"))
    if family == "revenue":
        return has_revenue
    if family == "semiconductor_systems":
        return has_revenue and "semiconductor systems" in text
    if family == "semiconductor_solutions":
        return has_revenue and "semiconductor solutions" in text
    return True


def _is_prior_comparison_metric(row: dict[str, Any]) -> bool:
    source = str(row.get("source_text") or "").lower()
    raw = str(row.get("raw_value_text") or "").strip().lower()
    if not source or not raw or "compared to" not in source:
        return False
    candidates = [raw, raw.replace("$", "").strip()]
    compare_idx = source.find("compared to")
    for candidate in candidates:
        if not candidate:
            continue
        value_idx = source.find(candidate)
        if value_idx > compare_idx >= 0:
            return True
    return False


def _is_change_column_label(value: Any) -> bool:
    text = str(value or "").lower()
    if not text:
        return False
    return " vs " in text or " versus " in text or re.search(r"(^|[\s$%])change($|\s)", text) is not None


def _ledger_row_allowed(
    row: dict[str, Any],
    query_contract: dict[str, Any],
    context_row: dict[str, Any] | None = None,
) -> bool:
    family = str(row.get("metric_family") or "")
    ticker = str(row.get("ticker") or "").upper()
    name = " ".join(str(row.get(key) or "") for key in ("metric_name", "row_label", "column_label"))
    name_lower = name.lower()
    source_signal_lower = " ".join(
        str(row.get(key) or "")
        for key in ("metric_name", "row_label", "column_label", "table_title", "record_title", "source_text")
    ).lower()
    row_text_lower = _ledger_row_text(row, context_row).lower()
    column_label_lower = str(row.get("column_label") or "").lower()
    rules = query_contract.get("ledger_rules") or {}
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    if _is_percentage_basis_table(row_text_lower) and row.get("unit") != "percent":
        return False
    if rules.get("prefer_focus_tickers") and focus and ticker not in focus:
        return False
    allowed_families = set(str(item) for item in rules.get("allowed_metric_families") or [])
    if allowed_families and family not in allowed_families:
        return False
    if rules.get("drop_human_capital_tables") and _is_human_capital_ledger_topic(row_text_lower):
        return False
    if _is_excluded_ledger_topic(family, row_text_lower):
        return False
    if any(term in column_label_lower for term in (" over ", " vs ", " versus ")):
        return False
    if re.search(r"(^|[\s$%])change($|\s)", column_label_lower):
        return False
    if "by segment" in column_label_lower:
        return False
    if family in BANKING_METRIC_FAMILIES:
        return _banking_ledger_row_allowed(row, row_text_lower, name_lower, source_signal_lower)
    if rules.get("drop_geographic_revenue_breakdowns") and family == "revenue":
        geographic_terms = {
            "americas",
            "emea",
            "apjc",
            "china",
            "korea",
            "taiwan",
            "japan",
            "asia pacific",
            "united states",
            "europe",
            "southeast asia",
        }
        if any(term in name_lower for term in geographic_terms):
            return False
    if any(
        term in name_lower
        for term in (
            "balance as of",
            "sales of businesses",
            "acquisition of",
            "business combinations",
            "purchase price",
            "pro forma net income",
            "goodwill",
            "intangible assets",
            "sales and marketing",
            "marketing and sales",
            "cost of revenue",
            "cost of sales",
            "general and administrative",
            "as a percent of revenue",
            "percentage of total revenue",
            "tax",
            "taxes",
            "tax credit",
            "tax benefit",
            "unrecognized tax",
            "valuation allowance",
            "global intangible low-taxed income",
            "foreign-derived intangible income",
            "interest income",
            "interest expense",
            "non-operating",
        )
    ):
        return False
    if family == "research_and_development" and row.get("unit") == "percent":
        return False
    revenue_like_families = {
        "advertising_revenue",
        "cloud_revenue",
        "data_center_revenue",
        "infrastructure_software",
        "product_revenue",
        "revenue",
        "semiconductor_solutions",
        "semiconductor_systems",
        "services_revenue",
        "subscription_revenue",
        "total_revenue",
    }
    if family in revenue_like_families and row.get("unit") == "percent":
        is_growth_rate = str(row.get("metric_role") or "") == "percentage_rate" and _contains_any(
            row_text_lower,
            ("increase", "increased", "decrease", "decreased", "grew", "growth", "declined"),
        )
        if not is_growth_rate:
            return False
    if family in revenue_like_families and row.get("unit") == "usd_millions":
        value = row.get("value")
        if isinstance(value, (int, float)) and 0 <= abs(float(value)) < 1000:
            return False
    if family in revenue_like_families and "profitability" in row_text_lower and not any(
        term in name_lower for term in ("revenue", "sales", "net sales", "收入")
    ):
        return False
    if family in revenue_like_families and _is_prior_comparison_metric(row):
        return False
    if family in revenue_like_families and not _has_revenue_measure_signal(family, row_text_lower):
        return False
    is_operating_income_segment_table = "operating income by segment" in source_signal_lower
    has_operating_income_name = any(
        term in name_lower for term in ("operating income", "income from operations", "operating profit", "营业利润", "经营利润")
    )
    if family == "operating_income" and not has_operating_income_name and not is_operating_income_segment_table:
        return False
    if family == "operating_income" and any(
        term in name_lower
        for term in (
            "revenue",
            "net sales",
            "operating expense",
            "operating expenses",
            "cost of revenue",
            "cost of sales",
        )
    ):
        return False
    if family == "operating_income" and row.get("unit") == "percent":
        return False
    if family == "operating_income" and str(row.get("metric_role") or "") == "period_change_amount":
        return False
    if family == "operating_income" and any(term in name_lower for term in ("non-operating", "other operating", "interest income", "interest expense")):
        return False
    if family == "operating_income" and any(
        term in source_signal_lower
        for term in (
            "increase in operating income",
            "decrease in operating income",
            "operating income increased",
            "operating income decreased",
            "operating income grew",
            "operating income declined",
            "effect of this change",
            "benefit of",
            "impacted operating income",
            "impact on operating income",
            "foreign exchange rates",
        )
    ):
        return False
    if family == "operating_cash_flow" and "lease" in name_lower:
        return False
    if family == "operating_cash_flow" and not any(
        term in row_text_lower
        for term in (
            "net cash provided by operating activities",
            "cash provided by operating activities",
            "net cash from operations",
            "operating cash flow",
        )
    ):
        return False
    if family == "research_and_development" and any(term in name_lower for term in ("deduction", "capitalizing")):
        return False
    if family == "semiconductor_systems" and "semiconductor systems" not in row_text_lower:
        return False
    if family == "semiconductor_solutions" and "semiconductor solutions" not in row_text_lower:
        return False
    if family == "gross_margin" and row.get("unit") != "percent":
        return False
    if family == "gross_margin":
        if str(row.get("cell_kind") or "").lower() == "change_value":
            return False
        if _is_change_column_label(row.get("column_label")):
            return False
        if (
            row.get("unit") == "percent"
            and "%" in str(row.get("raw_value_text") or "")
            and str(row.get("metric_name") or "").strip().lower() == "gross margin"
            and not str(row.get("column_label") or "").strip()
        ):
            return False
        if str(row.get("metric_role") or "") == "percentage_rate" and _contains_any(
            row_text_lower,
            ("increase", "increased", "decrease", "decreased", "grew", "growth", "declined"),
        ):
            return False
        value = row.get("value")
        raw_value = str(row.get("raw_value_text") or "")
        if "%" not in raw_value and ("in millions" in source_signal_lower or "except percentages" in source_signal_lower):
            return False
        if isinstance(value, (int, float)) and abs(float(value)) > 100:
            return False
    if family == "capital_expenditure_proxy" and not any(
        term in source_signal_lower
        for term in (
            "capital expenditure",
            "capital expenditures",
            "capex",
            "purchases of property and equipment",
            "additions to property and equipment",
            "purchase of property",
            "net purchase of property",
        )
    ):
        return False
    if family == "capital_expenditure_proxy" and any(
        term in name_lower for term in ("operating activities", "investing activities", "financing activities", "free cash flow")
    ):
        return False
    if family == "capital_expenditure_proxy" and any(
        term in name_lower for term in ("accrued but not paid", "property and equipment, net", "loss on sale", "disposal")
    ):
        return False
    if family == "capital_expenditure_proxy" and row.get("unit") == "percent":
        raw = str(row.get("raw_value_text") or "").strip()
        if re.fullmatch(r"-\s*\d+(?:\.\d+)?\s*%", raw):
            return False
    if family == "revenue" and any(term in name_lower for term in ("marketing and sales", "general and administrative")):
        return False
    if family == "semiconductor_solutions" and any(term in name_lower for term in ("balance as of", "sales of businesses")):
        return False
    if family in {"total", "balance_june_30_2023"}:
        return False
    if query_contract.get("task_type") == "ai_industry_financial_trend":
        if family in {"revenue", "total_revenue"} and not any(
            term in row_text_lower
            for term in (
                "ai",
                "cloud",
                "data center",
                "semiconductor",
                "infrastructure",
                "accelerator",
                "subscription",
                "security",
                "software",
                "platform",
            )
        ):
            return False
    return True


def _ledger_row_rank(
    row: dict[str, Any],
    query_contract: dict[str, Any],
    context_row: dict[str, Any] | None = None,
) -> tuple[float, float, float, str]:
    family_priority = {
        "net_interest_income": 106,
        "net_interest_margin": 104,
        "provision_for_credit_losses": 102,
        "net_charge_offs": 100,
        "allowance_for_credit_losses": 98,
        "nonperforming_assets": 96,
        "nonperforming_loans": 96,
        "deposits": 90,
        "loans": 88,
        "capital_ratio": 86,
        "total_assets": 84,
        "credit_quality": 80,
        "data_center_revenue": 100,
        "cloud_revenue": 95,
        "semiconductor_systems": 88,
        "semiconductor_solutions": 88,
        "capital_expenditure_proxy": 82,
        "free_cash_flow_proxy": 80,
        "operating_cash_flow": 76,
        "operating_income": 74,
        "infrastructure_software": 70,
        "subscription_revenue": 68,
        "services_revenue": 66,
        "product_revenue": 64,
        "total_revenue": 60,
        "research_and_development": 62,
        "advertising_revenue": 58,
        "gross_margin": 38,
        "revenue": 32,
    }
    family = str(row.get("metric_family") or "")
    ticker = str(row.get("ticker") or "")
    focus = [str(item).upper() for item in query_contract.get("focus_tickers") or []]
    focus_bonus = float(max(0, len(focus) - focus.index(ticker)) if ticker in focus else 0)
    rerank_score = float((context_row or {}).get("rerank_score") or 0.0)
    return (float(family_priority.get(family, 0)), focus_bonus, rerank_score, str(row.get("metric_id") or ""))


def _cap_ledger_rows(rows: list[dict[str, Any]], query_contract: dict[str, Any], max_rows: int) -> list[dict[str, Any]]:
    if query_contract.get("task_type") == "ai_industry_financial_trend":
        return _cap_ai_industry_ledger_rows(rows, query_contract, max_rows)
    if _contract_has_banking_intent(query_contract):
        return _cap_banking_ledger_rows(rows, query_contract, max_rows)
    per_ticker_limit = max_rows
    per_object_limit = max_rows
    ticker_counts: Counter[str] = Counter()
    object_counts: Counter[str] = Counter()
    capped: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "")
        object_id = str(row.get("object_id") or "")
        if ticker_counts[ticker] >= per_ticker_limit:
            continue
        if object_id and object_counts[object_id] >= per_object_limit:
            continue
        capped.append(row)
        ticker_counts[ticker] += 1
        if object_id:
            object_counts[object_id] += 1
        if len(capped) >= max_rows:
            break
    return capped


def _cap_banking_ledger_rows(rows: list[dict[str, Any]], query_contract: dict[str, Any], max_rows: int) -> list[dict[str, Any]]:
    effective_max = min(max_rows, int(os.environ.get("BANKING_LEDGER_EFFECTIVE_MAX_ROWS", "48")))
    task_family_groups = []
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families = [str(item) for item in task.get("required_metric_families") or [] if str(item)]
        if families:
            task_family_groups.append(families)
    if not task_family_groups:
        task_family_groups = [[str(item)] for item in query_contract.get("metric_families") or [] if str(item)]

    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str, str]] = set()
    family_ticker_year_counts: Counter[tuple[str, str, str]] = Counter()
    per_family_ticker_year_limit = int(os.environ.get("BANKING_LEDGER_PER_FAMILY_TICKER_YEAR_LIMIT", "1"))

    def add(row: dict[str, Any]) -> bool:
        if len(selected) >= effective_max:
            return False
        key = _ledger_dedupe_key(row)
        if key in selected_keys:
            return False
        family = str(row.get("metric_family") or "")
        ticker = str(row.get("ticker") or "")
        year = str(row.get("fiscal_year") or "")
        family_ticker_year_key = (family, ticker, year)
        if family_ticker_year_counts[family_ticker_year_key] >= per_family_ticker_year_limit:
            return False
        selected.append(row)
        selected_keys.add(key)
        family_ticker_year_counts[family_ticker_year_key] += 1
        return True

    for families in task_family_groups:
        target = max(2, effective_max // max(1, len(task_family_groups)))
        before = len(selected)
        family_set = set(families)
        for row in rows:
            if str(row.get("metric_family") or "") in family_set:
                add(row)
            if len(selected) - before >= target or len(selected) >= effective_max:
                break
    for row in rows:
        add(row)
        if len(selected) >= effective_max:
            break
    return selected


def _cap_ai_industry_ledger_rows(rows: list[dict[str, Any]], query_contract: dict[str, Any], max_rows: int) -> list[dict[str, Any]]:
    effective_max = min(max_rows, int(os.environ.get("AI_LEDGER_EFFECTIVE_MAX_ROWS", "36")))
    per_ticker_limit = int(os.environ.get("AI_LEDGER_PER_TICKER_LIMIT", "5"))
    per_object_limit = 4
    per_family_limit = int(os.environ.get("AI_LEDGER_PER_FAMILY_LIMIT", "10"))
    task_family_groups = []
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families = [str(item) for item in task.get("required_metric_families") or [] if str(item)]
        if families:
            task_family_groups.append(families)
    if not task_family_groups:
        task_family_groups = [[str(item)] for item in query_contract.get("metric_families") or [] if str(item)]
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str, str]] = set()
    ticker_counts: Counter[str] = Counter()
    object_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    family_ticker_year_counts: Counter[tuple[str, str, str]] = Counter()
    per_family_ticker_year_limit = int(os.environ.get("AI_LEDGER_PER_FAMILY_TICKER_YEAR_LIMIT", "1"))

    def add(row: dict[str, Any]) -> bool:
        if len(selected) >= effective_max:
            return False
        key = _ledger_dedupe_key(row)
        if key in selected_keys:
            return False
        ticker = str(row.get("ticker") or "")
        family = str(row.get("metric_family") or "")
        year = str(row.get("fiscal_year") or "")
        object_id = str(row.get("object_id") or "")
        family_ticker_year_key = (family, ticker, year)
        if family_ticker_year_counts[family_ticker_year_key] >= per_family_ticker_year_limit:
            return False
        if ticker_counts[ticker] >= per_ticker_limit:
            return False
        if family_counts[family] >= per_family_limit:
            return False
        if object_id and object_counts[object_id] >= per_object_limit:
            return False
        selected.append(row)
        selected_keys.add(key)
        ticker_counts[ticker] += 1
        family_counts[family] += 1
        family_ticker_year_counts[family_ticker_year_key] += 1
        if object_id:
            object_counts[object_id] += 1
        return True

    for families in task_family_groups:
        target = max(2, effective_max // max(1, len(task_family_groups)))
        before = len(selected)
        for row in rows:
            if str(row.get("metric_family") or "") in set(families):
                add(row)
            if len(selected) - before >= target or len(selected) >= effective_max:
                break
    for row in rows:
        add(row)
        if len(selected) >= effective_max:
            break
    return selected


def _metric_role(name: str, unit: str) -> str:
    text = name.lower()
    if unit == "percent":
        return "percentage_rate"
    if "change" in text or "increase" in text or "decrease" in text:
        return "period_change_amount"
    if "%" in text or "margin" in text or "rate" in text:
        return "percentage_rate"
    return "total_value"


def _display_value_zh(raw: str, unit: str) -> str:
    text = str(raw or "").strip()
    if unit == "usd_millions":
        stripped = re.sub(r"\b(million|millions)\b", "", text.replace("$", ""), flags=re.I).strip()
        if stripped.startswith("(") and not stripped.endswith(")"):
            stripped = f"{stripped})"
        stripped = re.sub(r"^\(\s+", "(", stripped)
        return f"{stripped}（百万美元）"
    if unit == "usd_billions":
        stripped = re.sub(r"\b(billion|billions)\b", "", text.replace("$", ""), flags=re.I).strip()
        if stripped.startswith("(") and not stripped.endswith(")"):
            stripped = f"{stripped})"
        stripped = re.sub(r"^\(\s+", "(", stripped)
        return f"{stripped}（十亿美元）"
    if unit == "usd_thousands":
        stripped = re.sub(r"\b(thousand|thousands)\b", "", text.replace("$", ""), flags=re.I).strip()
        if stripped.startswith("(") and not stripped.endswith(")"):
            stripped = f"{stripped})"
        stripped = re.sub(r"^\(\s+", "(", stripped)
        return f"{stripped}（千美元）"
    if unit == "percent":
        return text if "%" in text else f"{text}%"
    return text


def _display_number_value_zh(value: float, unit: str) -> str:
    raw = f"{value:,.0f}"
    if unit == "usd_millions":
        return f"{raw}（百万美元）"
    if unit == "usd_billions":
        return f"{value:,.1f}（十亿美元）"
    if unit == "usd_thousands":
        return f"{raw}（千美元）"
    if unit == "percent":
        return f"{value:g}%"
    return f"{value:g}"


def _ledger_metric_id(
    case_id: Any,
    ticker: Any,
    fiscal_year: Any,
    metric_family: Any,
    metric_role: Any,
    *,
    period_role: Any = None,
    suffix: Any = None,
) -> str:
    parts = [
        str(case_id or ""),
        str(ticker or "").upper(),
        str(fiscal_year or ""),
        str(metric_family or ""),
        str(metric_role or ""),
    ]
    if period_role:
        parts.append(str(period_role))
    if suffix:
        parts.append(str(suffix))
    return "::".join(parts)


def _ledger_dedupe_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("ticker") or ""),
        str(row.get("fiscal_year") or ""),
        str(row.get("metric_family") or ""),
        "|".join(
            str(row.get(key) or "")
            for key in ("metric_role", "period_role", "period", "raw_value_text")
        ),
    )


def _dedupe_metric_ids(rows: list[dict[str, Any]]) -> None:
    used: dict[str, int] = {}
    for row in rows:
        base = str(row.get("metric_id") or "")
        used[base] = used.get(base, 0) + 1
        if used[base] > 1:
            row["metric_id"] = f"{base}::{used[base]}"


def _run_id(prompt: str) -> str:
    digest = hashlib.sha1(prompt.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return datetime.now().strftime("%Y%m%d_%H%M%S_") + digest


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


def _year_from_value(value: Any) -> int | None:
    direct = _int_or_none(value)
    if direct is not None:
        return direct
    match = re.search(r"\b(20\d{2})\b", str(value or ""))
    return int(match.group(1)) if match else None


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _config_summary(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "llm_backend": args.llm_backend,
        "model_routes": public_routes_for_backend(
            roles=["planner", "synthesizer"],
            llm_backend=args.llm_backend,
            model=args.model,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
        ),
        "base_url": args.base_url,
        "chat_completions_path": args.chat_completions_path,
        "model": args.model,
        "api_key_env": args.api_key_env or None,
        "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
        "reasoning_effort": args.reasoning_effort or None,
        "enable_thinking": bool(args.enable_thinking),
        "tickers": args.tickers or "<infer/default>",
        "years": args.years or "<infer/default>",
        "manifest_path": args.manifest_path,
        "source_gap_path": args.source_gap_path or None,
        "bm25_index_dir": args.bm25_index_dir,
        "object_bm25_index_dir": args.object_bm25_index_dir,
        "bge_model": args.bge_model,
        "bge_device": args.bge_device,
        "bge_first": args.bge_first,
        "auto_start_qwen": args.auto_start_qwen,
        "evidence_top_k": args.evidence_top_k,
        "object_top_k": args.object_top_k,
        "max_context_rows": args.max_context_rows,
        "reranker_top_k": args.reranker_top_k,
        "ledger_max_rows": args.ledger_max_rows,
        "max_tokens": args.max_tokens,
        "query_planner": args.query_planner,
        "planner_max_tokens": args.planner_max_tokens,
        "planner_timeout_s": args.planner_timeout_s,
        "output_root": args.output_root,
        "quiet": bool(args.quiet),
    }


def _run(cmd: list[str], *, stream: bool = False) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    if stream:
        subprocess.run(cmd, cwd=REPO_ROOT, check=True, env=env)
        return
    proc = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, env=env)
    if proc.returncode == 0:
        return
    if proc.stdout:
        print(proc.stdout, file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _single_jsonl(path: Path) -> dict[str, Any]:
    rows = _read_jsonl(path)
    if not rows:
        raise RuntimeError(f"No rows found in {path}")
    return rows[0]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _input_output_markdown(user_query: str, raw_output: str, answer: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Interactive SEC Agent Input/Output",
            "",
            "## User Query",
            "",
            user_query,
            "",
            "## Final Answer JSON",
            "",
            "```json",
            json.dumps(answer, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Raw Model Output",
            "",
            "```text",
            raw_output,
            "```",
            "",
        ]
    )


def _rendered_answer_markdown(
    user_query: str,
    answer: dict[str, Any],
    metric_rows: dict[str, dict[str, Any]] | None = None,
    evidence_rows: dict[str, dict[str, Any]] | None = None,
) -> str:
    lines = ["# SEC Agent Answer", ""]
    query = str(user_query or "").strip()
    if query:
        lines.extend(["## User Query", "", query, ""])
    if not isinstance(answer, dict) or not answer:
        lines.extend(["No rendered answer is available.", ""])
        return "\n".join(lines)

    direct = _clean_display_text(answer.get("direct_answer") or answer.get("summary") or "")
    thesis = _clean_display_text(answer.get("investment_thesis") or "")
    has_memo_fields = bool(
        direct
        or thesis
        or answer.get("what_changed")
        or answer.get("why_it_matters")
        or answer.get("peer_readthrough")
        or answer.get("counterarguments")
        or answer.get("watch_items")
    )
    if direct:
        lines.extend(["## 直接回答", "", direct, ""])
    if thesis:
        lines.extend(["## 投资判断", "", thesis, ""])

    metric_rows = metric_rows or {}
    evidence_rows = evidence_rows or {}
    _append_rendered_items(lines, "关键变化", answer.get("what_changed") or [], ("claim", "point", "insight"), metric_rows, evidence_rows)
    _append_rendered_items(lines, "为什么重要", answer.get("why_it_matters") or [], ("insight", "business_implication", "claim"), metric_rows, evidence_rows)
    if not has_memo_fields:
        _append_rendered_items(lines, "决策驱动", answer.get("decision_drivers") or [], ("driver_claim", "why_it_matters", "caveat"), metric_rows, evidence_rows)
        _append_rendered_items(lines, "关键要点", answer.get("key_points") or [], ("point", "claim", "insight"), metric_rows, evidence_rows)
    _append_rendered_items(lines, "同行/竞争映射", answer.get("peer_readthrough") or [], ("peer_or_group", "role", "readthrough", "caveat"), metric_rows, evidence_rows)
    _append_rendered_items(lines, "反证与风险", answer.get("counterarguments") or [], ("claim", "why_it_could_weaken_thesis", "caveat"), metric_rows, evidence_rows)
    _append_rendered_items(lines, "后续观察项", answer.get("watch_items") or [], ("item", "why_it_matters", "source_to_watch"), metric_rows, evidence_rows)

    limitations = [
        _clean_display_text(item)
        for item in (answer.get("source_limitations") or answer.get("limitations") or [])
        if _clean_display_text(item)
    ]
    if limitations:
        lines.extend(["## 证据边界", ""])
        for item in limitations[:8]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _append_rendered_items(
    lines: list[str],
    title: str,
    rows: list[Any],
    text_keys: tuple[str, ...],
    metric_rows: dict[str, dict[str, Any]] | None = None,
    evidence_rows: dict[str, dict[str, Any]] | None = None,
) -> None:
    items = [item for item in rows if isinstance(item, dict)]
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for idx, item in enumerate(items, start=1):
        parts = [_clean_display_text(item.get(key) or "") for key in text_keys]
        text = " ".join(part for part in parts if part)
        if text:
            lines.append(f"{idx}. {text}")
        metric_ids = [str(value) for value in (item.get("metric_ids") or item.get("supporting_metric_ids") or []) if str(value or "").strip()]
        evidence_ids = [str(value) for value in (item.get("evidence_ids") or item.get("supporting_evidence_ids") or []) if str(value or "").strip()]
        if metric_ids or evidence_ids:
            metric_text = "；".join(_format_metric_refs(metric_ids, metric_rows or {}))
            evidence_text = ", ".join(_format_evidence_refs(evidence_ids, evidence_rows or {}))
            support_parts = []
            if metric_text:
                support_parts.append(f"metrics: {metric_text}")
            elif metric_ids:
                support_parts.append(f"{len(metric_ids)} metric refs")
            if evidence_text:
                support_parts.append(f"evidence: {evidence_text}")
            elif evidence_ids:
                support_parts.append(f"{len(evidence_ids)} evidence refs")
            lines.append(f"   - Support: {'; '.join(support_parts)}")
    lines.append("")


if __name__ == "__main__":
    raise SystemExit(main())
