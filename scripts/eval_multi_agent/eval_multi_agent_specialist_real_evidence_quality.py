from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.relationship_graph import query_relationship_graph  # noqa: E402
from sec_agent.mcp_tool_registry import invoke_mcp_tool  # noqa: E402
from sec_agent.specialist_llm import SpecialistLLMConfig, route_specialist_memolet_llm  # noqa: E402


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "multi_agent_specialist_real_evidence_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_specialist_real_evidence_quality"
DEFAULT_SECTOR_DEPTH_MANIFEST = REPO_ROOT / "data" / "processed_private" / "manifests" / "sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl"
DEFAULT_SECTOR_DEPTH_BM25 = REPO_ROOT / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027"
DEFAULT_SECTOR_DEPTH_OBJECT_BM25 = REPO_ROOT / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects"
DEFAULT_BGE_MODEL = Path("D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Specialist Analyst quality eval on real bounded evidence rows.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected case_id values. Repeatable.")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--materialize-only", action="store_true", help="Only materialize real evidence rows; do not call the LLM.")
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("SPECIALIST_TEMPERATURE", "0")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SPECIALIST_MAX_TOKENS", "1600")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("SPECIALIST_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("SPECIALIST_MAX_REPAIR_ATTEMPTS", "2")))
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless all quality gates pass.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = _read_jsonl(Path(args.fixture))
    if args.case_id:
        selected = {str(case_id) for case_id in args.case_id}
        rows = [row for row in rows if str(row.get("case_id") or "") in selected]
    if args.max_cases > 0:
        rows = rows[: args.max_cases]

    run_id = args.run_id or _default_run_id(args)
    output_dir = Path(args.output_dir) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    config = SpecialistLLMConfig(
        llm_backend=args.llm_backend,
        base_url=args.base_url,
        chat_completions_path=args.chat_completions_path,
        model=args.model,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        max_repair_attempts=args.max_repair_attempts,
    )

    materialized_rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for index, spec in enumerate(rows, start=1):
        case_started = time.time()
        materialized = materialize_real_evidence_case(spec)
        materialized_rows.append(materialized)
        if args.materialize_only:
            cases.append(_materialize_only_case(materialized, ordinal=index, total=len(rows), elapsed_sec=round(time.time() - case_started, 4)))
            continue

        request = {
            "agent_id": materialized.get("agent_id"),
            "user_query": materialized.get("user_query") or "",
            "bounded_evidence_rows": materialized.get("bounded_evidence_rows") or [],
            "relationship_summary": materialized.get("relationship_summary") or {},
            "coverage_summary": materialized.get("coverage_summary") or {},
            "source_boundaries": materialized.get("source_boundaries") or {},
            "known_evidence_refs": materialized.get("known_evidence_refs") or [],
        }
        route_result = route_specialist_memolet_llm(
            str(materialized.get("agent_id") or ""),
            request,
            config=config,
            known_evidence_refs=set(materialized.get("known_evidence_refs") or []),
        )
        cases.append(
            evaluate_real_evidence_case(
                materialized,
                route_result=route_result,
                elapsed_sec=round(time.time() - case_started, 4),
                ordinal=index,
                total=len(rows),
                max_repair_attempts=args.max_repair_attempts,
            )
        )

    materialized_path = output_dir / "materialized_specialist_real_evidence_cases.jsonl"
    _write_jsonl(materialized_path, materialized_rows)
    summary = _summarize(
        args=args,
        run_id=run_id,
        cases=cases,
        materialized_rows=materialized_rows,
        materialized_path=materialized_path,
        elapsed_sec=round(time.time() - started, 4),
    )
    output_path = output_dir / "specialist_real_evidence_quality_eval.json"
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, output_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def materialize_real_evidence_case(spec: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_refs: list[dict[str, Any]] = []
    for source in spec.get("evidence_sources") or []:
        if not isinstance(source, Mapping):
            continue
        source_type = str(source.get("type") or "").strip()
        source_rows: list[dict[str, Any]]
        if source_type == "runtime_ledger_json":
            source_rows = _rows_from_runtime_ledger_json(source)
        elif source_type == "market_evidence_jsonl":
            source_rows = _rows_from_market_evidence_jsonl(source)
        elif source_type == "industry_evidence_jsonl":
            source_rows = _rows_from_industry_evidence_jsonl(source)
        elif source_type == "coverage_matrix_json":
            source_rows = _rows_from_coverage_matrix_json(source)
        elif source_type == "relationship_graph_lookup":
            source_rows = _rows_from_relationship_graph_lookup(source)
        elif source_type == "sec_search_filings":
            source_rows = _rows_from_sec_search_filings(source)
        else:
            source_rows = []
        rows.extend(source_rows)
        source_refs.append(
            {
                "type": source_type,
                "path": str(source.get("path") or ""),
                "row_count": len(source_rows),
                "filters": dict(source.get("filters") or {}),
            }
        )
    rows = _dedupe_rows(rows)
    return {
        "case_id": spec.get("case_id"),
        "agent_id": spec.get("agent_id"),
        "user_query": spec.get("user_query") or "",
        "bounded_evidence_rows": rows,
        "relationship_summary": _relationship_summary_from_rows(rows),
        "coverage_summary": spec.get("coverage_summary") or _coverage_summary(rows),
        "source_boundaries": spec.get("source_boundaries") or _source_boundaries(rows),
        "known_evidence_refs": _known_refs(rows),
        "expected_min_observations": int(spec.get("expected_min_observations") or 0),
        "expect_unsupported_or_conflict": bool(spec.get("expect_unsupported_or_conflict")),
        "quality_expectations": dict(spec.get("quality_expectations") or {}),
        "real_evidence_source_refs": source_refs,
    }


def evaluate_real_evidence_case(
    row: Mapping[str, Any],
    *,
    route_result: Mapping[str, Any],
    elapsed_sec: float,
    ordinal: int,
    total: int,
    max_repair_attempts: int,
) -> dict[str, Any]:
    memolet = route_result.get("memolet") if isinstance(route_result.get("memolet"), Mapping) else {}
    validation = route_result.get("validation") if isinstance(route_result.get("validation"), Mapping) else {}
    observations = memolet.get("observations") if isinstance(memolet.get("observations"), list) else []
    unsupported = memolet.get("unsupported_claims") if isinstance(memolet.get("unsupported_claims"), list) else []
    conflicts = memolet.get("conflicts") if isinstance(memolet.get("conflicts"), list) else []
    bounded_rows = [dict(item) for item in row.get("bounded_evidence_rows") or [] if isinstance(item, Mapping)]
    quality = dict(row.get("quality_expectations") or {})
    known_refs = set(str(item) for item in row.get("known_evidence_refs") or [])
    observed_refs = {
        str(ref)
        for observation in observations
        if isinstance(observation, Mapping) and not observation.get("unsupported")
        for ref in observation.get("evidence_refs") or []
    }
    unknown_refs = sorted(observed_refs - known_refs)
    observed_source_families = {
        str(source)
        for observation in observations
        if isinstance(observation, Mapping)
        for source in observation.get("source_families") or []
        if str(source or "").strip()
    }
    input_source_families = {str(item.get("source_family") or "") for item in bounded_rows if item.get("source_family")}
    checks = {
        "llm_route_pass": route_result.get("status") == "pass",
        "validation_pass": validation.get("status") == "pass",
        "agent_id_match": memolet.get("agent_id") == row.get("agent_id"),
        "min_observations": len(observations) >= int(row.get("expected_min_observations") or 0),
        "evidence_refs_known": not unknown_refs,
        "forbidden_direct_tool_call_absent": _tool_call_count(route_result) == 0,
        "expected_unsupported_or_conflict": _expected_unsupported_check(row, unsupported, conflicts),
        "repair_budget_lte": int((route_result.get("routing_trace") or {}).get("repair_attempts") or 0) <= int(max_repair_attempts),
        "real_evidence_rows_present": bool(bounded_rows),
        "all_rows_marked_real": all(bool(((item.get("metadata") or {}).get("real_evidence_row"))) for item in bounded_rows),
        "input_required_source_families_present": set(_string_list(quality.get("required_input_source_families"))) <= input_source_families,
        "observation_source_families_allowed": _allowed_sources_check(quality, observed_source_families),
        "expected_observation_source_family_used": _expected_source_used_check(quality, observed_source_families),
        "required_observation_source_families_present": _required_sources_present_check(quality, observed_source_families),
        "required_source_family_evidence_refs_cited": _required_source_family_refs_cited_check(
            quality,
            observed_refs,
            bounded_rows,
        ),
        "required_evidence_ref_prefixes_present": _required_ref_prefixes_present(quality, observed_refs),
        "claim_terms_present": _claim_terms_present(quality, memolet),
    }
    return {
        "case_id": row.get("case_id"),
        "agent_id": row.get("agent_id"),
        "ordinal": ordinal,
        "total": total,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "input_row_count": len(bounded_rows),
        "input_source_families": sorted(input_source_families),
        "observed_source_families": sorted(observed_source_families),
        "unknown_evidence_refs": unknown_refs,
        "supported_observation_count": len(observations),
        "unsupported_claim_count": len(unsupported),
        "conflict_count": len(conflicts),
        "tool_call_count": _tool_call_count(route_result),
        "route_status": route_result.get("status"),
        "failure_reason": route_result.get("failure_reason") or "",
        "memolet": memolet,
        "validation": validation,
        "routing_trace": route_result.get("routing_trace") or {},
        "model_diagnostics": route_result.get("model_diagnostics") or {},
    }


def _materialize_only_case(row: Mapping[str, Any], *, ordinal: int, total: int, elapsed_sec: float) -> dict[str, Any]:
    bounded_rows = [dict(item) for item in row.get("bounded_evidence_rows") or [] if isinstance(item, Mapping)]
    input_source_families = sorted({str(item.get("source_family") or "") for item in bounded_rows if item.get("source_family")})
    checks = {
        "real_evidence_rows_present": bool(bounded_rows),
        "all_rows_marked_real": all(bool(((item.get("metadata") or {}).get("real_evidence_row"))) for item in bounded_rows),
    }
    return {
        "case_id": row.get("case_id"),
        "agent_id": row.get("agent_id"),
        "ordinal": ordinal,
        "total": total,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "input_row_count": len(bounded_rows),
        "input_source_families": input_source_families,
        "materialize_only": True,
    }


def _rows_from_runtime_ledger_json(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = _repo_path(source.get("path"))
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, Mapping) else payload
    filtered = _filter_rows([dict(item) for item in rows or [] if isinstance(item, Mapping)], source.get("filters") or {})
    return [_bounded_ledger_row(row, path=path) for row in filtered[: _limit(source)]]


def _rows_from_market_evidence_jsonl(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = _repo_path(source.get("path"))
    if not path.exists():
        return []
    filters = source.get("filters") if isinstance(source.get("filters"), Mapping) else {}
    rows = _filter_rows(_read_jsonl(path), filters)
    fields = _string_list(filters.get("fields")) or ["return_3m", "relative_return_vs_benchmark_3m", "pe_ttm", "ev_sales_ttm"]
    return [_bounded_market_row(row, path=path, fields=fields) for row in rows[: _limit(source)]]


def _rows_from_industry_evidence_jsonl(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = _repo_path(source.get("path"))
    if not path.exists():
        return []
    rows = _filter_rows(_read_jsonl(path), source.get("filters") or {})
    return [_bounded_industry_row(row, path=path) for row in rows[: _limit(source)]]


def _rows_from_coverage_matrix_json(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = _repo_path(source.get("path"))
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    tasks = payload.get("tasks") if isinstance(payload, Mapping) else []
    wanted_metrics = set(_string_list((source.get("filters") or {}).get("metric_families")))
    for task in tasks or []:
        if not isinstance(task, Mapping):
            continue
        for metric in task.get("missing_metric_families") or []:
            metric_text = str(metric or "").strip()
            if wanted_metrics and metric_text not in wanted_metrics:
                continue
            evidence_ref = f"coverage_gap:{task.get('task_id') or 'task'}:{metric_text}"
            rows.append(
                _with_real_metadata(
                    {
                        "evidence_ref": evidence_ref,
                        "source_family": "run_artifact",
                        "ticker": ",".join(str(item) for item in task.get("required_tickers") or []),
                        "metric": "source_gap",
                        "value": "",
                        "summary": f"Coverage matrix task {task.get('task_id') or ''} is missing required metric family: {metric_text}.",
                    },
                    path=path,
                    source_type="coverage_matrix_json",
                )
            )
    return rows[: _limit(source)]


def _rows_from_relationship_graph_lookup(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    args = dict(source.get("args") or {})
    lookup = query_relationship_graph(
        focus_tickers=_string_list(args.get("focus_tickers")),
        search_scope_tickers=_string_list(args.get("search_scope_tickers")),
        user_query=str(args.get("user_query") or ""),
        relationship_graph_path=args.get("relationship_graph_path") or "",
        sector_depth_pack_path=args.get("sector_depth_pack_path") or "",
        max_relationships=int(args.get("max_relationships") or _limit(source)),
        max_expanded_tickers=int(args.get("max_expanded_tickers") or 12),
        include_sector_depth=bool(args.get("include_sector_depth", True)),
    )
    rows = [dict(item) for item in lookup.get("relationship_rows") or [] if isinstance(item, Mapping)]
    path_text = str(args.get("relationship_graph_path") or args.get("sector_depth_pack_path") or "configs/sector_depth_packs_v0_2.yaml")
    path = _repo_path(path_text)
    return [
        _with_real_metadata(
            {
                "evidence_ref": str(row.get("evidence_ref") or f"relationship_row_{index}"),
                "source_family": "relationship_graph",
                "ticker": str(row.get("ticker") or ""),
                "period_role": "",
                "metric": str(row.get("relationship_type") or "relationship"),
                "value": "",
                "summary": str(row.get("summary") or ""),
                "claim_scope": str(row.get("claim_scope") or "scope_or_hypothesis_only"),
                "related_ticker": str(row.get("related_ticker") or ""),
            },
            path=path,
            source_type="relationship_graph_lookup",
        )
        for index, row in enumerate(rows[: _limit(source)], start=1)
    ]


def _rows_from_sec_search_filings(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    args = {**_default_sec_search_args(), **dict(source.get("args") or {})}
    args["build_runtime_ledger"] = bool(args.get("build_runtime_ledger", True))
    result = invoke_mcp_tool("sec_search_filings", args)
    rows = [dict(item) for item in result.get("context_rows") or [] if isinstance(item, Mapping)]
    ledger_rows = [dict(item) for item in result.get("runtime_ledger_rows") or [] if isinstance(item, Mapping)]
    bounded_rows = [_bounded_context_row(row, source=source, result=result, args=args) for row in rows[: _limit(source)]]
    remaining = max(0, _limit(source) - len(bounded_rows))
    if remaining:
        bounded_rows.extend(_bounded_ledger_row(row, path=_repo_path(args.get("manifest_path"))) for row in ledger_rows[:remaining])
    return bounded_rows


def _default_sec_search_args() -> dict[str, Any]:
    return {
        "manifest_path": str(DEFAULT_SECTOR_DEPTH_MANIFEST),
        "bm25_index_dir": str(DEFAULT_SECTOR_DEPTH_BM25),
        "object_bm25_index_dir": str(DEFAULT_SECTOR_DEPTH_OBJECT_BM25),
        "bge_model": str(DEFAULT_BGE_MODEL),
        "bge_device": os.environ.get("BGE_DEVICE", "cpu"),
        "context_runner": "in_process",
        "evidence_top_k": 4,
        "object_top_k": 4,
        "candidate_budget": 160,
        "rerank_budget": 32,
        "reranker_batch_size": 8,
        "reranker_max_length": 512,
        "reranker_doc_max_chars": 1800,
        "limit": 8,
        "run_id": "specialist_real_evidence_sec_search",
    }


def _bounded_context_row(
    row: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    result: Mapping[str, Any],
    args: Mapping[str, Any],
) -> dict[str, Any]:
    text = row.get("summary") or row.get("text") or row.get("snippet") or row.get("description") or ""
    summary = (
        f"{row.get('ticker') or ''} {row.get('form_type') or row.get('source_type') or ''} "
        f"{row.get('fiscal_year') or row.get('year') or ''}; "
        f"section={row.get('section') or row.get('item') or ''}; {text}"
    )
    return _with_real_metadata(
        {
            "evidence_ref": str(row.get("evidence_id") or row.get("source_evidence_id") or row.get("object_id") or ""),
            "source_family": str(row.get("source_family") or row.get("source_tier") or "primary_sec_filing"),
            "ticker": str(row.get("ticker") or ""),
            "period_role": str(row.get("period_role") or row.get("period") or ""),
            "metric": str(row.get("metric_family") or row.get("metric") or row.get("object_type") or "filing_context"),
            "value": str(row.get("value") or row.get("display_value") or ""),
            "summary": _truncate(summary, 900),
            "form_type": str(row.get("form_type") or row.get("source_type") or ""),
            "retrieval_status": str(result.get("status") or ""),
            "candidate_counts": dict(result.get("candidate_counts") or {}),
        },
        path=_repo_path(args.get("manifest_path")),
        source_type="sec_search_filings",
    )


def _filter_rows(rows: list[dict[str, Any]], filters: Mapping[str, Any]) -> list[dict[str, Any]]:
    tickers = set(_upper_list(filters.get("tickers")))
    metric_families = set(_string_list(filters.get("metric_families")))
    period_roles = set(_lower_list(filters.get("period_roles")))
    years = set(_int_list(filters.get("years")))
    source_families = set(_string_list(filters.get("source_families")))
    series_ids = set(_string_list(filters.get("series_ids")))
    out: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        metric_family = str(row.get("metric_family") or row.get("metric") or row.get("field") or "")
        period_role = str(row.get("period_role") or "").lower()
        fiscal_year = row.get("fiscal_year") or row.get("source_fiscal_year")
        source_family = str(row.get("source_family") or row.get("source_tier") or "")
        series_id = str(row.get("series_id") or "")
        if tickers and ticker not in tickers:
            continue
        if metric_families and metric_family not in metric_families:
            continue
        if period_roles and period_role not in period_roles:
            continue
        if years and _safe_int(fiscal_year) not in years:
            continue
        if source_families and source_family not in source_families:
            continue
        if series_ids and series_id not in series_ids:
            continue
        out.append(row)
    return out


def _bounded_ledger_row(row: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    value = row.get("display_value_zh") or row.get("raw_value_text") or row.get("value_text") or row.get("value") or ""
    metric = str(row.get("metric_family") or row.get("metric_name") or "")
    summary = (
        f"{row.get('ticker') or ''} {row.get('fiscal_year') or row.get('period') or ''} "
        f"{metric} {row.get('metric_role') or ''}: {value}; "
        f"source={row.get('form_type') or row.get('source_type') or ''}, period_role={row.get('period_role') or ''}, "
        f"section={row.get('section') or ''}."
    )
    return _with_real_metadata(
        {
            "evidence_ref": str(row.get("metric_id") or row.get("source_evidence_id") or row.get("object_id") or ""),
            "source_family": str(row.get("source_tier") or "primary_sec_filing"),
            "ticker": str(row.get("ticker") or ""),
            "period_role": str(row.get("period_role") or ""),
            "metric": metric,
            "value": str(value),
            "summary": _truncate(summary, 900),
            "source_evidence_id": str(row.get("source_evidence_id") or ""),
            "form_type": str(row.get("form_type") or row.get("source_type") or ""),
        },
        path=path,
        source_type="runtime_ledger_json",
    )


def _bounded_market_row(row: Mapping[str, Any], *, path: Path, fields: list[str]) -> dict[str, Any]:
    field_parts: list[str] = []
    for ref in row.get("field_refs") or []:
        if not isinstance(ref, Mapping):
            continue
        field = str(ref.get("field_name") or "")
        if fields and field not in fields:
            continue
        value = ref.get("value")
        field_parts.append(f"{field}={value}")
    event_parts = [f"{key}={value}" for key, value in (row.get("event_window") or {}).items() if key in fields]
    summary = (
        f"{row.get('ticker') or ''} market snapshot as_of={row.get('as_of_date') or ''}; "
        f"snapshot={row.get('snapshot_id') or ''}; "
        f"fields: {'; '.join([*field_parts, *event_parts])}; "
        f"derived_signals={','.join(str(item) for item in row.get('derived_signals') or [])}."
    )
    return _with_real_metadata(
        {
            "evidence_ref": str(row.get("evidence_id") or ""),
            "source_family": "market_snapshot",
            "ticker": str(row.get("ticker") or ""),
            "period_role": "snapshot",
            "metric": "market_snapshot",
            "value": "",
            "summary": _truncate(summary, 900),
            "snapshot_id": str(row.get("snapshot_id") or ""),
            "as_of_date": str(row.get("as_of_date") or ""),
        },
        path=path,
        source_type="market_evidence_jsonl",
    )


def _bounded_industry_row(row: Mapping[str, Any], *, path: Path) -> dict[str, Any]:
    summary = (
        f"{row.get('provider') or ''} {row.get('series_id') or ''}: {row.get('summary') or ''} "
        f"latest={row.get('latest_value') or ''} {row.get('unit') or ''} as_of={row.get('as_of_date') or ''}. "
        "Industry data is context only and must not overwrite company-filed facts."
    )
    return _with_real_metadata(
        {
            "evidence_ref": str(row.get("evidence_id") or ""),
            "source_family": "industry_snapshot",
            "ticker": "",
            "period_role": "snapshot",
            "metric": str(row.get("series_id") or row.get("source_family") or "industry_snapshot"),
            "value": str(row.get("latest_value") or ""),
            "summary": _truncate(summary, 900),
            "as_of_date": str(row.get("as_of_date") or ""),
            "provider_source_family": str(row.get("source_family") or ""),
        },
        path=path,
        source_type="industry_evidence_jsonl",
    )


def _with_real_metadata(row: dict[str, Any], *, path: Path, source_type: str) -> dict[str, Any]:
    clean = dict(row)
    clean["metadata"] = {
        **(clean.get("metadata") if isinstance(clean.get("metadata"), dict) else {}),
        "real_evidence_row": True,
        "source_type": source_type,
        "source_artifact_path": str(path),
    }
    if not clean.get("evidence_ref"):
        clean["evidence_ref"] = f"{source_type}:{abs(hash(json.dumps(clean, sort_keys=True, default=str))) % 10_000_000}"
    return clean


def _summarize(
    *,
    args: argparse.Namespace,
    run_id: str,
    cases: list[dict[str, Any]],
    materialized_rows: list[dict[str, Any]],
    materialized_path: Path,
    elapsed_sec: float,
) -> dict[str, Any]:
    total = len(cases)
    pass_count = sum(1 for case in cases if case["status"] == "pass")
    materialized_input_count = sum(int(len(row.get("bounded_evidence_rows") or [])) for row in materialized_rows)
    failed_cases = [case.get("case_id") for case in cases if case["status"] != "pass"]
    gate_pass = total > 0 and pass_count == total
    return {
        "schema_version": "sec_agent_specialist_real_evidence_quality_eval_v0.1",
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "diagnostic_only": True,
        "gate_status": "pass" if gate_pass else "fail",
        "fixture": str(Path(args.fixture).resolve()),
        "materialized_fixture": str(materialized_path.resolve()),
        "model_config": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
            "raw_llm_response_saved": False,
            "api_key_saved": False,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout_s": args.timeout_s,
            "max_repair_attempts": args.max_repair_attempts,
        },
        "metrics": {
            "case_count": total,
            "pass_count": pass_count,
            "failed_count": total - pass_count,
            "failed_cases": failed_cases,
            "materialized_input_row_count": materialized_input_count,
            "total_latency_ms": _sum_case_model_metric(cases, "latency_ms"),
            "total_tokens": _sum_case_model_metric(cases, "total_tokens"),
        },
        "cases": cases,
    }


def _stdout_summary(summary: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "gate_status": summary["gate_status"],
        "diagnostic_only": summary["diagnostic_only"],
        "output_path": str(output_path.resolve()),
        "metrics": summary["metrics"],
        "failures": [
            {
                "case_id": case.get("case_id"),
                "agent_id": case.get("agent_id"),
                "checks": case.get("checks"),
                "failure_reason": case.get("failure_reason", ""),
                "unknown_evidence_refs": case.get("unknown_evidence_refs", []),
            }
            for case in summary.get("cases") or []
            if case.get("status") != "pass"
        ],
    }


def _expected_unsupported_check(row: Mapping[str, Any], unsupported: list[Any], conflicts: list[Any]) -> bool:
    if bool(row.get("expect_unsupported_or_conflict")):
        return bool(unsupported or conflicts)
    return True


def _allowed_sources_check(quality: Mapping[str, Any], observed_source_families: set[str]) -> bool:
    allowed = set(_string_list(quality.get("allowed_observation_source_families")))
    forbidden = set(_string_list(quality.get("forbidden_observation_source_families")))
    if allowed and not observed_source_families <= allowed:
        return False
    if forbidden and observed_source_families & forbidden:
        return False
    return True


def _expected_source_used_check(quality: Mapping[str, Any], observed_source_families: set[str]) -> bool:
    expected_any = set(_string_list(quality.get("expected_observation_source_families_any")))
    if not expected_any:
        return True
    return bool(observed_source_families & expected_any)


def _required_sources_present_check(quality: Mapping[str, Any], observed_source_families: set[str]) -> bool:
    required = set(_string_list(quality.get("required_observation_source_families")))
    if not required:
        return True
    return required <= observed_source_families


def _required_source_family_refs_cited_check(
    quality: Mapping[str, Any],
    observed_refs: set[str],
    rows: list[dict[str, Any]],
) -> bool:
    required_families = set(_string_list(quality.get("required_cited_source_families")))
    if not required_families:
        return True
    refs_by_family: dict[str, set[str]] = {}
    for row in rows:
        family = str(row.get("source_family") or "").strip()
        ref = str(row.get("evidence_ref") or "").strip()
        if family and ref:
            refs_by_family.setdefault(family, set()).add(ref)
    for family in required_families:
        family_refs = refs_by_family.get(family) or set()
        if not family_refs or not (observed_refs & family_refs):
            return False
    return True


def _required_ref_prefixes_present(quality: Mapping[str, Any], observed_refs: set[str]) -> bool:
    prefixes = _string_list(quality.get("required_evidence_ref_prefixes"))
    if not prefixes:
        return True
    return all(any(ref.startswith(prefix) for ref in observed_refs) for prefix in prefixes)


def _claim_terms_present(quality: Mapping[str, Any], memolet: Mapping[str, Any]) -> bool:
    terms = [term.lower() for term in _string_list(quality.get("required_claim_terms_any"))]
    if not terms:
        return True
    text = json.dumps(memolet, ensure_ascii=False).lower()
    return any(term in text for term in terms)


def _tool_call_count(route_result: Mapping[str, Any]) -> int:
    diagnostics = route_result.get("model_diagnostics") if isinstance(route_result.get("model_diagnostics"), Mapping) else {}
    calls = diagnostics.get("calls") if isinstance(diagnostics.get("calls"), list) else []
    return sum(int(call.get("tool_call_count") or 0) for call in calls if isinstance(call, Mapping))


def _sum_case_model_metric(cases: list[dict[str, Any]], metric: str) -> int | None:
    values: list[int] = []
    for case in cases:
        value = (case.get("model_diagnostics") or {}).get(metric)
        if value is not None:
            values.append(int(value))
    if not values:
        return None
    return sum(values)


def _coverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sufficiency_level": "sufficient" if rows else "insufficient",
        "input_row_count": len(rows),
        "source_families": sorted({str(row.get("source_family") or "") for row in rows if row.get("source_family")}),
        "real_evidence_row_count": sum(1 for row in rows if (row.get("metadata") or {}).get("real_evidence_row")),
    }


def _source_boundaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "allowed_source_families": sorted({str(row.get("source_family") or "") for row in rows if row.get("source_family")}),
        "input_row_count": len(rows),
        "policy": "bounded_real_evidence_rows_only",
    }


def _relationship_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    relationships = [dict(row) for row in rows if str(row.get("source_family") or "") == "relationship_graph"]
    return {
        "scope_mode": "materialized_real_evidence_case",
        "focus_tickers": sorted({str(row.get("ticker") or "") for row in relationships if row.get("ticker")}),
        "expanded_tickers": sorted({str(row.get("related_ticker") or "") for row in relationships if row.get("related_ticker")}),
        "relationship_scope_rationale": "Relationship rows are bounded hypothesis context only.",
        "relationships": relationships[:8],
        "financial_fact_policy": "relationship_graph_hypothesis_only",
    }


def _known_refs(rows: list[dict[str, Any]]) -> list[str]:
    refs = sorted({str(row.get("evidence_ref") or "") for row in rows if str(row.get("evidence_ref") or "").strip()})
    return refs


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        ref = str(row.get("evidence_ref") or "")
        if not ref or ref in seen:
            continue
        seen.add(ref)
        out.append(row)
    return out


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _repo_path(value: Any) -> Path:
    text = str(value or "").strip()
    if text.startswith("/mnt/d/"):
        return Path("D:/" + text.removeprefix("/mnt/d/")).resolve()
    path = Path(text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _limit(source: Mapping[str, Any]) -> int:
    try:
        return max(1, min(int(source.get("limit") or 12), 100))
    except (TypeError, ValueError):
        return 12


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _upper_list(value: Any) -> list[str]:
    return [item.upper() for item in _string_list(value)]


def _lower_list(value: Any) -> list[str]:
    return [item.lower() for item in _string_list(value)]


def _int_list(value: Any) -> list[int]:
    out: list[int] = []
    for item in _string_list(value):
        parsed = _safe_int(item)
        if parsed is not None:
            out.append(parsed)
    return out


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truncate(text: str, max_chars: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def _default_run_id(args: argparse.Namespace) -> str:
    safe_model = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(args.model or "model")).strip("_") or "model"
    suffix = "materialize_only" if args.materialize_only else safe_model
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_multi_agent_specialist_real_evidence_{suffix}_v0_1"


if __name__ == "__main__":
    raise SystemExit(main())
