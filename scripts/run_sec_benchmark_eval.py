from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from evidence.structured_text import structured_object_search_text  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SEC benchmark v1 context preparation.")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--manifest-path", default="data/processed_private/manifests/sec_tech_10k_manifest.jsonl")
    parser.add_argument("--gold-context-dir", default="eval/sec_cases/gold_context")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Restrict the run to one or more case_id values. Repeat for multiple cases.",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "gold_context", "pipeline_context"],
        default="all",
        help="Context mode to prepare. This runner is context-only unless a model backend is added later.",
    )
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_10k")
    parser.add_argument("--object-bm25-index-dir", default="data/indexes/bm25/sec_tech_10k_objects")
    parser.add_argument("--evidence-top-k", type=int, default=4)
    parser.add_argument("--object-top-k", type=int, default=3)
    parser.add_argument("--max-context-rows", type=int, default=80)
    parser.add_argument(
        "--context-reranker",
        choices=["none", "bge"],
        default=os.environ.get("FIN_SEC_CONTEXT_RERANKER", "bge"),
        help=(
            "Semantic reranker for pipeline_context candidate rows. Default is bge so BM25/ObjectBM25 "
            "remain candidate generators only; use --context-reranker none together with "
            "--allow-bm25-only-pipeline for an explicit BM25-only ablation."
        ),
    )
    parser.add_argument(
        "--context-reranker-model",
        default=os.environ.get("FIN_SEC_CONTEXT_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
    )
    parser.add_argument("--context-reranker-device", default="")
    parser.add_argument("--context-reranker-batch-size", type=int, default=8)
    parser.add_argument("--context-reranker-max-length", type=int, default=2048)
    parser.add_argument("--context-reranker-doc-max-chars", type=int, default=6000)
    parser.add_argument("--context-reranker-candidate-limit", type=int, default=0)
    parser.add_argument("--context-reranker-top-k", type=int, default=120)
    parser.add_argument(
        "--allow-bm25-only-pipeline",
        action="store_true",
        help="Explicitly allow --context-reranker none for pipeline_context ablation runs.",
    )
    parser.add_argument(
        "--synthesis-backend",
        choices=["context_only", "external_command"],
        default="context_only",
        help="Synthesis backend. context_only keeps existing behavior; external_command invokes an external synthesis runner.",
    )
    parser.add_argument(
        "--synthesis-command",
        default="",
        help="Command template for external synthesis. Use {input_json} and {output_json} placeholders.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.object_bm25_retriever import ObjectBM25Retriever

    cases = _read_jsonl(REPO_ROOT / args.cases_path)
    if args.case_id:
        requested_case_ids = {str(case_id) for case_id in args.case_id}
        found_case_ids = {str(case.get("case_id") or "") for case in cases}
        missing_case_ids = sorted(requested_case_ids - found_case_ids)
        if missing_case_ids:
            raise ValueError(f"Unknown --case-id values: {missing_case_ids}")
        cases = [case for case in cases if str(case.get("case_id") or "") in requested_case_ids]
    manifest_rows = _read_jsonl(REPO_ROOT / args.manifest_path)
    manifest_index = {
        (str(row.get("ticker")).upper(), int(row.get("fiscal_year")), str(row.get("form_type")).upper()): row
        for row in manifest_rows
    }
    output_dir = _resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_modes = ["gold_context", "pipeline_context"] if args.mode == "all" else [args.mode]
    _enforce_pipeline_context_policy(args, cases, requested_modes)
    bm25 = BM25Retriever(REPO_ROOT / args.bm25_index_dir)
    object_bm25 = ObjectBM25Retriever(REPO_ROOT / args.object_bm25_index_dir)
    context_reranker = _load_context_reranker(args) if args.context_reranker != "none" else None
    agent_outputs = []
    claim_verification = []
    scores = []
    trace_logs = []
    bad_cases = []

    for case in cases:
        for mode in requested_modes:
            if mode not in set(case.get("evaluation_modes") or []):
                trace = _base_trace(case, mode, status="skipped_mode_not_supported")
                trace_logs.append(trace)
                continue
            trace = _prepare_trace(
                case=case,
                mode=mode,
                manifest_index=manifest_index,
                gold_context_dir=REPO_ROOT / args.gold_context_dir,
                bm25=bm25,
                object_bm25=object_bm25,
                context_reranker=context_reranker,
                args=args,
                evidence_top_k=args.evidence_top_k,
                object_top_k=args.object_top_k,
                max_context_rows=args.max_context_rows,
            )
            trace_logs.append(trace)
            context_rows = trace.get("context_rows") or []
            synthesis_result = _run_synthesis_backend(
                args=args,
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
            if trace["status"] != "context_prepared":
                bad_cases.append(trace)

    _write_jsonl(output_dir / "agent_outputs.jsonl", agent_outputs)
    _write_jsonl(output_dir / "claim_verification.jsonl", claim_verification)
    _write_jsonl(output_dir / "scores.jsonl", scores)
    _write_jsonl(output_dir / "trace_logs.jsonl", trace_logs)
    _write_bad_cases(output_dir / "bad_cases.md", bad_cases)
    summary = _summary(args, output_dir, trace_logs, agent_outputs)
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "trace_count": len(trace_logs),
                "agent_output_count": len(agent_outputs),
                "status_counts": summary["status_counts"],
                "mode_counts": summary["mode_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _prepare_trace(
    case: dict[str, Any],
    mode: str,
    manifest_index: dict[tuple[str, int, str], dict[str, Any]],
    gold_context_dir: Path,
    bm25: Any,
    object_bm25: Any,
    context_reranker: Any,
    args: argparse.Namespace,
    evidence_top_k: int,
    object_top_k: int,
    max_context_rows: int,
) -> dict[str, Any]:
    trace = _base_trace(case, mode, status="context_prepared")
    trace["planner_output"] = _deterministic_plan(case)
    trace["source_resolver_output"] = _source_resolver(case, manifest_index)
    if _source_missing_is_fatal(case, trace["source_resolver_output"]):
        trace["status"] = "source_missing"
        return trace
    if mode == "gold_context":
        context_path = gold_context_dir / f"{case.get('case_id')}.jsonl"
        if not context_path.exists():
            trace["status"] = "gold_context_missing"
            trace["context_summary"] = {"context_row_count": 0, "context_path": str(context_path)}
            return trace
        rows = _read_jsonl(context_path)
        trace["context_summary"] = _context_summary(rows, context_path=context_path)
        trace["context_preview"] = _context_preview(rows, max_rows=max_context_rows)
        trace["context_policy"] = {
            "candidate_generators": ["reviewed_gold_context"],
            "final_selector": "reviewed_gold_context_order",
            "bm25_only_allowed": False,
        }
        trace["context_rows"] = rows
        return trace
    timing_ms: dict[str, int] = {}
    stage_start = time.perf_counter()
    rows = _pipeline_context_rows(case, bm25, object_bm25, evidence_top_k, object_top_k)
    timing_ms["candidate_generation"] = int(round((time.perf_counter() - stage_start) * 1000))
    candidate_row_count = len(rows)
    if context_reranker is not None:
        stage_start = time.perf_counter()
        rows = _rerank_context_rows(case, rows, context_reranker, args)
        timing_ms["context_rerank"] = int(round((time.perf_counter() - stage_start) * 1000))
        final_selector = "bge-reranker-v2-m3"
    else:
        final_selector = "bm25_order_explicit_ablation"
    trace["context_summary"] = _context_summary(rows, context_path=None)
    trace["context_preview"] = _context_preview(rows, max_rows=max_context_rows)
    trace["context_policy"] = {
        "candidate_generators": ["evidence_bm25", "object_bm25", "requirement_bm25"],
        "final_selector": final_selector,
        "context_reranker": args.context_reranker,
        "context_reranker_model": args.context_reranker_model if context_reranker is not None else None,
        "bm25_only_allowed": bool(args.allow_bm25_only_pipeline),
        "candidate_row_count_pre_rerank": candidate_row_count,
        "timing_ms": timing_ms,
    }
    trace["context_rows"] = rows
    return trace


def _pipeline_context_rows(
    case: dict[str, Any],
    bm25: Any,
    object_bm25: Any,
    evidence_top_k: int,
    object_top_k: int,
) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    prompt = str(case.get("prompt") or "")
    companies = [str(ticker).upper() for ticker in case.get("companies") or []]
    years = [int(year) for year in case.get("years") or []]
    source_filters = _case_source_filters(case)
    for ticker in companies:
        for year in years:
            for hit in bm25.search(prompt, top_k=evidence_top_k, filters={"ticker": ticker, "fiscal_year": year, **source_filters}):
                key = ("evidence", hit.get("evidence_id"))
                if key in seen:
                    continue
                seen.add(key)
                record = hit.get("record") or {}
                rows.append(
                    {
                        "source_kind": "evidence_object",
                        "selection_method": "pipeline_bm25",
                        "rank": hit.get("rank"),
                        "score": hit.get("score"),
                        "evidence_id": hit.get("evidence_id"),
                        "ticker": hit.get("ticker"),
                        "fiscal_year": hit.get("fiscal_year"),
                        "section": hit.get("section"),
                        **_context_source_fields(record),
                        "preview": hit.get("text_preview") or hit.get("preview"),
                        "text": record.get("text") or hit.get("text_preview") or hit.get("preview"),
                    }
                )
            for query in _requirement_queries(case):
                for hit in bm25.search(query, top_k=min(5, evidence_top_k), filters={"ticker": ticker, "fiscal_year": year, **source_filters}):
                    key = ("evidence", hit.get("evidence_id"))
                    if key in seen:
                        continue
                    seen.add(key)
                    record = hit.get("record") or {}
                    rows.append(
                        {
                            "source_kind": "evidence_object",
                            "selection_method": "pipeline_bm25_requirement",
                            "selection_query": query,
                            "rank": hit.get("rank"),
                            "score": hit.get("score"),
                            "evidence_id": hit.get("evidence_id"),
                            "ticker": hit.get("ticker"),
                            "fiscal_year": hit.get("fiscal_year"),
                            "section": hit.get("section"),
                            **_context_source_fields(record),
                            "preview": hit.get("text_preview") or hit.get("preview"),
                            "text": record.get("text") or hit.get("text_preview") or hit.get("preview"),
                        }
                    )
    for check in case.get("numeric_checks") or []:
        metric_queries = _numeric_check_object_queries(check)
        for ticker in [str(item).upper() for item in check.get("companies") or companies]:
            for year in [int(item) for item in check.get("years") or years]:
                for metric_query in metric_queries:
                    hits = object_bm25.search(
                        metric_query,
                        top_k=object_top_k,
                        filters={
                            "ticker": [ticker],
                            "fiscal_year": year,
                            "object_type": ["metric", "table"],
                            **source_filters,
                        },
                    )
                    for hit in hits:
                        key = ("object", hit.get("object_id"))
                        if key in seen:
                            continue
                        seen.add(key)
                        record = hit.get("record") or {}
                        object_text = structured_object_search_text(record) if record else hit.get("preview")
                        rows.append(
                            {
                                "source_kind": "structured_object",
                                "selection_method": "pipeline_object_bm25",
                                "selection_query": metric_query,
                                "selection_task_id": check.get("task_id"),
                                "selection_task_priority": check.get("task_priority"),
                                "rank": hit.get("rank"),
                                "score": hit.get("score"),
                                "object_id": hit.get("object_id"),
                                "object_type": hit.get("object_type"),
                                "source_evidence_id": hit.get("source_evidence_id"),
                                "ticker": hit.get("ticker"),
                                "fiscal_year": hit.get("fiscal_year"),
                                "section": hit.get("section"),
                                **_context_source_fields(record),
                                "preview": hit.get("preview"),
                                "text": object_text,
                            }
                        )
    return rows


def _numeric_check_object_queries(check: dict[str, Any]) -> list[str]:
    metric = str(check.get("metric") or "").strip()
    aliases = {
        "advertising_revenue": "advertising revenue Google advertising revenue by source",
        "arr_or_recurring_proxy": "annual recurring revenue ARR recurring revenue",
        "operating_income": "total income from operations operating income segment profitability",
        "capital_expenditure_proxy": "purchases of property and equipment capital expenditures data center infrastructure capex",
        "capex": "purchases of property and equipment capital expenditures data center infrastructure capex cash flow",
        "ppe_purchases": "purchases of property and equipment additions to property and equipment cash flow",
        "cash_flow": "net cash provided by operating activities operating cash flow",
        "free_cash_flow_proxy": "free cash flow net cash provided by operating activities purchases of property and equipment",
        "research_and_development": "research and development R&D AI infrastructure costs",
        "gross_margin": "gross margin gross profit margin",
        "deferred_revenue": "deferred revenue unearned revenue contract liabilities",
        "subscription_revenue": "subscription revenue subscription and support revenue",
        "rpo": "remaining performance obligations RPO contracted backlog revenue visibility",
        "services_revenue": "services revenue service revenue services net sales",
        "product_revenue": "product revenue revenue disaggregation",
        "revenue": "revenue net sales total revenue",
        "total_revenue": "total revenue net sales revenue",
        "data_center_revenue": "data center revenue segment revenue",
        "compute_revenue": "Compute & Networking revenue segment revenue",
        "cloud_revenue": "cloud revenue AWS Azure cloud services",
        "semiconductor_systems": "semiconductor systems revenue",
        "semiconductor_solutions": "semiconductor solutions revenue",
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
        "provision_for_credit_losses": "provision for credit losses credit loss provision provision for loan losses provision for loan lease and other losses",
        "total_assets": "total assets consolidated assets",
    }
    queries = [metric] if metric else []
    for family in check.get("metric_families") or []:
        alias = aliases.get(str(family))
        if alias:
            queries.append(alias)
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(query)
    return deduped


def _case_source_filters(case: dict[str, Any]) -> dict[str, Any]:
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    filing_types = [
        _normalize_form_type(item)
        for item in (case.get("filing_types") or contract.get("filing_types") or [])
        if _normalize_form_type(item)
    ]
    source_tiers = [
        str(item)
        for item in (case.get("source_tiers") or contract.get("source_tiers") or [])
        if str(item)
    ]
    filters: dict[str, Any] = {}
    if filing_types:
        filters["form_type"] = filing_types
    if source_tiers:
        filters["source_tier"] = source_tiers
    return filters


def _context_source_fields(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    source_type = str(record.get("source_type") or metadata.get("source_type") or "").upper().strip()
    form_type = str(record.get("form_type") or metadata.get("form_type") or source_type).upper().strip()
    if not form_type:
        form_type = _form_type_from_source_id(record.get("source_evidence_id") or record.get("evidence_id") or record.get("object_id"))
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


def _form_type_from_source_id(value: Any) -> str:
    text = str(value or "").upper()
    if "_10Q_" in text:
        return "10-Q"
    if "_10K_" in text:
        return "10-K"
    return ""


def _normalize_form_type(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")


def _load_context_reranker(args: argparse.Namespace) -> Any:
    from sentence_transformers import CrossEncoder

    init_params = inspect.signature(CrossEncoder.__init__).parameters
    kwargs: dict[str, Any] = {"max_length": args.context_reranker_max_length}
    if args.context_reranker_device:
        kwargs["device"] = args.context_reranker_device
    if "trust_remote_code" in init_params:
        kwargs["trust_remote_code"] = True
    return CrossEncoder(args.context_reranker_model, **kwargs)


def _enforce_pipeline_context_policy(
    args: argparse.Namespace,
    cases: list[dict[str, Any]],
    requested_modes: list[str],
) -> None:
    if "pipeline_context" not in set(requested_modes):
        return
    has_pipeline_case = any("pipeline_context" in set(case.get("evaluation_modes") or []) for case in cases)
    if not has_pipeline_case:
        return
    if args.context_reranker != "none":
        return
    if args.allow_bm25_only_pipeline:
        return
    raise ValueError(
        "pipeline_context now requires BGE reranking by default. "
        "Use --context-reranker bge, or pass --context-reranker none "
        "--allow-bm25-only-pipeline for an explicit BM25-only ablation."
    )


def _rerank_context_rows(
    case: dict[str, Any],
    rows: list[dict[str, Any]],
    reranker: Any,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if not rows:
        return rows
    candidate_limit = args.context_reranker_candidate_limit or len(rows)
    candidates = rows[:candidate_limit]
    query = _context_rerank_query(case)
    pairs = [
        (query, _context_row_rerank_text(row)[: args.context_reranker_doc_max_chars])
        for row in candidates
    ]
    scores = reranker.predict(
        pairs,
        batch_size=args.context_reranker_batch_size,
        show_progress_bar=False,
    )
    scored = []
    for index, (row, score) in enumerate(zip(candidates, scores), start=1):
        copy = dict(row)
        copy["reranker"] = {
            "type": "bge_cross_encoder",
            "model": args.context_reranker_model,
            "candidate_rank": index,
            "score": float(score),
        }
        copy["rerank_score"] = float(score)
        scored.append(copy)
    scored.sort(key=lambda item: float(item.get("rerank_score") or 0.0), reverse=True)
    for rank, row in enumerate(scored, start=1):
        row["rerank_rank"] = rank
    tail = rows[candidate_limit:]
    return _apply_context_reservations(case, scored, args.context_reranker_top_k) + tail


def _apply_context_reservations(case: dict[str, Any], scored: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    if not scored or top_k <= 0:
        return scored[:top_k]
    reserved: list[dict[str, Any]] = []
    seen_reserved = set()
    _extend_source_coverage_reservations(case, scored, reserved, seen_reserved)
    peer_tickers = _case_peer_tickers(case)
    if peer_tickers:
        _extend_peer_structured_reservations(case, scored, reserved, seen_reserved, peer_tickers)

    if not reserved:
        return scored[:top_k]

    reserve_cap = min(len(reserved), max(1, top_k // 4))
    reserved = reserved[:reserve_cap]
    reserved_keys = {_context_row_key(row) for row in reserved}
    primary_budget = max(0, top_k - len(reserved))
    primary = [row for row in scored if _context_row_key(row) not in reserved_keys][:primary_budget]
    merged = primary + reserved
    for rank, row in enumerate(merged, start=1):
        row["context_rank_after_reservation"] = rank
    return merged


def _extend_peer_structured_reservations(
    case: dict[str, Any],
    scored: list[dict[str, Any]],
    reserved: list[dict[str, Any]],
    seen_reserved: set[tuple[str, str]],
    peer_tickers: list[str],
) -> None:
    per_peer_limit = 2
    for ticker in peer_tickers:
        count = 0
        for row in scored:
            if str(row.get("ticker") or "").upper() != ticker:
                continue
            if str(row.get("source_kind") or "") != "structured_object":
                continue
            key = _context_row_key(row)
            if key in seen_reserved:
                continue
            row["reservation_policy"] = "peer_structured_object"
            reserved.append(row)
            seen_reserved.add(key)
            count += 1
            if count >= per_peer_limit:
                break


def _extend_source_coverage_reservations(
    case: dict[str, Any],
    scored: list[dict[str, Any]],
    reserved: list[dict[str, Any]],
    seen_reserved: set[tuple[str, str]],
) -> None:
    if not _case_requests_8k_earnings(case):
        return
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    focus_tickers = [
        str(ticker).upper()
        for ticker in (contract.get("focus_tickers") or case.get("companies") or [])
        if str(ticker).strip()
    ]
    if not focus_tickers:
        focus_tickers = sorted({str(row.get("ticker") or "").upper() for row in scored if row.get("ticker")})
    per_ticker_limit = 2
    for ticker in focus_tickers:
        count = 0
        for row in scored:
            if str(row.get("ticker") or "").upper() != ticker:
                continue
            if _normalize_form_type(row.get("form_type")) != "8-K":
                continue
            if str(row.get("source_tier") or "") != "company_authored_unaudited_sec_filing":
                continue
            key = _context_row_key(row)
            if key in seen_reserved:
                continue
            row["reservation_policy"] = "requested_8k_earnings_source_coverage"
            reserved.append(row)
            seen_reserved.add(key)
            count += 1
            if count >= per_ticker_limit:
                break


def _case_peer_tickers(case: dict[str, Any]) -> list[str]:
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    focus = {str(item).upper() for item in contract.get("focus_tickers") or [] if str(item)}
    out = []
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        task_text = " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question"))
        has_peer_intent = any(term in task_text.lower() for term in ("peer", "compet", "竞争", "同行", "对手", "比较", "对比"))
        for ticker in task.get("peer_tickers") or []:
            ticker_text = str(ticker or "").upper()
            if ticker_text and ticker_text not in focus and ticker_text not in out:
                out.append(ticker_text)
        if has_peer_intent:
            for ticker in task.get("required_tickers") or []:
                ticker_text = str(ticker or "").upper()
                if ticker_text and ticker_text not in focus and ticker_text not in out:
                    out.append(ticker_text)
    return out[:12]


def _context_row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source_kind") or ""),
        str(row.get("object_id") or row.get("evidence_id") or row.get("source_evidence_id") or id(row)),
    )


def _context_rerank_query(case: dict[str, Any]) -> str:
    parts = [
        str(case.get("prompt") or ""),
        "Gold points:",
        " ".join(str(item) for item in case.get("gold_points") or []),
        "Caveats and traps:",
        " ".join(str(item) for item in case.get("hallucination_traps") or []),
        "Numeric checks:",
        " ".join(str(check.get("metric") or "") for check in case.get("numeric_checks") or []),
    ]
    return "\n".join(part for part in parts if part)


def _context_row_rerank_text(row: dict[str, Any]) -> str:
    metadata = [
        row.get("ticker"),
        row.get("fiscal_year"),
        row.get("section"),
        row.get("source_kind"),
        row.get("selection_query"),
        row.get("object_type"),
        row.get("evidence_id"),
        row.get("source_evidence_id"),
        row.get("object_id"),
    ]
    body = row.get("text") or row.get("object_text") or row.get("preview") or ""
    return "\n".join(str(part) for part in [*metadata, body] if part is not None and str(part))


def _requirement_queries(case: dict[str, Any]) -> list[str]:
    queries: list[str] = []
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    if _case_requests_8k_earnings(case):
        queries.extend(
            [
                "8-K Exhibit 99.1 earnings release cloud management commentary guidance outlook demand AI capital expenditures",
                "earnings release company-authored unaudited cloud revenue AWS Azure management outlook",
            ]
        )
    for item in contract.get("qualitative_queries") or []:
        text = str(item or "").strip()
        if len(text) >= 8:
            queries.append(text)
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        task_parts = [
            str(task.get("question_zh") or task.get("question") or "").strip(),
            " ".join(str(family).replace("_", " ") for family in task.get("required_metric_families") or []),
        ]
        text = " ".join(part for part in task_parts if part).strip()
        if len(text) >= 8:
            queries.append(text)
    for item in contract.get("facets") or []:
        text = str(item or "").replace("_", " ").strip()
        if len(text) >= 8:
            queries.append(text)
    for field in ("gold_points", "hallucination_traps"):
        for item in case.get(field) or []:
            text = str(item or "").strip()
            if _is_domain_requirement_query(text):
                queries.append(text)
    task_type = str(case.get("task_type") or "")
    if "semiconductor" in task_type:
        queries.extend(
            [
                "customer concentration 10% total revenue",
                "export controls China restrictions",
                "supply chain foundry capacity lead times",
                "segment definitions not comparable",
            ]
        )
    if "capex" in task_type or "cash_flow" in task_type:
        queries.extend(
            [
                "net cash provided by operating activities purchases of property and equipment",
                "capital expenditures additions to property and equipment cash flow",
                "total investing cash flow not capital expenditures",
            ]
        )
    if "ads_ai_infra" in task_type:
        queries.extend(
            [
                "advertising revenue Google advertising revenue by source",
                "total income from operations segment profitability",
                "purchases of property and equipment capital expenditures cash flow",
                "AI technical infrastructure investment cost pressure",
                "AI initiatives advertising monetization caveat",
            ]
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(query)
        if len(deduped) >= 16:
            break
    return deduped


def _case_requests_8k_earnings(case: dict[str, Any]) -> bool:
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    source_policy = str(case.get("source_policy") or contract.get("source_policy") or "")
    filing_types = {
        _normalize_form_type(item)
        for item in (case.get("filing_types") or contract.get("filing_types") or [])
        if _normalize_form_type(item)
    }
    source_tiers = {
        str(item)
        for item in (case.get("source_tiers") or contract.get("source_tiers") or [])
        if str(item)
    }
    return (
        source_policy == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
        or "8-K" in filing_types
        or "company_authored_unaudited_sec_filing" in source_tiers
    )


def _is_domain_requirement_query(text: str) -> bool:
    lowered = str(text or "").lower()
    if len(lowered) < 12:
        return False
    generic_policy_terms = (
        "do not use non-sec",
        "answer only from retrieved",
        "precise numeric values",
        "exact-value ledger",
        "source policy",
        "citation validator",
        "do not infer exact values",
        "do not attribute another company's",
    )
    if any(term in lowered for term in generic_policy_terms):
        return False
    domain_terms = (
        "revenue",
        "margin",
        "operating income",
        "cash flow",
        "capital expenditure",
        "capex",
        "rpo",
        "remaining performance",
        "risk",
        "customer concentration",
        "export control",
        "cloud",
        "data center",
        "semiconductor",
        "advertising",
        "subscription",
    )
    return any(term in lowered for term in domain_terms)


def _base_trace(case: dict[str, Any], mode: str, status: str) -> dict[str, Any]:
    return {
        "schema_version": "sec_benchmark_trace_v0.1",
        "case_id": case.get("case_id"),
        "mode": mode,
        "status": status,
        "task_type": case.get("task_type"),
        "level": case.get("level"),
        "case_group": case.get("case_group"),
        "source_policy": case.get("source_policy"),
    }


def _deterministic_plan(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": case.get("task_type"),
        "companies": case.get("companies") or [],
        "years": case.get("years") or [],
        "filing_types": case.get("filing_types") or [],
        "sections": case.get("expected_sections") or [],
        "needs_numeric_extraction": bool(case.get("numeric_checks")),
        "source_policy": case.get("source_policy"),
        "hard_gates": case.get("hard_gates") or [],
    }


def _source_resolver(case: dict[str, Any], manifest_index: dict[tuple[str, int, str], dict[str, Any]]) -> dict[str, Any]:
    available = []
    missing = []
    for ticker in [str(item).upper() for item in case.get("companies") or []]:
        for year in [int(item) for item in case.get("years") or []]:
            for filing_type in [str(item).upper() for item in case.get("filing_types") or []]:
                row = manifest_index.get((ticker, year, filing_type))
                if row:
                    available.append(
                        {
                            "ticker": ticker,
                            "year": year,
                            "filing_type": filing_type,
                            "filing_date": row.get("filing_date"),
                            "report_date": row.get("report_date"),
                            "accession_number": row.get("accession_number"),
                            "filing_url": row.get("filing_url"),
                        }
                    )
                else:
                    missing.append({"ticker": ticker, "year": year, "filing_type": filing_type})
    if not available:
        status = "missing_all"
    elif missing:
        status = "partial"
    else:
        status = "complete"
    return {
        "status": status,
        "available_filings": available,
        "missing_filings": missing,
        "available_count": len(available),
        "missing_count": len(missing),
    }


def _source_missing_is_fatal(case: dict[str, Any], resolver_output: dict[str, Any]) -> bool:
    missing = resolver_output.get("missing_filings") or []
    if not missing:
        return False
    if not resolver_output.get("available_filings"):
        return True
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    source_policy = str(case.get("source_policy") or contract.get("source_policy") or "")
    filing_types = {
        _normalize_form_type(item)
        for item in (case.get("filing_types") or contract.get("filing_types") or [])
        if _normalize_form_type(item)
    }
    if source_policy == "SEC_PRIMARY_MIXED_RECENT" or "10-Q" in filing_types:
        return False
    return False if (case.get("source_coverage_gaps") or contract.get("source_coverage_gaps")) else True


def _context_summary(rows: list[dict[str, Any]], context_path: Path | None) -> dict[str, Any]:
    kind_counts = Counter(str(row.get("source_kind") or "unknown") for row in rows)
    method_counts = Counter(str(row.get("selection_method") or "unknown") for row in rows)
    ticker_years = sorted(
        {
            f"{row.get('ticker')}:{row.get('fiscal_year')}"
            for row in rows
            if row.get("ticker") and row.get("fiscal_year")
        }
    )
    return {
        "context_path": str(context_path) if context_path else None,
        "context_row_count": len(rows),
        "source_kind_counts": dict(sorted(kind_counts.items())),
        "selection_method_counts": dict(sorted(method_counts.items())),
        "ticker_years": ticker_years,
    }


def _context_preview(rows: list[dict[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    preview = []
    for row in rows[:max_rows]:
        preview.append(
            {
                "source_kind": row.get("source_kind"),
                "selection_method": row.get("selection_method"),
                "evidence_id": row.get("evidence_id"),
                "object_id": row.get("object_id"),
                "object_type": row.get("object_type"),
                "ticker": row.get("ticker"),
                "fiscal_year": row.get("fiscal_year"),
                "section": row.get("section"),
                "score": row.get("score"),
                "review_status": row.get("review_status"),
            }
        )
    return preview


def _summary(args: argparse.Namespace, output_dir: Path, trace_logs: list[dict[str, Any]], outputs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "sec_benchmark_run_summary_v0.1",
        "run_type": "context_plus_optional_synthesis",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cases_path": str((REPO_ROOT / args.cases_path).resolve()),
        "case_id_filter": list(args.case_id or []),
        "output_dir": str(output_dir.resolve()),
        "mode": args.mode,
        "status_counts": dict(sorted(Counter(str(trace.get("status")) for trace in trace_logs).items())),
        "mode_counts": dict(sorted(Counter(str(trace.get("mode")) for trace in trace_logs).items())),
        "trace_count": len(trace_logs),
        "agent_output_count": len(outputs),
        "synthesis_backend": args.synthesis_backend,
        "pipeline_context_policy": {
            "default_final_selector": "bge-reranker-v2-m3",
            "effective_context_reranker": args.context_reranker,
            "context_reranker_model": args.context_reranker_model if args.context_reranker != "none" else None,
            "bm25_only_requires_explicit_allow": True,
            "bm25_only_allowed_for_this_run": bool(args.allow_bm25_only_pipeline),
            "candidate_generators": ["evidence_bm25", "object_bm25", "requirement_bm25"],
        },
        "notes": [
            "When synthesis_backend=context_only, this runner only prepares context and does not invoke synthesis.",
            "When synthesis_backend=external_command, this runner passes per-case context to an external synthesis command and records returned artifacts.",
            "For pipeline_context, BM25/ObjectBM25 are candidate generators; BGE-M3 is the default final selector.",
            "Gold-context rows generated by build_sec_gold_context_seed.py require human review before final benchmark use.",
        ],
    }


def _run_synthesis_backend(
    *,
    args: argparse.Namespace,
    case: dict[str, Any],
    mode: str,
    trace: dict[str, Any],
    context_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if trace.get("status") != "context_prepared":
        return {
            "agent_status": "skipped",
            "answer_status": "not_run_context_not_ready",
            "answer": None,
            "limitations": [f"context not prepared: {trace.get('status')}"],
            "claim_status": "not_run",
            "claims": [],
            "unsupported_claim_count": None,
            "score_status": "not_scored",
            "score_total": None,
            "scores": None,
            "failure_types": [str(trace.get("status") or "context_not_ready")],
            "score_notes": ["Synthesis skipped because context preparation failed."],
        }

    if args.synthesis_backend == "context_only":
        return {
            "agent_status": "context_prepared",
            "answer_status": "not_run_context_only",
            "answer": None,
            "limitations": [
                "This run prepared benchmark context only; no synthesis model was invoked.",
                "Seed gold context is programmatically selected and still requires human review.",
            ],
            "claim_status": "not_run_context_only",
            "claims": [],
            "unsupported_claim_count": None,
            "score_status": "not_scored_context_only",
            "score_total": None,
            "scores": None,
            "failure_types": [],
            "score_notes": ["No synthesis output was generated in this context-only run."],
        }

    if args.synthesis_backend == "external_command":
        return _run_external_synthesis_command(args, case, mode, context_rows)

    raise ValueError(f"Unsupported synthesis backend: {args.synthesis_backend}")


def _run_external_synthesis_command(
    args: argparse.Namespace,
    case: dict[str, Any],
    mode: str,
    context_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    template = str(args.synthesis_command or "").strip()
    if not template:
        return {
            "agent_status": "context_prepared",
            "answer_status": "external_command_missing",
            "answer": None,
            "limitations": ["synthesis_backend=external_command but --synthesis-command was empty."],
            "claim_status": "not_run_external_command_missing",
            "claims": [],
            "unsupported_claim_count": None,
            "score_status": "not_scored_external_command_missing",
            "score_total": None,
            "scores": None,
            "failure_types": ["external_command_missing"],
            "score_notes": ["Set --synthesis-command with {input_json} and {output_json} placeholders."],
        }

    payload = {
        "schema_version": "sec_benchmark_synthesis_input_v0.1",
        "case": case,
        "mode": mode,
        "context_rows": context_rows,
    }
    with tempfile.TemporaryDirectory(prefix="sec_eval_backend_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "output.json"
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        command = template.format(input_json=str(input_path), output_json=str(output_path))
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            return {
                "agent_status": "context_prepared",
                "answer_status": "external_command_failed",
                "answer": None,
                "limitations": [
                    "External synthesis command failed.",
                    f"return_code={completed.returncode}",
                    _trim_text(completed.stderr, 400),
                ],
                "claim_status": "not_run_external_command_failed",
                "claims": [],
                "unsupported_claim_count": None,
                "score_status": "not_scored_external_command_failed",
                "score_total": None,
                "scores": None,
                "failure_types": ["external_command_failed"],
                "score_notes": [_trim_text(completed.stdout, 240)],
            }
        if not output_path.exists():
            return {
                "agent_status": "context_prepared",
                "answer_status": "external_command_no_output",
                "answer": None,
                "limitations": ["External synthesis command completed but output file was not produced."],
                "claim_status": "not_run_external_command_no_output",
                "claims": [],
                "unsupported_claim_count": None,
                "score_status": "not_scored_external_command_no_output",
                "score_total": None,
                "scores": None,
                "failure_types": ["external_command_no_output"],
                "score_notes": [],
            }
        result = json.loads(output_path.read_text(encoding="utf-8"))
        return {
            "agent_status": str(result.get("status") or "answered"),
            "answer_status": str(result.get("answer_status") or "answered"),
            "answer": result.get("answer"),
            "limitations": list(result.get("limitations") or []),
            "claim_status": str(result.get("claim_status") or "not_provided"),
            "claims": list(result.get("claims") or []),
            "unsupported_claim_count": result.get("unsupported_claim_count"),
            "score_status": str(result.get("score_status") or "not_provided"),
            "score_total": result.get("score_total"),
            "scores": result.get("scores"),
            "failure_types": list(result.get("failure_types") or []),
            "score_notes": list(result.get("score_notes") or []),
        }


def _trim_text(text: str | None, max_chars: int) -> str:
    content = str(text or "").strip()
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "...[truncated]"


def _resolve_output_dir(raw: str | None) -> Path:
    if raw:
        return REPO_ROOT / raw
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S_context_only")
    return REPO_ROOT / "eval" / "sec_cases" / "outputs" / run_id


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_bad_cases(path: Path, traces: list[dict[str, Any]]) -> None:
    lines = ["# Bad Cases Report", "", "Context-only run. No synthesis bad cases were scored.", ""]
    if not traces:
        lines.append("No context-preparation failures.")
    for trace in traces:
        lines.extend(
            [
                f"## Case: {trace.get('case_id')} [{trace.get('mode')}]",
                "",
                f"- Status: {trace.get('status')}",
                f"- Task type: {trace.get('task_type')}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
