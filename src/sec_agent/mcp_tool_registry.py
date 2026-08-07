from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from sec_agent.industry_snapshot import query_industry_snapshot
from sec_agent.ledger_store import query_ledger_facts
from sec_agent.mcp_contracts import get_mcp_tool_contract, list_mcp_tool_contracts
from sec_agent.mcp_runtime import read_bounded_artifact
from sec_agent.relationship_graph import query_relationship_graph
from sec_agent.workbench.artifacts import inspect_run_artifacts
from sec_agent.web_evidence_runtime import execute_web_evidence_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MILVUS_DEPS_PATH = Path("Z:/FIN_Insight_Agent_artifacts/python_deps/milvus_lite")
DEFAULT_MILVUS_EMBEDDING_MODEL = Path("D:/hf_cache/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181")
_INTERACTIVE_MODULE: ModuleType | None = None
_BANKING_MCP_METRIC_FAMILIES = {
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
_SEC_FORM_TYPES = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
_SEC_FORM_ID_RE = re.compile(r"(?:^|[^A-Z0-9])(?P<form>10-?K|10-?Q|8-?K|20-?F|40-?F|6-?K)(?:[^A-Z0-9]|$)")
_SEC_FORM_EQUIVALENTS = {
    "10-K": {"20-F", "40-F"},
    "10-Q": {"6-K"},
    "8-K": {"6-K"},
}


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
    filing_types = _list_arg(args.get("filing_types"))
    period_roles = _list_arg(args.get("period_roles"))
    rows = _query_ledger_with_args(args, db_path=db_path, filing_types=filing_types, period_roles=period_roles)
    fallback_trace: list[dict[str, Any]] = []
    if not rows and filing_types:
        rows = _query_ledger_with_args(args, db_path=db_path, filing_types=[], period_roles=period_roles)
        fallback_trace.append(
            {
                "type": "relaxed_filing_type",
                "requested_filing_types": filing_types,
                "row_count": len(rows),
                "reason": "requested exact-value form type had no ledger rows; retained ticker/year/source/metric filters",
            }
        )
    if not rows and period_roles:
        rows = _query_ledger_with_args(args, db_path=db_path, filing_types=filing_types, period_roles=[])
        fallback_trace.append(
            {
                "type": "relaxed_period_role",
                "requested_period_roles": period_roles,
                "row_count": len(rows),
                "reason": "requested exact-value period role had no ledger rows; retained ticker/year/source/metric filters",
            }
        )
    if not rows and filing_types and period_roles:
        rows = _query_ledger_with_args(args, db_path=db_path, filing_types=[], period_roles=[])
        fallback_trace.append(
            {
                "type": "relaxed_filing_type_and_period_role",
                "requested_filing_types": filing_types,
                "requested_period_roles": period_roles,
                "row_count": len(rows),
                "reason": "requested exact-value form and period role had no ledger rows; retained ticker/year/source/metric filters",
            }
        )
    return {
        "status": "ok" if rows else "partial",
        "ledger_rows": rows,
        "row_count": len(rows),
        "fallback_trace": fallback_trace,
        "missing_dimensions": [],
        "artifact_refs": [{"artifact_id": "ledger_store", "path": str(Path(db_path).resolve()), "digest": "", "row_count": len(rows)}],
    }


def _query_ledger_with_args(
    args: dict[str, Any],
    *,
    db_path: Any,
    filing_types: list[str],
    period_roles: list[str],
) -> list[dict[str, Any]]:
    case_id = str(args.get("case_id") or "__mcp__")
    rows = query_ledger_facts(
        db_path,
        case_id=case_id,
        object_ids=_list_arg(args.get("object_ids")),
        tickers=_list_arg(args.get("tickers")),
        years=[int(year) for year in _list_arg(args.get("years")) if str(year).isdigit()],
        filing_types=filing_types,
        source_tiers=_list_arg(args.get("source_tiers")),
        metric_families=_list_arg(args.get("metric_families")),
        period_roles=period_roles,
        limit=int(args.get("limit") or 5000),
    )
    normalized = [_normalize_ledger_tool_metric_family(row, case_id=case_id) for row in rows]
    return [row for row in normalized if _ledger_tool_row_allowed(row)]


def _normalize_ledger_tool_metric_family(row: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    family = str(row.get("metric_family") or "").strip()
    ticker = str(row.get("ticker") or "").upper()
    label_text = " ".join(
        str(row.get(key) or "")
        for key in ("metric_name", "row_label", "column_label", "table_title", "record_title")
    ).lower()
    product_family_aliases = {
        "ai_optimized_servers",
        "traditional_servers_and_networking",
        "storage",
        "commercial",
        "consumer",
        "products",
        "services",
    }
    product_revenue_terms = (
        "ai-optimized servers",
        "traditional servers and networking",
        "total isg net revenue",
        "total csg net revenue",
        "storage",
        "commercial",
        "consumer",
    )
    if family not in product_family_aliases and not (
        ticker == "DELL"
        and family in {"revenue", "total_revenue", "segment_revenue"}
        and any(term in label_text for term in product_revenue_terms)
    ):
        return row
    normalized = dict(row)
    normalized["source_metric_family"] = family
    normalized["metric_family"] = "product_revenue"
    normalized["metric_name"] = str(normalized.get("metric_name") or normalized.get("row_label") or family.replace("_", " ")).strip()
    normalized["metric_role"] = "total_value" if str(normalized.get("unit") or "").startswith("usd") else str(normalized.get("metric_role") or "")
    normalized["metric_id"] = _ledger_tool_metric_id(
        case_id,
        normalized.get("ticker"),
        normalized.get("fiscal_year"),
        "product_revenue",
        normalized.get("metric_role") or "total_value",
        period_role=normalized.get("period_role"),
        suffix=_slug(str(normalized.get("row_label") or normalized.get("metric_name") or family)),
    )
    return normalized


def _ledger_tool_row_allowed(row: dict[str, Any]) -> bool:
    family = str(row.get("metric_family") or "")
    unit = str(row.get("unit") or "").lower()
    row_text = " ".join(
        str(row.get(key) or "")
        for key in ("metric_name", "row_label", "column_label", "table_title", "record_title", "source_text", "metric_id")
    ).lower()
    if family == "product_revenue" and unit == "percent":
        return False
    if family in {"rpo", "arr_or_recurring_proxy"}:
        if not any(term in row_text for term in ("remaining performance obligation", "rpo", "backlog", "bookings", "order backlog")):
            return False
        if any(
            term in row_text
            for term in (
                "corporate debt securities",
                "corporate notes",
                "corporate and other assets",
                "corporate_and_other_assets",
                "long-term debt",
                "long term debt",
                "long_term_debt",
                "debt securities",
                "debt_securities",
                "unamortized discount",
                "unamortized_discount",
                "issuance costs",
                "issuance_costs",
                "bonds",
            )
        ):
            return False
        if unit == "percent":
            return False
    return True


def _ledger_tool_metric_id(
    case_id: str,
    ticker: Any,
    fiscal_year: Any,
    metric_family: Any,
    metric_role: Any,
    *,
    period_role: Any = "",
    suffix: str = "",
) -> str:
    parts = [
        str(case_id or "__mcp__"),
        str(ticker or "").upper(),
        str(fiscal_year or ""),
        str(metric_family or ""),
        str(metric_role or ""),
    ]
    if period_role:
        parts.append(str(period_role))
    if suffix:
        parts.append(suffix)
    return "::".join(parts)


def _invoke_sec_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {"status": "error", "error": "query_required", "context_rows": []}
    validation_error = _validate_sec_search_arguments(args)
    if validation_error:
        return {"status": "error", "error": validation_error, "context_rows": []}

    interactive = _load_interactive_module()
    runtime_args = _interactive_args_for_sec_search(args)
    try:
        plan = interactive.build_query_plan_for_graph(runtime_args, query)
    except RuntimeError as exc:
        if "No available SEC filings matched inferred scope" not in str(exc):
            raise
        query_contract = _minimal_sec_search_contract_from_args(args, query)
        gaps = _sec_search_requested_scope_gaps(
            query_contract,
            reason_code="no_available_sec_filings_matched_inferred_scope",
            reason="Interactive SEC planning found no available filings for the requested ticker/year/form/tier scope.",
            source="mcp_sec_search_filings",
        )
        return _sec_search_source_gap_result(
            query_contract=query_contract,
            selected_tickers=query_contract.get("search_scope_tickers") or [],
            selected_years=query_contract.get("years") or [],
            gaps=gaps,
        )
    query_contract = _overlay_sec_search_contract(plan.get("query_contract") or {}, args, query)
    coverage_gaps = [gap for gap in query_contract.get("source_coverage_gaps") or [] if isinstance(gap, dict)]
    if coverage_gaps and not query_contract.get("evidence_requirements"):
        return _sec_search_source_gap_result(
            query_contract=query_contract,
            selected_tickers=query_contract.get("search_scope_tickers") or plan.get("selected_tickers") or [],
            selected_years=query_contract.get("years") or plan.get("selected_years") or [],
            gaps=coverage_gaps,
        )
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
    if isinstance(args.get("retrieval_plan"), dict):
        graph_state["retrieval_plan"] = dict(args.get("retrieval_plan") or {})
    try:
        result = interactive.retrieve_context_for_graph(runtime_args, graph_state)
    except RuntimeError as exc:
        if "No available SEC filings matched inferred scope" not in str(exc):
            raise
        gaps = [gap for gap in query_contract.get("source_coverage_gaps") or [] if isinstance(gap, dict)]
        if not gaps or not any(str(gap.get("reason_code") or "").strip() for gap in gaps):
            gaps = _sec_search_requested_scope_gaps(
                query_contract,
                reason_code="no_available_sec_filings_matched_inferred_scope",
                reason="Interactive SEC retrieval found no available filings for the requested ticker/year/form/tier scope.",
                source="mcp_sec_search_filings",
            )
        return _sec_search_source_gap_result(
            query_contract=query_contract,
            selected_tickers=graph_state["selected_tickers"],
            selected_years=graph_state["selected_years"],
            gaps=gaps,
        )
    rows = [row for row in result.get("context_rows") or [] if isinstance(row, dict)]
    trace = result.get("retrieval_trace") if isinstance(result.get("retrieval_trace"), dict) else {}
    ledger_rows: list[dict[str, Any]] = []
    ledger_artifact_refs: list[dict[str, Any]] = []
    if _bool_arg(args.get("build_runtime_ledger"), default=False) and rows:
        build_runtime_ledger = getattr(interactive, "build_runtime_ledger_for_graph", None)
        if callable(build_runtime_ledger):
            ledger_result = build_runtime_ledger(
                runtime_args,
                {
                    **graph_state,
                    "context_rows": rows,
                    "retrieval_trace": trace,
                },
            )
            ledger_rows = [row for row in ledger_result.get("runtime_ledger_rows") or [] if isinstance(row, dict)]
            ledger_artifact_refs = _artifact_refs_from_mapping(
                ledger_result.get("artifact_refs"),
                row_count=len(ledger_rows),
            )
    candidate_counts = _candidate_counts_from_trace(trace, rows)
    return {
        "status": "ok" if rows else "partial",
        "context_rows": rows,
        "runtime_ledger_rows": ledger_rows,
        "row_count": len(rows),
        "runtime_ledger_row_count": len(ledger_rows),
        "query_contract": query_contract,
        "selected_tickers": graph_state["selected_tickers"],
        "selected_years": graph_state["selected_years"],
        "retrieval_trace": trace,
        "context_runtime": result.get("context_runtime") if isinstance(result.get("context_runtime"), dict) else {},
        "candidate_counts": candidate_counts,
        "artifact_refs": [
            *_artifact_refs_from_mapping(result.get("artifact_refs"), row_count=len(rows)),
            *ledger_artifact_refs,
        ],
        "source_gaps": _sec_search_source_gaps(query_contract, rows),
    }


def _invoke_milvus_semantic(args: dict[str, Any]) -> dict[str, Any]:
    vector_kinds = _list_arg(args.get("vector_kinds"))
    if not vector_kinds:
        vector_kinds = ["narrative_chunk", "table_chunk", "paraphrase_context", "relationship_context"]
    db_path = str(args.get("milvus_db_path") or args.get("milvus_uri") or "").strip()
    collection_name = str(args.get("milvus_collection_name") or "").strip()
    embedding_model = str(args.get("embedding_model") or os.environ.get("MILVUS_EMBEDDING_MODEL") or DEFAULT_MILVUS_EMBEDDING_MODEL).strip()
    missing = []
    if not db_path:
        missing.append("milvus_db_path")
    if not collection_name:
        missing.append("milvus_collection_name")
    if not embedding_model:
        missing.append("embedding_model")
    if not bool(args.get("typed_filter_required", True)):
        missing.append("typed_filter_required")
    if db_path and not Path(db_path).exists():
        missing.append("milvus_db_path_exists")
    if embedding_model and not Path(embedding_model).exists():
        missing.append("embedding_model_exists")
    if missing:
        return _milvus_unavailable_result(
            args,
            reason_code="milvus_semantic_config_missing",
            missing=missing,
            vector_kinds=vector_kinds,
            collection_name=collection_name,
        )

    started = time.monotonic()
    query = str(args.get("query") or args.get("prompt") or "").strip()
    if not query:
        return _milvus_unavailable_result(
            args,
            reason_code="milvus_semantic_query_missing",
            missing=["query"],
            vector_kinds=vector_kinds,
            collection_name=collection_name,
        )

    top_k = _bounded_int(args.get("milvus_top_k") or args.get("limit") or args.get("top_k"), default=40, minimum=1, maximum=200)
    try:
        client = _milvus_client(db_path, collection_name)
        model = _milvus_embedding_model(embedding_model, _milvus_embedding_device(args))
        embedding = model.encode(
            [query],
            batch_size=1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        output_fields = _milvus_output_fields(include_typed=True)
        try:
            raw_results = client.search(
                collection_name=collection_name,
                data=[[float(item) for item in embedding.tolist()]],
                anns_field="embedding",
                limit=top_k,
                filter=_milvus_filter_expr(args, vector_kinds),
                output_fields=output_fields,
            )
        except Exception as exc:
            if not any(field in str(exc) for field in ("vector_role", "semantic_scope", "relationship_role", "intent_tags")):
                raise
            raw_results = client.search(
                collection_name=collection_name,
                data=[[float(item) for item in embedding.tolist()]],
                anns_field="embedding",
                limit=top_k,
                filter=_milvus_filter_expr(args, vector_kinds),
                output_fields=_milvus_output_fields(include_typed=False),
            )
        rows = _milvus_context_rows(raw_results[0] if raw_results else [], args=args)
        vector_kind_counts: dict[str, int] = {}
        for row in rows:
            kind = str(row.get("vector_kind") or "")
            if kind:
                vector_kind_counts[kind] = vector_kind_counts.get(kind, 0) + 1
        stats: dict[str, Any] = {}
        try:
            stats = dict(client.get_collection_stats(collection_name) or {})
        except Exception:
            stats = {}
        return {
            "status": "ok",
            "schema_version": "sec_agent_milvus_semantic_search_result_v0_1",
            "context_rows": rows,
            "row_count": len(rows),
            "vector_kind_counts": vector_kind_counts,
            "collection_name": collection_name,
            "collection_stats": stats,
            "typed_filter_required": True,
            "semantic_route_role": "semantic_recall_supplement",
            "exact_value_authority": False,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "artifact_refs": [
                {
                    "artifact_id": "milvus_semantic_collection",
                    "path": db_path,
                    "collection_name": collection_name,
                    "digest": "",
                    "row_count": int(stats.get("row_count") or 0),
                }
            ],
            "source_gaps": [],
        }
    except Exception as exc:  # noqa: BLE001
        return _milvus_unavailable_result(
            args,
            reason_code="milvus_semantic_runtime_error",
            missing=[],
            vector_kinds=vector_kinds,
            collection_name=collection_name,
            error=f"{type(exc).__name__}: {exc}",
        )


def _milvus_unavailable_result(
    args: dict[str, Any],
    *,
    reason_code: str,
    missing: list[str],
    vector_kinds: list[str],
    collection_name: str,
    error: str = "",
) -> dict[str, Any]:
    gap = {
        "source_family": "primary_sec_filing",
        "retrieval_route": "milvus_semantic",
        "reason_code": reason_code,
        "reason": (
            error
            or "Milvus semantic route is registered as a typed recall supplement, but the runtime search handler is not available."
        ),
        "missing": missing,
        "vector_kinds": vector_kinds,
        "source_available": False,
    }
    return {
        "status": "error",
        "error": gap["reason_code"],
        "context_rows": [],
        "row_count": 0,
        "vector_kind_counts": {},
        "collection_name": collection_name,
        "typed_filter_required": True,
        "semantic_route_role": "semantic_recall_supplement",
        "artifact_refs": [],
        "source_gaps": [gap],
    }


@lru_cache(maxsize=4)
def _milvus_client(db_path: str, collection_name: str) -> Any:
    _install_milvus_import_paths()
    from pymilvus import MilvusClient  # noqa: PLC0415

    client = MilvusClient(uri=db_path)
    client.load_collection(collection_name)
    return client


@lru_cache(maxsize=2)
def _milvus_embedding_model(model_path: str, device: str) -> Any:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TQDM_DISABLE", "1")
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    return SentenceTransformer(model_path, device=device)


def _install_milvus_import_paths() -> None:
    deps = Path(os.environ.get("MILVUS_DEPS_PATH") or os.environ.get("FINSIGHT_MILVUS_DEPS_PATH") or DEFAULT_MILVUS_DEPS_PATH)
    for path in (deps,):
        if path.exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _milvus_embedding_device(args: dict[str, Any]) -> str:
    requested = str(args.get("embedding_device") or os.environ.get("MILVUS_EMBEDDING_DEVICE") or "").strip().lower()
    if requested and requested not in {"auto", "default"}:
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _milvus_output_fields(*, include_typed: bool) -> list[str]:
    fields = [
        "vector_id",
        "evidence_id",
        "ticker",
        "fiscal_year",
        "form_type",
        "source_tier",
        "item_code",
        "category_slug",
        "period_type",
        "contains_table",
        "vector_kind",
        "object_type",
        "preview",
    ]
    if include_typed:
        fields.extend(["vector_role", "semantic_scope", "intent_tags", "relationship_role"])
    return fields


def _milvus_filter_expr(args: dict[str, Any], vector_kinds: list[str]) -> str:
    clauses: list[str] = []
    tickers = [str(item).upper() for item in _list_arg(args.get("tickers")) if str(item).strip()]
    years = [int(item) for item in _list_arg(args.get("years")) if str(item).strip().isdigit()]
    forms = [_normalize_sec_form_type(item) for item in _list_arg(args.get("filing_types")) if str(item).strip()]
    source_tiers = [str(item) for item in _list_arg(args.get("source_tiers")) if str(item).strip() and str(item) != "milvus_semantic"]
    if tickers:
        clauses.append(_milvus_in_clause("ticker", tickers))
    if years:
        clauses.append("fiscal_year in [" + ", ".join(str(year) for year in years) + "]")
    if forms:
        clauses.append(_milvus_in_clause("form_type", forms))
    if source_tiers:
        clauses.append(_milvus_in_clause("source_tier", source_tiers))
    if vector_kinds:
        clauses.append(_milvus_in_clause("vector_kind", vector_kinds))
    return " and ".join(clauses)


def _milvus_in_clause(field: str, values: list[str]) -> str:
    clean = []
    for value in values:
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        if escaped not in clean:
            clean.append(escaped)
    return f"{field} in [" + ", ".join(f'"{value}"' for value in clean) + "]"


def _normalize_sec_form_type(value: Any) -> str:
    text = str(value or "").upper().replace(" ", "").replace("_", "-")
    return text.replace("10K", "10-K").replace("10Q", "10-Q").replace("8K", "8-K").replace("20F", "20-F").replace("40F", "40-F").replace("6K", "6-K")


def _milvus_context_rows(hits: list[Any], *, args: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    route_id = str(args.get("route_id") or args.get("task_id") or "milvus_semantic")
    for rank, hit in enumerate(hits, start=1):
        entity = dict(hit.get("entity") or {})
        evidence_id = str(entity.get("evidence_id") or entity.get("vector_id") or "")
        if not evidence_id:
            continue
        rows.append(
            {
                "evidence_ref": evidence_id,
                "evidence_id": evidence_id,
                "source_family": "milvus_semantic",
                "original_source_family": "primary_sec_filing",
                "source_tier": entity.get("source_tier") or "",
                "retrieval_route": "milvus_semantic",
                "selection_route_id": route_id,
                "selection_route_ids": [route_id],
                "ticker": entity.get("ticker") or "",
                "fiscal_year": entity.get("fiscal_year"),
                "form_type": entity.get("form_type") or "",
                "item_code": entity.get("item_code") or "",
                "category_slug": entity.get("category_slug") or "",
                "period_type": entity.get("period_type") or "",
                "contains_table": bool(entity.get("contains_table")),
                "vector_kind": entity.get("vector_kind") or "",
                "vector_role": entity.get("vector_role") or "",
                "semantic_scope": entity.get("semantic_scope") or "",
                "intent_tags": entity.get("intent_tags") or "",
                "relationship_role": entity.get("relationship_role") or "",
                "object_type": entity.get("object_type") or "",
                "preview": entity.get("preview") or "",
                "text": entity.get("preview") or "",
                "rank": rank,
                "score": float(hit.get("distance") or 0.0),
                "semantic_route_role": "semantic_recall_supplement",
                "authority_boundary": "semantic_recall_supplement_not_exact_value_authority",
                "exact_value_authority": False,
            }
        )
    return rows


def _invoke_market(args: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(args.get("market_evidence_path") or "")).resolve()
    if not path.exists():
        return {"status": "error", "error": "market_evidence_path_not_found", "path": str(path)}
    catalog_path = Path(str(args.get("market_catalog_path") or "")).resolve() if str(args.get("market_catalog_path") or "").strip() else None
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
    artifact_refs = [{"artifact_id": "market_evidence_rows", "path": str(path), "digest": "", "row_count": len(rows)}]
    if catalog_path is not None:
        artifact_refs.append({"artifact_id": "market_catalog", "path": str(catalog_path), "digest": "", "row_count": 0})
    return {
        "status": "ok" if rows else "partial",
        "market_rows": rows,
        "snapshot_id": snapshot_id or (str(rows[0].get("snapshot_id") or "") if rows else ""),
        "as_of_date": str(args.get("as_of_date") or (rows[0].get("as_of_date") if rows else "") or ""),
        "field_gaps": field_gaps,
        "artifact_refs": artifact_refs,
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


def _invoke_relationship_graph(args: dict[str, Any]) -> dict[str, Any]:
    return query_relationship_graph(
        focus_tickers=_list_arg(args.get("focus_tickers")),
        search_scope_tickers=_list_arg(args.get("search_scope_tickers")),
        allowed_universe_tickers=_list_arg(args.get("allowed_universe_tickers")),
        user_query=str(args.get("user_query") or ""),
        relationship_graph_path=args.get("relationship_graph_path") or os.environ.get("RELATIONSHIP_GRAPH_PATH") or "",
        sector_depth_pack_path=args.get("sector_depth_pack_path") or os.environ.get("SECTOR_DEPTH_PACK_PATH") or "",
        expected_pack_ids=_list_arg(args.get("expected_pack_ids") or args.get("expected_relationship_pack_ids")),
        max_relationships=int(args.get("max_relationships") or 24),
        max_expanded_tickers=int(args.get("max_expanded_tickers") or 12),
        include_sector_depth=_bool_arg(args.get("include_sector_depth"), default=True),
    )


def _invoke_web_evidence_snapshot(args: dict[str, Any]) -> dict[str, Any]:
    return execute_web_evidence_snapshot(args)


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
    context_reranker = str(args.get("context_reranker") or "").strip().lower()
    if not context_reranker:
        context_reranker = "none" if rerank_budget == 0 else "bge"
    if context_reranker not in {"none", "bge"}:
        raise ValueError(f"unsupported_context_reranker:{context_reranker}")
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
        context_reranker=context_reranker,
        allow_bm25_only_pipeline=context_reranker == "none",
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
        rules = dict(clean.get("ledger_rules") or {})
        rules["allowed_metric_families"] = metric_families
        if tickers and set(metric_families) & _BANKING_MCP_METRIC_FAMILIES:
            rules["banking_metric_tickers"] = tickers
        clean["ledger_rules"] = rules
    if period_roles:
        clean["period_roles"] = period_roles

    requirements, source_gaps = _evidence_requirements_from_args(args, clean, query)
    if requirements:
        clean["evidence_requirements"] = requirements
    if source_gaps:
        clean["source_coverage_gaps"] = [*(clean.get("source_coverage_gaps") or []), *source_gaps]
    else:
        clean.setdefault("source_coverage_gaps", [])
    return clean


def _minimal_sec_search_contract_from_args(args: dict[str, Any], query: str) -> dict[str, Any]:
    tickers = [str(ticker).upper() for ticker in _list_arg(args.get("tickers"))]
    years = [int(year) for year in _list_arg(args.get("years")) if str(year).isdigit()]
    filing_types = [_normalize_form_type(form) for form in _list_arg(args.get("filing_types")) if _normalize_form_type(form)]
    source_tiers = [str(tier) for tier in _list_arg(args.get("source_tiers")) if str(tier).strip()]
    metric_families = [str(family) for family in _list_arg(args.get("metric_families")) if str(family).strip()]
    period_roles = [str(role).upper() for role in _list_arg(args.get("period_roles")) if str(role).strip()]
    return {
        "task_type": "sec_search_source_gap",
        "question": query,
        "search_scope_tickers": tickers,
        "focus_tickers": tickers,
        "years": years,
        "filing_types": filing_types,
        "source_tiers": source_tiers,
        "metric_families": metric_families,
        "period_roles": period_roles,
    }


def _sec_search_source_gap_result(
    *,
    query_contract: dict[str, Any],
    selected_tickers: list[Any],
    selected_years: list[Any],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "source_gap",
        "error": str(gaps[0].get("reason_code") or "sec_search_source_gap") if gaps else "sec_search_source_gap",
        "context_rows": [],
        "runtime_ledger_rows": [],
        "row_count": 0,
        "runtime_ledger_row_count": 0,
        "query_contract": query_contract,
        "selected_tickers": selected_tickers,
        "selected_years": selected_years,
        "retrieval_trace": {},
        "context_runtime": {},
        "candidate_counts": {
            "context_row_count": 0,
            "summary_context_row_count": 0,
            "candidate_row_count_pre_rerank": 0,
            "candidate_sent_to_bge": 0,
            "route_candidate_stats": [],
            "timing_ms": {},
        },
        "artifact_refs": [],
        "source_gaps": gaps,
    }


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
    if len(set(requested_forms)) <= 1 and not explicit_route:
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
        form = _manifest_row_form_type(row)
        tier = str(row.get("source_tier") or _default_source_tier_for_form(form)).strip()
        if not ticker or year is None or not form:
            continue
        if requested_tickers and ticker not in requested_tickers:
            continue
        if requested_years and year not in requested_years:
            continue
        if requested_form_set and not _manifest_form_satisfies_requested(form, requested_form_set):
            continue
        if requested_tier_set and tier not in requested_tier_set:
            continue
        route = explicit_route or _default_route_for_form(form)
        if not route:
            continue
        available_groups.setdefault((year, form, tier, route), set()).add(ticker)
        available_keys.add((ticker, year, form, tier))

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
        requirement["rerank_budget"] = rerank_budget
        requirements.append(requirement)

    source_gaps: list[dict[str, Any]] = []
    for ticker in sorted(requested_tickers):
        for year in sorted(requested_years):
            for form in sorted(requested_form_set):
                tiers = _tiers_for_requested_form(form, requested_tiers)
                for tier in tiers:
                    if _requested_sec_scope_has_available_form(
                        ticker,
                        year,
                        form,
                        tier,
                        available_keys,
                    ):
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
    if not available_groups and source_gaps:
        return [], source_gaps
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
    return (
        text.replace("10K", "10-K")
        .replace("10Q", "10-Q")
        .replace("8K", "8-K")
        .replace("20F", "20-F")
        .replace("40F", "40-F")
        .replace("6K", "6-K")
    )


def _manifest_row_form_type(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    for value in (
        row.get("form_type"),
        row.get("source_type"),
        metadata.get("form_type"),
        metadata.get("source_type"),
    ):
        form = _normalize_form_type(value)
        if form in _SEC_FORM_TYPES:
            return form
    for key in ("evidence_id", "source_evidence_id", "source_id", "chunk_id", "block_id", "object_id", "id"):
        form = _form_type_from_source_id(row.get(key))
        if form:
            return form
    return ""


def _form_type_from_source_id(value: Any) -> str:
    match = _SEC_FORM_ID_RE.search(str(value or "").upper())
    if not match:
        return ""
    form = _normalize_form_type(match.group("form"))
    return form if form in _SEC_FORM_TYPES else ""


def _default_source_tier_for_form(form: str) -> str:
    if form in {"8-K", "6-K"}:
        return "company_authored_unaudited_sec_filing"
    return "primary_sec_filing"


def _default_route_for_form(form: str) -> str:
    if form == "8-K":
        return "8k_commentary"
    if form == "6-K":
        return "8k_commentary"
    if form in {"10-K", "10-Q", "20-F", "40-F"}:
        return "filing_text"
    return ""


def _manifest_form_satisfies_requested(form: str, requested_forms: set[str]) -> bool:
    if form in requested_forms:
        return True
    return any(form in _SEC_FORM_EQUIVALENTS.get(requested_form, set()) for requested_form in requested_forms)


def _requested_sec_scope_has_available_form(
    ticker: str,
    year: int,
    requested_form: str,
    requested_tier: str,
    available_keys: set[tuple[str, int, str, str]],
) -> bool:
    forms = [requested_form, *sorted(_SEC_FORM_EQUIVALENTS.get(requested_form, set()))]
    for form in forms:
        tiers = {requested_tier, _default_source_tier_for_form(form)}
        for tier in tiers:
            if (ticker, year, form, tier) in available_keys:
                return True
    return False


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


def _web_domain(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"^[a-z]+://", "", text)
    text = text.split("/")[0].split("@")[-1].split(":")[0].strip(".")
    if text.startswith("www."):
        text = text[4:]
    return text


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


def _sec_search_requested_scope_gaps(
    contract: dict[str, Any],
    *,
    reason_code: str,
    reason: str,
    source: str,
) -> list[dict[str, Any]]:
    tickers = [
        str(item).upper()
        for item in contract.get("search_scope_tickers") or contract.get("focus_tickers") or []
        if str(item).strip()
    ]
    years = [int(item) for item in contract.get("years") or [] if str(item).isdigit()]
    forms = [_normalize_form_type(item) for item in contract.get("filing_types") or [] if _normalize_form_type(item)]
    tiers = [str(item) for item in contract.get("source_tiers") or [] if str(item).strip()]
    tickers = tickers or [""]
    years = years or [0]
    forms = forms or [""]
    gaps: list[dict[str, Any]] = []
    for ticker in tickers:
        for year in years:
            for form in forms:
                scoped_tiers = _tiers_for_requested_form(form, tiers) if form else (tiers or [""])
                for tier in scoped_tiers:
                    gap = {
                        "ticker": ticker,
                        "form_type": form,
                        "source_tier": tier,
                        "reason_code": reason_code,
                        "reason": reason,
                        "source": source,
                        "status": "missing",
                    }
                    if year:
                        gap["year"] = year
                    gaps.append(gap)
    return gaps


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "sec_search_filings": _invoke_sec_search,
    "sec_milvus_semantic_search": _invoke_milvus_semantic,
    "sec_query_exact_value_ledger": _invoke_ledger,
    "market_get_snapshot": _invoke_market,
    "industry_get_snapshot": _invoke_industry,
    "relationship_graph_lookup": _invoke_relationship_graph,
    "web_evidence_snapshot": _invoke_web_evidence_snapshot,
    "run_inspect_artifacts": _invoke_run_inspect,
    "run_read_artifact": _invoke_run_read,
}
