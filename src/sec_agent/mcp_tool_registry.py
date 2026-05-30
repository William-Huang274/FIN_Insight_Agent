from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from sec_agent.industry_snapshot import query_industry_snapshot
from sec_agent.ledger_store import query_ledger_facts
from sec_agent.mcp_contracts import get_mcp_tool_contract, list_mcp_tool_contracts
from sec_agent.mcp_runtime import read_bounded_artifact
from sec_agent.workbench.artifacts import inspect_run_artifacts


REPO_ROOT = Path(__file__).resolve().parents[2]
_INTERACTIVE_MODULE: ModuleType | None = None


def list_registered_tools() -> list[dict[str, Any]]:
    return list_mcp_tool_contracts()


def invoke_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = dict(arguments or {})
    handler = _HANDLERS.get(str(tool_name or ""))
    if handler is None:
        try:
            contract = get_mcp_tool_contract(str(tool_name or ""))
        except KeyError:
            return {"status": "error", "error": f"unknown_tool:{tool_name}"}
        return {
            "status": "error",
            "error": "tool_not_bound_in_registry",
            "tool_name": tool_name,
            "handler": contract.get("handler") or {},
        }
    try:
        return handler(args)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"{type(exc).__name__}:{exc}", "tool_name": tool_name}


def _invoke_ledger(args: dict[str, Any]) -> dict[str, Any]:
    db_path = args.get("ledger_store_path") or args.get("db_path") or ""
    if not str(db_path).strip():
        return {"status": "error", "error": "ledger_store_path_required"}
    rows = query_ledger_facts(
        db_path,
        case_id=str(args.get("case_id") or "__mcp__"),
        object_ids=_list_arg(args.get("object_ids")),
        tickers=_list_arg(args.get("tickers")),
        years=[int(year) for year in _list_arg(args.get("years")) if str(year).isdigit()],
        filing_types=_list_arg(args.get("filing_types")),
        source_tiers=_list_arg(args.get("source_tiers")),
        metric_families=_list_arg(args.get("metric_families")),
        period_roles=_list_arg(args.get("period_roles")),
        limit=int(args.get("limit") or 5000),
    )
    return {
        "status": "ok",
        "ledger_rows": rows,
        "row_count": len(rows),
        "missing_dimensions": [],
        "artifact_refs": [{"artifact_id": "ledger_store", "path": str(Path(db_path).resolve()), "digest": "", "row_count": len(rows)}],
    }


def _invoke_sec_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {"status": "error", "error": "query_required", "context_rows": []}
    validation_error = _validate_sec_search_arguments(args)
    if validation_error:
        return {"status": "error", "error": validation_error, "context_rows": []}

    interactive = _load_interactive_module()
    runtime_args = _interactive_args_for_sec_search(args)
    plan = interactive.build_query_plan_for_graph(runtime_args, query)
    query_contract = _overlay_sec_search_contract(plan.get("query_contract") or {}, args, query)
    output_dir = str(args.get("output_dir") or "").strip()
    if output_dir:
        resolved_output_dir = Path(output_dir).resolve()
    else:
        resolved_output_dir = _default_mcp_output_dir(query)
    graph_state = {
        "user_query": query,
        "run_id": str(args.get("run_id") or "__mcp_sec_search__"),
        "output_dir": str(resolved_output_dir),
        "selected_tickers": query_contract.get("search_scope_tickers") or plan.get("selected_tickers") or [],
        "selected_years": query_contract.get("years") or plan.get("selected_years") or [],
        "query_contract": query_contract,
    }
    result = interactive.retrieve_context_for_graph(runtime_args, graph_state)
    rows = [row for row in result.get("context_rows") or [] if isinstance(row, dict)]
    trace = result.get("retrieval_trace") if isinstance(result.get("retrieval_trace"), dict) else {}
    candidate_counts = _candidate_counts_from_trace(trace, rows)
    return {
        "status": "ok" if rows else "partial",
        "context_rows": rows,
        "row_count": len(rows),
        "query_contract": query_contract,
        "selected_tickers": graph_state["selected_tickers"],
        "selected_years": graph_state["selected_years"],
        "retrieval_trace": trace,
        "context_runtime": result.get("context_runtime") if isinstance(result.get("context_runtime"), dict) else {},
        "candidate_counts": candidate_counts,
        "artifact_refs": _artifact_refs_from_mapping(result.get("artifact_refs"), row_count=len(rows)),
        "source_gaps": _sec_search_source_gaps(query_contract, rows),
    }


def _invoke_market(args: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(args.get("market_evidence_path") or "")).resolve()
    if not path.exists():
        return {"status": "error", "error": "market_evidence_path_not_found", "path": str(path)}
    tickers = {ticker.upper() for ticker in _list_arg(args.get("tickers"))}
    snapshot_id = str(args.get("snapshot_id") or "").strip()
    limit = max(1, min(int(args.get("limit") or 1000), 1000))
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper()
            if tickers and ticker not in tickers:
                continue
            if snapshot_id and str(row.get("snapshot_id") or "") != snapshot_id:
                continue
            rows.append(row)
            if len(rows) >= limit:
                break
    field_gaps = []
    fields = _list_arg(args.get("fields"))
    if fields:
        for ticker in sorted(tickers):
            ticker_rows = [row for row in rows if str(row.get("ticker") or "").upper() == ticker]
            for field in fields:
                if ticker_rows and all(row.get(field) in {None, ""} for row in ticker_rows):
                    field_gaps.append({"ticker": ticker, "field": field, "reason": "missing_or_null"})
    return {
        "status": "ok" if rows else "partial",
        "market_rows": rows,
        "snapshot_id": snapshot_id or (str(rows[0].get("snapshot_id") or "") if rows else ""),
        "as_of_date": str(args.get("as_of_date") or (rows[0].get("as_of_date") if rows else "") or ""),
        "field_gaps": field_gaps,
        "artifact_refs": [{"artifact_id": "market_evidence_rows", "path": str(path), "digest": "", "row_count": len(rows)}],
    }


def _invoke_industry(args: dict[str, Any]) -> dict[str, Any]:
    return query_industry_snapshot(
        source_families=_list_arg(args.get("source_families")),
        providers=_list_arg(args.get("providers")),
        datasets=_list_arg(args.get("datasets")),
        series_ids=_list_arg(args.get("series_ids")),
        facets=args.get("facets") if isinstance(args.get("facets"), dict) else {},
        start_date=str(args.get("start_date") or ""),
        end_date=str(args.get("end_date") or ""),
        latest_only=bool(args.get("latest_only")),
        industry_evidence_path=str(args.get("industry_evidence_path") or ""),
        industry_snapshot_db_path=str(args.get("industry_snapshot_db_path") or ""),
        limit=int(args.get("limit") or 500),
    )


def _load_interactive_module() -> ModuleType:
    global _INTERACTIVE_MODULE
    if _INTERACTIVE_MODULE is not None:
        return _INTERACTIVE_MODULE
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_mcp_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load interactive adapter: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _INTERACTIVE_MODULE = module
    return module


def _interactive_args_for_sec_search(args: dict[str, Any]) -> argparse.Namespace:
    limit = _bounded_int(args.get("limit"), default=120, minimum=1, maximum=500)
    candidate_budget = _bounded_int(args.get("candidate_budget"), default=0, minimum=0, maximum=2000)
    rerank_budget = _bounded_int(args.get("rerank_budget"), default=0, minimum=0, maximum=500)
    bge_first = _bool_arg(args.get("bge_first"), default=_env_bool("BGE_FIRST"))
    bge_device = str(args.get("bge_device") or os.environ.get("BGE_DEVICE") or ("cuda" if bge_first else "cpu"))
    return argparse.Namespace(
        llm_backend=str(args.get("llm_backend") or os.environ.get("LLM_BACKEND") or "qwen_vllm"),
        base_url=str(args.get("base_url") or os.environ.get("BASE_URL") or "http://127.0.0.1:8000"),
        chat_completions_path=str(args.get("chat_completions_path") or os.environ.get("CHAT_COMPLETIONS_PATH") or "/v1/chat/completions"),
        model=str(args.get("model") or os.environ.get("MODEL_NAME") or "qwen9b"),
        api_key_env=str(args.get("api_key_env") or os.environ.get("API_KEY_ENV") or ""),
        reasoning_effort=str(args.get("reasoning_effort") or os.environ.get("REASONING_EFFORT") or ""),
        enable_thinking=_bool_arg(args.get("enable_thinking"), default=_env_bool("ENABLE_THINKING")),
        disable_thinking=_bool_arg(args.get("disable_thinking"), default=_env_bool("DISABLE_THINKING")),
        prompt="",
        tickers=_csv_arg(args.get("tickers")) or os.environ.get("TICKERS") or "ALL",
        years=_csv_arg(args.get("years")) or os.environ.get("YEARS") or "",
        manifest_path=str(args.get("manifest_path") or os.environ.get("MANIFEST_PATH") or "data/processed_private/manifests/sec_tech_10k_manifest.jsonl"),
        source_gap_path=str(args.get("source_gap_path") or os.environ.get("SOURCE_GAP_PATH") or ""),
        market_evidence_path=str(args.get("market_evidence_path") or os.environ.get("MARKET_EVIDENCE_PATH") or ""),
        market_snapshot_id=str(args.get("market_snapshot_id") or os.environ.get("MARKET_SNAPSHOT_ID") or ""),
        market_as_of_date=str(args.get("market_as_of_date") or os.environ.get("MARKET_AS_OF_DATE") or ""),
        industry_evidence_path=str(args.get("industry_evidence_path") or os.environ.get("INDUSTRY_EVIDENCE_PATH") or ""),
        industry_snapshot_id=str(args.get("industry_snapshot_id") or os.environ.get("INDUSTRY_SNAPSHOT_ID") or ""),
        industry_as_of_date=str(args.get("industry_as_of_date") or os.environ.get("INDUSTRY_AS_OF_DATE") or ""),
        bm25_index_dir=str(args.get("bm25_index_dir") or os.environ.get("BM25_INDEX_DIR") or "data/indexes/bm25/sec_tech_10k"),
        object_bm25_index_dir=str(args.get("object_bm25_index_dir") or os.environ.get("OBJECT_BM25_INDEX_DIR") or "data/indexes/bm25/sec_tech_10k_objects"),
        bge_model=str(args.get("bge_model") or os.environ.get("BGE_MODEL") or "/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3"),
        bge_device=bge_device,
        evidence_top_k=_bounded_int(args.get("evidence_top_k"), default=int(os.environ.get("EVIDENCE_TOP_K", "4")), minimum=1, maximum=100),
        object_top_k=_bounded_int(args.get("object_top_k"), default=int(os.environ.get("OBJECT_TOP_K", "4")), minimum=1, maximum=100),
        max_context_rows=limit,
        reranker_top_k=rerank_budget or min(limit, int(os.environ.get("RERANKER_TOP_K", "120"))),
        reranker_candidate_limit=candidate_budget or int(os.environ.get("RERANKER_CANDIDATE_LIMIT", "800")),
        reranker_batch_size=_bounded_int(args.get("reranker_batch_size"), default=int(os.environ.get("RERANKER_BATCH_SIZE", "16")), minimum=1, maximum=256),
        reranker_max_length=_bounded_int(args.get("reranker_max_length"), default=int(os.environ.get("RERANKER_MAX_LENGTH", "1024")), minimum=128, maximum=4096),
        reranker_doc_max_chars=_bounded_int(args.get("reranker_doc_max_chars"), default=int(os.environ.get("RERANKER_DOC_MAX_CHARS", "3000")), minimum=200, maximum=20000),
        ledger_store_path=str(args.get("ledger_store_path") or os.environ.get("LEDGER_STORE_PATH") or ""),
        ledger_max_rows=_bounded_int(args.get("ledger_max_rows"), default=int(os.environ.get("LEDGER_MAX_ROWS", "80")), minimum=1, maximum=10000),
        max_tokens=_bounded_int(args.get("max_tokens"), default=int(os.environ.get("MAX_TOKENS", "4000")), minimum=1, maximum=64000),
        temperature=float(args.get("temperature") or os.environ.get("TEMPERATURE") or "0.0"),
        query_planner=str(args.get("query_planner") or os.environ.get("QUERY_PLANNER") or "heuristic"),
        planner_max_tokens=_bounded_int(args.get("planner_max_tokens"), default=int(os.environ.get("PLANNER_MAX_TOKENS", "3000")), minimum=256, maximum=64000),
        planner_retry_max_tokens=_bounded_int(args.get("planner_retry_max_tokens"), default=int(os.environ.get("PLANNER_RETRY_MAX_TOKENS", "4000")), minimum=256, maximum=64000),
        planner_timeout_s=_bounded_int(args.get("planner_timeout_s"), default=int(os.environ.get("PLANNER_TIMEOUT_S", "180")), minimum=1, maximum=3600),
        planner_fail_closed=_bool_arg(args.get("planner_fail_closed"), default=_env_bool("PLANNER_FAIL_CLOSED")),
        output_root=str(args.get("output_root") or "eval/sec_cases/outputs/interactive_sec_agent"),
        print_config=False,
        plan_only=False,
        auto_start_qwen=_bool_arg(args.get("auto_start_qwen"), default=_env_bool("AUTO_START_QWEN")),
        bge_first=bge_first,
        context_runner=str(args.get("context_runner") or os.environ.get("CONTEXT_RUNNER") or os.environ.get("SEC_AGENT_CONTEXT_RUNNER") or "auto"),
        quiet=_bool_arg(args.get("quiet"), default=True),
    )


def _overlay_sec_search_contract(contract: dict[str, Any], args: dict[str, Any], query: str) -> dict[str, Any]:
    clean = dict(contract or {})
    tickers = [str(ticker).upper() for ticker in _list_arg(args.get("tickers"))]
    years = [int(year) for year in _list_arg(args.get("years")) if str(year).isdigit()]
    filing_types = [str(form).upper() for form in _list_arg(args.get("filing_types"))]
    source_tiers = [str(tier) for tier in _list_arg(args.get("source_tiers"))]
    metric_families = [str(family) for family in _list_arg(args.get("metric_families"))]
    period_roles = [str(role).upper() for role in _list_arg(args.get("period_roles"))]
    if tickers:
        clean["search_scope_tickers"] = tickers
        clean["focus_tickers"] = tickers
    if years:
        clean["years"] = years
    if filing_types:
        clean["filing_types"] = filing_types
    if source_tiers:
        clean["source_tiers"] = source_tiers
    if metric_families:
        clean["metric_families"] = metric_families
    if period_roles:
        clean["period_roles"] = period_roles

    requirements, source_gaps = _evidence_requirements_from_args(args, clean, query)
    if requirements:
        clean["evidence_requirements"] = requirements
    if source_gaps:
        clean["source_coverage_gaps"] = [*(clean.get("source_coverage_gaps") or []), *source_gaps]
    return clean


def _evidence_requirements_from_args(args: dict[str, Any], contract: dict[str, Any], query: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compiled = _compile_available_sec_requirements(args, contract, query)
    if compiled:
        return compiled
    requirement = _single_evidence_requirement_from_args(args, contract, query)
    return ([requirement] if requirement else [], [])


def _single_evidence_requirement_from_args(args: dict[str, Any], contract: dict[str, Any], query: str) -> dict[str, Any]:
    route = str(args.get("retrieval_route") or "").strip()
    routes = [route] if route else []
    candidate_budget = _bounded_int(args.get("candidate_budget"), default=0, minimum=0, maximum=2000)
    rerank_budget = _bounded_int(args.get("rerank_budget"), default=0, minimum=0, maximum=500)
    requirement = {
        "requirement_id": str(args.get("evidence_requirement_id") or "mcp_sec_search_requirement"),
        "question": query[:240],
        "question_zh": query[:120],
        "priority": "primary",
        "tickers": contract.get("search_scope_tickers") or contract.get("focus_tickers") or [],
        "years": contract.get("years") or [],
        "filing_types": contract.get("filing_types") or [],
        "source_tiers": contract.get("source_tiers") or [],
        "metric_families": contract.get("metric_families") or [],
        "period_roles": contract.get("period_roles") or [],
        "evidence_routes": routes,
    }
    if candidate_budget:
        requirement["candidate_budget"] = candidate_budget
    if rerank_budget:
        requirement["rerank_budget"] = rerank_budget
    return requirement


def _compile_available_sec_requirements(
    args: dict[str, Any],
    contract: dict[str, Any],
    query: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Compile mixed SEC source requests to available form/year route scopes.

    A mixed 10-K + 8-K request often means "use FY2025 10-K and the latest
    FY2026 8-K", not the Cartesian product of every selected year and form.
    This keeps the source contract strict while avoiding impossible route
    scopes before the benchmark source resolver runs.
    """
    explicit_route = str(args.get("retrieval_route") or "").strip()
    requested_forms = [_normalize_form_type(item) for item in contract.get("filing_types") or [] if _normalize_form_type(item)]
    requested_tiers = [str(item) for item in contract.get("source_tiers") or [] if str(item)]
    if explicit_route or len(set(requested_forms)) <= 1:
        return None
    manifest_rows = _read_manifest_rows(args.get("manifest_path"))
    if not manifest_rows:
        return None

    requested_tickers = {str(item).upper() for item in contract.get("search_scope_tickers") or contract.get("focus_tickers") or [] if str(item)}
    requested_years = {int(item) for item in contract.get("years") or [] if str(item).isdigit()}
    requested_form_set = set(requested_forms)
    requested_tier_set = set(requested_tiers)
    available_groups: dict[tuple[int, str, str, str], set[str]] = {}
    available_keys: set[tuple[str, int, str, str]] = set()
    for row in manifest_rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        year = _int_or_none(row.get("fiscal_year") or row.get("year"))
        form = _normalize_form_type(row.get("form_type") or row.get("source_type"))
        tier = str(row.get("source_tier") or _default_source_tier_for_form(form)).strip()
        if not ticker or year is None or not form:
            continue
        if requested_tickers and ticker not in requested_tickers:
            continue
        if requested_years and year not in requested_years:
            continue
        if requested_form_set and form not in requested_form_set:
            continue
        if requested_tier_set and tier not in requested_tier_set:
            continue
        route = _default_route_for_form(form)
        if not route:
            continue
        available_groups.setdefault((year, form, tier, route), set()).add(ticker)
        available_keys.add((ticker, year, form, tier))

    if not available_groups:
        return None

    candidate_budget = _bounded_int(args.get("candidate_budget"), default=0, minimum=0, maximum=2000)
    rerank_budget = _bounded_int(args.get("rerank_budget"), default=0, minimum=0, maximum=500)
    requirements: list[dict[str, Any]] = []
    for index, ((year, form, tier, route), tickers) in enumerate(sorted(available_groups.items()), start=1):
        requirement = {
            "requirement_id": f"{args.get('evidence_requirement_id') or 'mcp_sec_search_requirement'}_{_slug(form)}_{year}",
            "task_id": f"mcp_sec_search_{_slug(form)}_{year}",
            "question": query[:240],
            "question_zh": query[:120],
            "priority": "primary",
            "tickers": sorted(tickers),
            "years": [year],
            "filing_types": [form],
            "source_tiers": [tier],
            "metric_families": contract.get("metric_families") or [],
            "period_roles": contract.get("period_roles") or [],
            "evidence_routes": [route],
        }
        if candidate_budget:
            requirement["candidate_budget"] = candidate_budget
        if rerank_budget:
            requirement["rerank_budget"] = rerank_budget
        requirements.append(requirement)

    source_gaps: list[dict[str, Any]] = []
    for ticker in sorted(requested_tickers):
        for year in sorted(requested_years):
            for form in sorted(requested_form_set):
                tiers = _tiers_for_requested_form(form, requested_tiers)
                for tier in tiers:
                    if (ticker, year, form, tier) in available_keys:
                        continue
                    source_gaps.append(
                        {
                            "ticker": ticker,
                            "year": year,
                            "form_type": form,
                            "source_tier": tier,
                            "reason_code": "not_in_manifest_for_mcp_route_scope",
                            "reason": "Requested SEC form/year/tier is not present in the active manifest; compiled retrieval uses available route scopes only.",
                            "source": "mcp_sec_search_filings",
                            "status": "missing",
                        }
                    )
    return requirements, source_gaps


def _read_manifest_rows(path_value: Any) -> list[dict[str, Any]]:
    path_text = str(path_value or "").strip()
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _normalize_form_type(value: Any) -> str:
    text = str(value or "").upper().strip()
    return text.replace("10K", "10-K").replace("10Q", "10-Q").replace("20F", "20-F").replace("40F", "40-F")


def _default_source_tier_for_form(form: str) -> str:
    if form in {"8-K", "6-K"}:
        return "company_authored_unaudited_sec_filing"
    return "primary_sec_filing"


def _default_route_for_form(form: str) -> str:
    if form == "8-K":
        return "8k_commentary"
    if form in {"10-K", "10-Q", "20-F", "40-F"}:
        return "filing_text"
    return ""


def _tiers_for_requested_form(form: str, source_tiers: list[str]) -> list[str]:
    expected = _default_source_tier_for_form(form)
    tiers = [tier for tier in source_tiers if tier == expected]
    return tiers or [expected]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


def _slug(value: Any) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_") or "scope"


def _validate_sec_search_arguments(args: dict[str, Any]) -> str:
    allowed_source_tiers = {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
    allowed_routes = {"", "filing_text", "8k_commentary", "risk_text"}
    source_tiers = {str(tier) for tier in _list_arg(args.get("source_tiers"))}
    invalid_tiers = sorted(source_tiers - allowed_source_tiers)
    if invalid_tiers:
        return f"invalid_sec_search_source_tiers:{','.join(invalid_tiers)}"
    route = str(args.get("retrieval_route") or "").strip()
    if route not in allowed_routes:
        return f"invalid_sec_search_retrieval_route:{route}"
    return ""


def _invoke_run_inspect(args: dict[str, Any]) -> dict[str, Any]:
    result = inspect_run_artifacts(args.get("run_dir") or "")
    return result.model_dump()


def _invoke_run_read(args: dict[str, Any]) -> dict[str, Any]:
    return read_bounded_artifact(
        run_dir=args.get("run_dir") or "",
        artifact_id=str(args.get("artifact_id") or ""),
        rel_path=str(args.get("rel_path") or ""),
        max_bytes=int(args.get("max_bytes") or 200_000),
        parse_json=bool(args.get("parse_json")),
    )


def _list_arg(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _csv_arg(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value if str(item).strip())
    return str(value)


def _bool_arg(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_bool(name: str) -> bool:
    return _bool_arg(os.environ.get(name), default=False)


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(minimum, min(maximum, parsed))


def _default_mcp_output_dir(query: str) -> Path:
    digest = hashlib.sha1(query.encode("utf-8", errors="ignore")).hexdigest()[:10]
    run_id = datetime.now().strftime("mcp_sec_search_%Y%m%d_%H%M%S_") + digest
    return (REPO_ROOT / "eval" / "sec_cases" / "outputs" / "mcp_sec_search" / run_id).resolve()


def _candidate_counts_from_trace(trace: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy = trace.get("context_policy") if isinstance(trace.get("context_policy"), dict) else {}
    summary = trace.get("context_summary") if isinstance(trace.get("context_summary"), dict) else {}
    return {
        "context_row_count": len(rows),
        "summary_context_row_count": summary.get("context_row_count"),
        "candidate_row_count_pre_rerank": policy.get("candidate_row_count_pre_rerank"),
        "candidate_sent_to_bge": policy.get("candidate_sent_to_bge"),
        "route_candidate_stats": policy.get("route_candidate_stats") or [],
        "timing_ms": policy.get("timing_ms") or {},
    }


def _artifact_refs_from_mapping(value: Any, *, row_count: int) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    refs = []
    for artifact_id, path_value in value.items():
        if not path_value:
            continue
        refs.append({"artifact_id": str(artifact_id), "path": str(path_value), "digest": "", "row_count": row_count})
    return refs


def _sec_search_source_gaps(contract: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contract_gaps = [gap for gap in contract.get("source_coverage_gaps") or [] if isinstance(gap, dict)]
    if contract_gaps:
        return contract_gaps
    if rows:
        return []
    return [
        {
            "reason": "no_context_rows_returned",
            "tickers": contract.get("search_scope_tickers") or contract.get("focus_tickers") or [],
            "years": contract.get("years") or [],
            "filing_types": contract.get("filing_types") or [],
            "source_tiers": contract.get("source_tiers") or [],
        }
    ]


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "sec_search_filings": _invoke_sec_search,
    "sec_query_exact_value_ledger": _invoke_ledger,
    "market_get_snapshot": _invoke_market,
    "industry_get_snapshot": _invoke_industry,
    "run_inspect_artifacts": _invoke_run_inspect,
    "run_read_artifact": _invoke_run_read,
}
