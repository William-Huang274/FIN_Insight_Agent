from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
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

import run_sec_benchmark_eval as benchmark_context  # noqa: E402
import run_sec_benchmark_vllm_synthesis_from_traces as vllm_runner  # noqa: E402
import run_sec_eval_synthesis_qwen9b_backend as qwen_adapter  # noqa: E402
from evidence.schema import EvidenceObject  # noqa: E402
from evidence.structured_extractor import extract_structured_objects  # noqa: E402
from sec_agent.claim_verifier import verify_answer_claims  # noqa: E402
from sec_agent.coverage_matrix import build_coverage_matrix  # noqa: E402
from sec_agent.graph_nodes import state_resume_report  # noqa: E402
from sec_agent.graph_state import SecAgentState  # noqa: E402
from sec_agent.llm_gateway import chat_completion_content as gateway_chat_completion_content  # noqa: E402
from sec_agent.ledger_store import query_ledger_facts  # noqa: E402
from sec_agent.model_routes import public_routes_for_backend, route_for_role  # noqa: E402
from sec_agent.project_inventory import build_project_inventory, inventory_brief, inventory_prompt  # noqa: E402
from sec_agent.query_contract import (  # noqa: E402
    INDUSTRY_SOURCE_TIER,
    MARKET_ANALYSIS_TOOLS,
    MARKET_FIELDS,
    MARKET_SOURCE_POLICY,
    MARKET_SOURCE_TIER,
    MARKET_WINDOWS,
    METRIC_FAMILY_ONTOLOGY,
    QUERY_TASK_TYPES,
    SCOPE_MODES,
    validate_query_contract,
)
from sec_agent.retrieval_plan import build_retrieval_plan  # noqa: E402
from sec_agent.research_skills import research_skill_prompt  # noqa: E402


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
PLANNER_DEFAULT_MAX_TOKENS = 3000
PLANNER_DEFAULT_RETRY_MAX_TOKENS = 4000
PLANNER_MAX_DECOMPOSED_TASKS = 5
PLANNER_TASK_QUESTION_MAX_CHARS = 80
PLANNER_MAX_SHORT_LIST_ITEMS = 6
PLANNER_MAX_CAVEAT_CHARS = 120
PLANNER_RETRIEVAL_ROUTES = {"ledger_first", "filing_text", "8k_commentary", "market_snapshot", "industry_snapshot", "risk_text"}
PLANNER_PERIOD_ROLES = {"QTD", "YTD", "TTM", "ANNUAL"}
VALID_UNITS = {"usd_millions", "usd_billions", "usd_thousands", "percent"}
INDUSTRY_SOURCE_FAMILIES = {
    "industry_macro_rates_credit",
    "industry_consumer_macro",
    "industry_energy_commodities",
    "industry_materials_commodities",
    "industry_healthcare_regulatory",
    "industry_housing_real_estate_power",
    "industry_utilities_power_demand",
    "industry_industrial_macro",
}
CONTEXT_RUNNERS = ("auto", "in_process", "subprocess")
_CONTEXT_RUNTIME_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_OBJECT_RECORDS_RUNTIME_CACHE: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = {}
_MANIFEST_INDEX_CACHE: dict[tuple[Any, ...], dict[tuple[str, int, str], dict[str, Any]]] = {}
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
LEDGER_SUPPLEMENT_FAMILY_TERMS = {
    "advertising_revenue": ("advertising", "ads"),
    "allowance_for_credit_losses": ("allowance for credit losses", "allowance for loan losses", "expected credit losses"),
    "arr_or_recurring_proxy": ("annual recurring revenue", "arr", "recurring revenue", "remaining performance obligation", "rpo"),
    "asset_quality": ("asset quality", "nonperforming", "non-performing", "charge-off", "charge off"),
    "capital_expenditure_proxy": (
        "capital expenditure",
        "capital expenditures",
        "capex",
        "property and equipment",
        "additions to property",
        "purchases of property",
    ),
    "capital_ratio": ("cet1", "common equity tier", "tier 1 capital", "capital ratio"),
    "cloud_revenue": ("cloud", "aws", "azure", "intelligent cloud", "server products and cloud services"),
    "credit_quality": ("credit quality", "credit losses", "nonperforming", "net charge-off", "net charge off"),
    "credit_risk": ("credit risk", "credit losses", "allowance for credit losses", "delinquencies"),
    "data_center_revenue": ("data center", "compute & networking", "compute and networking"),
    "deferred_revenue": ("deferred revenue", "unearned revenue", "contract liabilities"),
    "deposits": ("deposits", "average deposits", "deposit balances"),
    "free_cash_flow_proxy": ("free cash flow", "operating cash", "property and equipment", "capital expenditure"),
    "gross_margin": ("gross margin", "gross profit"),
    "infrastructure_software": ("infrastructure software", "security software", "platform revenue"),
    "loans": ("loans", "average loans", "loan portfolio"),
    "net_charge_offs": ("net charge-offs", "net charge offs", "charge-offs", "charge offs"),
    "net_interest_income": ("net interest income", "taxable-equivalent net interest income"),
    "net_interest_margin": ("net interest margin", "net yield on interest-earning assets"),
    "nonperforming_assets": ("nonperforming assets", "non-performing assets", "nonaccrual assets"),
    "nonperforming_loans": ("nonperforming loans", "non-performing loans", "nonaccrual loans"),
    "operating_cash_flow": ("operating cash", "cash provided by operating", "net cash provided by operating"),
    "operating_income": ("operating income", "income from operations", "operating profit"),
    "product_revenue": ("product revenue", "product net sales"),
    "provision_for_credit_losses": ("provision for credit losses", "credit loss provision", "provision for loan losses"),
    "research_and_development": ("research and development", "r&d"),
    "revenue": ("revenue", "net sales"),
    "rpo": ("remaining performance obligation", "remaining performance obligations", "rpo"),
    "semiconductor_solutions": ("semiconductor solutions",),
    "semiconductor_systems": ("semiconductor systems",),
    "services_revenue": ("services revenue", "service revenue", "services net sales"),
    "subscription_revenue": ("subscription and support", "subscription revenue", "subscription"),
    "total_assets": ("total assets", "consolidated assets"),
    "total_revenue": ("total revenue", "net sales", "total net sales"),
}
RESUME_NODE_ORDER = (
    "retrieve_context",
    "attach_market_snapshot_context",
    "attach_industry_snapshot_context",
    "build_runtime_ledger",
    "build_coverage_matrix",
    "build_judgment_plan",
    "synthesize_memo",
    "run_deterministic_gates",
    "render_answer",
)
SUPPORTED_RESUME_NODES = set(RESUME_NODE_ORDER)
_LEDGER_SCOPE_RECORDS_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
_LEDGER_FAMILY_PREFILTER_CACHE: dict[tuple[str, tuple[str, ...]], bool] = {}
_LEDGER_PREFILTER_TEXT_CACHE: dict[str, str] = {}
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
    parser.add_argument(
        "--market-evidence-path",
        default=os.environ.get("MARKET_EVIDENCE_PATH", ""),
        help="Optional JSONL market snapshot evidence pack generated by scripts/market/40_build_market_evidence_pack.py.",
    )
    parser.add_argument(
        "--market-snapshot-id",
        default=os.environ.get("MARKET_SNAPSHOT_ID", ""),
        help="Optional explicit market snapshot id to stamp into the Query Contract.",
    )
    parser.add_argument(
        "--market-as-of-date",
        default=os.environ.get("MARKET_AS_OF_DATE", ""),
        help="Optional explicit market snapshot as-of date to stamp into the Query Contract.",
    )
    parser.add_argument(
        "--industry-evidence-path",
        default=os.environ.get("INDUSTRY_EVIDENCE_PATH", ""),
        help="Optional JSONL industry snapshot evidence rows generated by scripts/industry/10_download_industry_source_snapshot.py.",
    )
    parser.add_argument(
        "--industry-snapshot-id",
        default=os.environ.get("INDUSTRY_SNAPSHOT_ID", ""),
        help="Optional explicit industry snapshot id to stamp into the Query Contract.",
    )
    parser.add_argument(
        "--industry-as-of-date",
        default=os.environ.get("INDUSTRY_AS_OF_DATE", ""),
        help="Optional explicit industry snapshot as-of date to stamp into the Query Contract.",
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
    parser.add_argument("--reranker-candidate-limit", type=int, default=int(os.environ.get("RERANKER_CANDIDATE_LIMIT", "800")))
    parser.add_argument("--reranker-batch-size", type=int, default=int(os.environ.get("RERANKER_BATCH_SIZE", "16")))
    parser.add_argument("--reranker-max-length", type=int, default=int(os.environ.get("RERANKER_MAX_LENGTH", "1024")))
    parser.add_argument("--reranker-doc-max-chars", type=int, default=int(os.environ.get("RERANKER_DOC_MAX_CHARS", "3000")))
    parser.add_argument("--ledger-store-path", default=os.environ.get("LEDGER_STORE_PATH", ""))
    parser.add_argument("--ledger-max-rows", type=int, default=int(os.environ.get("LEDGER_MAX_ROWS", "80")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "4000")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TEMPERATURE", "0.0")))
    parser.add_argument("--query-planner", default=os.environ.get("QUERY_PLANNER", "heuristic"), choices=("heuristic", "llm"))
    parser.add_argument("--planner-max-tokens", type=int, default=int(os.environ.get("PLANNER_MAX_TOKENS", str(PLANNER_DEFAULT_MAX_TOKENS))))
    parser.add_argument(
        "--planner-retry-max-tokens",
        type=int,
        default=int(os.environ.get("PLANNER_RETRY_MAX_TOKENS", str(PLANNER_DEFAULT_RETRY_MAX_TOKENS))),
    )
    parser.add_argument("--planner-timeout-s", type=int, default=int(os.environ.get("PLANNER_TIMEOUT_S", "180")))
    parser.add_argument("--planner-fail-closed", action="store_true", default=_env_bool("PLANNER_FAIL_CLOSED"))
    parser.add_argument("--output-root", default="eval/sec_cases/outputs/interactive_sec_agent")
    parser.add_argument("--print-config", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--auto-start-qwen", action="store_true", default=_env_bool("AUTO_START_QWEN"))
    parser.add_argument("--bge-first", action="store_true", default=_env_bool("BGE_FIRST"))
    parser.add_argument(
        "--context-runner",
        choices=CONTEXT_RUNNERS,
        default=os.environ.get("CONTEXT_RUNNER", os.environ.get("SEC_AGENT_CONTEXT_RUNNER", "auto")),
        help="Context retrieval runtime. auto keeps DeepSeek/API sessions in-process and preserves subprocess isolation for local Qwen+BGE-first.",
    )
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
    plan = build_query_plan_for_graph(args, prompt)
    tickers = plan["selected_tickers"]
    years = plan["selected_years"]
    project_inventory = plan["project_inventory"]
    contract = plan["query_contract"]
    preview_case = _build_case(prompt, tickers, years, _run_id(prompt), contract)
    retrieval_plan = build_retrieval_plan(contract, case=preview_case)
    _print_project_inventory(project_inventory, tickers, years)
    _print_query_contract(contract)
    _print_retrieval_plan(retrieval_plan)
    print(json.dumps(contract, ensure_ascii=False, indent=2))


def build_query_plan_for_graph(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    """Build the validated planner output without running retrieval or synthesis.

    This is the behavior-preserving adapter used by the LangGraph-native
    plan_query node while the rest of the legacy pipeline is migrated.
    """
    manifest_rows = _read_jsonl(REPO_ROOT / args.manifest_path)
    available = _available_scope(manifest_rows)
    tickers = _resolve_tickers(args.tickers, prompt, available)
    years = _parse_years(args.years) or _infer_years(prompt) or _default_years_for_runtime_source_policy()
    tickers, years = _filter_available(tickers, years, available)
    if not tickers or not years:
        raise RuntimeError("No available SEC filings matched inferred scope. Use /scope TICKERS YEARS.")
    project_inventory = _project_inventory(args, manifest_rows)
    query_contract = _build_query_contract(args, prompt, tickers, years, project_inventory)
    planner_trace = _detach_planner_trace(query_contract) or {}
    return {
        "query_contract": query_contract,
        "planner_trace": planner_trace,
        "project_inventory": project_inventory,
        "selected_tickers": tickers,
        "selected_years": years,
    }


def retrieve_context_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Run the existing context retrieval stage as a LangGraph node adapter."""
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for context retrieval")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = output_dir / "trace"
    cases_path = output_dir / "case.jsonl"
    retrieval_plan_path = output_dir / "retrieval_plan.json"
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for context retrieval")
    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        graph_state.get("selected_tickers")
        or query_contract.get("search_scope_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(graph_state.get("selected_years") or query_contract.get("years") or [])
    run_id = str(graph_state.get("run_id") or _run_id(prompt))
    case = _build_case(prompt, tickers, years, run_id, query_contract)
    retrieval_plan = graph_state.get("retrieval_plan") if isinstance(graph_state.get("retrieval_plan"), dict) else {}
    if not retrieval_plan:
        retrieval_plan = build_retrieval_plan(query_contract, case=case)
    case["retrieval_plan"] = retrieval_plan
    _write_jsonl(cases_path, [case])
    _write_json(retrieval_plan_path, retrieval_plan)
    context_run = _run_context(args, cases_path, trace_dir)
    trace = _single_jsonl(trace_dir / "trace_logs.jsonl")
    context_rows = [row for row in trace.get("context_rows") or [] if isinstance(row, dict)]
    return {
        "retrieval_trace": trace,
        "context_rows": context_rows,
        "context_runtime": context_run.get("context_runtime") if isinstance(context_run, dict) else {},
        "artifact_refs": {
            "case": str(cases_path.resolve()),
            "retrieval_plan": str(retrieval_plan_path.resolve()),
            "retrieved_context": str((trace_dir / "trace_logs.jsonl").resolve()),
        },
    }


def attach_market_snapshot_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Attach market snapshot evidence rows for a LangGraph node adapter."""
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    trace = graph_state.get("retrieval_trace") if isinstance(graph_state.get("retrieval_trace"), dict) else {}
    if not _contract_requests_market_snapshot(query_contract):
        return {"context_rows": context_rows, "market_snapshot_rows": []}
    existing_market_rows = [row for row in context_rows if _is_market_snapshot_context_row(row)]
    if existing_market_rows:
        return {"context_rows": context_rows, "market_snapshot_rows": existing_market_rows, "retrieval_trace": trace}

    market_rows = _load_market_context_rows(str(getattr(args, "market_evidence_path", "") or ""), query_contract)
    if not market_rows:
        return {"context_rows": context_rows, "market_snapshot_rows": [], "retrieval_trace": trace}

    augmented_rows = _append_unique_context_rows(context_rows, market_rows)
    trace = dict(trace or {})
    trace["context_rows"] = augmented_rows
    summary = dict(trace.get("context_summary") or {})
    summary["context_row_count"] = len(augmented_rows)
    summary["market_context_row_count"] = len(market_rows)
    summary["market_evidence_path"] = str(getattr(args, "market_evidence_path", "") or "")
    trace["context_summary"] = summary

    artifact_refs: dict[str, str] = {}
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if output_dir_value:
        output_dir = Path(output_dir_value).resolve()
        market_context_path = output_dir / "market_snapshot_context_rows.jsonl"
        _write_jsonl(market_context_path, market_rows)
        artifact_refs["market_snapshot_context"] = str(market_context_path.resolve())
        trace_dir = output_dir / "trace"
        if trace_dir.exists():
            _write_jsonl(trace_dir / "trace_logs.jsonl", [trace])

    return {
        "context_rows": augmented_rows,
        "market_snapshot_rows": market_rows,
        "retrieval_trace": trace,
        "artifact_refs": artifact_refs,
    }


def attach_industry_snapshot_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Attach industry snapshot evidence rows for a LangGraph node adapter."""
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    trace = graph_state.get("retrieval_trace") if isinstance(graph_state.get("retrieval_trace"), dict) else {}
    if not _contract_requests_industry_snapshot(query_contract):
        return {"context_rows": context_rows, "industry_snapshot_rows": []}
    existing_industry_rows = [row for row in context_rows if _is_industry_snapshot_context_row(row)]
    if existing_industry_rows:
        return {"context_rows": context_rows, "industry_snapshot_rows": existing_industry_rows, "retrieval_trace": trace}

    industry_rows = _load_industry_context_rows(str(getattr(args, "industry_evidence_path", "") or ""), query_contract)
    if not industry_rows:
        return {"context_rows": context_rows, "industry_snapshot_rows": [], "retrieval_trace": trace}

    augmented_rows = _append_unique_context_rows(context_rows, industry_rows)
    trace = dict(trace or {})
    trace["context_rows"] = augmented_rows
    summary = dict(trace.get("context_summary") or {})
    summary["context_row_count"] = len(augmented_rows)
    summary["industry_context_row_count"] = len(industry_rows)
    summary["industry_evidence_path"] = str(getattr(args, "industry_evidence_path", "") or "")
    trace["context_summary"] = summary

    artifact_refs: dict[str, str] = {}
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if output_dir_value:
        output_dir = Path(output_dir_value).resolve()
        industry_context_path = output_dir / "industry_snapshot_context_rows.jsonl"
        _write_jsonl(industry_context_path, industry_rows)
        artifact_refs["industry_snapshot_context"] = str(industry_context_path.resolve())
        trace_dir = output_dir / "trace"
        if trace_dir.exists():
            _write_jsonl(trace_dir / "trace_logs.jsonl", [trace])

    return {
        "context_rows": augmented_rows,
        "industry_snapshot_rows": industry_rows,
        "retrieval_trace": trace,
        "artifact_refs": artifact_refs,
    }


def build_runtime_ledger_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Build the runtime exact-value ledger for a LangGraph node adapter."""
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for runtime ledger")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for runtime ledger")
    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        graph_state.get("selected_tickers")
        or query_contract.get("search_scope_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(graph_state.get("selected_years") or query_contract.get("years") or [])
    run_id = str(graph_state.get("run_id") or _run_id(prompt))
    case = _build_case(prompt, tickers, years, run_id, query_contract)
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    ledger_rows = _build_runtime_ledger(case, context_rows, args)
    ledger_path = output_dir / "runtime_exact_value_ledger.json"
    _write_json(
        ledger_path,
        {
            "schema_version": "sec_agent_runtime_exact_value_ledger_v0.1",
            "source": "langgraph_native_adapter",
            "case_id": case["case_id"],
            "row_count": len(ledger_rows),
            "rows": ledger_rows,
        },
    )
    return {
        "runtime_ledger_rows": ledger_rows,
        "artifact_refs": {"runtime_exact_value_ledger": str(ledger_path.resolve())},
    }


def build_coverage_matrix_for_graph(_args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic evidence coverage for a LangGraph node adapter."""
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for coverage matrix")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for coverage matrix")
    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        graph_state.get("selected_tickers")
        or query_contract.get("search_scope_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(graph_state.get("selected_years") or query_contract.get("years") or [])
    run_id = str(graph_state.get("run_id") or _run_id(prompt))
    case = _build_case(prompt, tickers, years, run_id, query_contract)
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    ledger_rows = [row for row in graph_state.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
    coverage_matrix = build_coverage_matrix(
        case=case,
        query_contract=query_contract,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
        run_id=run_id,
    )
    coverage_path = output_dir / "runtime_evidence_coverage_matrix.json"
    _write_json(coverage_path, coverage_matrix)
    return {
        "coverage_matrix": coverage_matrix,
        "artifact_refs": {"evidence_coverage_matrix": str(coverage_path.resolve())},
    }


def build_judgment_plan_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic Judgment Plan for a LangGraph node adapter."""
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for judgment plan")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for judgment plan")

    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        graph_state.get("selected_tickers")
        or query_contract.get("search_scope_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(graph_state.get("selected_years") or query_contract.get("years") or [])
    run_id = str(graph_state.get("run_id") or _run_id(prompt))
    case = _build_case(prompt, tickers, years, run_id, query_contract)
    retrieval_plan = graph_state.get("retrieval_plan") if isinstance(graph_state.get("retrieval_plan"), dict) else {}
    if retrieval_plan:
        case["retrieval_plan"] = retrieval_plan

    cases_path = output_dir / "case.jsonl"
    trace_dir = output_dir / "trace"
    ledger_path = output_dir / "runtime_exact_value_ledger.json"
    coverage_path = output_dir / "runtime_evidence_coverage_matrix.json"
    plan_path = output_dir / "runtime_judgment_plan.json"
    plan_report_path = output_dir / "runtime_judgment_plan_report.json"

    _write_jsonl(cases_path, [case])
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    trace = graph_state.get("retrieval_trace") if isinstance(graph_state.get("retrieval_trace"), dict) else {}
    trace = dict(trace or {"case_id": case["case_id"]})
    trace["context_rows"] = context_rows or [row for row in trace.get("context_rows") or [] if isinstance(row, dict)]
    _write_jsonl(trace_dir / "trace_logs.jsonl", [trace])

    ledger_rows = [dict(row) for row in graph_state.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
    if not ledger_rows and ledger_path.exists():
        ledger_rows = [dict(row) for row in (_read_json(ledger_path).get("rows") or []) if isinstance(row, dict)]
    normalized_ledger_rows = []
    for row in ledger_rows:
        normalized = dict(row)
        normalized.setdefault("case_id", case["case_id"])
        normalized_ledger_rows.append(normalized)
    _write_json(
        ledger_path,
        {
            "schema_version": "sec_agent_runtime_exact_value_ledger_v0.1",
            "source": "langgraph_native_adapter",
            "case_id": case["case_id"],
            "row_count": len(normalized_ledger_rows),
            "rows": normalized_ledger_rows,
        },
    )

    coverage_matrix = graph_state.get("coverage_matrix") if isinstance(graph_state.get("coverage_matrix"), dict) else {}
    if coverage_matrix:
        _write_json(coverage_path, coverage_matrix)

    judgment_plan = None
    if normalized_ledger_rows:
        _run(
            [
                sys.executable,
                "scripts/build_sec_benchmark_judgment_plan.py",
                "--cases-path",
                str(cases_path),
                "--ledger-path",
                str(ledger_path),
                "--trace-run-dir",
                str(trace_dir),
                "--output-path",
                str(plan_path),
                "--report-path",
                str(plan_report_path),
            ]
        )
        plan_payload = _read_json(plan_path)
        plan_payload = _compact_plan_payload_for_interactive(plan_payload, case, normalized_ledger_rows)
        plan_payload = _augment_plan_payload_with_market_snapshot(plan_payload, case, coverage_matrix)
        _write_json(plan_path, plan_payload)
        judgment_plan = next(
            (item for item in plan_payload.get("plans") or [] if item.get("case_id") == case["case_id"]),
            None,
        )
    else:
        _write_json(
            plan_path,
            {
                "schema_version": "sec_agent_runtime_judgment_plan_empty_v0.1",
                "source": "langgraph_native_adapter",
                "plans": [],
                "skipped": [{"case_id": case["case_id"], "reason": "no_runtime_ledger_rows"}],
            },
        )

    artifact_refs = {
        "case": str(cases_path.resolve()),
        "runtime_exact_value_ledger": str(ledger_path.resolve()),
        "judgment_plan": str(plan_path.resolve()),
    }
    if coverage_path.exists():
        artifact_refs["evidence_coverage_matrix"] = str(coverage_path.resolve())
    if plan_report_path.exists():
        artifact_refs["judgment_plan_report"] = str(plan_report_path.resolve())
    return {"judgment_plan": judgment_plan, "artifact_refs": artifact_refs}


def synthesize_answer_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Run LLM synthesis for a LangGraph node adapter."""
    started = time.time()
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for synthesis")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for synthesis")

    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        graph_state.get("selected_tickers")
        or query_contract.get("search_scope_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(graph_state.get("selected_years") or query_contract.get("years") or [])
    run_id = str(graph_state.get("run_id") or _run_id(prompt))
    case = _build_case(prompt, tickers, years, run_id, query_contract)
    coverage_matrix = graph_state.get("coverage_matrix") if isinstance(graph_state.get("coverage_matrix"), dict) else {}
    case_for_synthesis = dict(case)
    case_for_synthesis["evidence_coverage_matrix"] = _compact_coverage_matrix_for_prompt(coverage_matrix)
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    ledger_rows = [row for row in graph_state.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
    judgment_plan = graph_state.get("judgment_plan") if isinstance(graph_state.get("judgment_plan"), dict) else None
    trace = graph_state.get("retrieval_trace") if isinstance(graph_state.get("retrieval_trace"), dict) else {}
    trace = dict(trace or {"case_id": case["case_id"], "mode": "pipeline_context"})
    trace["case_id"] = trace.get("case_id") or case["case_id"]
    trace["mode"] = trace.get("mode") or "pipeline_context"

    selected_context_rows, evidence_pack = _select_synthesis_evidence_pack(
        args=args,
        case=case_for_synthesis,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
        coverage_matrix=coverage_matrix,
    )
    case_for_synthesis["prompt_context_max_rows"] = evidence_pack["selection"]["max_rows"]
    evidence_pack_path = output_dir / "runtime_evidence_pack.json"
    _write_json(evidence_pack_path, evidence_pack)

    _ensure_llm_ready(args)
    raw_output, llm_gateway_result = _ask_llm_server(
        args,
        case_for_synthesis,
        selected_context_rows,
        ledger_rows,
        judgment_plan,
    )
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

    qwen_result["claim_status"] = "not_verified"
    qwen_result["claims"] = []
    qwen_result["unsupported_claim_count"] = 0
    qwen_result["score_notes"] = [*qwen_result.get("score_notes", []), "claim_first_pending_native_verify_node"]
    qwen_result["debug"] = {
        "user_query": prompt,
        "parse_status": parse_status,
        "raw_output_chars": len(raw_output),
        "raw_output": raw_output,
        "raw_answer": raw_answer,
        "llm_gateway": _gateway_debug(llm_gateway_result),
    }

    qwen_dir = output_dir / "qwen"
    _write_run_outputs(qwen_dir, _trace_with_context_rows(trace, selected_context_rows), qwen_result, args, started, ledger_rows)
    rendered_answer = ""
    rendered_path = qwen_dir / "rendered_answer.md"
    if rendered_path.exists():
        rendered_answer = rendered_path.read_text(encoding="utf-8")
    return {
        "memo_answer": qwen_result,
        "rendered_answer": rendered_answer,
        "artifact_refs": {
            "evidence_pack": str(evidence_pack_path.resolve()),
            "memo_answer": str((qwen_dir / "agent_outputs.jsonl").resolve()),
            "rendered_answer": str(rendered_path.resolve()),
        },
    }


def verify_claims_for_graph(_args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Run claim verification as an independent LangGraph node adapter."""
    started = time.time()
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for claim verification")
    output_dir = Path(output_dir_value).resolve()
    qwen_dir = output_dir / "qwen"
    if not qwen_dir.exists():
        raise RuntimeError("claim verification requires qwen synthesis outputs")

    memo_answer = graph_state.get("memo_answer") if isinstance(graph_state.get("memo_answer"), dict) else {}
    if not memo_answer:
        memo_answer = _load_qwen_result(qwen_dir)
    qwen_result = dict(memo_answer)
    answer = qwen_result.get("answer") if isinstance(qwen_result.get("answer"), dict) else {}
    if not answer:
        raise RuntimeError("claim verification requires memo_answer.answer")

    trace_rows = _read_jsonl(qwen_dir / "trace_logs.jsonl")
    trace = trace_rows[0] if trace_rows else {}
    state_context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    trace_context_rows = [row for row in trace.get("context_rows") or [] if isinstance(row, dict)]
    context_rows = state_context_rows or trace_context_rows
    if state_context_rows:
        trace = dict(trace or {"case_id": f"INTERACTIVE_{graph_state.get('run_id') or ''}", "mode": "pipeline_context"})
        trace["context_rows"] = state_context_rows
    elif not trace:
        trace = {"case_id": f"INTERACTIVE_{graph_state.get('run_id') or ''}", "mode": "pipeline_context"}
    ledger_rows = [row for row in graph_state.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
    if not ledger_rows:
        ledger_path = output_dir / "runtime_exact_value_ledger.json"
        if ledger_path.exists():
            ledger_rows = [row for row in (_read_json(ledger_path).get("rows") or []) if isinstance(row, dict)]
    judgment_plan = graph_state.get("judgment_plan") if isinstance(graph_state.get("judgment_plan"), dict) else None
    raw_answer = (qwen_result.get("debug") or {}).get("raw_answer") if isinstance(qwen_result.get("debug"), dict) else None
    if raw_answer is None:
        raw_rows = _read_jsonl(qwen_dir / "raw_model_outputs.jsonl")
        raw_answer = (raw_rows[0].get("raw_answer") if raw_rows and isinstance(raw_rows[0], dict) else None)

    claim_first_report = verify_answer_claims(
        answer=answer,
        raw_answer=raw_answer,
        ledger_rows=ledger_rows,
        context_rows=context_rows,
        judgment_plan=judgment_plan,
    )
    qwen_result["answer"] = claim_first_report["answer"]
    qwen_result["claims"] = claim_first_report["claims"]
    qwen_result["claim_status"] = claim_first_report["claim_status"]
    qwen_result["unsupported_claim_count"] = claim_first_report["unsupported_claim_count"]
    qwen_result["score_notes"] = [
        *[note for note in qwen_result.get("score_notes", []) if note != "claim_first_pending_native_verify_node"],
        f"claim_first_candidate_count:{claim_first_report['summary']['candidate_count']}",
        f"claim_first_promoted_count:{claim_first_report['summary']['promoted_count']}",
        f"claim_first_downgraded_count:{claim_first_report['summary']['downgraded_count']}",
        f"claim_first_rejected_count:{claim_first_report['summary']['rejected_count']}",
    ]
    if claim_first_report["unsupported_claim_count"]:
        qwen_result["failure_types"] = [*qwen_result.get("failure_types", []), "claim_first_unsupported_candidates_removed"]
    debug = dict(qwen_result.get("debug") or {})
    debug["claim_first"] = claim_first_report["summary"]
    qwen_result["debug"] = debug

    args_for_output = argparse.Namespace(
        llm_backend=str((qwen_result.get("debug") or {}).get("llm_backend") or "native_graph"),
        base_url="",
        chat_completions_path="",
        model=str((qwen_result.get("debug") or {}).get("model") or ""),
    )
    _write_run_outputs(qwen_dir, _trace_with_context_rows(trace, context_rows), qwen_result, args_for_output, started, ledger_rows)
    claim_verification = {
        "status": qwen_result.get("claim_status"),
        "claims": qwen_result.get("claims") or [],
        "unsupported_claim_count": qwen_result.get("unsupported_claim_count", 0),
        "summary": claim_first_report["summary"],
    }
    return {
        "memo_answer": qwen_result,
        "claim_verification": claim_verification,
        "artifact_refs": {
            "memo_answer": str((qwen_dir / "agent_outputs.jsonl").resolve()),
            "claim_verification": str((qwen_dir / "claim_verification.jsonl").resolve()),
            "rendered_answer": str((qwen_dir / "rendered_answer.md").resolve()),
        },
    }


def run_deterministic_gates_for_graph(_args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Run post-generation deterministic gates for a LangGraph node adapter."""
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for deterministic gates")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for deterministic gates")

    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        graph_state.get("selected_tickers")
        or query_contract.get("search_scope_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(graph_state.get("selected_years") or query_contract.get("years") or [])
    run_id = str(graph_state.get("run_id") or _run_id(prompt))
    case = _build_case(prompt, tickers, years, run_id, query_contract)

    cases_path = output_dir / "case.jsonl"
    ledger_path = output_dir / "runtime_exact_value_ledger.json"
    plan_path = output_dir / "runtime_judgment_plan.json"
    qwen_dir = output_dir / "qwen"
    gate_dir = output_dir / "post_gates"
    gate_summary_path = gate_dir / "sec_benchmark_post_gates_summary.json"
    _write_jsonl(cases_path, [case])

    ledger_rows = [dict(row) for row in graph_state.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
    if ledger_rows:
        _write_json(
            ledger_path,
            {
                "schema_version": "sec_agent_runtime_exact_value_ledger_v0.1",
                "source": "langgraph_native_adapter",
                "case_id": case["case_id"],
                "row_count": len(ledger_rows),
                "rows": [dict(row, case_id=row.get("case_id") or case["case_id"]) for row in ledger_rows],
            },
        )
    if not ledger_path.exists():
        raise RuntimeError("deterministic gates require runtime_exact_value_ledger.json")

    judgment_plan = graph_state.get("judgment_plan") if isinstance(graph_state.get("judgment_plan"), dict) else None
    if judgment_plan and not plan_path.exists():
        _write_json(
            plan_path,
            {
                "schema_version": "sec_benchmark_judgment_plan_seed_v0.1",
                "source": "langgraph_native_adapter",
                "plans": [judgment_plan],
                "skipped": [],
            },
        )
    if not qwen_dir.exists():
        raise RuntimeError("deterministic gates require qwen synthesis outputs")

    _run_post_gates(cases_path, qwen_dir, ledger_path, plan_path, gate_dir, has_plan=bool(judgment_plan))
    gate_summary = _read_json(gate_summary_path) if gate_summary_path.exists() else {}
    fail_keys = [key for key, value in gate_summary.items() if key.endswith("_gate_pass") and value is False]
    gates = {
        "status": "completed",
        "ok": not fail_keys,
        "fail_keys": fail_keys,
        "summary": gate_summary,
    }
    return {
        "deterministic_gates": gates,
        "artifact_refs": {"deterministic_gates": str(gate_summary_path.resolve())},
    }


def render_answer_for_graph(_args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Render or load the final markdown answer for a LangGraph node adapter."""
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for render")
    output_dir = Path(output_dir_value).resolve()
    qwen_dir = output_dir / "qwen"
    rendered_path = qwen_dir / "rendered_answer.md"
    rendered = ""
    if rendered_path.exists():
        rendered = rendered_path.read_text(encoding="utf-8")
    else:
        memo_answer = graph_state.get("memo_answer") if isinstance(graph_state.get("memo_answer"), dict) else {}
        answer = memo_answer.get("answer") if isinstance(memo_answer.get("answer"), dict) else {}
        if answer:
            ledger_rows = [row for row in graph_state.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
            context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
            rendered = _rendered_answer_markdown(
                user_query=str(graph_state.get("user_query") or ""),
                answer=answer,
                metric_rows={str(row.get("metric_id") or ""): row for row in ledger_rows if row.get("metric_id")},
                evidence_rows=_evidence_rows_by_id(context_rows),
            )
            _write_text(rendered_path, rendered)
    return {
        "rendered_answer": rendered,
        "artifact_refs": {"rendered_answer": str(rendered_path.resolve())},
    }


def execute_second_pass_retrieval_for_graph(args: argparse.Namespace, graph_state: dict[str, Any]) -> dict[str, Any]:
    """Execute one graph-managed second-pass retrieval from sufficiency requests."""
    started = time.perf_counter()
    output_dir_value = str(graph_state.get("output_dir") or "").strip()
    if not output_dir_value:
        raise RuntimeError("graph_state.output_dir is required for second-pass retrieval")
    output_dir = Path(output_dir_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    attempts = int(graph_state.get("second_pass_attempts") or 0)
    pass_index = attempts + 1
    second_pass_trace_path = output_dir / "second_pass_retrieval_trace.json"
    context_rows = [row for row in graph_state.get("context_rows") or [] if isinstance(row, dict)]
    report = graph_state.get("evidence_sufficiency_report") if isinstance(graph_state.get("evidence_sufficiency_report"), dict) else {}
    requests = [row for row in report.get("second_pass_retrieval_requests") or [] if isinstance(row, dict)]
    base_payload = {
        "schema_version": "sec_agent_second_pass_retrieval_trace_v0.2",
        "created_at": _utc_now_iso(),
        "run_id": str(graph_state.get("run_id") or ""),
        "triggered": False,
        "reason": "no_second_pass_retrieval_requests",
        "pass_index": pass_index,
        "input_context_row_count": len(context_rows),
        "request_count": len(requests),
        "requests": requests,
    }
    if not requests:
        base_payload["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000))
        _write_json(second_pass_trace_path, base_payload)
        return {
            "context_rows": context_rows,
            "second_pass_attempts": attempts,
            "second_pass_result": base_payload,
            "artifact_refs": {"second_pass_retrieval_trace": str(second_pass_trace_path.resolve())},
        }

    query_contract = graph_state.get("query_contract") if isinstance(graph_state.get("query_contract"), dict) else {}
    if not query_contract:
        raise RuntimeError("graph_state.query_contract is required for second-pass retrieval")
    requirements = _second_pass_requirements_from_report_requests(requests, query_contract)
    if not requirements:
        payload = {
            **base_payload,
            "reason": "no_searchable_second_pass_scope",
            "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
        }
        _write_json(second_pass_trace_path, payload)
        return {
            "context_rows": context_rows,
            "second_pass_attempts": pass_index,
            "second_pass_result": payload,
            "artifact_refs": {"second_pass_retrieval_trace": str(second_pass_trace_path.resolve())},
        }

    second_contract = _second_pass_query_contract(query_contract, requirements)
    prompt = str(graph_state.get("user_query") or "")
    tickers = _unique_upper_values(
        second_contract.get("focus_tickers")
        or graph_state.get("selected_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    years = _unique_int_values(second_contract.get("years") or graph_state.get("selected_years") or query_contract.get("years") or [])
    second_run_id = f"{graph_state.get('run_id') or _run_id(prompt)}_second_pass_{pass_index}"
    second_case = _build_case(prompt, tickers, years, second_run_id, second_contract)
    second_case["case_id"] = f"{graph_state.get('run_id') or second_case['case_id']}__second_pass_{pass_index}"
    second_case["origin"] = "langgraph_native_second_pass"
    second_case["retrieval_plan"] = build_retrieval_plan(second_contract, case=second_case)

    second_root = output_dir / f"second_pass_retrieval_{pass_index}"
    second_cases_path = second_root / "case.jsonl"
    second_trace_dir = second_root / "trace"
    _write_jsonl(second_cases_path, [second_case])
    _write_json(second_root / "query_contract.json", second_contract)
    _write_json(second_root / "retrieval_plan.json", second_case["retrieval_plan"])

    context_run = _run_context(args, second_cases_path, second_trace_dir)
    second_trace = _single_jsonl(second_trace_dir / "trace_logs.jsonl")
    second_rows = [row for row in second_trace.get("context_rows") or [] if isinstance(row, dict)]
    augmented_rows = _append_unique_context_rows(context_rows, second_rows)
    added_rows = len(augmented_rows) - len(context_rows)
    trace = graph_state.get("retrieval_trace") if isinstance(graph_state.get("retrieval_trace"), dict) else {}
    merged_trace = _merge_second_pass_trace(
        trace,
        context_rows=augmented_rows,
        second_trace=second_trace,
        second_pass_metadata={
            "triggered": True,
            "reason": "langgraph_sufficiency_request",
            "pass_index": pass_index,
            "request_count": len(requests),
            "requirement_count": len(requirements),
            "candidate_count": len(second_rows),
            "added_context_rows": added_rows,
            "second_pass_trace_dir": str(second_trace_dir.resolve()),
            "retrieval_plan_summary": (second_case.get("retrieval_plan") or {}).get("summary") or {},
        },
    )
    trace_dir = output_dir / "trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(trace_dir / "trace_logs.jsonl", [merged_trace])

    payload = {
        **base_payload,
        "triggered": True,
        "reason": "langgraph_sufficiency_request",
        "second_pass_root": str(second_root.resolve()),
        "second_pass_trace_dir": str(second_trace_dir.resolve()),
        "second_pass_case_id": second_case["case_id"],
        "retrieval_plan_summary": (second_case.get("retrieval_plan") or {}).get("summary") or {},
        "context_runtime": context_run.get("context_runtime") if isinstance(context_run, dict) else {},
        "candidate_context_row_count": len(second_rows),
        "added_context_row_count": added_rows,
        "output_context_row_count": len(augmented_rows),
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
    }
    _write_json(second_pass_trace_path, payload)
    return {
        "context_rows": augmented_rows,
        "retrieval_trace": merged_trace,
        "context_runtime": context_run.get("context_runtime") if isinstance(context_run, dict) else {},
        "second_pass_attempts": pass_index,
        "second_pass_result": payload,
        "artifact_refs": {
            "second_pass_retrieval_trace": str(second_pass_trace_path.resolve()),
            "second_pass_retrieval_case": str(second_cases_path.resolve()),
            "second_pass_retrieved_context": str((second_trace_dir / "trace_logs.jsonl").resolve()),
        },
    }


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
    planning_started_at = _utc_now_iso()
    planning_started = time.perf_counter()
    manifest_rows = _read_jsonl(REPO_ROOT / args.manifest_path)
    available = _available_scope(manifest_rows)
    tickers = _resolve_tickers(args.tickers, prompt, available)
    years = _parse_years(args.years) or _infer_years(prompt) or _default_years_for_runtime_source_policy()
    tickers, years = _filter_available(tickers, years, available)
    if not tickers or not years:
        raise RuntimeError("No available SEC filings matched inferred scope. Use /scope TICKERS YEARS.")
    project_inventory = _project_inventory(args, manifest_rows)
    query_contract = _build_query_contract(args, prompt, tickers, years, project_inventory)
    planning_elapsed_ms = int(round((time.perf_counter() - planning_started) * 1000))
    planning_finished_at = _utc_now_iso()
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
    retrieval_plan = build_retrieval_plan(query_contract, case=case)
    case["retrieval_plan"] = retrieval_plan
    _write_jsonl(cases_path, [case])
    _write_json(run_root / "query_contract.json", query_contract)
    _write_json(run_root / "retrieval_plan.json", retrieval_plan)
    if planner_trace:
        _write_json(run_root / "planner_trace.json", planner_trace)
    _write_json(run_root / "project_inventory.json", project_inventory)
    _write_run_data_fingerprint(args, run_root, project_inventory, query_contract)
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
    _add_state_artifact(
        state,
        "retrieval_plan",
        run_root / "retrieval_plan.json",
        row_count=len(retrieval_plan.get("routes") or []),
        metadata={
            "validation": (retrieval_plan.get("retrieval_plan_validation") or {}).get("status"),
            "summary": retrieval_plan.get("summary") or {},
        },
    )
    state.mark_stage(
        "plan_query",
        "completed",
        started_at=planning_started_at,
        finished_at=planning_finished_at,
        elapsed_ms=planning_elapsed_ms,
        metadata={
            "focus_tickers": query_contract.get("focus_tickers") or [],
            "metric_families": query_contract.get("metric_families") or [],
            "task_count": len([task for task in query_contract.get("decomposed_tasks") or [] if isinstance(task, dict)]),
            "retrieval_route_count": len(retrieval_plan.get("routes") or []),
            "retrieval_route_counts": (retrieval_plan.get("summary") or {}).get("route_counts") or {},
        },
    )
    state.mark_stage(
        "validate_query_contract",
        "completed",
        started_at=planning_started_at,
        finished_at=planning_finished_at,
        elapsed_ms=planning_elapsed_ms,
        metadata={
            "validation": query_contract.get("validation"),
            "timing_scope": "query_contract_build_includes_validation",
        },
    )
    stage_timing_ms = dict(state.metadata.get("stage_timing_ms") or {})
    stage_timing_ms["plan_query"] = planning_elapsed_ms
    stage_timing_ms["validate_query_contract"] = planning_elapsed_ms
    state.metadata["stage_timing_ms"] = stage_timing_ms
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
    retrieval_plan_path = run_root / "retrieval_plan.json"
    if not retrieval_plan_path.exists():
        retrieval_plan = build_retrieval_plan(query_contract, case=case)
        case["retrieval_plan"] = retrieval_plan
        _write_json(retrieval_plan_path, retrieval_plan)
        if cases_path.exists():
            _write_jsonl(cases_path, [case])
    else:
        retrieval_plan = _read_json(retrieval_plan_path)
        if not isinstance(case.get("retrieval_plan"), dict):
            case["retrieval_plan"] = retrieval_plan
            _write_jsonl(cases_path, [case])
    if "retrieval_plan" not in state.artifacts:
        _add_state_artifact(
            state,
            "retrieval_plan",
            retrieval_plan_path,
            row_count=len((retrieval_plan or {}).get("routes") or []),
            metadata={
                "validation": ((retrieval_plan or {}).get("retrieval_plan_validation") or {}).get("status"),
                "summary": (retrieval_plan or {}).get("summary") or {},
            },
        )
        _write_sec_agent_state(state)
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
    fingerprint_path = _write_run_data_fingerprint(args, run_root, {}, query_contract)
    state.metadata["run_data_fingerprint_path"] = str(fingerprint_path.resolve())
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
        trace, context_rows = _timed_stage_call(
            state,
            run_root,
            ("retrieve_context", "rerank_context"),
            lambda: _stage_retrieve_context(args, state, paths, progress),
        )
    else:
        trace, context_rows = _load_trace_context(paths)

    if _resume_should_run(start_index, "attach_market_snapshot_context"):
        trace, context_rows = _timed_stage_call(
            state,
            run_root,
            ("attach_market_snapshot_context",),
            lambda: _stage_attach_market_snapshot_context(
                args,
                state,
                case,
                paths,
                trace,
                context_rows,
                progress,
            ),
        )

    if _resume_should_run(start_index, "attach_industry_snapshot_context"):
        trace, context_rows = _timed_stage_call(
            state,
            run_root,
            ("attach_industry_snapshot_context",),
            lambda: _stage_attach_industry_snapshot_context(
                args,
                state,
                case,
                paths,
                trace,
                context_rows,
                progress,
            ),
        )

    if _resume_should_run(start_index, "build_runtime_ledger"):
        ledger_rows = _timed_stage_call(
            state,
            run_root,
            ("build_runtime_ledger",),
            lambda: _stage_build_runtime_ledger(args, state, case, paths, context_rows, progress),
        )
    else:
        ledger_rows = _load_ledger_rows(paths)

    if _resume_should_run(start_index, "build_coverage_matrix"):
        coverage_matrix = _timed_stage_call(
            state,
            run_root,
            ("build_coverage_matrix",),
            lambda: _stage_build_coverage_matrix(state, case, query_contract, paths, context_rows, ledger_rows, progress),
        )
    else:
        coverage_matrix = _read_json(paths["coverage_matrix_path"])

    second_pass_result: dict[str, Any] = {}
    if _resume_should_run(start_index, "build_coverage_matrix"):
        second_pass_result = _stage_maybe_second_pass_retrieval(
            args,
            state,
            case,
            query_contract,
            paths,
            trace or {},
            context_rows,
            coverage_matrix,
            progress,
        )
        if second_pass_result.get("triggered"):
            trace = second_pass_result.get("trace") or trace
            context_rows = second_pass_result.get("context_rows") or context_rows
            ledger_rows = _timed_stage_call(
                state,
                run_root,
                ("build_runtime_ledger",),
                lambda: _stage_build_runtime_ledger(args, state, case, paths, context_rows, progress),
            )
            coverage_matrix = _timed_stage_call(
                state,
                run_root,
                ("build_coverage_matrix",),
                lambda: _stage_build_coverage_matrix(state, case, query_contract, paths, context_rows, ledger_rows, progress),
            )
            _annotate_coverage_matrix_with_second_pass(coverage_matrix, second_pass_result)
            _write_json(paths["coverage_matrix_path"], coverage_matrix)
            coverage_summary = coverage_matrix.get("summary") or {}
            _add_state_artifact(
                state,
                "evidence_coverage_matrix",
                paths["coverage_matrix_path"],
                row_count=len(coverage_matrix.get("tasks") or []),
                metadata={"summary": coverage_summary},
            )
            _write_sec_agent_state(state)

    if _resume_should_run(start_index, "build_judgment_plan"):
        judgment_plan = _timed_stage_call(
            state,
            run_root,
            ("build_judgment_plan",),
            lambda: _stage_build_judgment_plan(state, case, paths, ledger_rows, coverage_matrix, progress),
        )
    else:
        judgment_plan = _load_judgment_plan(case, paths["plan_path"])

    if _resume_should_run(start_index, "synthesize_memo"):
        qwen_result = _timed_stage_call(
            state,
            run_root,
            ("synthesize_memo", "verify_claims"),
            lambda: _stage_synthesize_memo(
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
            ),
        )
    else:
        qwen_result = _load_qwen_result(paths["qwen_dir"])

    post_gate_ok = True
    if _resume_should_run(start_index, "run_deterministic_gates"):
        post_gate_ok = _timed_stage_call(
            state,
            run_root,
            ("run_deterministic_gates",),
            lambda: _stage_run_deterministic_gates(state, case, paths, judgment_plan, progress),
        )
    elif paths["gate_summary_path"].exists():
        gate_summary = _read_json(paths["gate_summary_path"])
        fail_keys = [key for key, value in gate_summary.items() if key.endswith("_gate_pass") and value is False]
        post_gate_ok = not fail_keys

    if _resume_should_run(start_index, "render_answer"):
        _timed_stage_call(
            state,
            run_root,
            ("render_answer",),
            lambda: _stage_render_answer(state, paths),
        )

    state.status = "completed" if post_gate_ok else "completed_with_gate_failures"
    state.metadata["total_elapsed_sec"] = round(time.time() - started, 4)
    performance_path = _write_run_performance_report(state, run_root, started, paths, qwen_result, post_gate_ok)
    state.metadata["run_performance_path"] = str(performance_path.resolve())
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
        "retrieval_plan_path": run_root / "retrieval_plan.json",
        "ledger_path": run_root / "runtime_exact_value_ledger.json",
        "coverage_matrix_path": run_root / "runtime_evidence_coverage_matrix.json",
        "second_pass_trace_path": run_root / "second_pass_retrieval_trace.json",
        "evidence_pack_path": run_root / "runtime_evidence_pack.json",
        "market_context_path": run_root / "market_snapshot_context_rows.jsonl",
        "industry_context_path": run_root / "industry_snapshot_context_rows.jsonl",
        "plan_path": run_root / "runtime_judgment_plan.json",
        "plan_report_path": run_root / "runtime_judgment_plan_report.json",
        "gate_summary_path": gate_dir / "sec_benchmark_post_gates_summary.json",
        "rendered_path": qwen_dir / "rendered_answer.md",
        "run_data_fingerprint_path": run_root / "run_data_fingerprint.json",
        "run_performance_path": run_root / "run_performance.json",
    }


def _resume_node_index(node: str) -> int:
    if node not in RESUME_NODE_ORDER:
        raise RuntimeError(f"Unsupported resume node: {node}")
    return RESUME_NODE_ORDER.index(node)


def _resume_should_run(start_index: int, node: str) -> bool:
    return RESUME_NODE_ORDER.index(node) >= start_index


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timed_stage_call(
    state: SecAgentState,
    run_root: Path,
    stage_names: tuple[str, ...],
    fn: Any,
) -> Any:
    started_at = _utc_now_iso()
    start_index = len(state.stages)
    start = time.perf_counter()
    result = fn()
    elapsed_ms = int(round((time.perf_counter() - start) * 1000))
    finished_at = _utc_now_iso()
    _stamp_stage_records(
        state,
        start_index=start_index,
        stage_names=set(stage_names),
        started_at=started_at,
        finished_at=finished_at,
        elapsed_ms=elapsed_ms,
    )
    _write_sec_agent_state(state)
    return result


def _stamp_stage_records(
    state: SecAgentState,
    *,
    start_index: int,
    stage_names: set[str],
    started_at: str,
    finished_at: str,
    elapsed_ms: int,
) -> None:
    stage_timing_ms = dict(state.metadata.get("stage_timing_ms") or {})
    for stage in state.stages[start_index:]:
        if stage.name not in stage_names:
            continue
        if not stage.started_at:
            stage.started_at = started_at
        if not stage.finished_at:
            stage.finished_at = finished_at
        if stage.elapsed_ms is None:
            stage.elapsed_ms = elapsed_ms
        stage_timing_ms[stage.name] = stage.elapsed_ms
    if stage_timing_ms:
        state.metadata["stage_timing_ms"] = stage_timing_ms


def _context_runner_mode(args: argparse.Namespace) -> str:
    requested = str(getattr(args, "context_runner", "auto") or "auto")
    if requested != "auto":
        return requested
    if bool(getattr(args, "bge_first", False)) and _uses_local_qwen(args):
        return "subprocess"
    return "in_process"


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
    context_runner = _context_runner_mode(args)
    progress(
        f"[1/5] retrieving SEC context with BM25 + BGE-M3 rerank on {args.bge_device} ({context_runner}) ...",
        user_message=f"[1/5] retrieving and reranking SEC evidence on {args.bge_device} ...",
    )
    context_run = _run_context(args, paths["cases_path"], paths["trace_dir"])
    progress("[1/5] retrieval complete.", user_message="[1/5] retrieval complete.")
    trace, context_rows = _load_trace_context(paths)
    context_runtime = context_run.get("context_runtime") if isinstance(context_run, dict) else {}
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
            "context_runner": context_runner,
            **(context_runtime if isinstance(context_runtime, dict) else {}),
        },
    )
    state.mark_stage(
        "retrieve_context",
        "completed",
        metadata={
            "context_row_count": len(context_rows),
            "trace_dir": str(paths["trace_dir"].resolve()),
            "context_runner": context_runner,
            **(context_runtime if isinstance(context_runtime, dict) else {}),
        },
    )
    state.mark_stage(
        "rerank_context",
        "completed",
        metadata={
            "bge_device": args.bge_device,
            "reranker_top_k": args.reranker_top_k,
            "context_runner": context_runner,
            **(context_runtime if isinstance(context_runtime, dict) else {}),
        },
    )
    _write_sec_agent_state(state)
    return trace, context_rows


def _stage_attach_market_snapshot_context(
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    trace: dict[str, Any],
    context_rows: list[dict[str, Any]],
    progress: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    if not _contract_requests_market_snapshot(query_contract):
        state.mark_stage("attach_market_snapshot_context", "skipped", metadata={"reason": "market_snapshot_not_requested"})
        _write_sec_agent_state(state)
        return trace, context_rows
    if any(_is_market_snapshot_context_row(row) for row in context_rows):
        state.mark_stage(
            "attach_market_snapshot_context",
            "completed",
            metadata={"market_context_row_count": len([row for row in context_rows if _is_market_snapshot_context_row(row)])},
        )
        _write_sec_agent_state(state)
        return trace, context_rows
    market_rows = _load_market_context_rows(args.market_evidence_path, query_contract)
    if not market_rows:
        progress(
            "[market] market_snapshot requested but no matching evidence rows were provided.",
            user_message="[market] requested; no local snapshot evidence rows matched.",
        )
        state.mark_stage(
            "attach_market_snapshot_context",
            "completed_with_gaps",
            metadata={"market_evidence_path": args.market_evidence_path or "", "market_context_row_count": 0},
        )
        _write_sec_agent_state(state)
        return trace, context_rows

    progress(
        f"[market] attaching {len(market_rows)} market snapshot context row(s) ...",
        user_message=f"[market] attaching {len(market_rows)} market snapshot row(s) ...",
    )
    augmented_rows = _append_unique_context_rows(context_rows, market_rows)
    trace = dict(trace or {})
    trace["context_rows"] = augmented_rows
    summary = dict(trace.get("context_summary") or {})
    summary["context_row_count"] = len(augmented_rows)
    summary["market_context_row_count"] = len(market_rows)
    summary["market_evidence_path"] = args.market_evidence_path or ""
    trace["context_summary"] = summary
    if paths["trace_dir"].exists():
        _write_jsonl(paths["trace_dir"] / "trace_logs.jsonl", [trace])
    _write_jsonl(paths["market_context_path"], market_rows)
    _add_state_artifact(
        state,
        "market_snapshot_context",
        paths["market_context_path"],
        row_count=len(market_rows),
        metadata={
            "market_evidence_path": args.market_evidence_path or "",
            "snapshot_ids": sorted({str(row.get("snapshot_id") or "") for row in market_rows if row.get("snapshot_id")}),
            "as_of_dates": sorted({str(row.get("as_of_date") or "") for row in market_rows if row.get("as_of_date")}),
        },
    )
    state.mark_stage(
        "attach_market_snapshot_context",
        "completed",
        metadata={"market_context_row_count": len(market_rows), "context_row_count": len(augmented_rows)},
    )
    _write_sec_agent_state(state)
    return trace, augmented_rows


def _stage_attach_industry_snapshot_context(
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    trace: dict[str, Any],
    context_rows: list[dict[str, Any]],
    progress: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    if not _contract_requests_industry_snapshot(query_contract):
        state.mark_stage("attach_industry_snapshot_context", "skipped", metadata={"reason": "industry_snapshot_not_requested"})
        _write_sec_agent_state(state)
        return trace, context_rows
    if any(_is_industry_snapshot_context_row(row) for row in context_rows):
        state.mark_stage(
            "attach_industry_snapshot_context",
            "completed",
            metadata={"industry_context_row_count": len([row for row in context_rows if _is_industry_snapshot_context_row(row)])},
        )
        _write_sec_agent_state(state)
        return trace, context_rows
    industry_rows = _load_industry_context_rows(args.industry_evidence_path, query_contract)
    if not industry_rows:
        progress(
            "[industry] industry_snapshot requested but no matching evidence rows were provided.",
            user_message="[industry] requested; no local industry evidence rows matched.",
        )
        state.mark_stage(
            "attach_industry_snapshot_context",
            "completed_with_gaps",
            metadata={"industry_evidence_path": args.industry_evidence_path or "", "industry_context_row_count": 0},
        )
        _write_sec_agent_state(state)
        return trace, context_rows

    progress(
        f"[industry] attaching {len(industry_rows)} industry snapshot context row(s) ...",
        user_message=f"[industry] attaching {len(industry_rows)} industry context row(s) ...",
    )
    augmented_rows = _append_unique_context_rows(context_rows, industry_rows)
    trace = dict(trace or {})
    trace["context_rows"] = augmented_rows
    summary = dict(trace.get("context_summary") or {})
    summary["context_row_count"] = len(augmented_rows)
    summary["industry_context_row_count"] = len(industry_rows)
    summary["industry_evidence_path"] = args.industry_evidence_path or ""
    trace["context_summary"] = summary
    if paths["trace_dir"].exists():
        _write_jsonl(paths["trace_dir"] / "trace_logs.jsonl", [trace])
    _write_jsonl(paths["industry_context_path"], industry_rows)
    _add_state_artifact(
        state,
        "industry_snapshot_context",
        paths["industry_context_path"],
        row_count=len(industry_rows),
        metadata={
            "industry_evidence_path": args.industry_evidence_path or "",
            "source_families": sorted({str(row.get("source_family") or "") for row in industry_rows if row.get("source_family")}),
            "as_of_dates": sorted({str(row.get("as_of_date") or "") for row in industry_rows if row.get("as_of_date")}),
        },
    )
    state.mark_stage(
        "attach_industry_snapshot_context",
        "completed",
        metadata={"industry_context_row_count": len(industry_rows), "context_row_count": len(augmented_rows)},
    )
    _write_sec_agent_state(state)
    return trace, augmented_rows


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


def _stage_maybe_second_pass_retrieval(
    args: argparse.Namespace,
    state: SecAgentState,
    case: dict[str, Any],
    query_contract: dict[str, Any],
    paths: dict[str, Path],
    trace: dict[str, Any],
    context_rows: list[dict[str, Any]],
    coverage_matrix: dict[str, Any],
    progress: Any,
) -> dict[str, Any]:
    started = time.perf_counter()
    requirements = _second_pass_requirements_from_coverage(query_contract, coverage_matrix)
    base_payload = {
        "schema_version": "sec_agent_second_pass_retrieval_trace_v0.1",
        "created_at": _utc_now_iso(),
        "run_id": state.run_id,
        "triggered": False,
        "reason": "coverage_sufficient_or_no_searchable_gap",
        "input_context_row_count": len(context_rows),
        "requirement_count": len(requirements),
        "requirements": requirements,
    }
    if not requirements:
        base_payload["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000))
        _write_json(paths["second_pass_trace_path"], base_payload)
        state.metadata["second_pass_retrieval_trace_path"] = str(paths["second_pass_trace_path"].resolve())
        state.mark_stage(
            "second_pass_retrieval",
            "skipped",
            elapsed_ms=base_payload["elapsed_ms"],
            metadata={"reason": base_payload["reason"], "requirement_count": 0},
        )
        _write_sec_agent_state(state)
        return base_payload

    progress(
        f"[coverage] second-pass retrieval triggered for {len(requirements)} scoped requirement(s) ...",
        user_message=f"[coverage] expanding retrieval for {len(requirements)} evidence gap(s) ...",
    )
    second_contract = _second_pass_query_contract(query_contract, requirements)
    tickers = _unique_upper_values(second_contract.get("focus_tickers") or state.selected_tickers)
    years = _unique_int_values(second_contract.get("years") or state.selected_years)
    second_run_id = f"{state.run_id}_second_pass"
    second_case = _build_case(state.user_query, tickers, years, second_run_id, second_contract)
    second_case["case_id"] = f"{case.get('case_id') or state.run_id}__second_pass"
    second_case["origin"] = "coverage_matrix_second_pass"
    second_case["retrieval_plan"] = build_retrieval_plan(second_contract, case=second_case)

    second_root = paths["second_pass_trace_path"].parent / "second_pass_retrieval"
    second_cases_path = second_root / "case.jsonl"
    second_trace_dir = second_root / "trace"
    _write_jsonl(second_cases_path, [second_case])
    _write_json(second_root / "query_contract.json", second_contract)
    _write_json(second_root / "retrieval_plan.json", second_case["retrieval_plan"])

    context_run = _run_context(args, second_cases_path, second_trace_dir)
    second_trace = _single_jsonl(second_trace_dir / "trace_logs.jsonl")
    second_rows = [row for row in second_trace.get("context_rows") or [] if isinstance(row, dict)]
    augmented_rows = _append_unique_context_rows(context_rows, second_rows)
    added_rows = len(augmented_rows) - len(context_rows)
    merged_trace = _merge_second_pass_trace(
        trace,
        context_rows=augmented_rows,
        second_trace=second_trace,
        second_pass_metadata={
            "triggered": True,
            "reason": "coverage_matrix_searchable_in_current_inventory",
            "requirement_count": len(requirements),
            "candidate_count": len(second_rows),
            "added_context_rows": added_rows,
            "second_pass_trace_dir": str(second_trace_dir.resolve()),
            "retrieval_plan_summary": (second_case.get("retrieval_plan") or {}).get("summary") or {},
        },
    )
    _write_jsonl(paths["trace_dir"] / "trace_logs.jsonl", [merged_trace])

    payload = {
        **base_payload,
        "triggered": True,
        "reason": "coverage_matrix_searchable_in_current_inventory",
        "second_pass_root": str(second_root.resolve()),
        "second_pass_trace_dir": str(second_trace_dir.resolve()),
        "second_pass_case_id": second_case["case_id"],
        "retrieval_plan_summary": (second_case.get("retrieval_plan") or {}).get("summary") or {},
        "context_runtime": context_run.get("context_runtime") if isinstance(context_run, dict) else {},
        "candidate_context_row_count": len(second_rows),
        "added_context_row_count": added_rows,
        "output_context_row_count": len(augmented_rows),
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
    }
    _write_json(paths["second_pass_trace_path"], payload)
    state.metadata["second_pass_retrieval_trace_path"] = str(paths["second_pass_trace_path"].resolve())
    state.metadata["second_pass_retrieval"] = {
        "triggered": True,
        "requirement_count": len(requirements),
        "candidate_context_row_count": len(second_rows),
        "added_context_row_count": added_rows,
    }
    state.mark_stage(
        "second_pass_retrieval",
        "completed",
        elapsed_ms=payload["elapsed_ms"],
        metadata={
            "requirement_count": len(requirements),
            "candidate_context_row_count": len(second_rows),
            "added_context_row_count": added_rows,
            "trace_path": str(paths["second_pass_trace_path"].resolve()),
        },
    )
    _write_sec_agent_state(state)
    progress(
        f"[coverage] second-pass retrieval added {added_rows} new context row(s).",
        user_message=f"[coverage] expanded evidence by {added_rows} row(s).",
    )
    return {**payload, "trace": merged_trace, "context_rows": augmented_rows}


def _second_pass_requirements_from_coverage(
    query_contract: dict[str, Any],
    coverage_matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = coverage_matrix.get("summary") if isinstance(coverage_matrix.get("summary"), dict) else {}
    if summary.get("coverage_complete") is True and summary.get("primary_task_support_complete") is True:
        return []
    contract_tickers = _unique_upper_values(
        query_contract.get("search_scope_tickers")
        or (query_contract.get("scope") or {}).get("universe_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    contract_years = _unique_int_values(query_contract.get("years") or (query_contract.get("scope") or {}).get("years") or [])
    contract_forms = _unique_form_values(query_contract.get("filing_types") or (query_contract.get("scope") or {}).get("filing_types") or [])
    contract_tiers = _unique_compact_strings(query_contract.get("source_tiers") or (query_contract.get("scope") or {}).get("source_tiers") or [])
    source_gaps = [gap for gap in coverage_matrix.get("source_coverage_gaps") or [] if isinstance(gap, dict)]
    requirements: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for index, task in enumerate(coverage_matrix.get("tasks") or [], start=1):
        if not isinstance(task, dict):
            continue
        support_level = str(task.get("support_level") or "")
        if support_level not in {"partial", "insufficient"}:
            continue
        req = _second_pass_requirement_for_task(
            task,
            index=index,
            query_contract=query_contract,
            contract_tickers=contract_tickers,
            contract_years=contract_years,
            contract_forms=contract_forms,
            contract_tiers=contract_tiers,
            source_gaps=source_gaps,
        )
        if not req:
            continue
        key = (
            tuple(req.get("tickers") or []),
            tuple(req.get("years") or []),
            tuple(req.get("filing_types") or []),
            tuple(req.get("source_tiers") or []),
            tuple(req.get("metric_families") or []),
            tuple(req.get("evidence_routes") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        requirements.append(req)
        if len(requirements) >= 8:
            break
    return requirements


def _second_pass_requirements_from_report_requests(
    requests: list[dict[str, Any]],
    query_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    contract_tickers = _unique_upper_values(
        query_contract.get("search_scope_tickers")
        or (query_contract.get("scope") or {}).get("universe_tickers")
        or query_contract.get("focus_tickers")
        or []
    )
    contract_years = _unique_int_values(query_contract.get("years") or (query_contract.get("scope") or {}).get("years") or [])
    contract_forms = _unique_form_values(query_contract.get("filing_types") or (query_contract.get("scope") or {}).get("filing_types") or [])
    contract_tiers = _unique_compact_strings(query_contract.get("source_tiers") or (query_contract.get("scope") or {}).get("source_tiers") or [])
    requirements: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, request in enumerate(requests, start=1):
        tickers = [
            ticker
            for ticker in _unique_upper_values(request.get("tickers") or request.get("missing_tickers") or contract_tickers)
            if not contract_tickers or ticker in set(contract_tickers)
        ]
        years = [
            year
            for year in _unique_int_values(request.get("years") or request.get("missing_years") or contract_years)
            if not contract_years or year in set(contract_years)
        ]
        forms = _unique_form_values(request.get("filing_types") or request.get("missing_filing_types") or contract_forms)
        tiers = _unique_compact_strings(request.get("source_tiers") or request.get("missing_source_tiers") or contract_tiers)
        tiers = [tier for tier in tiers if tier != MARKET_SOURCE_TIER]
        forms = _second_pass_forms_for_tiers(forms, tiers)
        tiers = _second_pass_tiers_for_forms(tiers, forms)
        metric_families = _unique_compact_strings(
            request.get("metric_families")
            or request.get("missing_metric_families")
            or query_contract.get("metric_families")
            or []
        )[:8]
        routes = _unique_compact_strings(
            request.get("evidence_routes")
            or _second_pass_routes(
                question=str(request.get("reason") or ""),
                filing_types=forms,
                source_tiers=tiers,
                metric_families=metric_families,
            )
        )
        if not tickers or not years or not forms or not tiers or not routes:
            continue
        key = (tuple(tickers), tuple(years), tuple(forms), tuple(tiers), tuple(metric_families), tuple(routes))
        if key in seen:
            continue
        seen.add(key)
        requirements.append(
            {
                "requirement_id": str(request.get("request_id") or f"second_pass_report_{index}"),
                "task_id": str(request.get("task_id") or f"second_pass_task_{index}"),
                "question_zh": "补查覆盖矩阵标记的缺口证据。",
                "priority": "primary",
                "analysis_intent": "coverage_gap_expansion",
                "tickers": tickers[:24],
                "peer_tickers": [],
                "years": years,
                "filing_types": forms,
                "source_tiers": tiers,
                "metric_families": metric_families,
                "period_roles": ["ANNUAL", "YTD", "QTD", "TTM"],
                "evidence_routes": routes,
                "section_hints": _second_pass_section_hints(routes),
                "market_fields": [],
                "candidate_budget": 0,
                "rerank_budget": 0,
                "second_pass_policy": {
                    "enabled": False,
                    "max_passes": 0,
                    "trigger": "already_in_second_pass",
                    "external_gap_behavior": "report_boundary_without_autosearch",
                },
                "coverage_requirements": {
                    "tickers": tickers[:24],
                    "years": years,
                    "filing_types": forms,
                    "source_tiers": tiers,
                    "metric_families": metric_families,
                    "period_roles": ["ANNUAL", "YTD", "QTD", "TTM"],
                    "market_fields": [],
                },
            }
        )
        if len(requirements) >= 8:
            break
    return requirements


def _second_pass_requirement_for_task(
    task: dict[str, Any],
    *,
    index: int,
    query_contract: dict[str, Any],
    contract_tickers: list[str],
    contract_years: list[int],
    contract_forms: list[str],
    contract_tiers: list[str],
    source_gaps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    missing_tickers = _unique_upper_values([*(task.get("missing_tickers") or []), *(task.get("missing_peer_tickers") or [])])
    required_tickers = _unique_upper_values([*(task.get("required_tickers") or []), *(task.get("peer_tickers") or [])])
    target_tickers = [ticker for ticker in (missing_tickers or required_tickers or contract_tickers) if not contract_tickers or ticker in set(contract_tickers)]
    missing_years = _unique_int_values(task.get("missing_years") or [])
    target_years = [year for year in (missing_years or contract_years) if not contract_years or year in set(contract_years)]
    missing_forms = _unique_form_values(task.get("missing_filing_types") or [])
    target_forms = [form for form in (missing_forms or contract_forms) if form in {"10-K", "10-Q", "8-K"}]
    missing_tiers = _unique_compact_strings(task.get("missing_source_tiers") or [])
    non_market_tiers = [tier for tier in contract_tiers if tier != MARKET_SOURCE_TIER]
    target_tiers = _second_pass_tiers_for_forms(
        [tier for tier in (missing_tiers or non_market_tiers) if tier != MARKET_SOURCE_TIER],
        target_forms,
    )
    target_forms = _second_pass_forms_for_tiers(target_forms, target_tiers)
    missing_families = _unique_compact_strings(task.get("missing_metric_families") or [])
    required_families = _unique_compact_strings(task.get("required_metric_families") or query_contract.get("metric_families") or [])
    metric_families = (missing_families or required_families)[:8]
    searchable_tickers = [
        ticker
        for ticker in target_tickers
        if not _source_gap_blocks_all_scope(source_gaps, ticker, target_years, target_forms, target_tiers)
    ]
    if not searchable_tickers or not target_years or not target_forms or not target_tiers:
        return None
    has_searchable_gap = bool(
        missing_tickers
        or missing_years
        or missing_forms
        or missing_tiers
        or missing_families
        or task.get("support_level") == "insufficient"
    )
    if not has_searchable_gap:
        return None
    routes = _second_pass_routes(
        question=str(task.get("question_zh") or ""),
        filing_types=target_forms,
        source_tiers=target_tiers,
        metric_families=metric_families,
    )
    if not routes:
        return None
    return {
        "requirement_id": f"second_pass_{task.get('task_id') or index}",
        "task_id": str(task.get("task_id") or f"task_{index}"),
        "question_zh": _second_pass_question(task),
        "priority": str(task.get("priority") or "supporting"),
        "analysis_intent": "coverage_gap_expansion",
        "tickers": searchable_tickers[:24],
        "peer_tickers": [],
        "years": target_years,
        "filing_types": target_forms,
        "source_tiers": target_tiers,
        "metric_families": metric_families,
        "period_roles": ["ANNUAL", "YTD", "QTD", "TTM"],
        "evidence_routes": routes,
        "section_hints": _second_pass_section_hints(routes),
        "market_fields": [],
        "candidate_budget": 0,
        "rerank_budget": 0,
        "second_pass_policy": {
            "enabled": False,
            "max_passes": 0,
            "trigger": "already_in_second_pass",
            "external_gap_behavior": "report_boundary_without_autosearch",
        },
        "coverage_requirements": {
            "tickers": searchable_tickers[:24],
            "years": target_years,
            "filing_types": target_forms,
            "source_tiers": target_tiers,
            "metric_families": metric_families,
            "period_roles": ["ANNUAL", "YTD", "QTD", "TTM"],
            "market_fields": [],
        },
    }


def _second_pass_query_contract(query_contract: dict[str, Any], requirements: list[dict[str, Any]]) -> dict[str, Any]:
    contract = dict(query_contract)
    contract["planner"] = "coverage_matrix_second_pass"
    contract["planner_source"] = "deterministic_coverage_gap_compiler"
    contract["evidence_requirements"] = requirements
    contract["decomposed_tasks"] = [
        {
            "task_id": req.get("task_id"),
            "priority": req.get("priority"),
            "question_zh": req.get("question_zh"),
            "required_tickers": req.get("tickers") or [],
            "required_metric_families": req.get("metric_families") or [],
        }
        for req in requirements
    ]
    contract["focus_tickers"] = _unique_upper_values(ticker for req in requirements for ticker in req.get("tickers") or [])
    contract["search_scope_tickers"] = _unique_upper_values(
        query_contract.get("search_scope_tickers") or contract["focus_tickers"]
    )
    contract["years"] = _unique_int_values(year for req in requirements for year in req.get("years") or [])
    contract["filing_types"] = _unique_form_values(form for req in requirements for form in req.get("filing_types") or [])
    contract["source_tiers"] = _unique_compact_strings(tier for req in requirements for tier in req.get("source_tiers") or [])
    contract["metric_families"] = _unique_compact_strings(family for req in requirements for family in req.get("metric_families") or [])
    return contract


def _merge_second_pass_trace(
    trace: dict[str, Any],
    *,
    context_rows: list[dict[str, Any]],
    second_trace: dict[str, Any],
    second_pass_metadata: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(trace or {})
    merged["context_rows"] = context_rows
    summary = dict(merged.get("context_summary") or {})
    summary["context_row_count"] = len(context_rows)
    summary["second_pass_added_context_rows"] = second_pass_metadata.get("added_context_rows", 0)
    merged["context_summary"] = summary
    policy = dict(merged.get("context_policy") or {})
    policy["second_pass_retrieval"] = second_pass_metadata
    policy["second_pass_context_policy"] = second_trace.get("context_policy") or {}
    merged["context_policy"] = policy
    merged["context_preview"] = [
        {
            "source_kind": row.get("source_kind"),
            "ticker": row.get("ticker"),
            "fiscal_year": row.get("fiscal_year"),
            "section": row.get("section"),
            "object_id": row.get("object_id"),
            "evidence_id": row.get("evidence_id"),
            "retrieval_route": row.get("retrieval_route"),
        }
        for row in context_rows[:12]
    ]
    return merged


def _annotate_coverage_matrix_with_second_pass(coverage_matrix: dict[str, Any], second_pass_result: dict[str, Any]) -> None:
    metadata = {
        "triggered": bool(second_pass_result.get("triggered")),
        "reason": second_pass_result.get("reason") or "",
        "requirement_count": second_pass_result.get("requirement_count", 0),
        "candidate_context_row_count": second_pass_result.get("candidate_context_row_count", 0),
        "added_context_row_count": second_pass_result.get("added_context_row_count", 0),
        "trace_path": second_pass_result.get("second_pass_trace_dir") or "",
    }
    coverage_matrix["second_pass_retrieval"] = metadata
    summary = dict(coverage_matrix.get("summary") or {})
    summary["second_pass_triggered"] = metadata["triggered"]
    summary["second_pass_added_context_rows"] = metadata["added_context_row_count"]
    coverage_matrix["summary"] = summary


def _second_pass_routes(
    *,
    question: str,
    filing_types: list[str],
    source_tiers: list[str],
    metric_families: list[str],
) -> list[str]:
    routes: list[str] = []
    forms = set(filing_types)
    tiers = set(source_tiers)
    text = question.lower()
    if metric_families and ({"10-K", "10-Q"} & forms or "primary_sec_filing" in tiers):
        routes.extend(["ledger_first", "filing_text"])
    if "8-K" in forms or "company_authored_unaudited_sec_filing" in tiers:
        routes.append("8k_commentary")
    if any(term in text for term in ("risk", "uncertainty", "风险", "反证", "不确定")):
        routes.append("risk_text")
    if not routes and ({"10-K", "10-Q"} & forms or "primary_sec_filing" in tiers):
        routes.append("filing_text")
    return _unique_compact_strings(routes)


def _second_pass_tiers_for_forms(source_tiers: list[str], filing_types: list[str]) -> list[str]:
    forms = set(filing_types)
    tiers = [tier for tier in source_tiers if tier != MARKET_SOURCE_TIER]
    if "8-K" not in forms:
        tiers = [tier for tier in tiers if tier != "company_authored_unaudited_sec_filing"]
    if not ({"10-K", "10-Q"} & forms):
        tiers = [tier for tier in tiers if tier != "primary_sec_filing"]
    return _unique_compact_strings(tiers)


def _second_pass_forms_for_tiers(filing_types: list[str], source_tiers: list[str]) -> list[str]:
    tiers = set(source_tiers)
    forms = list(filing_types)
    if "company_authored_unaudited_sec_filing" in tiers and "primary_sec_filing" not in tiers:
        forms = [form for form in forms if form == "8-K"]
    elif "primary_sec_filing" in tiers and "company_authored_unaudited_sec_filing" not in tiers:
        forms = [form for form in forms if form in {"10-K", "10-Q"}]
    return _unique_form_values(forms)


def _second_pass_question(task: dict[str, Any]) -> str:
    parts = [
        str(task.get("question_zh") or "").strip(),
        "missing metric families: " + ", ".join(str(item) for item in task.get("missing_metric_families") or []),
        "missing tickers: " + ", ".join(str(item) for item in [*(task.get("missing_tickers") or []), *(task.get("missing_peer_tickers") or [])]),
        "missing filing types/source tiers: "
        + ", ".join(str(item) for item in [*(task.get("missing_filing_types") or []), *(task.get("missing_source_tiers") or [])]),
    ]
    return " | ".join(part for part in parts if part and not part.endswith(": "))[:160]


def _second_pass_section_hints(routes: list[str]) -> list[str]:
    hints: list[str] = []
    if "ledger_first" in routes:
        hints.extend(["financial_statements", "segment_tables", "cash_flow_tables"])
    if "filing_text" in routes:
        hints.extend(["md&a", "business", "segment_discussion"])
    if "8k_commentary" in routes:
        hints.extend(["item_2_02", "exhibit_99_1", "earnings_release"])
    if "risk_text" in routes:
        hints.extend(["risk_factors", "md&a_risk"])
    return _unique_compact_strings(hints)


def _source_gap_blocks_all_scope(
    gaps: list[dict[str, Any]],
    ticker: str,
    years: list[int],
    forms: list[str],
    tiers: list[str],
) -> bool:
    if not gaps or not years or not forms:
        return False
    for year in years:
        for form in forms:
            for tier in tiers or [""]:
                if not _has_source_gap(gaps, ticker, year, form, tier):
                    return False
    return True


def _has_source_gap(gaps: list[dict[str, Any]], ticker: str, year: int, form: str, tier: str) -> bool:
    ticker = str(ticker or "").upper()
    form = _normalize_form_type(form)
    tier = str(tier or "")
    for gap in gaps:
        gap_ticker = str(gap.get("ticker") or "").upper()
        gap_year = _int_or_none(gap.get("year") or gap.get("filing_year") or gap.get("fiscal_year"))
        gap_form = _normalize_form_type(gap.get("form_type") or gap.get("filing_type"))
        gap_tier = str(gap.get("source_tier") or "")
        if gap_ticker and gap_ticker != ticker:
            continue
        if gap_year is not None and gap_year != year:
            continue
        if gap_form and gap_form != form:
            continue
        if gap_tier and tier and gap_tier != tier:
            continue
        return True
    return False


def _unique_upper_values(values: Iterable[Any]) -> list[str]:
    return [item.upper() for item in _unique_compact_strings(values)]


def _unique_int_values(values: Iterable[Any]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for value in values:
        parsed = _int_or_none(value)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        out.append(parsed)
    return out


def _unique_form_values(values: Iterable[Any]) -> list[str]:
    forms: list[str] = []
    seen: set[str] = set()
    for value in values:
        form = _normalize_form_type(value)
        if not form or form in seen:
            continue
        seen.add(form)
        forms.append(form)
    return forms


def _stage_build_judgment_plan(
    state: SecAgentState,
    case: dict[str, Any],
    paths: dict[str, Path],
    ledger_rows: list[dict[str, Any]],
    coverage_matrix: dict[str, Any],
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
        plan_payload = _augment_plan_payload_with_market_snapshot(plan_payload, case, coverage_matrix)
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


def _contract_requests_market_snapshot(query_contract: dict[str, Any]) -> bool:
    source_tiers = {str(item or "").strip() for item in query_contract.get("source_tiers") or [] if str(item or "").strip()}
    if MARKET_SOURCE_TIER in source_tiers or str(query_contract.get("source_policy") or "") == MARKET_SOURCE_POLICY:
        return True
    market = query_contract.get("market_snapshot")
    return isinstance(market, dict) and bool(market.get("required") or market.get("fields") or market.get("analysis_tools"))


def _contract_requests_industry_snapshot(query_contract: dict[str, Any]) -> bool:
    source_tiers = {str(item or "").strip() for item in query_contract.get("source_tiers") or [] if str(item or "").strip()}
    if INDUSTRY_SOURCE_TIER in source_tiers:
        return True
    industry = query_contract.get("industry_snapshot")
    return isinstance(industry, dict) and bool(industry.get("required") or industry.get("source_families") or industry.get("snapshot_id"))


def _load_market_context_rows(path_value: str, query_contract: dict[str, Any]) -> list[dict[str, Any]]:
    if not path_value:
        return []
    path = _repo_path(path_value)
    rows = _read_jsonl(path)
    if not rows:
        return []
    tickers = {
        str(item or "").upper()
        for item in (
            query_contract.get("focus_tickers")
            or query_contract.get("search_scope_tickers")
            or (query_contract.get("scope") or {}).get("focus_tickers")
            or []
        )
        if str(item or "").strip()
    }
    market = query_contract.get("market_snapshot") if isinstance(query_contract.get("market_snapshot"), dict) else {}
    snapshot_id = str(market.get("snapshot_id") or "").strip()
    as_of_date = str(market.get("as_of_date") or "").strip()
    selected = []
    for row in rows:
        if not isinstance(row, dict) or not _is_market_snapshot_context_row(row):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if tickers and ticker not in tickers:
            continue
        if snapshot_id and str(row.get("snapshot_id") or "") != snapshot_id:
            continue
        if as_of_date and str(row.get("as_of_date") or "") != as_of_date:
            continue
        selected.append(_normalize_market_context_row(row))
    return selected


def _load_industry_context_rows(path_value: str, query_contract: dict[str, Any]) -> list[dict[str, Any]]:
    if not path_value:
        return []
    path = _repo_path(path_value)
    rows = _read_jsonl(path)
    if not rows:
        return []
    industry = query_contract.get("industry_snapshot") if isinstance(query_contract.get("industry_snapshot"), dict) else {}
    requested_families = {
        str(item or "").strip()
        for item in (
            industry.get("source_families")
            or industry.get("required_source_families")
            or _industry_source_families_from_requirements(query_contract)
        )
        if str(item or "").strip()
    }
    snapshot_id = str(industry.get("snapshot_id") or "").strip()
    as_of_date = str(industry.get("as_of_date") or "").strip()
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_family = str(row.get("source_family") or "").strip()
        if requested_families and source_family not in requested_families:
            continue
        if snapshot_id and str(row.get("snapshot_id") or "") != snapshot_id:
            continue
        if as_of_date and str(row.get("as_of_date") or "") != as_of_date:
            continue
        selected.append(_normalize_industry_context_row(row))
    return selected


def _industry_source_families_from_requirements(query_contract: dict[str, Any]) -> list[str]:
    families: list[str] = []
    for requirement in query_contract.get("evidence_requirements") or []:
        if not isinstance(requirement, dict):
            continue
        routes = {str(route or "").strip() for route in requirement.get("evidence_routes") or [] if str(route or "").strip()}
        tiers = {str(tier or "").strip() for tier in requirement.get("source_tiers") or [] if str(tier or "").strip()}
        if INDUSTRY_SOURCE_TIER not in routes and INDUSTRY_SOURCE_TIER not in tiers:
            continue
        families.extend(str(item or "").strip() for item in requirement.get("source_families") or [] if str(item or "").strip())
    return _unique_compact_strings(families)


def _normalize_industry_context_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["source_kind"] = normalized.get("source_kind") or INDUSTRY_SOURCE_TIER
    normalized["source_type"] = normalized.get("source_type") or INDUSTRY_SOURCE_TIER
    normalized["source_tier"] = INDUSTRY_SOURCE_TIER
    evidence_id = str(
        normalized.get("evidence_id")
        or normalized.get("object_id")
        or f"INDUSTRY::{normalized.get('source_family')}::{normalized.get('series_id') or normalized.get('dataset_id')}::{normalized.get('as_of_date')}"
    )
    normalized["evidence_id"] = evidence_id
    normalized["object_id"] = str(normalized.get("object_id") or evidence_id)
    normalized["source_evidence_id"] = str(normalized.get("source_evidence_id") or evidence_id)
    normalized["section"] = normalized.get("section") or "industry_snapshot"
    normalized["text"] = str(normalized.get("text") or normalized.get("summary") or "")
    normalized["source_boundary"] = normalized.get("source_boundary") or (
        "industry_snapshot; context_only; "
        f"source_family={normalized.get('source_family') or ''}; "
        f"provider={normalized.get('provider') or ''}; "
        f"as_of_date={normalized.get('as_of_date') or ''}"
    )
    normalized["allowed_claim_types"] = normalized.get("allowed_claim_types") or []
    normalized["caveats"] = normalized.get("caveats") or [
        "Industry snapshot provides macro or sector context only.",
        "Do not use it as company-filed financial fact evidence.",
    ]
    return normalized


def _normalize_market_context_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["source_kind"] = normalized.get("source_kind") or MARKET_SOURCE_TIER
    normalized["source_type"] = normalized.get("source_type") or MARKET_SOURCE_TIER
    normalized["source_tier"] = MARKET_SOURCE_TIER
    normalized["evidence_id"] = str(
        normalized.get("evidence_id")
        or normalized.get("object_id")
        or f"MARKET_SNAPSHOT::{normalized.get('snapshot_id')}::{normalized.get('ticker')}::{normalized.get('window')}::{normalized.get('as_of_date')}"
    )
    normalized["object_id"] = str(normalized.get("object_id") or normalized["evidence_id"])
    normalized["source_evidence_id"] = str(normalized.get("source_evidence_id") or normalized["evidence_id"])
    normalized["section"] = normalized.get("section") or "market_snapshot"
    normalized["source_boundary"] = normalized.get("source_boundary") or (
        f"market_snapshot; non-real-time; as_of_date={normalized.get('as_of_date') or ''}"
    )
    return normalized


def _append_unique_context_rows(
    context_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = list(context_rows)
    seen = {_context_row_stable_id(row) for row in out if isinstance(row, dict)}
    for row in extra_rows:
        key = _context_row_stable_id(row)
        if key in seen:
            continue
        out.append(row)
        seen.add(key)
    return out


def _is_market_snapshot_context_row(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    values = {
        str(row.get("source_tier") or "").strip(),
        str(row.get("source_type") or "").strip(),
        str(row.get("source_kind") or "").strip(),
        str(metadata.get("source_tier") or "").strip(),
        str(metadata.get("source_type") or "").strip(),
    }
    if MARKET_SOURCE_TIER in values:
        return True
    evidence_id = " ".join(str(row.get(key) or "") for key in ("evidence_id", "source_evidence_id", "object_id"))
    return "MARKET_SNAPSHOT::" in evidence_id


def _is_industry_snapshot_context_row(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    values = {
        str(row.get("source_tier") or "").strip(),
        str(row.get("source_type") or "").strip(),
        str(row.get("source_kind") or "").strip(),
        str(metadata.get("source_tier") or "").strip(),
        str(metadata.get("source_type") or "").strip(),
    }
    if INDUSTRY_SOURCE_TIER in values:
        return True
    evidence_id = " ".join(str(row.get(key) or "") for key in ("evidence_id", "source_evidence_id", "object_id"))
    return "INDUSTRY::" in evidence_id


def _write_run_data_fingerprint(
    args: argparse.Namespace,
    run_root: Path,
    project_inventory: dict[str, Any],
    query_contract: dict[str, Any],
) -> Path:
    output_path = run_root / "run_data_fingerprint.json"
    payload = {
        "schema_version": "sec_agent_run_data_fingerprint_v0.1",
        "created_at": _utc_now_iso(),
        "run_root": str(run_root.resolve()),
        "inventory_digest": str(
            project_inventory.get("inventory_digest")
            or query_contract.get("project_inventory_digest")
            or ""
        ),
        "selected_scope": {
            "tickers": query_contract.get("focus_tickers") or query_contract.get("search_scope_tickers") or [],
            "years": query_contract.get("years") or [],
            "filing_types": query_contract.get("filing_types") or [],
            "source_tiers": query_contract.get("source_tiers") or [],
            "source_policy": query_contract.get("source_policy"),
        },
        "inputs": {
            "manifest": _path_fingerprint(_repo_path(args.manifest_path), kind="jsonl"),
            "source_gap": _path_fingerprint(_repo_path(args.source_gap_path), kind="jsonl") if args.source_gap_path else None,
            "bm25_index": _index_dir_fingerprint(_repo_path(args.bm25_index_dir)),
            "object_bm25_index": _index_dir_fingerprint(_repo_path(args.object_bm25_index_dir)),
            "ledger_store": _path_fingerprint(_repo_path(getattr(args, "ledger_store_path", "")), kind="large_file")
            if getattr(args, "ledger_store_path", "")
            else None,
            "market_evidence": _path_fingerprint(_repo_path(args.market_evidence_path), kind="jsonl") if args.market_evidence_path else None,
            "industry_evidence": _path_fingerprint(_repo_path(getattr(args, "industry_evidence_path", "")), kind="jsonl")
            if getattr(args, "industry_evidence_path", "")
            else None,
        },
        "runtime_knobs": {
            "context_runner": getattr(args, "context_runner", "auto"),
            "effective_context_runner": _context_runner_mode(args),
            "evidence_top_k": args.evidence_top_k,
            "object_top_k": args.object_top_k,
            "max_context_rows": args.max_context_rows,
            "reranker_top_k": getattr(args, "reranker_top_k", None),
            "reranker_candidate_limit": getattr(args, "reranker_candidate_limit", None),
            "reranker_batch_size": getattr(args, "reranker_batch_size", None),
            "reranker_max_length": getattr(args, "reranker_max_length", None),
            "reranker_doc_max_chars": getattr(args, "reranker_doc_max_chars", None),
            "ledger_max_rows": args.ledger_max_rows,
        },
    }
    _write_json(output_path, payload)
    return output_path


def _path_fingerprint(path: Path, *, kind: str = "file") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "kind": kind,
    }
    if not path.exists() or not path.is_file():
        return payload
    stat = path.stat()
    payload.update(
        {
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }
    )
    if kind == "jsonl":
        payload["row_count"] = _count_lines(path)
    elif kind == "large_file":
        payload["digest"] = ""
    else:
        payload["digest"] = _file_digest(path)
    return payload


def _index_dir_fingerprint(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists() and path.is_dir(),
        "kind": "bm25_index_dir",
    }
    if not payload["exists"]:
        return payload
    metadata_path = path / "metadata.json"
    records_path = path / "records.jsonl"
    bm25_path = path / "bm25.pkl"
    payload["metadata"] = _read_json(metadata_path) if metadata_path.exists() else {}
    payload["files"] = {
        "metadata": _path_fingerprint(metadata_path),
        "records": _path_fingerprint(records_path, kind="large_file"),
        "bm25": _path_fingerprint(bm25_path, kind="large_file"),
    }
    return payload


def _count_lines(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _file_digest(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _write_run_performance_report(
    state: SecAgentState,
    run_root: Path,
    started: float,
    paths: dict[str, Path],
    qwen_result: dict[str, Any] | None,
    post_gate_ok: bool,
) -> Path:
    output_path = paths.get("run_performance_path") or (run_root / "run_performance.json")
    stages = [stage.to_dict() for stage in state.stages]
    stage_timing_ms = dict(state.metadata.get("stage_timing_ms") or {})
    for stage in state.stages:
        if stage.elapsed_ms is not None:
            stage_timing_ms[stage.name] = stage.elapsed_ms
    payload = {
        "schema_version": "sec_agent_run_performance_v0.1",
        "created_at": _utc_now_iso(),
        "run_id": state.run_id,
        "status": state.status,
        "post_gate_ok": bool(post_gate_ok),
        "total_elapsed_sec": round(time.time() - started, 4),
        "stage_timing_ms": stage_timing_ms,
        "stages": stages,
        "artifact_rows": {
            key: ref.row_count
            for key, ref in state.artifacts.items()
            if ref.row_count is not None
        },
        "llm_gateway": _gateway_debug(((qwen_result or {}).get("debug") or {}).get("llm_gateway") or {}),
    }
    _write_json(output_path, payload)
    return output_path


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
            "context_runner": args.context_runner,
            "effective_context_runner": _context_runner_mode(args),
            "market_evidence_path": args.market_evidence_path or "",
            "max_context_rows": args.max_context_rows,
            "reranker_top_k": getattr(args, "reranker_top_k", None),
            "reranker_candidate_limit": getattr(args, "reranker_candidate_limit", None),
            "reranker_batch_size": getattr(args, "reranker_batch_size", None),
            "reranker_max_length": getattr(args, "reranker_max_length", None),
            "reranker_doc_max_chars": getattr(args, "reranker_doc_max_chars", None),
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


def _run_context(args: argparse.Namespace, cases_path: Path, trace_dir: Path) -> dict[str, Any]:
    if _context_runner_mode(args) == "in_process":
        return _run_context_in_process(args, cases_path, trace_dir)
    return _run_context_subprocess(args, cases_path, trace_dir)


def _run_context_subprocess(args: argparse.Namespace, cases_path: Path, trace_dir: Path) -> dict[str, Any]:
    cmd = [
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
        str(args.reranker_batch_size),
        "--context-reranker-max-length",
        str(args.reranker_max_length),
        "--context-reranker-doc-max-chars",
        str(args.reranker_doc_max_chars),
        "--context-reranker-candidate-limit",
        str(args.reranker_candidate_limit),
    ]
    ledger_store_path = str(getattr(args, "ledger_store_path", "") or "")
    if ledger_store_path:
        cmd.extend(["--ledger-store-path", ledger_store_path])
    _run(cmd, stream=not args.quiet)
    return {"context_runtime": {"context_runner": "subprocess"}}


def _run_context_in_process(args: argparse.Namespace, cases_path: Path, trace_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    trace_dir.mkdir(parents=True, exist_ok=True)
    bench_args = _benchmark_context_args(args, cases_path, trace_dir)
    cases = _read_jsonl(cases_path)
    requested_modes = ["pipeline_context"]
    benchmark_context._enforce_pipeline_context_policy(bench_args, cases, requested_modes)
    manifest_index = _load_manifest_index_cached(_repo_path(args.manifest_path))
    resources, resource_runtime = _get_context_runtime_resources(args, bench_args)
    bm25 = resources["bm25"]
    object_bm25 = resources["object_bm25"]
    context_reranker = resources["context_reranker"]

    agent_outputs: list[dict[str, Any]] = []
    claim_verification: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    trace_logs: list[dict[str, Any]] = []
    bad_cases: list[dict[str, Any]] = []
    context_runtime = {
        "context_runner": "in_process",
        "bge_device": str(args.bge_device or ""),
        "bge_model_ref": _model_ref(args.bge_model),
        "cuda_available": _cuda_available() if str(args.bge_device or "").lower().startswith("cuda") else None,
        "reranker_batch_size": int(args.reranker_batch_size),
        "reranker_max_length": int(args.reranker_max_length),
        "reranker_doc_max_chars": int(args.reranker_doc_max_chars),
        "reranker_candidate_limit": int(args.reranker_candidate_limit),
        "reranker_top_k": int(args.reranker_top_k),
        **resource_runtime,
    }
    for case in cases:
        for mode in requested_modes:
            if mode not in set(case.get("evaluation_modes") or []):
                trace = benchmark_context._base_trace(case, mode, status="skipped_mode_not_supported")
                _stamp_trace_context_runtime(trace, context_runtime)
                trace_logs.append(trace)
                continue
            trace = benchmark_context._prepare_trace(
                case=case,
                mode=mode,
                manifest_index=manifest_index,
                gold_context_dir=REPO_ROOT / "eval" / "sec_cases" / "gold_context",
                bm25=bm25,
                object_bm25=object_bm25,
                context_reranker=context_reranker,
                args=bench_args,
                evidence_top_k=args.evidence_top_k,
                object_top_k=args.object_top_k,
                max_context_rows=args.max_context_rows,
            )
            _stamp_trace_context_runtime(trace, context_runtime)
            trace_logs.append(trace)
            context_rows = trace.get("context_rows") or []
            synthesis_result = benchmark_context._run_synthesis_backend(
                args=bench_args,
                case=case,
                mode=mode,
                trace=trace,
                context_rows=context_rows,
            )
            agent_outputs.append(
                {
                    "schema_version": "sec_benchmark_agent_output_v0.1",
                    "case_id": case.get("case_id"),
                    "mode": mode,
                    "status": synthesis_result["agent_status"],
                    "answer_status": synthesis_result["answer_status"],
                    "answer": synthesis_result["answer"],
                    "limitations": synthesis_result["limitations"],
                    "context_row_count": trace.get("context_summary", {}).get("context_row_count", 0),
                }
            )
            claim_verification.append(
                {
                    "schema_version": "sec_benchmark_claim_verification_v0.1",
                    "case_id": case.get("case_id"),
                    "mode": mode,
                    "status": synthesis_result["claim_status"],
                    "claims": synthesis_result["claims"],
                    "unsupported_claim_count": synthesis_result["unsupported_claim_count"],
                }
            )
            scores.append(
                {
                    "schema_version": "sec_benchmark_score_v0.1",
                    "case_id": case.get("case_id"),
                    "mode": mode,
                    "status": synthesis_result["score_status"],
                    "score_total": synthesis_result["score_total"],
                    "scores": synthesis_result["scores"],
                    "failure_types": synthesis_result["failure_types"],
                    "notes": synthesis_result["score_notes"],
                }
            )
            if trace.get("status") != "context_prepared":
                bad_cases.append(trace)

    _write_jsonl(trace_dir / "agent_outputs.jsonl", agent_outputs)
    _write_jsonl(trace_dir / "claim_verification.jsonl", claim_verification)
    _write_jsonl(trace_dir / "scores.jsonl", scores)
    _write_jsonl(trace_dir / "trace_logs.jsonl", trace_logs)
    benchmark_context._write_bad_cases(trace_dir / "bad_cases.md", bad_cases)
    context_runtime["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000))
    summary = benchmark_context._summary(bench_args, trace_dir, trace_logs, agent_outputs)
    summary["context_runtime"] = context_runtime
    _write_json(trace_dir / "run_summary.json", summary)
    return {"context_runtime": context_runtime}


def _benchmark_context_args(args: argparse.Namespace, cases_path: Path, trace_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        cases_path=str(cases_path),
        manifest_path=args.manifest_path,
        gold_context_dir="eval/sec_cases/gold_context",
        output_dir=str(trace_dir),
        case_id=[],
        mode="pipeline_context",
        bm25_index_dir=args.bm25_index_dir,
        object_bm25_index_dir=args.object_bm25_index_dir,
        evidence_top_k=args.evidence_top_k,
        object_top_k=args.object_top_k,
        max_context_rows=args.max_context_rows,
        context_reranker="bge",
        context_reranker_model=args.bge_model,
        context_reranker_device=args.bge_device,
        context_reranker_batch_size=args.reranker_batch_size,
        context_reranker_max_length=args.reranker_max_length,
        context_reranker_doc_max_chars=args.reranker_doc_max_chars,
        context_reranker_candidate_limit=args.reranker_candidate_limit,
        context_reranker_top_k=args.reranker_top_k,
        ledger_store_path=getattr(args, "ledger_store_path", ""),
        allow_bm25_only_pipeline=False,
        synthesis_backend="context_only",
        synthesis_command="",
    )


def _get_context_runtime_resources(
    args: argparse.Namespace,
    bench_args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.object_bm25_retriever import ObjectBM25Retriever

    key = _context_runtime_cache_key(args)
    cached = _CONTEXT_RUNTIME_CACHE.get(key)
    if cached is not None:
        return cached, {
            "context_cache_hit": True,
            "context_cache_key": _short_digest(json.dumps(key, sort_keys=True, default=str)),
        }
    load_started = time.perf_counter()
    object_index_dir = _repo_path(args.object_bm25_index_dir)
    object_bm25 = ObjectBM25Retriever(object_index_dir)
    _register_object_records(object_index_dir, object_bm25.records)
    resources = {
        "bm25": BM25Retriever(_repo_path(args.bm25_index_dir)),
        "object_bm25": object_bm25,
        "context_reranker": benchmark_context._load_context_reranker(bench_args),
    }
    _CONTEXT_RUNTIME_CACHE.clear()
    _CONTEXT_RUNTIME_CACHE[key] = resources
    return resources, {
        "context_cache_hit": False,
        "context_cache_key": _short_digest(json.dumps(key, sort_keys=True, default=str)),
        "context_resource_load_ms": int(round((time.perf_counter() - load_started) * 1000)),
    }


def _context_runtime_cache_key(args: argparse.Namespace) -> tuple[Any, ...]:
    return (
        _index_cache_token(_repo_path(args.bm25_index_dir)),
        _index_cache_token(_repo_path(args.object_bm25_index_dir)),
        str(args.bge_model),
        str(args.bge_device),
        int(args.reranker_max_length),
    )


def _model_ref(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""
    if "/" in text and ":" in text[:4]:
        return text.rstrip("/").split("/")[-1]
    return text


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def _load_manifest_index_cached(path: Path) -> dict[tuple[str, int, str], dict[str, Any]]:
    key = _file_cache_token(path)
    cached = _MANIFEST_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    rows = _read_jsonl(path)
    manifest_index = {
        (str(row.get("ticker")).upper(), int(row.get("fiscal_year")), str(row.get("form_type")).upper()): row
        for row in rows
        if row.get("ticker") and row.get("fiscal_year") and row.get("form_type")
    }
    _MANIFEST_INDEX_CACHE.clear()
    _MANIFEST_INDEX_CACHE[key] = manifest_index
    return manifest_index


def _stamp_trace_context_runtime(trace: dict[str, Any], runtime: dict[str, Any]) -> None:
    policy = trace.get("context_policy")
    if not isinstance(policy, dict):
        policy = {}
        trace["context_policy"] = policy
    policy["context_runtime"] = dict(runtime)


def _index_cache_token(path: Path) -> tuple[Any, ...]:
    return (
        str(path.resolve()),
        _file_cache_token(path / "metadata.json"),
        _file_cache_token(path / "records.jsonl"),
        _file_cache_token(path / "bm25.pkl"),
    )


def _file_cache_token(path: Path) -> tuple[Any, ...]:
    if not path.exists() or not path.is_file():
        return (str(path.resolve()), False, 0, 0)
    stat = path.stat()
    return (str(path.resolve()), True, stat.st_size, stat.st_mtime_ns)


def _short_digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


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
    has_8k_context = qwen_adapter._has_company_authored_8k_context(prompt_case, context_rows)
    has_market_context = qwen_adapter._has_market_snapshot_context(prompt_case, context_rows)
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    focus_tickers = [str(item).upper() for item in (query_contract.get("focus_tickers") or case.get("companies") or [])]
    is_broad_ai = str(query_contract.get("task_type") or case.get("task_type") or "") == "ai_industry_financial_trend" or (
        len(focus_tickers) >= 8
        and _contains_any(str(case.get("prompt") or "").lower(), ("ai", "人工智能", "算力", "数据中心", "芯片"))
    )
    driver_cap = 8 if is_broad_ai else (6 if api_insight_mode else 4)
    point_cap = 8 if is_broad_ai else (7 if api_insight_mode else 5)
    if synthesis_profile == "api_memo_v1":
        numeric_source_rule = _api_memo_source_rule(has_8k_context=has_8k_context, has_market_context=has_market_context)
        system_content = (
            "你是SEC证据约束下的财务分析师，输出目标是高质量投研memo，而不是审计清单。"
            f"{numeric_source_rule}"
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
            + (
                "除已给定 market_snapshot 外，不能使用新闻、电话会、分析师预期、实时行情或source policy外信息。"
                if has_market_context
                else "不能使用股价、估值、新闻、电话会、分析师预期或source policy外信息。"
            )
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


def _api_memo_source_rule(*, has_8k_context: bool, has_market_context: bool) -> str:
    parts = [
        "必须只基于给定证据回答；10-K/10-Q财务精确数值必须来自 Exact-Value Ledger。"
    ]
    if has_8k_context:
        parts.append(
            "8-K earnings release 只能作为带 evidence_id 的公司未审计/管理层口径材料引用，不能当作 audited ledger fact。"
            "当8-K证据能解释业绩、guidance、demand、capex/投资节奏或管理层评论时，要主动引用并标注来源边界。"
        )
    if has_market_context:
        parts.append(
            "market_snapshot 只能作为带 market evidence_id 的非实时市场/估值/收益证据引用；"
            "必须标注 snapshot_id/as_of_date/source boundary，不能覆盖 SEC reported fundamentals，也不能补充实时行情或模型记忆。"
        )
    return "".join(parts)


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
                "required_market_fields": task.get("required_market_fields") or [],
                "covered_market_fields": task.get("covered_market_fields") or [],
                "missing_market_fields": task.get("missing_market_fields") or [],
                "required_market_tools": task.get("required_market_tools") or [],
                "covered_market_tools": task.get("covered_market_tools") or [],
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
                "sample_market_field_refs": (task.get("sample_market_field_refs") or [])[:6],
            }
        )
    return {
        "schema_version": coverage_matrix.get("schema_version"),
        "source_policy": coverage_matrix.get("source_policy"),
        "filing_types": coverage_matrix.get("filing_types") or [],
        "source_tiers": coverage_matrix.get("source_tiers") or [],
        "source_coverage_gaps": (coverage_matrix.get("source_coverage_gaps") or [])[:10],
        "market_snapshot_coverage": coverage_matrix.get("market_snapshot_coverage") or {},
        "second_pass_retrieval": coverage_matrix.get("second_pass_retrieval") or {},
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


def _augment_plan_payload_with_market_snapshot(
    plan_payload: dict[str, Any],
    case: dict[str, Any],
    coverage_matrix: dict[str, Any],
) -> dict[str, Any]:
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    if not _contract_requests_market_snapshot(query_contract):
        return plan_payload
    market_summary = coverage_matrix.get("market_snapshot_coverage") if isinstance(coverage_matrix, dict) else {}
    if not isinstance(market_summary, dict) or not market_summary.get("market_context_row_count"):
        return plan_payload
    sample_ids = [str(item) for item in market_summary.get("sample_evidence_ids") or [] if str(item)]
    if not sample_ids:
        return plan_payload
    missing_fields = [str(item) for item in market_summary.get("missing_market_fields") or [] if str(item)]
    strength = "medium" if not missing_fields else "weak"
    driver = {
        "rank": 0,
        "claim": "Market snapshot evidence can support market reaction, relative return, and valuation-context interpretation without changing SEC filed fundamentals.",
        "claim_role": "market_snapshot_context",
        "why_ranked_here": "Planner requested market_snapshot; deterministic coverage found stamped market evidence rows.",
        "supporting_metric_ids": [],
        "supporting_evidence_ids": sample_ids[:8],
        "covered_companies": [str(item) for item in case.get("companies") or []][:8],
        "covered_years": [],
        "metric_families": [],
        "market_fields": market_summary.get("covered_market_fields") or [],
        "market_snapshot_ids": market_summary.get("market_snapshot_ids") or [],
        "market_snapshot_as_of_dates": market_summary.get("market_snapshot_as_of_dates") or [],
        "conclusion_strength": strength,
        "caveats": [
            "Market snapshot is non-real-time and supports market/valuation claims only; SEC Exact-Value Ledger remains authoritative for reported fundamentals."
        ],
        "support_score": 6.0,
        "downgrade_reasons": [f"Missing market fields: {', '.join(missing_fields)}"] if missing_fields else [],
    }
    for plan in plan_payload.get("plans") or []:
        if not isinstance(plan, dict) or plan.get("case_id") != case.get("case_id"):
            continue
        drivers = [item for item in plan.get("drivers") or [] if isinstance(item, dict)]
        if any(str(item.get("claim_role") or "") == "market_snapshot_context" for item in drivers):
            continue
        drivers.append(driver)
        for rank, item in enumerate(drivers, start=1):
            item["rank"] = rank
        plan["drivers"] = drivers
        if missing_fields:
            plan.setdefault("must_downgrade_because", []).append(
                "Market snapshot coverage is partial; missing requested fields cannot be inferred from model memory."
            )
        plan.setdefault("do_not_overstate", []).append(
            "Do not use market snapshot values to overwrite SEC reported financial facts."
        )
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
    ledger_store_path = str(getattr(args, "ledger_store_path", "") or "").strip()
    if ledger_store_path and _repo_path(ledger_store_path).exists():
        return _build_runtime_ledger_from_store(case, context_rows, args, _repo_path(ledger_store_path))

    object_ids = [
        str(row.get("object_id") or "")
        for row in context_rows
        if row.get("source_kind") == "structured_object" and row.get("object_id")
    ]
    object_index_dir = _repo_path(args.object_bm25_index_dir)
    records = _load_object_records_for_ids(object_index_dir, object_ids)
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    scoped_records = _ledger_supplement_scope_records_from_index(object_index_dir, case, records, query_contract)
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
    _supplement_ai_focus_ledger(case, scoped_records, rows, seen, query_contract)
    _supplement_contract_metric_family_ledger(case, scoped_records, rows, seen, query_contract)
    _supplement_context_evidence_object_ledger(case, context_rows, rows, seen, query_contract)
    _supplement_banking_context_ledger(case, context_rows, rows, seen, query_contract)
    _supplement_free_cash_flow_proxy(case, rows, seen, query_contract)
    rows.sort(key=lambda row: _ledger_row_rank(row, query_contract, context_by_object_id.get(str(row.get("object_id") or ""))), reverse=True)
    rows = _cap_ledger_rows(rows, query_contract, args.ledger_max_rows)
    _dedupe_metric_ids(rows)
    return rows[: args.ledger_max_rows]


def _build_runtime_ledger_from_store(
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    args: argparse.Namespace,
    ledger_store_path: Path,
) -> list[dict[str, Any]]:
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    context_by_object_id = {
        str(row.get("object_id") or ""): row
        for row in context_rows
        if row.get("object_id")
    }
    object_ids = sorted(context_by_object_id)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    if object_ids:
        for row in query_ledger_facts(
            ledger_store_path,
            case_id=str(case.get("case_id") or ""),
            object_ids=object_ids,
            limit=max(1000, len(object_ids) * 8),
        ):
            context_row = context_by_object_id.get(str(row.get("object_id") or ""))
            if not _ledger_row_allowed(row, query_contract, context_row):
                continue
            key = _ledger_dedupe_key(row)
            if key not in seen:
                rows.append(row)
                seen.add(key)

    scoped_rows = _query_ledger_store_scope_rows(case, query_contract, ledger_store_path, limit=max(5000, args.ledger_max_rows * 80))
    for row in scoped_rows:
        if not _ledger_row_allowed(row, query_contract, None):
            continue
        key = _ledger_dedupe_key(row)
        if key not in seen:
            rows.append(row)
            seen.add(key)

    _supplement_banking_context_ledger(case, context_rows, rows, seen, query_contract)
    _supplement_free_cash_flow_proxy(case, rows, seen, query_contract)
    rows.sort(key=lambda row: _ledger_row_rank(row, query_contract, context_by_object_id.get(str(row.get("object_id") or ""))), reverse=True)
    rows = _cap_ledger_rows(rows, query_contract, args.ledger_max_rows)
    _dedupe_metric_ids(rows)
    return rows[: args.ledger_max_rows]


def _query_ledger_store_scope_rows(
    case: dict[str, Any],
    query_contract: dict[str, Any],
    ledger_store_path: Path,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    family_tickers = _contract_required_family_tickers(query_contract)
    focus = sorted(set().union(*family_tickers.values())) if family_tickers else []
    if not focus:
        focus = [str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)]
    if not focus:
        focus = [str(item).upper() for item in case.get("companies") or [] if str(item)]
    years = [int(year) for year in case.get("years") or [] if _int_or_none(year) is not None]
    filing_types = [
        _normalize_form_type(item)
        for item in (case.get("filing_types") or query_contract.get("filing_types") or [])
        if _normalize_form_type(item)
    ]
    source_tiers = [
        str(item)
        for item in (case.get("source_tiers") or query_contract.get("source_tiers") or [])
        if str(item)
    ]
    metric_families = sorted(_contract_required_metric_families(query_contract))
    return query_ledger_facts(
        ledger_store_path,
        case_id=str(case.get("case_id") or ""),
        tickers=focus,
        years=years,
        filing_types=filing_types,
        source_tiers=source_tiers,
        metric_families=metric_families,
        limit=limit,
    )


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
    role_text = " ".join(
        str(record.get(key) or "")
        for key in ("metric_name", "row_label", "column_label")
        if str(record.get(key) or "")
    )
    role = _metric_role(role_text or metric_name, unit)
    if role == "total_value" and unit != "percent" and _raw_amount_is_period_change(raw, metric_context):
        role = "period_change_amount"
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
    rows.extend(_ledger_change_rate_rows_from_table(case_id, record, years))
    return rows


def _ledger_change_rate_rows_from_table(case_id: str, record: dict[str, Any], years: set[int]) -> list[dict[str, Any]]:
    ticker = str(record.get("ticker") or "").upper()
    if not ticker or record.get("object_type") != "table":
        return []
    cells_by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for cell in record.get("cells") or []:
        row_index = _int_or_none(cell.get("row_index"))
        if row_index is None:
            continue
        cells_by_row[row_index].append(cell)
    rows: list[dict[str, Any]] = []
    for row_index, cells in cells_by_row.items():
        period_cells = [
            cell
            for cell in cells
            if _year_from_value(cell.get("period")) is not None and isinstance(cell.get("value"), (int, float))
        ]
        if len(period_cells) < 2:
            continue
        period_cells.sort(key=lambda cell: int(_year_from_value(cell.get("period")) or 0), reverse=True)
        current, prior = period_cells[0], period_cells[1]
        current_year = _year_from_value(current.get("period"))
        if current_year is None or (years and current_year not in years):
            continue
        current_value = float(current.get("value"))
        prior_value = float(prior.get("value"))
        if prior_value == 0:
            continue
        expected = (current_value - prior_value) / abs(prior_value) * 100.0
        for change_cell in cells:
            if _year_from_value(change_cell.get("period")) is not None:
                continue
            raw = str(change_cell.get("raw_value") or "").strip()
            change_value = _numeric_raw_to_float(raw)
            if change_value is None or abs(change_value) > 500:
                continue
            if abs(change_value - expected) > 1.5 and round(change_value) != round(expected):
                continue
            metric_name = " ".join(
                str(part)
                for part in (change_cell.get("active_group"), change_cell.get("row_label"))
                if part
            ) or str(record.get("title") or "table_metric")
            family = _metric_family(metric_name, str(record.get("title") or ""))
            period_role = _ledger_period_role(record, current)
            rows.append(
                {
                    "metric_id": _ledger_metric_id(
                        case_id,
                        ticker,
                        current_year,
                        family,
                        "percentage_rate",
                        period_role=period_role,
                        suffix=_slug(str(change_cell.get("row_label") or "change_rate")),
                    ),
                    "case_id": case_id,
                    "ticker": ticker,
                    "fiscal_year": current_year,
                    "source_fiscal_year": _year_from_value(record.get("fiscal_year")),
                    "period": str(current.get("period") or current_year),
                    "period_role": period_role,
                    **_ledger_source_fields(record),
                    "metric_family": family,
                    "metric_role": "percentage_rate",
                    "metric_name": f"{metric_name} change rate",
                    "raw_value_text": f"{change_value:g}%",
                    "display_value_zh": f"{change_value:g}%",
                    "value": change_value,
                    "unit": "percent",
                    "object_id": record.get("object_id"),
                    "source_evidence_id": record.get("source_evidence_id"),
                    "section": record.get("section"),
                    "row_label": change_cell.get("row_label"),
                    "column_label": "Change",
                    "table_title": record.get("title"),
                    "active_group": change_cell.get("active_group"),
                    "cell_kind": "period_change_rate",
                    "row_index": row_index,
                }
            )
            break
    return rows


def _numeric_raw_to_float(raw: str) -> float | None:
    text = str(raw or "").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -abs(value) if negative else value


def _normalized_ledger_value(value: Any, raw: str, family: str) -> Any:
    if not isinstance(value, (int, float)):
        return value
    raw_text = str(raw or "").strip()
    if raw_text.startswith("(") and family in {"capital_expenditure_proxy"}:
        return -abs(float(value))
    return value


def _ledger_supplement_scope_records(
    case: dict[str, Any],
    records: dict[str, dict[str, Any]],
    query_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    family_tickers = _contract_required_family_tickers(query_contract)
    focus = set().union(*family_tickers.values()) if family_tickers else set()
    if not focus:
        focus = {str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    filing_types = {
        _normalize_form_type(item)
        for item in (case.get("filing_types") or query_contract.get("filing_types") or [])
        if _normalize_form_type(item)
    }
    source_tiers = {
        str(item)
        for item in (case.get("source_tiers") or query_contract.get("source_tiers") or [])
        if str(item)
    }
    cache_key = (
        id(records),
        tuple(sorted(focus)),
        tuple(sorted(years)),
        tuple(sorted(filing_types)),
        tuple(sorted(source_tiers)),
    )
    cached = _LEDGER_SCOPE_RECORDS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    scoped: list[dict[str, Any]] = []
    for record in records.values():
        ticker = str(record.get("ticker") or "").upper()
        if focus and ticker not in focus:
            continue
        source_fields = _ledger_source_fields(record)
        if filing_types and _normalize_form_type(source_fields.get("form_type")) not in filing_types:
            continue
        if source_tiers and str(source_fields.get("source_tier") or "") not in source_tiers:
            continue
        if years and not _record_overlaps_years(record, years):
            continue
        scoped.append(record)
    if len(_LEDGER_SCOPE_RECORDS_CACHE) > 16:
        _LEDGER_SCOPE_RECORDS_CACHE.clear()
    _LEDGER_SCOPE_RECORDS_CACHE[cache_key] = scoped
    return scoped


def _record_overlaps_years(record: dict[str, Any], years: set[int]) -> bool:
    record_year = _year_from_value(record.get("fiscal_year")) or _year_from_value(record.get("period"))
    if record_year in years:
        return True
    if record.get("object_type") == "table":
        for cell in record.get("cells") or []:
            cell_year = _year_from_value(cell.get("period")) or _year_from_value(cell.get("column_label"))
            if cell_year in years:
                return True
    return record_year is None


def _record_may_match_metric_families(record: dict[str, Any], desired_families: set[str]) -> bool:
    if not desired_families:
        return True
    family_key = tuple(sorted(str(item) for item in desired_families))
    cache_id = str(record.get("object_id") or id(record))
    cache_key = (cache_id, family_key)
    cached = _LEDGER_FAMILY_PREFILTER_CACHE.get(cache_key)
    if cached is not None:
        return cached
    text = _ledger_supplement_prefilter_text(record)
    if not text:
        return True
    checked_any = False
    matched = False
    for family in desired_families:
        terms = LEDGER_SUPPLEMENT_FAMILY_TERMS.get(family)
        if not terms:
            continue
        checked_any = True
        if any(term in text for term in terms):
            matched = True
            break
    result = matched or not checked_any
    if len(_LEDGER_FAMILY_PREFILTER_CACHE) > 500000:
        _LEDGER_FAMILY_PREFILTER_CACHE.clear()
    _LEDGER_FAMILY_PREFILTER_CACHE[cache_key] = result
    return result


def _ledger_supplement_prefilter_text(record: dict[str, Any]) -> str:
    cache_id = str(record.get("object_id") or "")
    if cache_id and cache_id in _LEDGER_PREFILTER_TEXT_CACHE:
        return _LEDGER_PREFILTER_TEXT_CACHE[cache_id]
    parts = [
        record.get("object_type"),
        record.get("metric_name"),
        record.get("row_label"),
        record.get("column_label"),
        record.get("title"),
        record.get("section"),
        record.get("subsection"),
        record.get("context"),
    ]
    if record.get("object_type") == "table":
        for cell in record.get("cells") or []:
            parts.extend((cell.get("active_group"), cell.get("row_label"), cell.get("column_label")))
    text = " ".join(str(part or "") for part in parts).lower()
    if cache_id:
        if len(_LEDGER_PREFILTER_TEXT_CACHE) > 500000:
            _LEDGER_PREFILTER_TEXT_CACHE.clear()
        _LEDGER_PREFILTER_TEXT_CACHE[cache_id] = text
    return text


def _supplement_ai_focus_ledger(
    case: dict[str, Any],
    records: Iterable[dict[str, Any]],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    if query_contract.get("task_type") != "ai_industry_financial_trend":
        return
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    target_labels = ("compute & networking", "data center")
    for record in records:
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
    records: Iterable[dict[str, Any]],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    family_tickers = _contract_required_family_tickers(query_contract)
    focus = set().union(*family_tickers.values()) if family_tickers else set()
    if not focus:
        focus = {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    desired_families = set(family_tickers) or _contract_required_metric_families(query_contract)
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
    for record in records:
        ticker = str(record.get("ticker") or "").upper()
        if ticker not in focus:
            continue
        if not _record_may_match_metric_families(record, desired_families):
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
            allowed_tickers = family_tickers.get(family)
            if allowed_tickers and ticker not in allowed_tickers:
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


def _supplement_context_evidence_object_ledger(
    case: dict[str, Any],
    context_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    query_contract: dict[str, Any],
) -> None:
    desired_families = _contract_required_metric_families(query_contract)
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    scan_limit = int(os.environ.get("CONTEXT_EVIDENCE_LEDGER_EXTRACTION_SCAN_LIMIT", "80"))
    added = 0
    for context_row in context_rows[: max(1, scan_limit)]:
        evidence = _context_row_to_evidence_object(context_row)
        if evidence is None:
            continue
        try:
            extraction = extract_structured_objects(evidence)
        except Exception:  # noqa: BLE001
            continue
        for metric in extraction.metrics:
            record = metric.model_dump(mode="json")
            base_row = _ledger_row_from_metric(str(case.get("case_id") or ""), record)
            if not base_row:
                continue
            candidates = [base_row, *_ledger_growth_rate_rows_from_metric(str(case.get("case_id") or ""), record, base_row)]
            for row in candidates:
                row_year = _int_or_none(row.get("fiscal_year"))
                if years and row_year not in years:
                    continue
                family = str(row.get("metric_family") or "")
                if desired_families and family not in desired_families:
                    continue
                if not _ledger_row_allowed(row, query_contract, context_row):
                    continue
                key = _ledger_dedupe_key(row)
                if key in seen:
                    continue
                row["ledger_extraction_source"] = "context_evidence_object_structured_extractor"
                rows.append(row)
                seen.add(key)
                added += 1
                if added >= int(getattr(case, "ledger_max_rows", 0) or os.environ.get("CONTEXT_EVIDENCE_LEDGER_EXTRACTION_ROW_LIMIT", "160")):
                    return


def _context_row_to_evidence_object(row: dict[str, Any]) -> EvidenceObject | None:
    text = str(row.get("text") or row.get("summary") or row.get("preview") or "").strip()
    if not text or ("[TABLE_START" not in text and not re.search(r"\d", text)):
        return None
    source_type = _normalize_form_type(row.get("source_type") or row.get("form_type") or "")
    if source_type not in {"10-K", "10-Q", "8-K"}:
        source_type = "8-K" if str(row.get("source_tier") or "") == "company_authored_unaudited_sec_filing" else "10-Q"
    source_tier = str(row.get("source_tier") or row.get("source_family") or "").strip()
    if source_tier not in {"primary_filing", "primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        source_tier = "company_authored_unaudited_sec_filing" if source_type == "8-K" else "primary_sec_filing"
    evidence_id = str(row.get("evidence_id") or row.get("evidence_ref") or row.get("id") or "").strip()
    if not evidence_id:
        digest = hashlib.sha1(text[:2000].encode("utf-8")).hexdigest()[:12]
        evidence_id = f"context_evidence::{digest}"
    try:
        fiscal_year = int(row.get("fiscal_year") or row.get("year")) if row.get("fiscal_year") or row.get("year") else None
    except (TypeError, ValueError):
        fiscal_year = None
    return EvidenceObject(
        evidence_id=evidence_id,
        source_type=source_type,  # type: ignore[arg-type]
        source_tier=source_tier,  # type: ignore[arg-type]
        ticker=str(row.get("ticker") or "").upper(),
        company=str(row.get("company") or "") or None,
        fiscal_year=fiscal_year,
        period_end=str(row.get("period_end") or "") or None,
        period_type=str(row.get("period_type") or "") or None,
        duration_months=_int_or_none(row.get("duration_months")),
        fiscal_period=str(row.get("fiscal_period") or "") or None,
        publication_date=str(row.get("publication_date") or row.get("filing_date") or "") or None,
        section=str(row.get("section") or "") or None,
        subsection=str(row.get("subsection") or "") or None,
        evidence_type=str(row.get("evidence_type") or row.get("source_kind") or "filing_text"),
        text=text,
        source_url=str(row.get("source_url") or row.get("filing_url") or "") or None,
        local_path=None,
        metadata={
            "form_type": source_type,
            "source_tier": source_tier,
            "period_end": str(row.get("period_end") or "") or None,
            "period_type": str(row.get("period_type") or "") or None,
            "duration_months": _int_or_none(row.get("duration_months")),
            "fiscal_period": str(row.get("fiscal_period") or "") or None,
            "block_id": row.get("block_id"),
            "context_evidence_ref": evidence_id,
        },
    )


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
    family_tickers = _contract_required_family_tickers(query_contract)
    banking_family_tickers = {
        family: tickers
        for family, tickers in family_tickers.items()
        if family in BANKING_METRIC_FAMILIES
    }
    effective_banking_tickers = _contract_banking_metric_tickers(query_contract)
    if effective_banking_tickers:
        for family in (_contract_required_metric_families(query_contract) & BANKING_METRIC_FAMILIES):
            banking_family_tickers.setdefault(family, set()).update(effective_banking_tickers)
    focus = set().union(*banking_family_tickers.values()) if banking_family_tickers else set()
    if not focus:
        focus = effective_banking_tickers or {str(item).upper() for item in query_contract.get("focus_tickers") or []}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    desired_families = (set(banking_family_tickers) or _contract_required_metric_families(query_contract)) & BANKING_METRIC_FAMILIES
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
            row_year_int = _int_or_none(row.get("fiscal_year"))
            if years and row_year_int not in years:
                continue
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
    token_spans: list[tuple[str, int]] = []
    for match in re.finditer(r"(?<![A-Za-z])[$(]?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:%|million|billion)?\)?", line, re.I):
        raw = match.group(0).strip()
        if _is_standalone_year_text(raw):
            continue
        token_spans.append((raw, match.start()))
    tokens = [raw for raw, _start in token_spans]
    if family in {"net_interest_margin", "capital_ratio"}:
        first_pipe = str(line).find("|")
        filtered = []
        for token, start in token_spans:
            if "%" in token:
                filtered.append(token)
                continue
            if first_pipe >= 0 and start < first_pipe:
                continue
            if re.fullmatch(r"\d", re.sub(r"[,%()$]", "", token).strip()):
                continue
            if re.search(r"\b\d+(?:\.\d+)?\b", token):
                filtered.append(token)
        return filtered
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
    return _expand_metric_family_aliases(families)


def _expand_metric_family_aliases(families: Iterable[str]) -> set[str]:
    aliases = {
        "capex": {"capex", "capital_expenditure_proxy"},
        "margin": {"gross_margin", "operating_income"},
        "operating_margin": {"operating_income"},
        "segment_revenue": {"segment_revenue", "revenue", "total_revenue", "product_revenue", "data_center_revenue"},
        "orders_backlog": {"orders_backlog", "rpo", "deferred_revenue", "arr_or_recurring_proxy"},
        "rpo_deferred_revenue": {"rpo_deferred_revenue", "rpo", "deferred_revenue", "arr_or_recurring_proxy"},
    }
    expanded: set[str] = set()
    for family in families:
        text = str(family or "").strip()
        if not text:
            continue
        expanded.update(aliases.get(text, {text}))
    return expanded


def _contract_required_family_tickers(query_contract: dict[str, Any]) -> dict[str, set[str]]:
    task_map: dict[str, set[str]] = {}
    default_focus = {str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)}
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families = [str(item) for item in task.get("required_metric_families") or [] if str(item)]
        tickers = {str(item).upper() for item in task.get("required_tickers") or [] if str(item)}
        if not families:
            continue
        if not tickers:
            tickers = set(default_focus)
        for family in families:
            task_map.setdefault(family, set()).update(tickers)
    if task_map:
        return task_map
    return {
        family: set(default_focus)
        for family in _contract_required_metric_families(query_contract)
    }


def _contract_banking_metric_tickers(query_contract: dict[str, Any]) -> set[str]:
    rules = query_contract.get("ledger_rules") if isinstance(query_contract.get("ledger_rules"), dict) else {}
    configured = {str(item).upper() for item in rules.get("banking_metric_tickers") or [] if str(item).strip()}
    candidate_tickers = {
        str(item).upper()
        for item in [
            *(query_contract.get("search_scope_tickers") or []),
            *(query_contract.get("focus_tickers") or []),
        ]
        if str(item).strip()
    }
    evidence_banking_tickers: set[str] = set()
    for requirement in query_contract.get("evidence_requirements") or []:
        if not isinstance(requirement, dict):
            continue
        families = {str(item) for item in requirement.get("metric_families") or [] if str(item)}
        if not (families & BANKING_METRIC_FAMILIES):
            continue
        tickers = {str(item).upper() for item in requirement.get("tickers") or [] if str(item).strip()}
        evidence_banking_tickers.update(tickers)
        candidate_tickers.update(tickers)

    if not candidate_tickers:
        return configured

    project_inventory = query_contract.get("project_inventory") if isinstance(query_contract.get("project_inventory"), dict) else {}
    inventory_banking = set(_banking_tickers_for_focus(sorted(candidate_tickers), project_inventory)) if project_inventory else set()
    explicit_banking_scope = inventory_banking or evidence_banking_tickers
    if explicit_banking_scope:
        if not configured:
            return explicit_banking_scope
        if evidence_banking_tickers and not evidence_banking_tickers <= configured:
            return configured | explicit_banking_scope
    return configured


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
    if source_policy == MARKET_SOURCE_POLICY:
        return [
            "Use retrieved market_snapshot evidence only for non-real-time market reaction, relative return, drawdown, and valuation-context claims.",
            "Label market_snapshot evidence with snapshot_id/as_of_date and do not treat it as SEC filing evidence.",
            "Do not use market_snapshot values to overwrite SEC Exact-Value Ledger fundamentals.",
        ]
    if source_policy == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS":
        return [
            "Use retrieved 8-K earnings-release evidence as qualitative support for earnings explanation, guidance, demand commentary, capex/investment cadence, and business momentum when relevant; label it as company-authored unaudited material.",
            "Label 8-K earnings-release evidence as company-authored unaudited material.",
            "Do not use 8-K earnings-release values as audited Exact-Value Ledger facts.",
        ]
    if source_policy == "SEC_PRIMARY_MIXED_RECENT":
        return ["Label 10-Q evidence as unaudited quarterly material when relevant."]
    return []


def _source_policy_hallucination_traps(source_policy: str) -> list[str]:
    if source_policy == MARKET_SOURCE_POLICY:
        return [
            "Do not make unstamped current market or valuation claims without market_snapshot as_of_date.",
            "Do not use market snapshot values to overwrite SEC reported financial facts.",
        ]
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
    elif is_peer and asks_direct_compare and len(focus) <= 8:
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
    _apply_market_snapshot_runtime_seed(fallback, args)
    _apply_industry_snapshot_runtime_seed(fallback, args)
    fallback = _apply_planner_output_limits(fallback)
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
            if _planner_retry_needed(planner_gateway_result) and args.planner_retry_max_tokens > args.planner_max_tokens:
                retry_raw, retry_gateway_result = _ask_query_contract_planner(
                    args,
                    prompt,
                    tickers,
                    years,
                    project_inventory,
                    fallback,
                    max_tokens=args.planner_retry_max_tokens,
                    retry_reason="length_truncated_json",
                )
                retry_parsed = _extract_planner_json_object(retry_raw)
                planner_trace["retry"] = {
                    "reason": "finish_reason_length_parse_failed",
                    "raw_output": retry_raw,
                    "raw_output_chars": len(retry_raw),
                    "llm_gateway": _gateway_debug(retry_gateway_result),
                    "parse_status": "parsed" if retry_parsed else "parse_failed",
                }
                if retry_parsed:
                    raw = retry_raw
                    planner_gateway_result = retry_gateway_result
                    parsed = retry_parsed
                    planner_trace.update(
                        {
                            "status": "parsed_after_length_retry",
                            "raw_output": raw,
                            "raw_output_chars": len(raw),
                            "llm_gateway": _gateway_debug(planner_gateway_result),
                        }
                    )
            if not parsed:
                raise ValueError("planner_returned_no_json_object")
        if planner_trace.get("status") != "parsed_after_length_retry":
            planner_trace["status"] = "parsed"
        planner_trace["parsed_contract"] = parsed
        contract = _normalize_llm_query_contract(parsed, fallback, tickers, years, project_inventory)
        contract = _repair_query_contract_from_prompt(contract, prompt, tickers, years, project_inventory)
        _apply_market_snapshot_runtime_seed(contract, args)
        _apply_industry_snapshot_runtime_seed(contract, args)
        contract = _apply_planner_output_limits(contract)
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
        if getattr(args, "planner_fail_closed", False):
            raise
        if not args.quiet:
            print(f"[plan] llm planner failed; using heuristic contract: {type(exc).__name__}: {exc}")
        fallback["planner_backend"] = f"llm:{args.llm_backend}"
        fallback["planner_status"] = "fallback_after_error"
        fallback["planner_model"] = args.model
        fallback["planner_error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        fallback = _repair_query_contract_from_prompt(fallback, prompt, tickers, years, project_inventory)
        _apply_market_snapshot_runtime_seed(fallback, args)
        _apply_industry_snapshot_runtime_seed(fallback, args)
        fallback = _apply_planner_output_limits(fallback)
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


def _planner_retry_needed(result: dict[str, Any]) -> bool:
    finish_reason = str((result or {}).get("finish_reason") or "").strip().lower()
    if finish_reason == "length":
        return True
    trace_tags = (result or {}).get("trace_tags") if isinstance((result or {}).get("trace_tags"), dict) else {}
    requested = _int_or_none(trace_tags.get("requested_max_tokens"))
    output_tokens = _int_or_none((result or {}).get("output_tokens"))
    return requested is not None and output_tokens is not None and output_tokens >= max(1, requested - 8)


def _detach_planner_trace(contract: dict[str, Any]) -> dict[str, Any] | None:
    trace = contract.pop("_planner_trace", None)
    return trace if isinstance(trace, dict) else None


def _planner_contract_summary(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": contract.get("task_type"),
        "scope_mode": contract.get("scope_mode") or (contract.get("scope") or {}).get("scope_mode"),
        "search_scope_count": len(contract.get("search_scope_tickers") or (contract.get("scope") or {}).get("universe_tickers") or []),
        "focus_count": len(contract.get("focus_tickers") or []),
        "focus_tickers": contract.get("focus_tickers") or [],
        "task_count": len([task for task in contract.get("decomposed_tasks") or [] if isinstance(task, dict)]),
        "evidence_requirement_count": len([req for req in contract.get("evidence_requirements") or [] if isinstance(req, dict)]),
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
    *,
    max_tokens: int | None = None,
    retry_reason: str = "",
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
    requested_max_tokens = int(max_tokens or args.planner_max_tokens)
    return _chat_completion_content(
        args,
        [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        max_tokens=requested_max_tokens,
        temperature=0.0,
        timeout_s=args.planner_timeout_s,
        role="planner",
        trace_tags={
            "inventory_digest": str(project_inventory.get("inventory_digest") or ""),
            "selected_ticker_count": len(tickers),
            "selected_years": ",".join(str(year) for year in years),
            "planner_retry_reason": retry_reason,
        },
    )


def _query_planner_system_prompt(project_inventory: dict[str, Any], tickers: list[str], years: list[int]) -> str:
    inv = inventory_prompt(project_inventory, selected_tickers=tickers, selected_years=years)
    ontology = ", ".join(METRIC_FAMILY_ONTOLOGY)
    task_types = ", ".join(sorted(QUERY_TASK_TYPES))
    runtime_policy = _runtime_source_policy() or "SEC_ONLY_10K"
    try:
        planner_skill = research_skill_prompt("planner", max_chars=1800)
    except Exception:
        planner_skill = ""
    return (
        "你是 FIN Insight Agent 的 Query Contract planner。你的任务不是回答用户问题，而是把自由问题改写成后续 SEC 检索、"
        "Exact-Value Ledger、Judgment Plan 和 synthesis 都能执行的任务协议。\n\n"
        f"{inv}\n\n"
        f"INVESTMENT RESEARCH SKILL\n{planner_skill}\n\n"
        f"ACTIVE SOURCE POLICY: {runtime_policy}\n"
        "CONTRACT RULES\n"
        f"- task_type 必须属于：{task_types}\n"
        f"- required_metric_families / metric_families 只能优先使用这些 ontology 名称：{ontology}\n"
        "- scope_mode 必须是 full_universe、sector_representative 或 focused_peer。full_universe 表示用户要求覆盖完整候选 universe；sector_representative 表示 search_scope 保持完整 universe，但答案聚焦代表公司；focused_peer 表示用户明确点名公司或 peer group。\n"
        "- search_scope_tickers 必须保持 SELECTED COMPANY FILINGS 的完整候选公司范围；不要把它缩成代表公司。系统最终仍以 inventory 解析出的 search_scope 为准。\n"
        "- focus_tickers 必须来自 SELECTED COMPANY FILINGS；如果用户问全局趋势，可以选择 evidence-relevant 代表公司，但必须配合 scope_mode=sector_representative，并在 representative_tickers 中重复这些代表公司。\n"
        "- years 必须来自候选 scope；不要规划项目没有的年份。\n"
        "- filing_types 必须来自 SELECTED COMPANY FILINGS；如 ACTIVE SOURCE POLICY 是 SEC_PRIMARY_MIXED_RECENT 且 10-Q 可用，必须保留 10-Q 及其未经审计季报边界；如 ACTIVE SOURCE POLICY 是 SEC_PRIMARY_MIXED_WITH_8K_EARNINGS 且 8-K 可用，必须保留 8-K 但标注公司未审计管理层口径。\n"
        "- source_tiers 只能来自 PROJECT SOURCE INVENTORY；10-K/10-Q 使用 primary_sec_filing，8-K earnings release 使用 company_authored_unaudited_sec_filing；只有当用户明确或隐含询问股价、估值、市场反应、相对收益、是否 priced in 时，才可额外加入外部 source tier market_snapshot；只有当用户询问行业/宏观/利率/大宗商品/监管/需求环境时，才可加入 industry_snapshot。\n"
        "- market_snapshot 不是 SEC filing；不得用它替代 SEC ledger。若请求 market_snapshot，必须输出 market_snapshot object，包含 required/window/fields/analysis_tools；snapshot_id 和 as_of_date 只有在 seed 明确提供时才能填写，否则留空让后续 coverage 标记 source gap。\n"
        "- industry_snapshot 不是公司披露文件；只能作为行业背景/解释证据，不能替代公司财务事实。若请求 industry_snapshot，必须输出 industry_snapshot object，包含 required/source_families/snapshot_id/as_of_date；source_families 只能来自当前行业数据合约中可解释的行业数据族。\n"
        "- market_snapshot.window 只能是 3M、6M、YTD、1Y；fields 最多 16 个，优先 close_price、market_cap、return_3m、relative_return_vs_benchmark_3m、max_drawdown_3m、volatility_3m、pe_ttm、ev_sales_ttm；analysis_tools 最多 5 个，优先 return_summary、peer_relative_return、valuation_peer_rank、post_filing_event_return、fundamental_market_divergence。\n"
        f"- decomposed_tasks 要服务于用户问题，避免机械套用行业模板；宽问题至少拆成 2 个任务，最多 {PLANNER_MAX_DECOMPOSED_TASKS} 个任务，每个 question_zh 不超过 {PLANNER_TASK_QUESTION_MAX_CHARS} 字。\n"
        "- 如果用户问银行盈利质量、净息差、存贷款或信用风险，优先使用银行指标族："
        "net_interest_income、net_interest_margin、provision_for_credit_losses、net_charge_offs、"
        "allowance_for_credit_losses、nonperforming_assets、nonperforming_loans、deposits、loans、capital_ratio、total_assets。\n"
        "- 如果用户问题包含同行、竞争对手、peer、替代、自研、对比等意图，必须新增 peer_competition_mapping 或 peer_comparison 任务；"
        "该任务必须写 required_tickers 和 peer_tickers，peer_tickers 只能来自 PROJECT SOURCE INVENTORY。\n"
        "- evidence_requirements 要列示每个任务需要哪些证据，而不是输出答案。每条 requirement 可宽可窄，但必须包含 task_id、tickers、years、filing_types、source_tiers、metric_families 和 evidence_routes。\n"
        "- evidence_routes 只能来自 ledger_first、filing_text、8k_commentary、market_snapshot、industry_snapshot、risk_text。财务数值、capex、cash flow、margin、RPO、银行指标等走 ledger_first；10-K/10-Q 管理层讨论和业务解释走 filing_text；8-K 业绩新闻稿和 Exhibit 99 管理层口径走 8k_commentary；市场/估值/相对收益走 market_snapshot；宏观/行业背景/监管/利率/大宗商品/需求环境走 industry_snapshot；风险和反证走 risk_text。\n"
        "- 如果你能判断需要补查当前 inventory 已有的 10-Q、8-K 或 market_snapshot，应把它写入 evidence_requirements，而不是让最终答案写“建议补查”。只有当前 source policy/inventory 不存在的资料才写入 caveat 或 forbidden claim。\n"
        f"- required_caveats 和 forbidden_claims 各最多 {PLANNER_MAX_SHORT_LIST_ITEMS} 条，每条不超过 {PLANNER_MAX_CAVEAT_CHARS} 字；只写短标签式约束。\n"
        "- 不要输出 evidence_gaps；如果用户问到项目资料没有的来源，用一条短 required_caveats/forbidden_claims 标明边界。\n"
        "- 不能输出最终答案、精确数字、metric_id、evidence_id 或 SEC 原文长引用。\n\n"
        "OUTPUT LIMITS\n"
        f"- metric_queries/qualitative_queries 各最多 {PLANNER_MAX_SHORT_LIST_ITEMS} 条，每条不超过 80 字。\n"
        "- 不要解释、不要 markdown、不要代码块、不要 trailing comments。\n\n"
        "RETURN JSON SCHEMA\n"
        "{\n"
        '  "schema_version": "interactive_query_contract_planner_v0.1",\n'
        '  "rewritten_question_zh": "...",\n'
        '  "task_type": "...",\n'
        '  "scope_mode": "full_universe|sector_representative|focused_peer",\n'
        '  "search_scope_tickers": ["..."],\n'
        '  "focus_tickers": ["..."],\n'
        '  "representative_tickers": ["..."],\n'
        '  "years": [2023],\n'
        '  "filing_types": ["10-K", "10-Q", "8-K"],\n'
        '  "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot"],\n'
        '  "market_snapshot": {"required": false, "snapshot_id": "", "as_of_date": "", "window": "3M", "fields": ["return_3m"], "analysis_tools": ["return_summary"]},\n'
        '  "industry_snapshot": {"required": false, "snapshot_id": "", "as_of_date": "", "source_families": ["industry_macro_rates_credit"]},\n'
        '  "analysis_axes": ["growth", "profitability"],\n'
        '  "facets": ["..."],\n'
        '  "metric_families": ["..."],\n'
        '  "metric_queries": ["..."],\n'
        '  "qualitative_queries": ["..."],\n'
        '  "decomposed_tasks": [{"task_id": "...", "question_zh": "...", "priority": "primary|supporting|caveat", "required_tickers": ["..."], "peer_tickers": ["..."], "required_metric_families": ["..."]}],\n'
        '  "evidence_requirements": [{"requirement_id": "...", "task_id": "...", "question_zh": "...", "analysis_intent": "...", "tickers": ["..."], "years": [2023], "filing_types": ["10-K"], "source_tiers": ["primary_sec_filing"], "metric_families": ["revenue"], "period_roles": ["ANNUAL"], "evidence_routes": ["ledger_first", "filing_text"], "section_hints": ["md&a"], "market_fields": ["return_3m"], "source_families": ["industry_macro_rates_credit"], "candidate_budget": 120, "rerank_budget": 64}],\n'
        '  "required_caveats": ["..."],\n'
        '  "forbidden_claims": ["..."],\n'
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
    planned_scope = planned.get("scope") if isinstance(planned.get("scope"), dict) else {}
    planned_focus_values = (
        planned.get("focus_tickers")
        or planned.get("representative_tickers")
        or planned_scope.get("focus_tickers")
        or planned_scope.get("representative_tickers")
    )
    focus = _clamp_tickers(planned_focus_values, tickers) or list(fallback.get("focus_tickers") or tickers)
    filing_types = _clamp_form_types(
        planned.get("filing_types") or planned.get("source_types"),
        _selected_form_types(project_inventory, tickers, years),
    ) or list(fallback.get("filing_types") or ["10-K"])
    allowed_source_tiers = _selected_source_tiers(project_inventory, tickers, years, filing_types)
    market_requested = _market_snapshot_requested_from_planner(planned) or _market_snapshot_requested_from_planner(fallback)
    industry_requested = _industry_snapshot_requested_from_planner(planned) or _industry_snapshot_requested_from_planner(fallback)
    allowed_source_tiers_for_contract = list(allowed_source_tiers)
    if market_requested and MARKET_SOURCE_TIER not in allowed_source_tiers_for_contract:
        allowed_source_tiers_for_contract.append(MARKET_SOURCE_TIER)
    if industry_requested and INDUSTRY_SOURCE_TIER not in allowed_source_tiers_for_contract:
        allowed_source_tiers_for_contract.append(INDUSTRY_SOURCE_TIER)
    source_tiers = _merge_source_tiers(
        _clamp_source_tiers(planned.get("source_tiers") or (planned.get("scope") or {}).get("source_tiers"), allowed_source_tiers_for_contract)
        or _clamp_source_tiers(fallback.get("source_tiers") or (fallback.get("scope") or {}).get("source_tiers"), allowed_source_tiers_for_contract)
        or [],
        _source_policy_source_tiers(filing_types, allowed_source_tiers),
    )
    if market_requested and MARKET_SOURCE_TIER not in source_tiers:
        source_tiers.append(MARKET_SOURCE_TIER)
    if industry_requested and INDUSTRY_SOURCE_TIER not in source_tiers:
        source_tiers.append(INDUSTRY_SOURCE_TIER)
    scope_mode = _normalize_scope_mode(
        planned.get("scope_mode") or planned_scope.get("scope_mode") or fallback.get("scope_mode"),
        tickers,
        focus,
        task_type,
    )
    if scope_mode == "full_universe":
        focus = list(tickers)
    clean.update(
        {
            "task_type": task_type,
            "rewritten_question_zh": _short_text(planned.get("rewritten_question_zh"), 500),
            "scope_mode": scope_mode,
            "search_scope_tickers": tickers,
            "focus_tickers": focus,
            "years": years,
            "filing_types": filing_types,
            "source_tiers": source_tiers,
            "source_policy": _source_policy_for_scope(filing_types, source_tiers),
            "scope": _contract_scope(tickers, focus, years, filing_types, source_tiers, scope_mode=scope_mode),
            "analysis_axes": _string_list(planned.get("analysis_axes"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS) or clean.get("analysis_axes") or [],
            "facets": _string_list(planned.get("facets"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS) or clean.get("facets") or [],
            "metric_families": _metric_family_list(planned.get("metric_families")) or clean.get("metric_families") or [],
            "metric_queries": _string_list(planned.get("metric_queries"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=80) or clean.get("metric_queries") or [],
            "qualitative_queries": _string_list(planned.get("qualitative_queries"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=80) or clean.get("qualitative_queries") or [],
            "required_caveats": _string_list(planned.get("required_caveats"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=PLANNER_MAX_CAVEAT_CHARS)
            or clean.get("required_caveats")
            or [],
            "forbidden_claims": _string_list(planned.get("forbidden_claims"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=PLANNER_MAX_CAVEAT_CHARS)
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
    clean["evidence_requirements"] = _normalize_evidence_requirements_planner_block(
        planned.get("evidence_requirements") or (planned.get("evidence_requirement_plan") or {}).get("requirements"),
        clean,
    )
    if market_requested:
        clean["market_snapshot"] = _normalize_market_snapshot_planner_block(
            planned.get("market_snapshot") or fallback.get("market_snapshot"),
            prompt_text=str(planned.get("rewritten_question_zh") or ""),
        )
    if industry_requested:
        clean["industry_snapshot"] = _normalize_industry_snapshot_planner_block(
            planned.get("industry_snapshot") or fallback.get("industry_snapshot"),
            prompt_text=str(planned.get("rewritten_question_zh") or fallback.get("rewritten_question_zh") or ""),
        )
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
    repaired["scope_mode"] = _normalize_scope_mode(repaired.get("scope_mode"), tickers, focus, str(repaired.get("task_type") or ""))
    if repaired["scope_mode"] == "full_universe":
        focus = list(tickers)
        repaired["focus_tickers"] = focus
    allowed_filing_types = _selected_form_types(project_inventory, tickers, years)
    filing_types = _clamp_form_types(repaired.get("filing_types"), allowed_filing_types)
    repaired["filing_types"] = _source_policy_filing_types(filing_types or allowed_filing_types, allowed_filing_types)
    allowed_source_tiers = _selected_source_tiers(project_inventory, tickers, years, repaired["filing_types"])
    market_blocked = _prompt_excludes_market_snapshot(prompt_text)
    market_requested = False if market_blocked else (
        _has_market_snapshot_intent(prompt_text) or _market_snapshot_requested_from_planner(repaired)
    )
    industry_requested = _has_industry_snapshot_intent(prompt_text) or _industry_snapshot_requested_from_planner(repaired)
    allowed_source_tiers_for_contract = list(allowed_source_tiers)
    if market_requested and MARKET_SOURCE_TIER not in allowed_source_tiers_for_contract:
        allowed_source_tiers_for_contract.append(MARKET_SOURCE_TIER)
    if industry_requested and INDUSTRY_SOURCE_TIER not in allowed_source_tiers_for_contract:
        allowed_source_tiers_for_contract.append(INDUSTRY_SOURCE_TIER)
    repaired["source_tiers"] = _merge_source_tiers(
        _clamp_source_tiers(repaired.get("source_tiers") or (repaired.get("scope") or {}).get("source_tiers"), allowed_source_tiers_for_contract)
        or [],
        _source_policy_source_tiers(repaired["filing_types"], allowed_source_tiers),
    )
    if market_requested and MARKET_SOURCE_TIER not in repaired["source_tiers"]:
        repaired["source_tiers"].append(MARKET_SOURCE_TIER)
    if industry_requested and INDUSTRY_SOURCE_TIER not in repaired["source_tiers"]:
        repaired["source_tiers"].append(INDUSTRY_SOURCE_TIER)
    repaired["source_policy"] = _source_policy_for_scope(repaired["filing_types"], repaired["source_tiers"])
    repaired["scope"] = _contract_scope(
        tickers,
        focus,
        years,
        repaired["filing_types"],
        repaired["source_tiers"],
        scope_mode=repaired["scope_mode"],
    )
    if market_blocked:
        _remove_market_snapshot_contract(repaired)
    elif market_requested:
        _apply_market_snapshot_repairs(repaired, prompt_text)
    if industry_requested:
        repaired["industry_snapshot"] = _normalize_industry_snapshot_planner_block(
            repaired.get("industry_snapshot"),
            prompt_text=prompt_text,
        )

    _append_contract_task(repaired, _user_question_anchor_task(prompt_text, focus, repaired))
    for task in _prompt_driven_repair_tasks(prompt_text, focus, tickers):
        _append_contract_task(repaired, task)
    _ensure_mixed_banking_task(repaired, focus, project_inventory)
    if has_peer_intent:
        _ensure_peer_mapping_task(repaired, prompt_text, focus, tickers, project_inventory)
    if offscope_terms:
        remaining_offscope_terms = _offscope_terms_after_source_policy(offscope_terms, repaired)
        if remaining_offscope_terms:
            _apply_offscope_repairs(repaired, remaining_offscope_terms)
    _strip_unrequested_external_source_tasks(repaired, prompt_text)

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


def _has_market_snapshot_intent(prompt: str) -> bool:
    text = str(prompt or "").lower()
    return _contains_any(
        text,
        (
            "market reaction",
            "market performance",
            "share price",
            "stock price",
            "valuation",
            "market cap",
            "multiple",
            "p/e",
            "ev/sales",
            "return",
            "drawdown",
            "volatility",
            "priced in",
            "price in",
            "跑赢",
            "跑输",
            "股价",
            "市场反应",
            "市场表现",
            "相对收益",
            "收益率",
            "回撤",
            "波动率",
            "估值",
            "市值",
            "已经反映",
            "是否反映",
            "估值语境",
        ),
    )


def _has_industry_snapshot_intent(prompt: str) -> bool:
    text = str(prompt or "").lower()
    return _contains_any(
        text,
        (
            "industry context",
            "sector context",
            "macro",
            "macroeconomic",
            "interest rate",
            "credit cycle",
            "commodity",
            "oil price",
            "natural gas",
            "consumer demand",
            "retail sales",
            "housing",
            "regulatory",
            "regulation",
            "manufacturing",
            "orders",
            "inventory cycle",
            "行业背景",
            "行业环境",
            "板块背景",
            "宏观",
            "利率",
            "信用周期",
            "大宗商品",
            "油价",
            "天然气",
            "消费需求",
            "零售销售",
            "住房",
            "地产",
            "监管",
            "制造业",
            "订单",
            "库存周期",
        ),
    )


def _prompt_excludes_market_snapshot(prompt: str) -> bool:
    text = str(prompt or "").lower()
    negated = _contains_any(
        text,
        (
            "不要引入",
            "不引入",
            "不能引入",
            "不得引入",
            "不要使用",
            "不使用",
            "不能使用",
            "不得使用",
            "do not use",
            "don't use",
            "without",
            "exclude",
            "no external",
        ),
    )
    market_terms = _contains_any(
        text,
        (
            "市场数据",
            "市场快照",
            "当前市场",
            "实时行情",
            "行情",
            "股价",
            "估值",
            "market data",
            "market snapshot",
            "current market",
            "stock price",
            "share price",
            "valuation",
        ),
    )
    return bool(negated and market_terms)


def _remove_market_snapshot_contract(contract: dict[str, Any]) -> None:
    contract.pop("market_snapshot", None)
    source_tiers = [
        str(tier)
        for tier in contract.get("source_tiers") or []
        if str(tier) and str(tier) != MARKET_SOURCE_TIER
    ]
    contract["source_tiers"] = source_tiers
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        task.pop("required_market_fields", None)
        task.pop("required_market_tools", None)
    filing_types = [
        str(form or "").upper().strip()
        for form in contract.get("filing_types") or []
        if str(form or "").strip()
    ]
    contract["source_policy"] = _source_policy_for_scope(filing_types, source_tiers)


def _market_snapshot_requested_from_planner(contract: dict[str, Any]) -> bool:
    tiers = {str(tier or "").strip() for tier in (contract.get("source_tiers") or []) if str(tier or "").strip()}
    market = contract.get("market_snapshot")
    if MARKET_SOURCE_TIER in tiers or str(contract.get("source_policy") or "") == MARKET_SOURCE_POLICY:
        return True
    return isinstance(market, dict) and bool(market.get("required") or market.get("fields") or market.get("analysis_tools"))


def _apply_market_snapshot_runtime_seed(contract: dict[str, Any], args: argparse.Namespace) -> None:
    if not _market_snapshot_requested_from_planner(contract):
        return
    snapshot_id = str(getattr(args, "market_snapshot_id", "") or "").strip()
    as_of_date = str(getattr(args, "market_as_of_date", "") or "").strip()
    if not snapshot_id and not as_of_date:
        return
    market = contract.get("market_snapshot") if isinstance(contract.get("market_snapshot"), dict) else {}
    market = dict(market)
    market["required"] = True
    if snapshot_id:
        market["snapshot_id"] = snapshot_id
    if as_of_date:
        market["as_of_date"] = as_of_date
    contract["market_snapshot"] = _normalize_market_snapshot_planner_block(market, prompt_text="")


def _industry_snapshot_requested_from_planner(contract: dict[str, Any]) -> bool:
    tiers = {str(tier or "").strip() for tier in (contract.get("source_tiers") or []) if str(tier or "").strip()}
    if INDUSTRY_SOURCE_TIER in tiers:
        return True
    industry = contract.get("industry_snapshot")
    if isinstance(industry, dict) and bool(
        industry.get("required") or industry.get("source_families") or industry.get("snapshot_id")
    ):
        return True
    for requirement in contract.get("evidence_requirements") or []:
        if not isinstance(requirement, dict):
            continue
        req_tiers = {
            str(tier or "").strip()
            for tier in _list_like(requirement.get("source_tiers"))
            if str(tier or "").strip()
        }
        req_routes = {
            str(route or "").strip()
            for route in _list_like(requirement.get("evidence_routes"))
            if str(route or "").strip()
        }
        if INDUSTRY_SOURCE_TIER in req_tiers or INDUSTRY_SOURCE_TIER in req_routes:
            return True
    return False


def _apply_industry_snapshot_runtime_seed(contract: dict[str, Any], args: argparse.Namespace) -> None:
    if not _industry_snapshot_requested_from_planner(contract):
        return
    snapshot_id = str(getattr(args, "industry_snapshot_id", "") or "").strip()
    as_of_date = str(getattr(args, "industry_as_of_date", "") or "").strip()
    if not snapshot_id and not as_of_date:
        contract["industry_snapshot"] = _normalize_industry_snapshot_planner_block(contract.get("industry_snapshot"))
        return
    industry = contract.get("industry_snapshot") if isinstance(contract.get("industry_snapshot"), dict) else {}
    industry = dict(industry)
    industry["required"] = True
    if snapshot_id:
        industry["snapshot_id"] = snapshot_id
    if as_of_date:
        industry["as_of_date"] = as_of_date
    contract["industry_snapshot"] = _normalize_industry_snapshot_planner_block(industry)


def _normalize_market_snapshot_planner_block(value: Any, *, prompt_text: str = "") -> dict[str, Any]:
    market = dict(value) if isinstance(value, dict) else {}
    window = str(market.get("window") or market.get("market_window") or "3M").upper().strip()
    if window not in MARKET_WINDOWS:
        window = "3M"
    fields = _market_field_list(market.get("fields") or market.get("market_fields"))
    tools = _market_tool_list(market.get("analysis_tools") or market.get("market_analysis_tools"))
    if not fields:
        fields = _default_market_fields_for_prompt(prompt_text)
    if not tools:
        tools = _default_market_tools_for_prompt(prompt_text)
    return {
        "required": True,
        "snapshot_id": _short_text(market.get("snapshot_id"), 96),
        "as_of_date": _market_date_text(market.get("as_of_date")),
        "window": window,
        "fields": fields,
        "analysis_tools": tools,
        "provider": _short_text(market.get("provider") or "manual_fixture", 80),
        "benchmark_ticker": _short_text(market.get("benchmark_ticker") or "SPY", 16).upper(),
    }


def _normalize_industry_snapshot_planner_block(value: Any, *, prompt_text: str = "") -> dict[str, Any]:
    industry = dict(value) if isinstance(value, dict) else {}
    families = _industry_source_family_list(
        industry.get("source_families")
        or industry.get("required_source_families")
        or industry.get("industry_source_families")
    )
    if not families:
        families = _default_industry_source_families_for_prompt(prompt_text)
    return {
        "required": True,
        "snapshot_id": _short_text(industry.get("snapshot_id"), 96),
        "as_of_date": _market_date_text(industry.get("as_of_date")),
        "source_families": families,
        "provider": _short_text(industry.get("provider") or "mixed_public_industry_sources", 80),
    }


def _default_market_fields_for_prompt(prompt: str) -> list[str]:
    text = str(prompt or "").lower()
    fields = ["close_price", "return_3m", "relative_return_vs_benchmark_3m", "max_drawdown_3m"]
    if _contains_any(text, ("valuation", "multiple", "p/e", "ev/sales", "估值", "市值")):
        fields.extend(["market_cap", "pe_ttm", "ev_sales_ttm"])
    if _contains_any(text, ("volatility", "波动")):
        fields.append("volatility_3m")
    return _dedupe_strings([field for field in fields if field in MARKET_FIELDS])[:16]


def _default_market_tools_for_prompt(prompt: str) -> list[str]:
    text = str(prompt or "").lower()
    tools = ["return_summary", "peer_relative_return"]
    if _contains_any(text, ("valuation", "multiple", "p/e", "ev/sales", "估值", "市值")):
        tools.append("valuation_peer_rank")
    if _contains_any(text, ("8-k", "10-q", "filing", "earnings release", "业绩", "财报")):
        tools.append("post_filing_event_return")
    if _contains_any(text, ("divergence", "priced in", "是否反映", "已经反映", "分歧")):
        tools.append("fundamental_market_divergence")
    return _dedupe_strings([tool for tool in tools if tool in MARKET_ANALYSIS_TOOLS])[:5]


def _default_industry_source_families_for_prompt(prompt: str) -> list[str]:
    text = str(prompt or "").lower()
    families: list[str] = []
    if _contains_any(text, ("rate", "rates", "credit", "bank", "financial", "real estate", "utilities", "利率", "信用", "银行", "金融", "地产", "公用事业")):
        families.append("industry_macro_rates_credit")
    if _contains_any(text, ("consumer", "retail", "restaurant", "auto", "apparel", "消费", "零售", "餐饮", "汽车", "服装")):
        families.append("industry_consumer_macro")
    if _contains_any(text, ("energy", "oil", "gas", "lng", "commodity", "能源", "油价", "天然气", "大宗商品")):
        families.append("industry_energy_commodities")
    if _contains_any(text, ("materials", "metal", "chemical", "input cost", "材料", "金属", "化工", "成本")):
        families.append("industry_materials_commodities")
    if _contains_any(text, ("healthcare", "pharma", "medical", "fda", "cms", "regulatory", "医疗", "制药", "监管")):
        families.append("industry_healthcare_regulatory")
    if _contains_any(text, ("housing", "real estate", "住房", "地产")):
        families.append("industry_housing_real_estate_power")
    if _contains_any(text, ("power", "electricity", "utility", "utilities", "load", "电力", "用电", "公用事业", "负荷", "售电", "电价")):
        families.append("industry_utilities_power_demand")
    if _contains_any(text, ("industrial", "manufacturing", "orders", "inventory", "工业", "制造业", "订单", "库存")):
        families.append("industry_industrial_macro")
    return _dedupe_strings(families)[:12]


def _industry_source_family_list(value: Any) -> list[str]:
    out: list[str] = []
    for item in _list_like(value):
        family = _slug(str(item or ""))
        if family in INDUSTRY_SOURCE_FAMILIES and family not in out:
            out.append(family)
        if len(out) >= 12:
            break
    return out


def _apply_market_snapshot_repairs(contract: dict[str, Any], prompt: str) -> None:
    contract["market_snapshot"] = _normalize_market_snapshot_planner_block(contract.get("market_snapshot"), prompt_text=prompt)
    required_caveats = contract.setdefault("required_caveats", [])
    for caveat in (
        "Market snapshot is non-real-time and must show snapshot_id/as_of_date.",
        "Market data supports valuation/return claims only; SEC ledger controls reported fundamentals.",
    ):
        if caveat not in required_caveats:
            required_caveats.append(caveat)
    forbidden_claims = contract.setdefault("forbidden_claims", [])
    for claim in (
        "Do not make current/latest market claims without market snapshot date.",
        "Do not use market data to overwrite SEC reported facts.",
    ):
        if claim not in forbidden_claims:
            forbidden_claims.append(claim)


def _market_field_list(value: Any) -> list[str]:
    out = []
    for item in _list_like(value):
        field = _slug(str(item or ""))
        if field in MARKET_FIELDS and field not in out:
            out.append(field)
        if len(out) >= 16:
            break
    return out


def _market_tool_list(value: Any) -> list[str]:
    out = []
    for item in _list_like(value):
        tool = _slug(str(item or ""))
        if tool in MARKET_ANALYSIS_TOOLS and tool not in out:
            out.append(tool)
        if len(out) >= 5:
            break
    return out


def _market_date_text(value: Any) -> str:
    text = _short_text(value, 20)
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else ""


def _list_like(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _dedupe_strings(values: list[str]) -> list[str]:
    out = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _source_policy_for_scope(filing_types: list[str], source_tiers: list[str]) -> str:
    forms = {str(form or "").upper().strip() for form in filing_types if str(form or "").strip()}
    tiers = {str(tier or "").strip() for tier in source_tiers if str(tier or "").strip()}
    if MARKET_SOURCE_TIER in tiers:
        return MARKET_SOURCE_POLICY
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


def _strip_unrequested_external_source_tasks(contract: dict[str, Any], prompt: str) -> None:
    prompt_text = str(prompt or "").lower()
    external_groups = {
        "analyst_consensus": ("分析师", "一致预期", "市场预期", "analyst", "consensus"),
        "macro": ("宏观", "美联储", "降息", "fed", "federal reserve", "macro"),
        "geopolitical": ("地缘", "geopolitical"),
    }
    blocked_terms = []
    for terms in external_groups.values():
        if not _contains_any(prompt_text, terms):
            blocked_terms.extend(terms)
    if not blocked_terms:
        return

    def blocked(value: Any) -> bool:
        text = str(value or "").lower()
        return _contains_any(text, blocked_terms)

    contract["decomposed_tasks"] = [
        task
        for task in contract.get("decomposed_tasks") or []
        if not (isinstance(task, dict) and blocked(_task_text_for_repair(task)))
    ]
    for key in ("metric_queries", "qualitative_queries", "facets", "analysis_axes"):
        contract[key] = [item for item in contract.get(key) or [] if not blocked(item)]


def _task_text_for_repair(task: dict[str, Any]) -> str:
    return " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question", "description"))


def _ensure_mixed_banking_task(
    contract: dict[str, Any],
    focus_tickers: list[str],
    project_inventory: dict[str, Any],
) -> None:
    banking_tickers = _banking_tickers_for_focus(focus_tickers, project_inventory)
    if not banking_tickers or len({str(ticker).upper() for ticker in focus_tickers}) <= len(set(banking_tickers)):
        return
    banking_set = set(banking_tickers)
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families = {str(item) for item in task.get("required_metric_families") or []}
        required = {str(item).upper() for item in task.get("required_tickers") or []}
        if families & BANKING_METRIC_FAMILIES and required and required <= banking_set:
            return
    task = _repair_task(
        "mixed_scope_banking_metrics",
        "对混合行业范围中的银行/金融公司单独提取净利息、信贷损失、不良资产等银行指标，且不与非银行公司直接混比。",
        [
            "net_interest_income",
            "net_interest_margin",
            "provision_for_credit_losses",
            "net_charge_offs",
            "nonperforming_assets",
            "allowance_for_credit_losses",
        ],
        banking_tickers,
        priority="supporting",
    )
    tasks = [item for item in contract.get("decomposed_tasks") or [] if isinstance(item, dict)]
    tasks.append(task)
    contract["decomposed_tasks"] = tasks[:PLANNER_MAX_DECOMPOSED_TASKS]


def _banking_tickers_for_focus(focus_tickers: list[str], project_inventory: dict[str, Any]) -> list[str]:
    focus = [str(ticker).upper() for ticker in focus_tickers if str(ticker).strip()]
    focus_set = set(focus)
    banking: set[str] = set()
    for category in project_inventory.get("categories") or []:
        category_name = str(category.get("category") or "").lower()
        if "bank" not in category_name and "financial" not in category_name:
            continue
        banking.update(str(ticker).upper() for ticker in category.get("tickers") or [] if str(ticker).upper() in focus_set)
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if ticker not in focus_set:
            continue
        category_name = str(company.get("category") or "").lower()
        if "bank" in category_name or "financial" in category_name:
            banking.add(ticker)
    return [ticker for ticker in focus if ticker in banking]


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
        "question_zh": _short_text(question_zh, PLANNER_TASK_QUESTION_MAX_CHARS),
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
                PLANNER_TASK_QUESTION_MAX_CHARS,
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
                PLANNER_TASK_QUESTION_MAX_CHARS,
            )
            return
    tasks.append(task)
    contract["decomposed_tasks"] = tasks[:PLANNER_MAX_DECOMPOSED_TASKS]


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
    contract["evidence_gaps"] = gaps[:4]
    caveats = [str(item) for item in contract.get("required_caveats") or [] if str(item)]
    caveat = "外部来源/未来年份/市场预期/股价估值/macro 假设不在当前 SEC-only source policy 内；只能作为 evidence gap。"
    if caveat not in caveats:
        caveats.append(caveat)
    contract["required_caveats"] = [_short_text(item, PLANNER_MAX_CAVEAT_CHARS) for item in caveats[:PLANNER_MAX_SHORT_LIST_ITEMS]]
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
    contract["forbidden_claims"] = [_short_text(item, PLANNER_MAX_CAVEAT_CHARS) for item in forbidden[:PLANNER_MAX_SHORT_LIST_ITEMS]]
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        question = str(task.get("question_zh") or "")
        if _contains_any(question.lower(), tuple(term.lower() for term in gap_terms)):
            task["question_zh"] = _short_text(
                f"{question}（该外部假设当前不支持/unsupported；只检索 SEC 内相关财务或风险披露。）",
                PLANNER_TASK_QUESTION_MAX_CHARS,
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


def _offscope_terms_after_source_policy(gap_terms: list[str], contract: dict[str, Any]) -> list[str]:
    if not _contract_requests_market_snapshot(contract):
        return gap_terms
    market_supported_terms = {
        "stock_price",
        "valuation",
        "股价",
        "估值",
    }
    return [term for term in gap_terms if str(term).lower() not in market_supported_terms]


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
        "scope_mode": contract.get("scope_mode") or (contract.get("scope") or {}).get("scope_mode"),
        "search_scope_tickers": contract.get("search_scope_tickers") or (contract.get("scope") or {}).get("universe_tickers"),
        "focus_tickers": contract.get("focus_tickers"),
        "representative_tickers": (contract.get("scope") or {}).get("representative_tickers") or [],
        "years": contract.get("years"),
        "filing_types": contract.get("filing_types"),
        "source_tiers": contract.get("source_tiers"),
        "facets": contract.get("facets"),
        "metric_families": contract.get("metric_families"),
    }


def _contract_scope(
    search_tickers: list[str],
    focus_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str] | None = None,
    *,
    scope_mode: str = "",
) -> dict[str, Any]:
    normalized_scope_mode = _normalize_scope_mode(scope_mode, search_tickers, focus_tickers, "")
    scope = {
        "scope_mode": normalized_scope_mode,
        "universe_tickers": list(search_tickers),
        "focus_tickers": list(focus_tickers),
        "universe_count": len(search_tickers),
        "focus_count": len(focus_tickers),
        "years": list(years),
        "filing_types": list(filing_types),
        "sec_sections": list(DEFAULT_SECTIONS),
    }
    if normalized_scope_mode == "sector_representative":
        scope["representative_tickers"] = list(focus_tickers)
    if source_tiers:
        scope["source_tiers"] = list(source_tiers)
    return scope


def _normalize_scope_mode(value: Any, search_tickers: list[str], focus_tickers: list[str], task_type: str = "") -> str:
    explicit = str(value or "").strip()
    search_set = {str(ticker).upper() for ticker in search_tickers if str(ticker).strip()}
    focus_set = {str(ticker).upper() for ticker in focus_tickers if str(ticker).strip()}
    if explicit in SCOPE_MODES:
        if explicit == "full_universe" and search_set and focus_set and focus_set < search_set:
            return "sector_representative"
        return explicit
    if search_set and focus_set and focus_set < search_set:
        return "sector_representative"
    if str(task_type or "") in {"ai_industry_financial_trend", "open_analysis"} or len(search_set) >= 5:
        return "full_universe"
    return "focused_peer"


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
    items = [value] if isinstance(value, str) else (value or [])
    for item in items:
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


def _normalize_evidence_requirements_planner_block(value: Any, contract: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_tickers = contract.get("search_scope_tickers") or contract.get("focus_tickers") or []
    allowed_years = {int(year) for year in contract.get("years") or [] if _int_or_none(year) is not None}
    allowed_forms = {str(form).upper().strip() for form in contract.get("filing_types") or [] if str(form).strip()}
    allowed_tiers = {str(tier) for tier in contract.get("source_tiers") or [] if str(tier)}
    requirements: list[dict[str, Any]] = []
    for index, item in enumerate(value or [], start=1):
        if not isinstance(item, dict):
            continue
        routes = [
            route
            for route in _string_list(item.get("evidence_routes") or item.get("retrieval_routes") or item.get("retrieval_route"), max_items=5, max_chars=40)
            if route in PLANNER_RETRIEVAL_ROUTES
        ]
        if not routes:
            continue
        years = []
        seen_years: set[int] = set()
        for year in item.get("years") or []:
            parsed = _int_or_none(year)
            if parsed is None or (allowed_years and int(parsed) not in allowed_years) or int(parsed) in seen_years:
                continue
            seen_years.add(int(parsed))
            years.append(int(parsed))
        row = {
            "requirement_id": _slug(str(item.get("requirement_id") or item.get("evidence_requirement_id") or f"req_{index}"))[:64],
            "task_id": _slug(str(item.get("task_id") or f"task_{index}"))[:64],
            "question_zh": _short_text(item.get("question_zh") or item.get("question") or "", PLANNER_TASK_QUESTION_MAX_CHARS),
            "analysis_intent": _short_text(item.get("analysis_intent"), 80),
            "tickers": _clamp_tickers(item.get("tickers") or item.get("required_tickers"), allowed_tickers)[:16],
            "peer_tickers": _clamp_tickers(item.get("peer_tickers"), allowed_tickers)[:8],
            "years": years[:6],
            "filing_types": [form for form in _clamp_form_types(item.get("filing_types"), sorted(allowed_forms)) if not allowed_forms or form in allowed_forms],
            "source_tiers": [tier for tier in _clamp_source_tiers(item.get("source_tiers"), sorted(allowed_tiers)) if not allowed_tiers or tier in allowed_tiers],
            "metric_families": _metric_family_list(item.get("metric_families") or item.get("required_metric_families")),
            "period_roles": [
                str(role).upper()
                for role in item.get("period_roles") or []
                if str(role).upper() in PLANNER_PERIOD_ROLES
            ][:4],
            "evidence_routes": routes,
            "section_hints": _string_list(item.get("section_hints"), max_items=6, max_chars=48),
            "market_fields": _market_field_list(item.get("market_fields") or item.get("required_market_fields")),
            "candidate_budget": _bounded_int(item.get("candidate_budget"), 0, 1000, 0),
            "rerank_budget": _bounded_int(item.get("rerank_budget"), 0, 1000, 0),
        }
        if not row["tickers"]:
            row["tickers"] = list(contract.get("focus_tickers") or allowed_tickers)[:16]
        if not row["years"]:
            row["years"] = list(contract.get("years") or [])[:6]
        if not row["filing_types"]:
            row["filing_types"] = list(contract.get("filing_types") or [])
        if not row["source_tiers"]:
            row["source_tiers"] = list(contract.get("source_tiers") or [])
        requirements.append(row)
        if len(requirements) >= PLANNER_MAX_DECOMPOSED_TASKS * 3:
            break
    return requirements


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    parsed = _int_or_none(value)
    if parsed is None:
        parsed = default
    return max(minimum, min(maximum, int(parsed)))


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
                "question_zh": _short_text(item.get("question_zh") or item.get("question") or "", PLANNER_TASK_QUESTION_MAX_CHARS),
                "priority": priority,
                "required_metric_families": families,
                "required_tickers": required_tickers,
                "peer_tickers": peer_tickers,
            }
        )
        if len(tasks) >= PLANNER_MAX_DECOMPOSED_TASKS:
            break
    return tasks


def _normalize_evidence_gaps(value: Any) -> list[dict[str, str]]:
    gaps = []
    for item in value or []:
        if isinstance(item, dict):
            task_id = _slug(str(item.get("task_id") or "gap"))[:64] or "gap"
            gap = _short_text(item.get("gap") or item.get("description") or "", PLANNER_MAX_CAVEAT_CHARS)
        else:
            task_id = "gap"
            gap = _short_text(item, PLANNER_MAX_CAVEAT_CHARS)
        if gap:
            gaps.append({"task_id": task_id, "gap": gap})
        if len(gaps) >= 4:
            break
    return gaps


def _planner_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low"} else "medium"


def _apply_planner_output_limits(contract: dict[str, Any]) -> dict[str, Any]:
    limited = dict(contract)
    limited["scope_mode"] = _normalize_scope_mode(
        limited.get("scope_mode") or (limited.get("scope") or {}).get("scope_mode"),
        limited.get("search_scope_tickers") or (limited.get("scope") or {}).get("universe_tickers") or [],
        limited.get("focus_tickers") or (limited.get("scope") or {}).get("focus_tickers") or [],
        str(limited.get("task_type") or ""),
    )
    tasks = []
    for task in limited.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        row = dict(task)
        row["question_zh"] = _short_text(row.get("question_zh") or row.get("question") or "", PLANNER_TASK_QUESTION_MAX_CHARS)
        row["required_metric_families"] = _metric_family_list(row.get("required_metric_families"))
        row["required_tickers"] = _clamp_tickers(row.get("required_tickers"), limited.get("search_scope_tickers") or limited.get("focus_tickers") or [])[:8]
        row["peer_tickers"] = _clamp_tickers(row.get("peer_tickers"), limited.get("search_scope_tickers") or limited.get("focus_tickers") or [])[:8]
        tasks.append(row)
        if len(tasks) >= PLANNER_MAX_DECOMPOSED_TASKS:
            break
    limited["decomposed_tasks"] = tasks
    limited["metric_queries"] = _string_list(limited.get("metric_queries"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=80)
    limited["qualitative_queries"] = _string_list(limited.get("qualitative_queries"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=80)
    limited["analysis_axes"] = _string_list(limited.get("analysis_axes"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=80)
    limited["facets"] = _string_list(limited.get("facets"), max_items=PLANNER_MAX_SHORT_LIST_ITEMS, max_chars=80)
    limited["required_caveats"] = _string_list(
        limited.get("required_caveats"),
        max_items=PLANNER_MAX_SHORT_LIST_ITEMS,
        max_chars=PLANNER_MAX_CAVEAT_CHARS,
    )
    limited["forbidden_claims"] = _string_list(
        limited.get("forbidden_claims"),
        max_items=PLANNER_MAX_SHORT_LIST_ITEMS,
        max_chars=PLANNER_MAX_CAVEAT_CHARS,
    )
    limited["evidence_requirements"] = _normalize_evidence_requirements_planner_block(
        limited.get("evidence_requirements") or (limited.get("evidence_requirement_plan") or {}).get("requirements"),
        limited,
    )
    limited["evidence_gaps"] = _normalize_evidence_gaps(limited.get("evidence_gaps"))[:4]
    if _market_snapshot_requested_from_planner(limited):
        limited["market_snapshot"] = _normalize_market_snapshot_planner_block(limited.get("market_snapshot"))
    if _industry_snapshot_requested_from_planner(limited):
        limited["industry_snapshot"] = _normalize_industry_snapshot_planner_block(limited.get("industry_snapshot"))
    limited["scope"] = _contract_scope(
        list(limited.get("search_scope_tickers") or (limited.get("scope") or {}).get("universe_tickers") or []),
        list(limited.get("focus_tickers") or (limited.get("scope") or {}).get("focus_tickers") or []),
        list(limited.get("years") or (limited.get("scope") or {}).get("years") or []),
        list(limited.get("filing_types") or (limited.get("scope") or {}).get("filing_types") or []),
        list(limited.get("source_tiers") or (limited.get("scope") or {}).get("source_tiers") or []),
        scope_mode=limited["scope_mode"],
    )
    return limited


def _short_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_chars]


def _print_query_contract(contract: dict[str, Any]) -> None:
    focus = contract.get("focus_tickers") or []
    scope = contract.get("search_scope_tickers") or []
    scope_mode = contract.get("scope_mode") or (contract.get("scope") or {}).get("scope_mode") or "<unset>"
    validation = contract.get("query_contract_validation") if isinstance(contract.get("query_contract_validation"), dict) else {}
    focus_text = ",".join(focus[:18]) + (f",...(+{len(focus)-18})" if len(focus) > 18 else "")
    print(
        "[plan] "
        f"task={contract.get('task_type')} "
        f"planner={contract.get('planner_backend', '<unset>')}:{contract.get('planner_status', '<unset>')} "
        f"validation={validation.get('status', '<unset>')} "
        f"scope_mode={scope_mode} "
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


def _print_retrieval_plan(plan: dict[str, Any]) -> None:
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    validation = plan.get("retrieval_plan_validation") if isinstance(plan.get("retrieval_plan_validation"), dict) else {}
    route_counts = summary.get("route_counts") if isinstance(summary.get("route_counts"), dict) else {}
    route_text = ",".join(f"{key}={value}" for key, value in sorted(route_counts.items())) or "<none>"
    print(
        "[retrieval-plan] "
        f"validation={validation.get('status', '<unset>')} "
        f"tasks={summary.get('task_count', 0)} "
        f"routes={summary.get('route_count', 0)} "
        f"bge_budget={summary.get('rerank_budget_total', 0)} "
        f"routes_by_type={route_text}"
    )


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
                print(f"   证据: {'；'.join(evidence_refs)}")
        for idx, point in enumerate(answer.get("key_points") or [], start=1):
            print(f"\n{idx}. {_clean_display_text(point.get('point') or '')}")
            mids = point.get("metric_ids") or []
            eids = point.get("evidence_ids") or []
            metric_refs = _format_metric_refs([str(item) for item in mids], metric_rows)
            evidence_refs = _format_evidence_refs([str(item) for item in eids], evidence_rows)
            if metric_refs:
                print(f"   依据数值: {'；'.join(metric_refs)}")
            if evidence_refs:
                print(f"   证据: {'；'.join(evidence_refs)}")
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
            print(f"   证据: {'；'.join(evidence_refs)}")


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
    role = str(row.get("metric_role") or "").strip().lower()
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
    base_label = family_labels.get(family, family or "指标")
    label = _display_metric_role_label(base_label, role, name)
    if name and len(name) <= 42 and name.lower() not in {"total", "revenue", "net sales"}:
        return f"{name} ({label})"
    return label


def _display_metric_role_label(base_label: str, role: str, name: str) -> str:
    name_lower = str(name or "").lower()
    if role == "percentage_rate":
        if any(term in name_lower for term in ("growth", "grew", "increase", "decrease", "decline")):
            if base_label.endswith("收入"):
                return f"{base_label}增长率"
            return f"{base_label}变化率"
        if "margin" in name_lower or "毛利率" in base_label or base_label.endswith("率"):
            return base_label
        return f"{base_label}百分比指标"
    if role == "period_change_amount":
        return f"{base_label}期间变动额"
    if role == "derived_value":
        return f"{base_label}（派生）"
    return base_label


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

    if evidence_id.startswith("MARKET_SNAPSHOT::") or source_tier == MARKET_SOURCE_TIER:
        parts = evidence_id.split("::")
        ticker = (parts[2] if len(parts) > 2 else str(row.get("ticker") or "")).upper()
        window = str(row.get("window") or (parts[3] if len(parts) > 3 else "") or "").strip()
        as_of = str(row.get("as_of_date") or (parts[4] if len(parts) > 4 else "") or "").strip()
        snapshot_id = str(row.get("snapshot_id") or (parts[1] if len(parts) > 1 else "") or "").strip()
        label = " ".join(part for part in (ticker, window, "market snapshot", f"as_of={as_of}" if as_of else "") if part).strip()
        suffix = boundary or "market snapshot; non-real-time"
        if snapshot_id:
            suffix = f"{suffix}; snapshot_id={snapshot_id}"
        return f"{label} ({suffix})"

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
        MARKET_SOURCE_TIER: "market snapshot; non-real-time",
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
    focus = {str(ticker).upper() for ticker in focus_tickers or [] if str(ticker).strip()}
    return bool(focus and focus <= {"JPM"})


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
    cache_key = _index_cache_token(index_dir)
    cached = _OBJECT_RECORDS_RUNTIME_CACHE.get(cache_key)
    if cached is not None:
        return cached
    sqlite_path = index_dir / "records.sqlite"
    if sqlite_path.exists():
        return {}
    return _load_object_records_cached(str(index_dir.resolve()))


def _load_object_records_for_ids(index_dir: Path, object_ids: Iterable[Any]) -> dict[str, dict[str, Any]]:
    ids = [str(object_id) for object_id in object_ids if str(object_id or "").strip()]
    if not ids:
        return {}
    sqlite_path = index_dir / "records.sqlite"
    if not sqlite_path.exists():
        records = _load_object_records(index_dir)
        return {object_id: records[object_id] for object_id in ids if object_id in records}

    unique_ids = list(dict.fromkeys(ids))
    records: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(str(sqlite_path)) as con:
        con.row_factory = sqlite3.Row
        for start in range(0, len(unique_ids), 400):
            chunk = unique_ids[start : start + 400]
            placeholders = ", ".join("?" for _ in chunk)
            rows = con.execute(
                f"SELECT object_id, record_json FROM object_records WHERE object_id IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                try:
                    record = json.loads(str(row["record_json"] or "{}"))
                except json.JSONDecodeError:
                    continue
                object_id = str(row["object_id"] or record.get("object_id") or "")
                if object_id:
                    records[object_id] = record
    return records


def _ledger_supplement_scope_records_from_index(
    index_dir: Path,
    case: dict[str, Any],
    context_records: dict[str, dict[str, Any]],
    query_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    sqlite_path = index_dir / "records.sqlite"
    if not sqlite_path.exists():
        records = _load_object_records(index_dir)
        if context_records:
            records = {**records, **context_records}
        return _ledger_supplement_scope_records(case, records, query_contract)

    family_tickers = _contract_required_family_tickers(query_contract)
    focus = set().union(*family_tickers.values()) if family_tickers else set()
    if not focus:
        focus = {str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)}
    years = {int(year) for year in case.get("years") or [] if _int_or_none(year) is not None}
    filing_types = {
        _normalize_form_type(item)
        for item in (case.get("filing_types") or query_contract.get("filing_types") or [])
        if _normalize_form_type(item)
    }
    source_tiers = {
        str(item)
        for item in (case.get("source_tiers") or query_contract.get("source_tiers") or [])
        if str(item)
    }

    where: list[str] = []
    params: list[Any] = []
    if focus:
        placeholders = ", ".join("?" for _ in focus)
        where.append(f"ticker IN ({placeholders})")
        params.extend(sorted(focus))
    if years:
        placeholders = ", ".join("?" for _ in years)
        where.append(f"fiscal_year IN ({placeholders})")
        params.extend(sorted(years))
    if filing_types:
        placeholders = ", ".join("?" for _ in filing_types)
        where.append(f"form_type IN ({placeholders})")
        params.extend(sorted(filing_types))
    if source_tiers:
        placeholders = ", ".join("?" for _ in source_tiers)
        where.append(f"source_tier IN ({placeholders})")
        params.extend(sorted(source_tiers))
    clauses = " AND ".join(where) if where else "1=1"

    records: list[dict[str, Any]] = []
    with sqlite3.connect(str(sqlite_path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            f"SELECT record_json FROM object_records WHERE {clauses} ORDER BY idx LIMIT ?",
            [*params, 50000],
        ).fetchall()
        for row in rows:
            try:
                record = json.loads(str(row["record_json"] or "{}"))
            except json.JSONDecodeError:
                continue
            records.append(record)
    return records


def _register_object_records(index_dir: Path, records: Iterable[dict[str, Any]]) -> None:
    cache_key = _index_cache_token(index_dir)
    _OBJECT_RECORDS_RUNTIME_CACHE.clear()
    _OBJECT_RECORDS_RUNTIME_CACHE[cache_key] = {
        str(row.get("object_id") or ""): row
        for row in records
        if str(row.get("object_id") or "")
    }


@lru_cache(maxsize=4)
def _load_object_records_cached(index_dir: str) -> dict[str, dict[str, Any]]:
    path = Path(index_dir) / "records.jsonl"
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
    return any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", normalized) for term in human_terms)


def _banking_ledger_row_allowed(row: dict[str, Any], text: str, name_lower: str, source_signal_lower: str) -> bool:
    family = str(row.get("metric_family") or "")
    if family not in BANKING_METRIC_FAMILIES:
        return True
    if str(row.get("extraction_method") or "") != "banking_context_runtime_heuristic" and not str(row.get("column_label") or "").strip():
        return False
    if _is_human_capital_ledger_topic(text):
        return False
    metric_scope_text = f"{name_lower} {source_signal_lower}"
    if any(term in metric_scope_text for term in ("income tax", "tax expense", "tax benefit", "provision for income taxes")):
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
    if allowed_families:
        allowed_families = _expand_metric_family_aliases(allowed_families)
    else:
        allowed_families = _contract_required_metric_families(query_contract)
    if allowed_families and family not in allowed_families:
        return False
    if rules.get("drop_human_capital_tables") and _is_human_capital_ledger_topic(row_text_lower):
        return False
    if _is_excluded_ledger_topic(family, row_text_lower):
        return False
    if any(term in column_label_lower for term in (" over ", " vs ", " versus ")):
        return False
    if re.search(r"(^|[\s$%])change($|\s)", column_label_lower) and row.get("cell_kind") != "period_change_rate":
        return False
    if "by segment" in column_label_lower:
        return False
    if family in BANKING_METRIC_FAMILIES:
        banking_scope = _contract_banking_metric_tickers(query_contract)
        if banking_scope and ticker not in banking_scope:
            return False
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
        is_growth_rate = str(row.get("metric_role") or "") == "percentage_rate" and (
            row.get("cell_kind") == "period_change_rate"
            or _contains_any(
                row_text_lower,
                ("increase", "increased", "decrease", "decreased", "grew", "growth", "declined"),
            )
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
    requested_metric_families = _expand_metric_family_aliases(query_contract.get("metric_families") or [])
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)}
    if len(focus) <= 1 and requested_metric_families and requested_metric_families <= {"capex", "capital_expenditure_proxy"}:
        return _cap_single_metric_ledger_rows(rows, max_rows)
    task_family_groups = _task_metric_family_groups(query_contract)
    if len(task_family_groups) >= 2:
        return _cap_task_balanced_ledger_rows(rows, task_family_groups, query_contract, max_rows)
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


def _cap_single_metric_ledger_rows(rows: list[dict[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    capped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = _ledger_dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        capped.append(row)
        if len(capped) >= max_rows:
            break
    return capped


def _task_metric_family_groups(query_contract: dict[str, Any]) -> list[list[str]]:
    groups: list[list[str]] = []
    for task in query_contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        families = [str(item) for item in task.get("required_metric_families") or [] if str(item)]
        if families:
            groups.append(families)
    return groups


def _cap_task_balanced_ledger_rows(
    rows: list[dict[str, Any]],
    task_family_groups: list[list[str]],
    query_contract: dict[str, Any],
    max_rows: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str, str]] = set()
    family_ticker_year_counts: Counter[tuple[str, str, str]] = Counter()
    focus = {str(item).upper() for item in query_contract.get("focus_tickers") or [] if str(item)}
    required_families = _contract_required_metric_families(query_contract)
    default_family_year_limit = 3 if len(focus) <= 1 and len(required_families) <= 2 else 1
    per_family_ticker_year_limit = int(os.environ.get("LEDGER_PER_FAMILY_TICKER_YEAR_LIMIT", str(default_family_year_limit)))

    def add(row: dict[str, Any]) -> bool:
        if len(selected) >= max_rows:
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

    target_per_task = max(2, max_rows // max(1, len(task_family_groups)))
    for families in task_family_groups:
        before = len(selected)
        family_set = _expand_metric_family_aliases(families)
        for row in rows:
            if str(row.get("metric_family") or "") in family_set:
                add(row)
            if len(selected) - before >= target_per_task or len(selected) >= max_rows:
                break
    for row in rows:
        add(row)
        if len(selected) >= max_rows:
            break
    return selected


def _cap_banking_ledger_rows(rows: list[dict[str, Any]], query_contract: dict[str, Any], max_rows: int) -> list[dict[str, Any]]:
    effective_max = min(max_rows, int(os.environ.get("BANKING_LEDGER_EFFECTIVE_MAX_ROWS", "48")))
    task_family_groups = _task_metric_family_groups(query_contract)
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
    task_family_groups = _task_metric_family_groups(query_contract)
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


def _raw_amount_is_period_change(raw: str, context: str) -> bool:
    raw_text = str(raw or "").strip()
    source = str(context or "")
    if not raw_text or not source:
        return False
    candidates = [
        raw_text,
        raw_text.replace("$", "").strip(),
        re.sub(r"\s+", " ", raw_text.replace("$", "")).strip(),
    ]
    lowered = source.lower()
    for candidate in {item.lower() for item in candidates if item}:
        start = lowered.find(candidate)
        if start < 0:
            continue
        before = lowered[max(0, start - 80) : start]
        if re.search(
            r"(?:increase|increased|decrease|decreased|change|changed|grew|declined|higher|lower|up|down)\s+(?:by|of|approximately|about|nearly|roughly)?\s*$",
            before,
        ):
            return True
    return False


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
        "market_evidence_path": args.market_evidence_path or None,
        "industry_evidence_path": args.industry_evidence_path or None,
        "bm25_index_dir": args.bm25_index_dir,
        "object_bm25_index_dir": args.object_bm25_index_dir,
        "bge_model": args.bge_model,
        "bge_device": args.bge_device,
        "bge_first": args.bge_first,
        "auto_start_qwen": args.auto_start_qwen,
        "context_runner": args.context_runner,
        "effective_context_runner": _context_runner_mode(args),
        "evidence_top_k": args.evidence_top_k,
        "object_top_k": args.object_top_k,
        "max_context_rows": args.max_context_rows,
        "reranker_top_k": args.reranker_top_k,
        "ledger_max_rows": args.ledger_max_rows,
        "max_tokens": args.max_tokens,
        "query_planner": args.query_planner,
        "planner_max_tokens": args.planner_max_tokens,
        "planner_retry_max_tokens": args.planner_retry_max_tokens,
        "planner_fail_closed": bool(args.planner_fail_closed),
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
