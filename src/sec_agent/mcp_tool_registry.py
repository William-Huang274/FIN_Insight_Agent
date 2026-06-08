from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from sec_agent.industry_snapshot import query_industry_snapshot
from sec_agent.ledger_store import query_ledger_facts
from sec_agent.mcp_contracts import get_mcp_tool_contract, list_mcp_tool_contracts
from sec_agent.mcp_runtime import read_bounded_artifact
from sec_agent.relationship_graph import query_relationship_graph
from sec_agent.workbench.artifacts import inspect_run_artifacts


REPO_ROOT = Path(__file__).resolve().parents[2]
_INTERACTIVE_MODULE: ModuleType | None = None
_MILVUS_EMBEDDING_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MILVUS_CLIENT_CACHE: dict[tuple[str, str], Any] = {}
_SEC_SEARCH_RESULT_CACHE: dict[str, dict[str, Any]] = {}
_SEC_MANIFEST_ROWS_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
_RESIDENT_FORWARD_TOOLS = {"sec_search_filings", "sec_milvus_semantic_search"}
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


def list_registered_tools() -> list[dict[str, Any]]:
    return list_mcp_tool_contracts()


def invoke_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = dict(arguments or {})
    if _should_forward_to_resident(str(tool_name or "")):
        return _invoke_resident_worker(str(tool_name or ""), args)
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


def _should_forward_to_resident(tool_name: str) -> bool:
    if os.environ.get("SEC_AGENT_MCP_RESIDENT_BYPASS"):
        return False
    if tool_name not in _RESIDENT_FORWARD_TOOLS:
        return False
    return bool(str(os.environ.get("SEC_AGENT_MCP_RESIDENT_URL") or "").strip())


def _invoke_resident_worker(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    base_url = str(os.environ.get("SEC_AGENT_MCP_RESIDENT_URL") or "").strip().rstrip("/")
    timeout_s = _bounded_int(os.environ.get("SEC_AGENT_MCP_RESIDENT_TIMEOUT_S"), default=900, minimum=1, maximum=7200)
    payload = json.dumps({"tool_name": tool_name, "arguments": args}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/invoke",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    started = datetime.now()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - local worker URL is explicitly configured.
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": "error",
            "error": "resident_worker_unavailable",
            "tool_name": tool_name,
            "resident_worker": {"url": base_url, "elapsed_ms": int((datetime.now() - started).total_seconds() * 1000)},
            "source_gaps": [
                {
                    "source_family": "run_artifact",
                    "reason_code": "resident_worker_unavailable",
                    "reason": "Configured resident MCP worker could not be reached; fail closed to avoid cold-start fallback.",
                    "error": f"{type(exc).__name__}:{exc}"[:500],
                }
            ],
        }
    try:
        result = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"resident_worker_invalid_json:{exc}", "tool_name": tool_name}
    if not isinstance(result, dict):
        return {"status": "error", "error": "resident_worker_invalid_response", "tool_name": tool_name}
    metadata = dict(result.get("resident_worker") or {}) if isinstance(result.get("resident_worker"), dict) else {}
    metadata.update({"url": base_url, "client_elapsed_ms": int((datetime.now() - started).total_seconds() * 1000)})
    result["resident_worker"] = metadata
    return result


def _invoke_ledger(args: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
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
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000)),
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
    return query_ledger_facts(
        db_path,
        case_id=str(args.get("case_id") or "__mcp__"),
        object_ids=_list_arg(args.get("object_ids")),
        tickers=_list_arg(args.get("tickers")),
        years=[int(year) for year in _list_arg(args.get("years")) if str(year).isdigit()],
        filing_types=filing_types,
        source_tiers=_list_arg(args.get("source_tiers")),
        metric_families=_list_arg(args.get("metric_families")),
        period_roles=period_roles,
        limit=int(args.get("limit") or 5000),
    )


def _invoke_sec_search(args: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    timing_ms: dict[str, int] = {}

    def mark(stage: str, stage_started: float) -> None:
        timing_ms[stage] = int(round((time.perf_counter() - stage_started) * 1000))

    query = str(args.get("query") or "").strip()
    if not query:
        return {"status": "error", "error": "query_required", "context_rows": []}
    validation_error = _validate_sec_search_arguments(args)
    if validation_error:
        return {"status": "error", "error": validation_error, "context_rows": []}

    cache_enabled = _sec_search_result_cache_enabled(args)
    cache_key = _sec_search_result_cache_key(args) if cache_enabled else ""
    if cache_key and cache_key in _SEC_SEARCH_RESULT_CACHE:
        stage_started = time.perf_counter()
        result = copy.deepcopy(_SEC_SEARCH_RESULT_CACHE[cache_key])
        mark("result_cache_deepcopy", stage_started)
        result["mcp_result_cache"] = {
            "hit": True,
            "cache_key": cache_key,
            "cache_size": len(_SEC_SEARCH_RESULT_CACHE),
            "policy": "sec_search_result_cache_excludes_run_artifact_paths_v0_1",
        }
        result["registry_timing_ms"] = timing_ms
        result["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000))
        return result

    stage_started = time.perf_counter()
    interactive = _load_interactive_module()
    mark("load_interactive_module", stage_started)
    stage_started = time.perf_counter()
    runtime_args = _interactive_args_for_sec_search(args)
    plan = interactive.build_query_plan_for_graph(runtime_args, query)
    query_plan_timing = plan.get("query_plan_timing_ms") if isinstance(plan.get("query_plan_timing_ms"), dict) else {}
    query_contract = _overlay_sec_search_contract(plan.get("query_contract") or {}, args, query)
    mark("build_query_plan", stage_started)
    if query_plan_timing:
        timing_ms["query_plan_detail"] = _cacheable_value(query_plan_timing)  # type: ignore[assignment]
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
    stage_started = time.perf_counter()
    result = interactive.retrieve_context_for_graph(runtime_args, graph_state)
    mark("retrieve_context_for_graph", stage_started)
    stage_started = time.perf_counter()
    rows = [row for row in result.get("context_rows") or [] if isinstance(row, dict)]
    trace = result.get("retrieval_trace") if isinstance(result.get("retrieval_trace"), dict) else {}
    mark("extract_context_rows", stage_started)
    ledger_rows: list[dict[str, Any]] = []
    ledger_artifact_refs: list[dict[str, Any]] = []
    if _bool_arg(args.get("build_runtime_ledger"), default=False) and rows:
        build_runtime_ledger = getattr(interactive, "build_runtime_ledger_for_graph", None)
        if callable(build_runtime_ledger):
            stage_started = time.perf_counter()
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
            mark("build_runtime_ledger", stage_started)
    stage_started = time.perf_counter()
    candidate_counts = _candidate_counts_from_trace(trace, rows)
    result = {
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
        "registry_timing_ms": timing_ms,
        "artifact_refs": [
            *_artifact_refs_from_mapping(result.get("artifact_refs"), row_count=len(rows)),
            *ledger_artifact_refs,
        ],
        "source_gaps": _sec_search_source_gaps(query_contract, rows),
    }
    mark("assemble_result", stage_started)
    if cache_key and result["status"] in {"ok", "partial"}:
        stage_started = time.perf_counter()
        _SEC_SEARCH_RESULT_CACHE[cache_key] = copy.deepcopy(result)
        _trim_sec_search_result_cache()
        mark("result_cache_store", stage_started)
        result["mcp_result_cache"] = {
            "hit": False,
            "cache_key": cache_key,
            "cache_size": len(_SEC_SEARCH_RESULT_CACHE),
            "policy": "sec_search_result_cache_excludes_run_artifact_paths_v0_1",
        }
    result["registry_timing_ms"] = timing_ms
    result["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000))
    return result


def _invoke_milvus_semantic(args: dict[str, Any]) -> dict[str, Any]:
    vector_kinds = _list_arg(args.get("vector_kinds"))
    if not vector_kinds:
        vector_kinds = ["narrative_chunk", "table_chunk", "paraphrase_context"]
    db_path = str(args.get("milvus_db_path") or args.get("milvus_uri") or os.environ.get("MILVUS_DB_PATH") or os.environ.get("MILVUS_URI") or "").strip()
    collection_name = str(args.get("milvus_collection_name") or os.environ.get("MILVUS_COLLECTION_NAME") or "").strip()
    embedding_model = str(args.get("embedding_model") or os.environ.get("MILVUS_EMBEDDING_MODEL") or os.environ.get("BGE_EMBEDDING_MODEL") or "").strip()
    missing = []
    if not db_path:
        missing.append("milvus_db_path")
    if not collection_name:
        missing.append("milvus_collection_name")
    if not embedding_model:
        missing.append("embedding_model")
    if not bool(args.get("typed_filter_required", True)):
        missing.append("typed_filter_required")
    if missing:
        gap = _milvus_semantic_gap("milvus_semantic_config_missing", args, missing=missing, vector_kinds=vector_kinds, source_available=False)
        return _milvus_semantic_error(gap, collection_name=collection_name)

    try:
        from pymilvus import MilvusClient
    except Exception as exc:  # noqa: BLE001
        gap = _milvus_semantic_gap("pymilvus_unavailable", args, missing=[], vector_kinds=vector_kinds, source_available=False, error=str(exc))
        return _milvus_semantic_error(gap, collection_name=collection_name)

    started = datetime.now()
    client = _milvus_client(MilvusClient, db_path, collection_name)
    try:
        model = _milvus_embedding_model(embedding_model, str(args.get("embedding_device") or os.environ.get("MILVUS_EMBEDDING_DEVICE") or os.environ.get("BGE_DEVICE") or "auto"))
        query_probes = _milvus_query_probes(args)
        embeddings = model.encode(
            query_probes,
            batch_size=_bounded_int(args.get("embedding_batch_size") or os.environ.get("MILVUS_QUERY_EMBEDDING_BATCH_SIZE"), default=16, minimum=1, maximum=128),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        filter_expr = _milvus_semantic_filter_expr(args, vector_kinds)
        top_k = _bounded_int(args.get("milvus_top_k") or args.get("limit"), default=40, minimum=1, maximum=200)
        final_top_k = _bounded_int(args.get("final_top_k") or args.get("limit") or args.get("milvus_top_k"), default=min(top_k, 40), minimum=1, maximum=200)
        output_fields = [
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
            "vector_role",
            "semantic_scope",
            "intent_tags",
            "relationship_role",
            "object_type",
            "preview",
        ]
        results = client.search(
            collection_name=collection_name,
            data=[_embedding_to_float_list(embedding) for embedding in embeddings],
            anns_field="embedding",
            limit=top_k,
            filter=filter_expr,
            output_fields=output_fields,
        )
    except Exception as exc:  # noqa: BLE001
        gap = _milvus_semantic_gap("milvus_semantic_search_failed", args, missing=[], vector_kinds=vector_kinds, source_available=True, error=str(exc))
        return _milvus_semantic_error(gap, collection_name=collection_name)

    rows = _milvus_context_rows_from_results(results if results else [], args=args, vector_kinds=vector_kinds, query_probes=query_probes, top_k=final_top_k)
    vector_kind_counts = _count_by(rows, "vector_kind")
    gaps = []
    if not rows:
        gaps.append(_milvus_semantic_gap("milvus_semantic_no_hits_for_typed_filter", args, missing=[], vector_kinds=vector_kinds, source_available=True))
    return {
        "status": "ok" if rows else "partial",
        "context_rows": rows,
        "row_count": len(rows),
        "vector_kind_counts": vector_kind_counts,
        "collection_name": collection_name,
        "typed_filter_required": True,
        "semantic_route_role": "semantic_recall_supplement",
        "elapsed_ms": int((datetime.now() - started).total_seconds() * 1000),
        "filter_expr": _milvus_semantic_filter_expr(args, vector_kinds),
        "query_probes": query_probes,
        "query_probe_count": len(query_probes),
        "milvus_batch_search": {
            "enabled": len(query_probes) > 1,
            "per_probe_top_k": top_k,
            "final_top_k": final_top_k,
            "fusion_policy": "weighted_rrf_by_evidence_id_v0_1",
        },
        "artifact_refs": [
            {
                "artifact_id": "milvus_semantic_collection",
                "path": db_path,
                "digest": "",
                "row_count": len(rows),
                "metadata": {"collection_name": collection_name},
            }
        ],
        "source_gaps": gaps,
    }


def _milvus_embedding_model(model_ref: str, device: str) -> Any:
    resolved_device = _resolve_embedding_device(device)
    key = (model_ref, resolved_device)
    cached = _MILVUS_EMBEDDING_MODEL_CACHE.get(key)
    if cached is not None:
        return cached
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_ref, device=resolved_device)
    _MILVUS_EMBEDDING_MODEL_CACHE[key] = model
    return model


def _milvus_query_probes(args: dict[str, Any]) -> list[str]:
    base = str(args.get("query") or "").strip()
    probes = [base]
    probes.extend(str(item).strip() for item in _list_arg(args.get("query_probes") or args.get("semantic_probes")) if str(item).strip())
    if not any(probe for probe in probes):
        probes = [base]
    limit = _bounded_int(args.get("query_probe_limit") or os.environ.get("MILVUS_QUERY_PROBE_LIMIT"), default=8, minimum=1, maximum=16)
    return _dedupe_strings([probe for probe in probes if probe])[:limit]


def _embedding_to_float_list(embedding: Any) -> list[float]:
    if hasattr(embedding, "tolist"):
        return [float(item) for item in embedding.tolist()]
    return [float(item) for item in embedding]


def _resolve_embedding_device(device: str) -> str:
    requested = str(device or "").strip().lower()
    if requested and requested not in {"auto", "default"}:
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def _load_milvus_collection(client: Any, collection_name: str) -> None:
    load = getattr(client, "load_collection", None)
    if not callable(load):
        return
    try:
        load(collection_name=collection_name)
    except TypeError:
        load(collection_name)


def _milvus_client(client_cls: Any, db_path: str, collection_name: str) -> Any:
    key = (db_path, collection_name)
    cached = _MILVUS_CLIENT_CACHE.get(key)
    if cached is not None:
        return cached
    client = client_cls(uri=db_path)
    _load_milvus_collection(client, collection_name)
    _MILVUS_CLIENT_CACHE[key] = client
    return client


def _close_milvus_client(client: Any) -> None:
    for name in ("close", "disconnect"):
        method = getattr(client, name, None)
        if not callable(method):
            continue
        try:
            method()
        except Exception:
            pass
        return


def _milvus_semantic_filter_expr(args: dict[str, Any], vector_kinds: list[Any]) -> str:
    clauses = []
    tickers = [str(item).upper() for item in _list_arg(args.get("tickers")) if str(item).strip()]
    if tickers:
        clauses.append(_milvus_in_clause("ticker", tickers))
    years = [int(item) for item in _list_arg(args.get("years")) if str(item).isdigit()]
    if years:
        clauses.append("fiscal_year in [" + ", ".join(str(year) for year in years) + "]")
    forms = [_normalize_form_type(item) for item in _list_arg(args.get("filing_types")) if str(item).strip()]
    if forms:
        clauses.append(_milvus_in_clause("form_type", forms))
    source_tiers = [str(item) for item in _list_arg(args.get("source_tiers")) if str(item).strip()]
    if source_tiers:
        clauses.append(_milvus_in_clause("source_tier", source_tiers))
    kinds = [str(item) for item in vector_kinds if str(item).strip()]
    if kinds:
        clauses.append(_milvus_in_clause("vector_kind", kinds))
    return " and ".join(clause for clause in clauses if clause)


def _milvus_in_clause(field: str, values: list[str]) -> str:
    quoted = ", ".join(json.dumps(str(value), ensure_ascii=False) for value in values)
    return f"{field} in [{quoted}]"


def _milvus_context_rows(hits: list[Any], *, args: dict[str, Any], vector_kinds: list[Any]) -> list[dict[str, Any]]:
    by_evidence_id: dict[str, dict[str, Any]] = {}
    for raw_rank, hit in enumerate(hits, start=1):
        entity = dict(hit.get("entity") or {}) if isinstance(hit, dict) else {}
        evidence_id = str(entity.get("evidence_id") or "").strip()
        if not evidence_id:
            continue
        score = float((hit.get("distance") if isinstance(hit, dict) else 0.0) or 0.0)
        row = by_evidence_id.get(evidence_id)
        if row is None or raw_rank < int(row.get("raw_semantic_rank") or 999999):
            row = _milvus_context_row(entity, score=score, raw_rank=raw_rank, args=args, vector_kinds=vector_kinds)
            by_evidence_id[evidence_id] = row
        else:
            row.setdefault("matched_vector_ids", []).append(str(entity.get("vector_id") or ""))
        kind = str(entity.get("vector_kind") or "")
        if kind:
            row.setdefault("vector_kinds", [])
            if kind not in row["vector_kinds"]:
                row["vector_kinds"].append(kind)
    rows = sorted(by_evidence_id.values(), key=lambda item: int(item.get("raw_semantic_rank") or 999999))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def _milvus_context_rows_from_results(
    results: list[Any],
    *,
    args: dict[str, Any],
    vector_kinds: list[Any],
    query_probes: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    if len(results) <= 1:
        rows = _milvus_context_rows(results[0] if results else [], args=args, vector_kinds=vector_kinds)
        for row in rows:
            row["matched_query_indices"] = [0]
            row["matched_queries"] = query_probes[:1]
        return rows[:top_k]
    scores: dict[str, float] = {}
    by_evidence_id: dict[str, dict[str, Any]] = {}
    for query_index, hits in enumerate(results):
        query_weight = 1.0 if query_index == 0 else 0.85
        for raw_rank, hit in enumerate(hits or [], start=1):
            entity = dict(hit.get("entity") or {}) if isinstance(hit, dict) else {}
            evidence_id = str(entity.get("evidence_id") or "").strip()
            if not evidence_id:
                continue
            score = float((hit.get("distance") if isinstance(hit, dict) else 0.0) or 0.0)
            scores[evidence_id] = scores.get(evidence_id, 0.0) + query_weight * _milvus_semantic_hit_weight(entity) / (60.0 + raw_rank)
            row = by_evidence_id.get(evidence_id)
            if row is None or raw_rank < int(row.get("raw_semantic_rank") or 999999):
                row = _milvus_context_row(entity, score=score, raw_rank=raw_rank, args=args, vector_kinds=vector_kinds)
                by_evidence_id[evidence_id] = row
            row.setdefault("matched_query_indices", [])
            row["matched_query_indices"].append(query_index)
            row.setdefault("matched_queries", [])
            if 0 <= query_index < len(query_probes):
                row["matched_queries"].append(query_probes[query_index])
            kind = str(entity.get("vector_kind") or "")
            if kind:
                row.setdefault("vector_kinds", [])
                if kind not in row["vector_kinds"]:
                    row["vector_kinds"].append(kind)
            vector_id = str(entity.get("vector_id") or "")
            if vector_id:
                row.setdefault("matched_vector_ids", [])
                if vector_id not in row["matched_vector_ids"]:
                    row["matched_vector_ids"].append(vector_id)
    ranked_ids = [evidence_id for evidence_id, _score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]]
    rows = []
    for rank, evidence_id in enumerate(ranked_ids, start=1):
        row = by_evidence_id[evidence_id]
        row["rank"] = rank
        row["semantic_score"] = round(float(scores.get(evidence_id) or 0.0), 8)
        row["matched_query_indices"] = sorted({int(item) for item in row.get("matched_query_indices") or []})
        row["matched_queries"] = _dedupe_strings([str(item) for item in row.get("matched_queries") or [] if str(item).strip()])
        row["vector_kinds"] = _dedupe_strings([str(item) for item in row.get("vector_kinds") or [] if str(item).strip()])
        rows.append(row)
    return rows


def _milvus_semantic_hit_weight(entity: dict[str, Any]) -> float:
    weight = 1.0
    if str(entity.get("vector_kind") or "") in {"relationship_context", "paraphrase_context", "metric_row", "table_row"}:
        weight += 0.12
    if str(entity.get("vector_role") or "") in {"economic_linkage_context", "plain_language_context"}:
        weight += 0.08
    if str(entity.get("semantic_scope") or "") in {"relationship", "paraphrase"}:
        weight += 0.06
    return weight


def _milvus_context_row(entity: dict[str, Any], *, score: float, raw_rank: int, args: dict[str, Any], vector_kinds: list[Any]) -> dict[str, Any]:
    source_tier = str(entity.get("source_tier") or "primary_sec_filing")
    vector_kind = str(entity.get("vector_kind") or "")
    evidence_id = str(entity.get("evidence_id") or "")
    preview = str(entity.get("preview") or "")
    return {
        "evidence_ref": evidence_id,
        "evidence_id": evidence_id,
        "source_family": source_tier,
        "source_tier": source_tier,
        "retrieval_route": "milvus_semantic",
        "semantic_route_role": "semantic_recall_supplement",
        "ticker": str(entity.get("ticker") or "").upper(),
        "fiscal_year": int(entity.get("fiscal_year") or 0),
        "form_type": str(entity.get("form_type") or ""),
        "source_type": str(entity.get("form_type") or ""),
        "item_code": str(entity.get("item_code") or ""),
        "category_slug": str(entity.get("category_slug") or ""),
        "period_type": str(entity.get("period_type") or ""),
        "contains_table": bool(entity.get("contains_table")),
        "object_type": str(entity.get("object_type") or ""),
        "vector_kind": vector_kind,
        "vector_kinds": [vector_kind] if vector_kind else [str(item) for item in vector_kinds if str(item).strip()],
        "vector_role": str(entity.get("vector_role") or ""),
        "semantic_scope": str(entity.get("semantic_scope") or ""),
        "intent_tags": [part for part in str(entity.get("intent_tags") or "").split("|") if part],
        "relationship_role": str(entity.get("relationship_role") or ""),
        "summary": preview,
        "text": preview,
        "preview": preview,
        "semantic_score": score,
        "raw_semantic_rank": raw_rank,
        "matched_vector_ids": [str(entity.get("vector_id") or "")],
        "retrieval_query": str(args.get("query") or ""),
        "claim_scope_boundary": "semantic_recall_supplement_not_exact_value_authority",
    }


def _milvus_semantic_gap(
    reason_code: str,
    args: dict[str, Any],
    *,
    missing: list[str],
    vector_kinds: list[Any],
    source_available: bool,
    error: str = "",
) -> dict[str, Any]:
    return {
        "source_family": "primary_sec_filing",
        "retrieval_route": "milvus_semantic",
        "reason_code": reason_code,
        "reason": "Milvus typed semantic recall did not return bounded rows for the requested typed filter.",
        "missing": missing,
        "vector_kinds": [str(item) for item in vector_kinds if str(item).strip()],
        "tickers": [str(item).upper() for item in _list_arg(args.get("tickers")) if str(item).strip()],
        "years": [int(item) for item in _list_arg(args.get("years")) if str(item).isdigit()],
        "source_available": source_available,
        "error": error[:500],
    }


def _milvus_semantic_error(gap: dict[str, Any], *, collection_name: str) -> dict[str, Any]:
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


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = _list_arg(row.get(key))
        if not values and key == "vector_kind":
            values = _list_arg(row.get("vector_kinds"))
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


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
        user_query=str(args.get("user_query") or ""),
        relationship_graph_path=args.get("relationship_graph_path") or os.environ.get("RELATIONSHIP_GRAPH_PATH") or "",
        sector_depth_pack_path=args.get("sector_depth_pack_path") or os.environ.get("SECTOR_DEPTH_PACK_PATH") or "",
        expected_pack_ids=_list_arg(args.get("expected_pack_ids") or args.get("expected_relationship_pack_ids")),
        max_relationships=int(args.get("max_relationships") or 24),
        max_expanded_tickers=int(args.get("max_expanded_tickers") or 12),
        include_sector_depth=_bool_arg(args.get("include_sector_depth"), default=True),
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
        context_runner=_context_runner_arg(args.get("context_runner") or os.environ.get("CONTEXT_RUNNER") or os.environ.get("SEC_AGENT_CONTEXT_RUNNER") or "auto"),
        quiet=_bool_arg(args.get("quiet"), default=True),
    )


def _context_runner_arg(value: Any) -> str:
    text = str(value or "auto").strip().lower().replace("-", "_")
    if text in {"interactive", "resident", "mcp", "resident_worker"}:
        return "in_process"
    if text in {"auto", "in_process", "subprocess"}:
        return text
    return "auto"


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
        if requested_form_set and form not in requested_form_set:
            continue
        if requested_tier_set and tier not in requested_tier_set:
            continue
        route = explicit_route or _default_route_for_form(form)
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
    cache_key = _file_cache_token(path)
    cached = _SEC_MANIFEST_ROWS_CACHE.get(cache_key)
    if cached is not None:
        return cached
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
    _SEC_MANIFEST_ROWS_CACHE.clear()
    _SEC_MANIFEST_ROWS_CACHE[cache_key] = rows
    return rows


def _file_cache_token(path: Path) -> tuple[Any, ...]:
    if not path.exists() or not path.is_file():
        return (str(path.resolve()), False, 0, 0)
    stat = path.stat()
    return (str(path.resolve()), True, stat.st_size, stat.st_mtime_ns)


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


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


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


def _sec_search_result_cache_enabled(args: dict[str, Any]) -> bool:
    if str(args.get("disable_result_cache") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if "cache_result" in args:
        return _bool_arg(args.get("cache_result"), default=True)
    if os.environ.get("SEC_AGENT_MCP_SEC_SEARCH_RESULT_CACHE") is not None:
        return _env_bool("SEC_AGENT_MCP_SEC_SEARCH_RESULT_CACHE")
    return True


def _sec_search_result_cache_key(args: dict[str, Any]) -> str:
    stable_args = _sec_search_cache_relevant_args(args)
    env_fingerprint = {
        name: os.environ.get(name, "")
        for name in (
            "MANIFEST_PATH",
            "BM25_INDEX_DIR",
            "OBJECT_BM25_INDEX_DIR",
            "BGE_MODEL",
            "BGE_DEVICE",
            "LEDGER_STORE_PATH",
            "SEC_AGENT_CONTEXT_RUNNER",
            "CONTEXT_RUNNER",
        )
    }
    payload = {"args": stable_args, "env": env_fingerprint}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]


def _sec_search_cache_relevant_args(args: dict[str, Any]) -> dict[str, Any]:
    relevant_keys = {
        "query",
        "tickers",
        "years",
        "filing_types",
        "source_tiers",
        "metric_families",
        "period_roles",
        "retrieval_route",
        "candidate_budget",
        "rerank_budget",
        "bge_first",
        "bge_device",
        "build_runtime_ledger",
        "evidence_top_k",
        "object_top_k",
        "reranker_candidate_limit",
        "reranker_top_k",
        "reranker_batch_size",
        "reranker_max_length",
        "reranker_doc_max_chars",
        "context_runner",
        "limit",
        "manifest_path",
        "bm25_index_dir",
        "object_bm25_index_dir",
        "bge_model",
        "ledger_store_path",
    }
    stable = {
        key: _cacheable_value(args[key])
        for key in sorted(relevant_keys)
        if key in args
    }
    if isinstance(args.get("retrieval_plan"), dict):
        stable["retrieval_plan"] = _stable_sec_search_retrieval_plan(args["retrieval_plan"])
    return stable


def _stable_sec_search_retrieval_plan(plan: dict[str, Any]) -> dict[str, Any]:
    stable_routes = []
    for route in plan.get("routes") or []:
        if not isinstance(route, dict):
            continue
        route_keys = {
            "retrieval_route",
            "tickers",
            "years",
            "filing_types",
            "source_tiers",
            "metric_families",
            "period_roles",
            "candidate_budget",
            "rerank_budget",
        }
        stable_route = {
            key: _cacheable_value(route[key])
            for key in sorted(route_keys)
            if key in route
        }
        coverage = route.get("coverage_requirements")
        if isinstance(coverage, dict):
            stable_route["coverage_requirements"] = {
                key: _cacheable_value(coverage[key])
                for key in sorted(
                    {
                        "tickers",
                        "years",
                        "filing_types",
                        "source_tiers",
                        "metric_families",
                        "period_roles",
                    }
                )
                if key in coverage
            }
        stable_routes.append(stable_route)
    return {"routes": stable_routes}


def _cacheable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _cacheable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_cacheable_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_cacheable_value(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    return value


def _trim_sec_search_result_cache() -> None:
    max_entries = _bounded_int(os.environ.get("SEC_AGENT_MCP_SEC_SEARCH_RESULT_CACHE_SIZE"), default=16, minimum=0, maximum=256)
    if max_entries <= 0:
        _SEC_SEARCH_RESULT_CACHE.clear()
        return
    while len(_SEC_SEARCH_RESULT_CACHE) > max_entries:
        oldest_key = next(iter(_SEC_SEARCH_RESULT_CACHE))
        _SEC_SEARCH_RESULT_CACHE.pop(oldest_key, None)


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
    "sec_milvus_semantic_search": _invoke_milvus_semantic,
    "sec_query_exact_value_ledger": _invoke_ledger,
    "market_get_snapshot": _invoke_market,
    "industry_get_snapshot": _invoke_industry,
    "relationship_graph_lookup": _invoke_relationship_graph,
    "run_inspect_artifacts": _invoke_run_inspect,
    "run_read_artifact": _invoke_run_read,
}
