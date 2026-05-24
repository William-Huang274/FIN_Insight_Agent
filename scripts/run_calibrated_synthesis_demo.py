from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import vllm_hardware_profiles  # noqa: E402


SYNTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer_zh",
        "conclusion_quality",
        "thesis_zh",
        "decision_drivers",
        "secondary_context",
        "limiting_caveats",
        "facet_findings",
        "numeric_claims",
        "missing_or_uncertain_zh",
        "evidence_use_notes_zh",
    ],
    "properties": {
        "answer_zh": {"type": "string", "maxLength": 1100},
        "conclusion_quality": {"type": "string", "enum": ["good", "mixed", "weak"]},
        "thesis_zh": {"type": "string", "maxLength": 240},
        "decision_drivers": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rank", "driver_zh", "decision_impact_zh", "evidence_strength", "cited_object_ids"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                    "driver_zh": {"type": "string", "maxLength": 220},
                    "decision_impact_zh": {"type": "string", "maxLength": 220},
                    "evidence_strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                    "cited_object_ids": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "secondary_context": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["context_zh", "why_secondary_zh", "cited_object_ids"],
                "properties": {
                    "context_zh": {"type": "string", "maxLength": 220},
                    "why_secondary_zh": {"type": "string", "maxLength": 180},
                    "cited_object_ids": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "limiting_caveats": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["caveat_type", "caveat_zh", "impact_on_thesis_zh", "cited_object_ids"],
                "properties": {
                    "caveat_type": {
                        "type": "string",
                        "enum": ["missing_evidence", "comparability", "metric_role", "counter_evidence", "scope_limit"],
                    },
                    "caveat_zh": {"type": "string", "maxLength": 240},
                    "impact_on_thesis_zh": {"type": "string", "maxLength": 220},
                    "cited_object_ids": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "facet_findings": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["facet_zh", "coverage_status", "importance", "takeaway_zh", "cited_object_ids"],
                "properties": {
                    "facet_zh": {"type": "string", "maxLength": 80},
                    "coverage_status": {
                        "type": "string",
                        "enum": ["covered", "partial", "missing", "conflicted"],
                    },
                    "importance": {"type": "string", "enum": ["primary", "supporting", "caveat_only"]},
                    "takeaway_zh": {"type": "string", "maxLength": 260},
                    "cited_object_ids": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "numeric_claims": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "claim_location",
                    "metric_id",
                    "metric_label_zh",
                    "raw_value_text",
                    "unit",
                    "metric_role",
                    "role_check_zh",
                    "cited_object_ids",
                ],
                "properties": {
                    "claim_location": {
                        "type": "string",
                        "enum": ["answer", "thesis", "decision_driver", "secondary_context", "limiting_caveat", "facet_finding"],
                    },
                    "metric_id": {"type": "string", "maxLength": 180},
                    "metric_label_zh": {"type": "string", "maxLength": 100},
                    "raw_value_text": {"type": "string", "maxLength": 120},
                    "display_value_zh": {"type": "string", "maxLength": 120},
                    "unit": {"type": "string", "maxLength": 80},
                    "metric_role": {
                        "type": "string",
                        "enum": [
                            "total_value",
                            "period_change_amount",
                            "percentage_rate",
                            "ratio",
                            "derived",
                            "qualitative_context",
                            "unknown",
                        ],
                    },
                    "role_check_zh": {"type": "string", "maxLength": 220},
                    "cited_object_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "key_findings": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim_zh", "cited_object_ids"],
                "properties": {
                    "claim_zh": {"type": "string", "maxLength": 220},
                    "cited_object_ids": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "comparability_caveats_zh": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string", "maxLength": 220},
        },
        "missing_evidence_by_facet": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["facet_zh", "missing_or_uncertain_zh"],
                "properties": {
                    "facet_zh": {"type": "string", "maxLength": 80},
                    "missing_or_uncertain_zh": {"type": "string", "maxLength": 240},
                },
            },
        },
        "missing_or_uncertain_zh": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 220},
        },
        "evidence_use_notes_zh": {"type": "string", "maxLength": 420},
    },
}

METRIC_TABLE_SYNTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer_zh",
        "conclusion_quality",
        "cell_table",
        "key_findings",
        "missing_or_uncertain_zh",
        "evidence_use_notes_zh",
    ],
    "properties": {
        "answer_zh": {"type": "string", "maxLength": 700},
        "conclusion_quality": {"type": "string", "enum": ["good", "mixed", "weak"]},
        "cell_table": {
            "type": "object",
            "additionalProperties": False,
            "required": ["unit_policy", "cells"],
            "properties": {
                "unit_policy": {"type": "string", "maxLength": 160},
                "cells": {
                    "type": "array",
                    "maxItems": 120,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "ticker",
                            "fiscal_year",
                            "metric",
                            "value",
                            "unit",
                            "status",
                            "citation_object_id",
                            "note",
                        ],
                        "properties": {
                            "ticker": {"type": "string", "maxLength": 12},
                            "fiscal_year": {"type": "integer", "minimum": 1900, "maximum": 2100},
                            "metric": {"type": "string", "maxLength": 100},
                            "value": {"type": ["number", "null"]},
                            "unit": {"type": ["string", "null"], "maxLength": 60},
                            "status": {"type": "string", "enum": ["reported", "missing", "unsupported"]},
                            "citation_object_id": {"type": ["string", "null"], "maxLength": 180},
                            "citation_object_ids": {
                                "type": "array",
                                "maxItems": 4,
                                "items": {"type": "string", "maxLength": 180},
                            },
                            "derivation": {"type": ["string", "null"], "maxLength": 180},
                            "note": {"type": "string", "maxLength": 180},
                        },
                    },
                },
            },
        },
        "key_findings": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim_zh", "cited_object_ids"],
                "properties": {
                    "claim_zh": {"type": "string", "maxLength": 220},
                    "cited_object_ids": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "missing_or_uncertain_zh": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 180},
        },
        "evidence_use_notes_zh": {"type": "string", "maxLength": 320},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run final Chinese synthesis over the calibrated aspect evidence pool."
    )
    parser.add_argument(
        "--grouped-pool-path",
        default="reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument(
        "--facet-memory-path",
        default="",
        help="Optional facet-level evidence memory JSON. When set, final synthesis packs memory instead of raw aspect evidence.",
    )
    parser.add_argument(
        "--driver-pack-path",
        default="",
        help="Optional normalized Decision Driver Pack JSON. When set, synthesis uses Driver Pack plus Exact-Value Ledger instead of raw evidence pool.",
    )
    parser.add_argument(
        "--driver-pack-candidate-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json",
    )
    parser.add_argument(
        "--exact-value-ledger-path",
        default="reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json",
    )
    parser.add_argument(
        "--pool-report-path",
        default="reports/metrics/sec_tech_10k_calibrated_evidence_pool_report.json",
    )
    parser.add_argument(
        "--human-gold-eval-path",
        default="reports/metrics/sec_tech_10k_calibrated_evidence_pool_human_gold_eval.json",
    )
    parser.add_argument(
        "--reasoning-eval-path",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl",
    )
    parser.add_argument(
        "--model-path",
        default="data/models_private/modelscope/Qwen/Qwen3.5-9B",
    )
    parser.add_argument(
        "--output",
        default="reports/demo/qwen9b_calibrated_synthesis_demo.json",
    )
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-model-len", type=int, default=8192)
    parser.add_argument("--synthesis-max-tokens", type=int, default=900)
    parser.add_argument("--context-safety-margin", type=int, default=1400)
    parser.add_argument("--citation-chars", type=int, default=900)
    parser.add_argument("--background-chars", type=int, default=450)
    parser.add_argument("--max-background-per-aspect", type=int, default=1)
    parser.add_argument(
        "--memory-pack-profile",
        choices=["auto", "full"],
        default="auto",
        help="For facet memory input, use auto context compaction or pack all available memory evidence.",
    )
    parser.add_argument(
        "--raw-pack-profile",
        choices=["auto", "citation-only-all", "full-all"],
        default="auto",
        help="For raw grouped pool input, use auto compaction, all citation evidence only, or all citation/background evidence.",
    )
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--quantization", default="none")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.86)
    parser.add_argument("--cpu-offload-gb", type=float, default=0.0)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--language-model-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-mm-profiling", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--structured-json", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--disable-vllm", action="store_true")
    vllm_hardware_profiles.add_hardware_profile_arg(parser)
    args = parser.parse_args()
    vllm_hardware_profiles.apply_hardware_profile(args, workload="long_context_synthesis")
    return args


def main() -> None:
    args = parse_args()
    started = time.time()
    timings: dict[str, float] = {}

    t_load = time.time()
    if args.driver_pack_path:
        grouped = _read_json(REPO_ROOT / args.driver_pack_path)
        candidate_payload = _read_json(REPO_ROOT / args.driver_pack_candidate_path)
        ledger_payload = _read_json(REPO_ROOT / args.exact_value_ledger_path)
        candidate_by_query = {str(item.get("query_id")): item for item in candidate_payload.get("queries") or []}
        ledger_by_metric_id = {str(row.get("metric_id")): row for row in ledger_payload.get("rows") or []}
        ledger_by_object_id: dict[str, list[dict[str, Any]]] = {}
        for row in ledger_payload.get("rows") or []:
            ledger_by_object_id.setdefault(str(row.get("object_id")), []).append(row)
        queries = _select_queries(grouped.get("results", []), query_ids=set(args.query_id), limit=args.limit)
    else:
        grouped = _read_json(REPO_ROOT / args.facet_memory_path) if args.facet_memory_path else _read_json(REPO_ROOT / args.grouped_pool_path)
        candidate_by_query = {}
        ledger_by_metric_id = {}
        ledger_by_object_id = {}
        queries = _select_queries(grouped.get("queries", []), query_ids=set(args.query_id), limit=args.limit)
    pool_report = _read_json_if_exists(REPO_ROOT / args.pool_report_path)
    human_gold_eval = _read_json_if_exists(REPO_ROOT / args.human_gold_eval_path)
    reference_records = _read_jsonl_map(REPO_ROOT / args.reasoning_eval_path)
    output_path = REPO_ROOT / args.output
    timings["load_inputs_sec"] = round(time.time() - t_load, 4)

    llm = None
    tokenizer = None
    if not args.disable_vllm:
        t_model = time.time()
        llm, tokenizer = _load_vllm(args)
        timings["load_model_sec"] = round(time.time() - t_model, 4)

    results = []
    for query in queries:
        query_started = time.time()
        try:
            if args.driver_pack_path:
                package, package_metrics = _build_driver_pack_query_package(
                    query,
                    candidate_by_query.get(str(query.get("query_id")), {}),
                    ledger_by_metric_id,
                    ledger_by_object_id,
                    tokenizer=tokenizer,
                    max_model_len=args.max_model_len,
                    synthesis_max_tokens=args.synthesis_max_tokens,
                    context_safety_margin=args.context_safety_margin,
                )
            else:
                package, package_metrics = _build_query_package(
                    query,
                    reference_records.get(str(query.get("query_id")), {}),
                    tokenizer=tokenizer,
                    max_model_len=args.max_model_len,
                    synthesis_max_tokens=args.synthesis_max_tokens,
                    context_safety_margin=args.context_safety_margin,
                    citation_chars=args.citation_chars,
                    background_chars=args.background_chars,
                    max_background_per_aspect=args.max_background_per_aspect,
                    memory_pack_profile=args.memory_pack_profile,
                    raw_pack_profile=args.raw_pack_profile,
                )
            prompt = _make_prompt(package, tokenizer)
            prompt_tokens = _prompt_token_count(tokenizer, prompt)
            synthesis, raw_output, parse_status = _run_synthesis(
                llm=llm,
                prompt=prompt,
                max_tokens=args.synthesis_max_tokens,
                structured_schema=_schema_for_package(package) if args.structured_json else None,
            )
            if args.driver_pack_path:
                synthesis = _repair_metric_id_citations(synthesis, package)
            output_metrics = _evaluate_output_use(package_metrics, synthesis)
        except Exception as exc:
            prompt_tokens = None
            package_metrics = {
                "facet_count": len(query.get("facets", [])),
                "aspect_count": sum(len(facet.get("aspects", [])) for facet in query.get("facets", [])),
                "citation_evidence_count": 0,
                "background_evidence_count": 0,
                "missing_aspect_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
            synthesis = {
                "answer_zh": "",
                "conclusion_quality": "weak",
                "thesis_zh": "生成失败，无法形成主判断。",
                "decision_drivers": [],
                "secondary_context": [],
                "limiting_caveats": [],
                "key_findings": [],
                "facet_findings": [],
                "numeric_claims": [],
                "comparability_caveats_zh": [],
                "missing_evidence_by_facet": [],
                "missing_or_uncertain_zh": [f"synthesis_failed: {type(exc).__name__}: {exc}"],
                "evidence_use_notes_zh": "query failed before or during generation",
            }
            raw_output = ""
            parse_status = "error"
            output_metrics = _evaluate_output_use(package_metrics, synthesis)
        results.append(
            {
                "query_id": query.get("query_id"),
                "mode": query.get("mode"),
                "ticker": query.get("ticker"),
                "fiscal_year": query.get("fiscal_year"),
                "query": query.get("query") or (package.get("query_contract") or {}).get("query"),
                "package_metrics": package_metrics | {"prompt_tokens": prompt_tokens, "prompt_chars": len(prompt)},
                "parse_status": parse_status,
                "synthesis": synthesis,
                "raw_output": raw_output,
                "output_metrics": output_metrics,
                "elapsed_sec": round(time.time() - query_started, 4),
            }
        )
        _write_report(
            output_path,
            args=args,
            pool_report=pool_report,
            human_gold_eval=human_gold_eval,
            results=results,
            timings=timings,
            started=started,
            partial=True,
        )
        print(
            json.dumps(
                {
                    "query_id": query.get("query_id"),
                    "parse_status": parse_status,
                    "elapsed_sec": results[-1]["elapsed_sec"],
                    "quality": synthesis.get("conclusion_quality"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    _write_report(
        output_path,
        args=args,
        pool_report=pool_report,
        human_gold_eval=human_gold_eval,
        results=results,
        timings=timings,
        started=started,
        partial=False,
    )
    print(json.dumps({"output": str(output_path), "queries": len(results)}, ensure_ascii=False), flush=True)


def _write_report(
    output_path: Path,
    *,
    args: argparse.Namespace,
    pool_report: dict[str, Any],
    human_gold_eval: dict[str, Any],
    results: list[dict[str, Any]],
    timings: dict[str, float],
    started: float,
    partial: bool,
) -> None:
    report = {
        "schema_version": "calibrated_synthesis_demo_v0.1",
        "partial": partial,
        "run_profile": {
            "model_path": args.model_path,
            "hardware_profile": getattr(args, "hardware_profile_metadata", {}),
            "resident_model_enabled": not args.disable_vllm,
            "max_model_len": args.max_model_len,
            "synthesis_max_tokens": args.synthesis_max_tokens,
            "context_safety_margin": args.context_safety_margin,
            "citation_chars": args.citation_chars,
            "background_chars": args.background_chars,
            "max_background_per_aspect": args.max_background_per_aspect,
            "memory_pack_profile": args.memory_pack_profile,
            "raw_pack_profile": args.raw_pack_profile,
            "facet_memory_path": args.facet_memory_path or None,
            "driver_pack_path": args.driver_pack_path or None,
            "driver_pack_candidate_path": args.driver_pack_candidate_path if args.driver_pack_path else None,
            "exact_value_ledger_path": args.exact_value_ledger_path if args.driver_pack_path else None,
            "uses_facet_memory": bool(args.facet_memory_path),
            "uses_driver_pack": bool(args.driver_pack_path),
            "structured_json": args.structured_json,
            "dtype": args.dtype,
            "quantization": args.quantization,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "cpu_offload_gb": args.cpu_offload_gb,
            "max_num_seqs": args.max_num_seqs,
            "language_model_only": args.language_model_only,
            "skip_mm_profiling": args.skip_mm_profiling,
        },
        "input_pool_report": pool_report,
        "human_gold_eval": human_gold_eval,
        "summary": _summarize(results, pool_report, human_gold_eval),
        "timings": timings | {"total_sec": round(time.time() - started, 4)},
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_queries(queries: list[dict[str, Any]], *, query_ids: set[str], limit: int) -> list[dict[str, Any]]:
    selected = [query for query in queries if not query_ids or str(query.get("query_id")) in query_ids]
    if limit > 0:
        selected = selected[:limit]
    return selected


def _build_driver_pack_query_package(
    result: dict[str, Any],
    candidate_query: dict[str, Any],
    ledger_by_metric_id: dict[str, dict[str, Any]],
    ledger_by_object_id: dict[str, list[dict[str, Any]]],
    *,
    tokenizer,
    max_model_len: int,
    synthesis_max_tokens: int,
    context_safety_margin: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pack = result.get("driver_pack") or {}
    contract_index, _metric_index = _driver_candidate_indexes(candidate_query)
    query_contract = candidate_query.get("query_contract") or {}
    input_citation_ids: set[str] = set()
    input_metric_ids: set[str] = set()
    package_drivers = []

    for driver in pack.get("decision_drivers") or []:
        if not isinstance(driver, dict):
            continue
        evidence = _contracts_for_ids(driver.get("supporting_contract_ids") or [], contract_index)
        metrics = _ledger_rows_for_ids(driver.get("supporting_metric_ids") or [], ledger_by_metric_id)
        metrics = _merge_ledger_rows(
            metrics,
            _ledger_rows_for_evidence(
                evidence,
                ledger_by_object_id,
                query_id=str(result.get("query_id") or pack.get("query_id") or ""),
                allowed_families={str(item) for item in driver.get("metric_families") or []},
                limit=12,
            ),
            limit=14,
        )
        input_citation_ids.update(str(item.get("object_id")) for item in evidence if item.get("object_id"))
        input_citation_ids.update(str(item.get("object_id")) for item in metrics if item.get("object_id"))
        input_metric_ids.update(str(item.get("metric_id")) for item in metrics if item.get("metric_id"))
        package_drivers.append(
            {
                "driver_id": driver.get("driver_id"),
                "rank": driver.get("rank"),
                "driver_claim_zh": driver.get("driver_claim_zh"),
                "why_it_matters_zh": driver.get("why_it_matters_zh"),
                "conclusion_strength": driver.get("conclusion_strength"),
                "global_claim_allowed": driver.get("global_claim_allowed"),
                "covered_companies": driver.get("covered_companies") or [],
                "covered_years": driver.get("covered_years") or [],
                "covered_facets": driver.get("covered_facets") or [],
                "metric_families": driver.get("metric_families") or [],
                "counter_evidence_or_caveat_zh": driver.get("counter_evidence_or_caveat_zh"),
                "supporting_evidence": evidence,
                "authorized_ledger_metrics": metrics,
            }
        )

    secondary_context = []
    for item in pack.get("secondary_context") or []:
        if not isinstance(item, dict):
            continue
        evidence = _contracts_for_ids(item.get("supporting_contract_ids") or [], contract_index)
        input_citation_ids.update(str(contract.get("object_id")) for contract in evidence if contract.get("object_id"))
        secondary_context.append(
            {
                "context_zh": item.get("context_zh"),
                "why_secondary_zh": item.get("why_secondary_zh"),
                "supporting_evidence": evidence,
            }
        )

    limiting_caveats = []
    for item in pack.get("limiting_caveats") or []:
        if not isinstance(item, dict):
            continue
        evidence = _contracts_for_ids(item.get("supporting_contract_ids") or [], contract_index)
        input_citation_ids.update(str(contract.get("object_id")) for contract in evidence if contract.get("object_id"))
        limiting_caveats.append(
            {
                "caveat_zh": item.get("caveat_zh"),
                "affected_driver_ids": item.get("affected_driver_ids") or [],
                "downgrade_effect_zh": item.get("downgrade_effect_zh"),
                "supporting_evidence": evidence,
            }
        )

    package = {
        "package_type": "driver_pack",
        "query_id": result.get("query_id") or pack.get("query_id"),
        "mode": result.get("mode") or query_contract.get("query_type"),
        "query": query_contract.get("query"),
        "query_contract": query_contract,
        "driver_pack_policy": {
            "source": "normalized Decision Driver Evidence Pack",
            "raw_planner_parse_status": result.get("parse_status"),
            "normalization_status": result.get("normalization_status"),
            "thesis_candidate_zh": pack.get("thesis_candidate_zh"),
            "conclusion_strength": pack.get("conclusion_strength"),
            "numeric_rule": (
                "Exact numeric values may only be copied from authorized_ledger_metrics. "
                "Every exact numeric value in prose must have a numeric_claim with metric_id and display_value_zh copied exactly."
            ),
            "citation_rule": "Use object_id from supporting_evidence or authorized_ledger_metrics only.",
        },
        "decision_drivers": package_drivers,
        "secondary_context": secondary_context,
        "limiting_caveats": limiting_caveats,
        "missing_primary_facets": pack.get("missing_primary_facets") or [],
        "output_contract": "driver_pack_ledger_synthesis_v0.1",
        "answer_policy": _answer_policy({"scoring_profile": "complex_insight_driver_pack"}),
    }
    prompt = _make_prompt(package, tokenizer)
    prompt_tokens = _prompt_token_count(tokenizer, prompt)
    max_input_tokens = max(512, max_model_len - synthesis_max_tokens - context_safety_margin)
    package_metrics = {
        "facet_count": len(candidate_query.get("candidate_facets") or []),
        "aspect_count": 0,
        "included_aspect_count": 0,
        "omitted_aspect_count": 0,
        "citation_evidence_count": len(input_citation_ids),
        "background_evidence_count": 0,
        "missing_aspect_count": len(pack.get("missing_primary_facets") or []),
        "input_citation_object_ids": sorted(input_citation_ids),
        "input_background_object_ids": [],
        "input_authorized_metric_ids": sorted(input_metric_ids),
        "authorized_ledger_metric_count": len(input_metric_ids),
        "driver_count": len(package_drivers),
        "prompt_tokens": prompt_tokens,
        "prompt_chars": len(prompt),
        "context_safety_margin": context_safety_margin,
        "max_input_tokens": max_input_tokens,
        "within_context_budget": prompt_tokens is None or prompt_tokens <= max_input_tokens,
        "budget_fit_strategy": "driver_pack_ledger",
        "raw_driver_pack_parse_status": result.get("parse_status"),
        "normalization_status": result.get("normalization_status"),
    }
    return package, package_metrics


def _driver_candidate_indexes(candidate_query: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    contract_index: dict[str, dict[str, Any]] = {}
    metric_index: dict[str, dict[str, Any]] = {}
    for facet in candidate_query.get("candidate_facets") or []:
        facet_id = str(facet.get("facet_id") or "")
        for contract in facet.get("candidate_contracts") or []:
            item = dict(contract)
            item["facet_id"] = facet_id
            contract_index[str(item.get("contract_id"))] = item
        for metric in facet.get("candidate_metrics") or []:
            item = dict(metric)
            item.setdefault("facet_ids", [facet_id])
            metric_index[str(item.get("metric_id"))] = item
    return contract_index, metric_index


def _contracts_for_ids(contract_ids: list[Any], contract_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for contract_id in contract_ids:
        item = contract_index.get(str(contract_id))
        if not item:
            continue
        object_id = str(item.get("object_id") or "")
        key = str(item.get("contract_id") or object_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "object_id": item.get("object_id"),
                "object_type": item.get("object_type"),
                "ticker": item.get("ticker"),
                "fiscal_year": item.get("fiscal_year"),
                "facet_id": item.get("facet_id"),
                "metric_families": item.get("metric_families") or [],
                "allowed_claim_roles": item.get("allowed_claim_roles") or [],
                "disallowed_claim_roles": item.get("disallowed_claim_roles") or [],
                "source_text_preview": _trim(str(item.get("source_text_preview") or ""), 520),
            }
        )
    return rows


def _ledger_rows_for_ids(metric_ids: list[Any], ledger_by_metric_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for metric_id in metric_ids:
        row = ledger_by_metric_id.get(str(metric_id))
        if not row:
            continue
        metric_key = str(row.get("metric_id"))
        if metric_key in seen:
            continue
        seen.add(metric_key)
        rows.append(
            {
                "metric_id": row.get("metric_id"),
                "object_id": row.get("object_id"),
                "ticker": row.get("ticker"),
                "fiscal_year": row.get("fiscal_year"),
                "period_year": row.get("period_year"),
                "metric_family": row.get("metric_family"),
                "metric_role": row.get("metric_role"),
                "metric_label": row.get("metric_label"),
                "raw_value_text": row.get("raw_value_text"),
                "unit": row.get("unit"),
                "display_value_zh": row.get("display_value_zh"),
                "allowed_claim_roles": row.get("allowed_claim_roles") or [],
                "disallowed_claim_roles": row.get("disallowed_claim_roles") or [],
                "narrative_guard_zh": row.get("narrative_guard_zh"),
            }
        )
    return rows


def _ledger_rows_for_evidence(
    evidence: list[dict[str, Any]],
    ledger_by_object_id: dict[str, list[dict[str, Any]]],
    *,
    query_id: str,
    allowed_families: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows = []
    for item in evidence:
        for row in ledger_by_object_id.get(str(item.get("object_id")), []):
            if query_id and str(row.get("query_id")) != query_id:
                continue
            if allowed_families and str(row.get("metric_family")) not in allowed_families:
                continue
            rows.append(_compact_ledger_row(row))
            if len(rows) >= limit:
                return rows
    return rows


def _merge_ledger_rows(first: list[dict[str, Any]], second: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    merged = []
    seen: set[str] = set()
    for row in first + second:
        metric_id = str(row.get("metric_id") or "")
        if not metric_id or metric_id in seen:
            continue
        seen.add(metric_id)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged


def _compact_ledger_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": row.get("metric_id"),
        "object_id": row.get("object_id"),
        "ticker": row.get("ticker"),
        "fiscal_year": row.get("fiscal_year"),
        "period_year": row.get("period_year"),
        "metric_family": row.get("metric_family"),
        "metric_role": row.get("metric_role"),
        "metric_label": row.get("metric_label"),
        "raw_value_text": row.get("raw_value_text"),
        "unit": row.get("unit"),
        "display_value_zh": row.get("display_value_zh"),
        "allowed_claim_roles": row.get("allowed_claim_roles") or [],
        "disallowed_claim_roles": row.get("disallowed_claim_roles") or [],
        "narrative_guard_zh": row.get("narrative_guard_zh"),
    }


def _build_query_package(
    query: dict[str, Any],
    reference_record: dict[str, Any],
    *,
    tokenizer,
    max_model_len: int,
    synthesis_max_tokens: int,
    context_safety_margin: int,
    citation_chars: int,
    background_chars: int,
    max_background_per_aspect: int,
    memory_pack_profile: str = "auto",
    raw_pack_profile: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if query.get("memory_type") == "facet_evidence_memory":
        return _build_memory_query_package(
            query,
            tokenizer=tokenizer,
            max_model_len=max_model_len,
            synthesis_max_tokens=synthesis_max_tokens,
            context_safety_margin=context_safety_margin,
            pack_profile=memory_pack_profile,
        )
    if raw_pack_profile != "auto":
        citation_limit = 1_000_000
        background_limit = 0 if raw_pack_profile == "citation-only-all" else 1_000_000
        selected_background_chars = 0 if raw_pack_profile == "citation-only-all" else background_chars
        package, metrics = _compact_query(
            query,
            reference_record,
            citation_chars=citation_chars,
            background_chars=selected_background_chars,
            max_background_per_aspect=background_limit,
            max_citations_per_aspect=citation_limit,
            max_aspects_per_facet=None,
        )
        prompt = _make_prompt(package, tokenizer)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        max_input_tokens = max(512, max_model_len - synthesis_max_tokens - context_safety_margin)
        metrics["prompt_tokens"] = prompt_tokens
        metrics["prompt_chars"] = len(prompt)
        metrics["selected_citation_chars"] = citation_chars
        metrics["selected_citations_per_aspect"] = citation_limit
        metrics["selected_background_chars"] = selected_background_chars
        metrics["selected_background_limit"] = background_limit
        metrics["context_safety_margin"] = context_safety_margin
        metrics["max_input_tokens"] = max_input_tokens
        metrics["within_context_budget"] = prompt_tokens is None or prompt_tokens <= max_input_tokens
        metrics["budget_fit_strategy"] = f"raw_{raw_pack_profile}"
        return package, metrics
    budgets = _budget_candidates(citation_chars, background_chars, max_background_per_aspect)
    max_input_tokens = max(512, max_model_len - synthesis_max_tokens - context_safety_margin)
    last_package: dict[str, Any] | None = None
    last_metrics: dict[str, Any] | None = None
    for citation_budget, background_budget, background_limit, citation_limit in budgets:
        package, metrics = _compact_query(
            query,
            reference_record,
            citation_chars=citation_budget,
            background_chars=background_budget,
            max_background_per_aspect=background_limit,
            max_citations_per_aspect=citation_limit,
            max_aspects_per_facet=None,
        )
        prompt = _make_prompt(package, tokenizer)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        metrics["prompt_tokens"] = prompt_tokens
        metrics["prompt_chars"] = len(prompt)
        metrics["selected_citation_chars"] = citation_budget
        metrics["selected_citations_per_aspect"] = citation_limit
        metrics["selected_background_chars"] = background_budget
        metrics["selected_background_limit"] = background_limit
        metrics["context_safety_margin"] = context_safety_margin
        metrics["max_input_tokens"] = max_input_tokens
        metrics["within_context_budget"] = prompt_tokens is None or prompt_tokens <= max_input_tokens
        metrics["budget_fit_strategy"] = "text_compaction"
        last_package, last_metrics = package, metrics
        if metrics["within_context_budget"]:
            return package, metrics
    for max_aspects_per_facet in (12, 8, 5, 3, 2, 1):
        package, metrics = _compact_query(
            query,
            reference_record,
            citation_chars=40,
            background_chars=0,
            max_background_per_aspect=0,
            max_citations_per_aspect=1,
            max_aspects_per_facet=max_aspects_per_facet,
        )
        prompt = _make_prompt(package, tokenizer)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        metrics["prompt_tokens"] = prompt_tokens
        metrics["prompt_chars"] = len(prompt)
        metrics["selected_citation_chars"] = 40
        metrics["selected_citations_per_aspect"] = 1
        metrics["selected_background_chars"] = 0
        metrics["selected_background_limit"] = 0
        metrics["selected_max_aspects_per_facet"] = max_aspects_per_facet
        metrics["context_safety_margin"] = context_safety_margin
        metrics["max_input_tokens"] = max_input_tokens
        metrics["within_context_budget"] = prompt_tokens is None or prompt_tokens <= max_input_tokens
        metrics["budget_fit_strategy"] = "facet_balanced_aspect_cap"
        last_package, last_metrics = package, metrics
        if metrics["within_context_budget"]:
            return package, metrics
    assert last_package is not None and last_metrics is not None
    return last_package, last_metrics


def _build_memory_query_package(
    query: dict[str, Any],
    *,
    tokenizer,
    max_model_len: int,
    synthesis_max_tokens: int,
    context_safety_margin: int,
    pack_profile: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    max_input_tokens = max(512, max_model_len - synthesis_max_tokens - context_safety_margin)
    if pack_profile == "full":
        package, metrics = _compact_memory_query(
            query,
            max_citations_per_facet=1_000_000,
            max_background_per_facet=1_000_000,
            fact_chars=1_000_000,
            include_aspect_status=True,
        )
        prompt = _make_prompt(package, tokenizer)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        metrics["prompt_tokens"] = prompt_tokens
        metrics["prompt_chars"] = len(prompt)
        metrics["max_input_tokens"] = max_input_tokens
        metrics["within_context_budget"] = prompt_tokens is None or prompt_tokens <= max_input_tokens
        metrics["budget_fit_strategy"] = "facet_memory_full"
        metrics["selected_max_citations_per_facet"] = 1_000_000
        metrics["selected_max_background_per_facet"] = 1_000_000
        metrics["selected_fact_chars"] = 1_000_000
        metrics["included_aspect_status"] = True
        return package, metrics
    last_package: dict[str, Any] | None = None
    last_metrics: dict[str, Any] | None = None
    for max_citations_per_facet, max_background_per_facet, fact_chars, include_aspect_status in (
        (36, 6, 420, True),
        (24, 4, 320, True),
        (16, 3, 260, True),
        (12, 2, 220, False),
        (8, 1, 180, False),
        (5, 1, 140, False),
        (3, 0, 110, False),
        (2, 0, 90, False),
        (1, 0, 70, False),
    ):
        package, metrics = _compact_memory_query(
            query,
            max_citations_per_facet=max_citations_per_facet,
            max_background_per_facet=max_background_per_facet,
            fact_chars=fact_chars,
            include_aspect_status=include_aspect_status,
        )
        prompt = _make_prompt(package, tokenizer)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        metrics["prompt_tokens"] = prompt_tokens
        metrics["prompt_chars"] = len(prompt)
        metrics["max_input_tokens"] = max_input_tokens
        metrics["within_context_budget"] = prompt_tokens is None or prompt_tokens <= max_input_tokens
        metrics["budget_fit_strategy"] = "facet_memory_compaction"
        metrics["selected_max_citations_per_facet"] = max_citations_per_facet
        metrics["selected_max_background_per_facet"] = max_background_per_facet
        metrics["selected_fact_chars"] = fact_chars
        metrics["included_aspect_status"] = include_aspect_status
        last_package, last_metrics = package, metrics
        if metrics["within_context_budget"]:
            return package, metrics
    assert last_package is not None and last_metrics is not None
    return last_package, last_metrics


def _compact_memory_query(
    query: dict[str, Any],
    *,
    max_citations_per_facet: int,
    max_background_per_facet: int,
    fact_chars: int,
    include_aspect_status: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    compact_facets = []
    citation_ids: list[str] = []
    background_ids: list[str] = []
    object_type_counts: Counter[str] = Counter()
    missing_aspects = []
    aspect_count = 0
    included_aspect_count = 0

    for facet in query.get("facets") or []:
        facet_citations = [
            _compact_memory_evidence(evidence, fact_chars=fact_chars)
            for evidence in (facet.get("citation_evidence") or [])[:max_citations_per_facet]
        ]
        facet_background = [
            _compact_memory_evidence(evidence, fact_chars=max(60, fact_chars // 2))
            for evidence in (facet.get("background_evidence") or [])[:max_background_per_facet]
        ]
        facet_status = facet.get("aspect_status") or []
        aspect_count += int((facet.get("coverage") or {}).get("aspect_count") or len(facet_status))
        included_aspect_count += len(facet_status) if include_aspect_status else int((facet.get("coverage") or {}).get("covered_aspects") or 0)
        missing_aspects.extend(facet.get("missing_aspects") or [])
        for evidence in facet_citations:
            citation_ids.append(str(evidence.get("object_id")))
            object_type_counts.update([str(evidence.get("object_type"))])
        for evidence in facet_background:
            background_ids.append(str(evidence.get("object_id")))
            object_type_counts.update([str(evidence.get("object_type"))])
        compact_facet = {
            "facet": facet.get("facet"),
            "facet_note": facet.get("facet_note"),
            "coverage": facet.get("coverage") or {},
            "citation_evidence": facet_citations,
            "background_evidence": facet_background,
            "missing_aspects": facet.get("missing_aspects") or [],
        }
        if include_aspect_status:
            compact_facet["aspect_status"] = facet_status
        compact_facets.append(compact_facet)

    package = {
        "package_type": "facet_memory",
        "query_id": query.get("query_id"),
        "mode": query.get("mode"),
        "scoring_profile": query.get("scoring_profile"),
        "ticker": query.get("ticker"),
        "tickers": query.get("tickers") or query.get("ticker"),
        "fiscal_year": query.get("fiscal_year"),
        "fiscal_years": query.get("fiscal_years") or query.get("fiscal_year"),
        "query": query.get("query"),
        "table_requirements": query.get("table_requirements") or {},
        "facets": compact_facets,
        "memory_summary": query.get("memory_summary") or {},
        "output_contract": _output_contract(query),
        "answer_policy": _answer_policy(query),
    }
    metrics = {
        "facet_count": len(compact_facets),
        "aspect_count": aspect_count,
        "included_aspect_count": included_aspect_count,
        "omitted_aspect_count": max(0, aspect_count - included_aspect_count),
        "citation_evidence_count": len(set(citation_ids)),
        "background_evidence_count": len(set(background_ids)),
        "missing_aspect_count": len(missing_aspects),
        "missing_aspects": missing_aspects,
        "input_citation_object_ids": sorted(set(citation_ids)),
        "input_background_object_ids": sorted(set(background_ids)),
        "input_object_type_counts": dict(sorted(object_type_counts.items())),
    }
    return package, metrics


def _budget_candidates(
    citation_chars: int,
    background_chars: int,
    max_background_per_aspect: int,
) -> list[tuple[int, int, int, int]]:
    candidates = [
        (citation_chars, background_chars, max_background_per_aspect, 3),
        (min(citation_chars, 700), min(background_chars, 300), max_background_per_aspect, 2),
        (min(citation_chars, 500), min(background_chars, 200), min(max_background_per_aspect, 1), 2),
        (min(citation_chars, 350), min(background_chars, 100), min(max_background_per_aspect, 1), 1),
        (min(citation_chars, 350), 0, 0, 1),
        (220, 0, 0, 1),
        (120, 0, 0, 1),
        (80, 0, 0, 1),
    ]
    deduped: list[tuple[int, int, int, int]] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _compact_query(
    query: dict[str, Any],
    reference_record: dict[str, Any],
    *,
    citation_chars: int,
    background_chars: int,
    max_background_per_aspect: int,
    max_citations_per_aspect: int,
    max_aspects_per_facet: int | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    compact_facets = []
    citation_ids: list[str] = []
    background_ids: list[str] = []
    missing_aspects = []
    omitted_aspects = []
    object_type_counts: Counter[str] = Counter()
    source_evidence_ids: set[str] = set()
    aspect_count = 0
    included_aspect_count = 0

    for facet in query.get("facets", []):
        compact_aspects = []
        facet_aspects = list(facet.get("aspects", []))
        for aspect_index, aspect in enumerate(facet_aspects):
            aspect_count += 1
            if max_aspects_per_facet is not None and aspect_index >= max_aspects_per_facet:
                omitted_aspects.append(
                    {
                        "facet": facet.get("facet"),
                        "aspect_id": aspect.get("aspect_id"),
                        "aspect": aspect.get("aspect"),
                        "reason": "context_budget_aspect_cap",
                    }
                )
                continue
            included_aspect_count += 1
            citations = [
                _compact_evidence(evidence, text_chars=citation_chars)
                for evidence in (aspect.get("citation_evidence", [])[:max_citations_per_aspect])
            ]
            backgrounds = [
                _compact_evidence(evidence, text_chars=background_chars)
                for evidence in (aspect.get("background_evidence", [])[:max_background_per_aspect])
                if background_chars > 0
            ]
            for evidence in citations:
                citation_ids.append(evidence["object_id"])
                object_type_counts.update([str(evidence.get("object_type"))])
                if evidence.get("source_evidence_id"):
                    source_evidence_ids.add(str(evidence["source_evidence_id"]))
            for evidence in backgrounds:
                background_ids.append(evidence["object_id"])
                object_type_counts.update([str(evidence.get("object_type"))])
                if evidence.get("source_evidence_id"):
                    source_evidence_ids.add(str(evidence["source_evidence_id"]))
            if aspect.get("missing_aspect"):
                missing_aspects.append(
                    {
                        "facet": facet.get("facet"),
                        "aspect_id": aspect.get("aspect_id"),
                        "aspect": aspect.get("aspect"),
                        "missing_reason": aspect.get("missing_reason"),
                    }
                )
            compact_aspects.append(
                {
                    "aspect_id": aspect.get("aspect_id"),
                    "aspect": aspect.get("aspect"),
                    "citation_evidence": citations,
                    "background_evidence": backgrounds,
                    "missing_aspect": aspect.get("missing_aspect"),
                    "missing_reason": aspect.get("missing_reason"),
                }
            )
        compact_facets.append(
            {
                "facet": facet.get("facet"),
                "facet_must_find": facet.get("facet_must_find") or [],
                "aspects": compact_aspects,
                "missing_aspects": facet.get("missing_aspects") or [],
            }
        )

    package = {
        "query_id": query.get("query_id"),
        "mode": query.get("mode"),
        "ticker": query.get("ticker"),
        "fiscal_year": query.get("fiscal_year"),
        "query": query.get("query"),
        "scoring_profile": query.get("scoring_profile"),
        "table_requirements": query.get("table_requirements") or {},
        "facets": compact_facets,
        "output_contract": _output_contract(query),
        "answer_policy": _answer_policy(query),
        "context_budget_note": {
            "original_aspect_count": aspect_count,
            "included_aspect_count": included_aspect_count,
            "omitted_aspect_count": len(omitted_aspects),
        },
    }
    metrics = {
        "facet_count": len(query.get("facets", [])),
        "aspect_count": aspect_count,
        "included_aspect_count": included_aspect_count,
        "omitted_aspect_count": len(omitted_aspects),
        "omitted_aspects": omitted_aspects,
        "citation_evidence_count": len(citation_ids),
        "background_evidence_count": len(background_ids),
        "missing_aspect_count": len(missing_aspects),
        "missing_aspects": missing_aspects,
        "input_citation_object_ids": sorted(set(citation_ids)),
        "input_background_object_ids": sorted(set(background_ids)),
        "input_source_evidence_ids": sorted(source_evidence_ids),
        "input_object_type_counts": dict(sorted(object_type_counts.items())),
    }
    return package, metrics


def _compact_evidence(evidence: dict[str, Any], *, text_chars: int) -> dict[str, Any]:
    compact = {
        "object_id": evidence.get("object_id"),
        "object_type": evidence.get("object_type"),
        "source_evidence_id": evidence.get("source_evidence_id"),
        "text": _trim(str(evidence.get("object_text") or evidence.get("preview") or ""), text_chars),
    }
    metric_hint = _metric_hint_from_evidence(evidence)
    if metric_hint:
        compact["metric_hint"] = metric_hint
    return compact


def _compact_memory_evidence(evidence: dict[str, Any], *, fact_chars: int) -> dict[str, Any]:
    compact = {
        "object_id": evidence.get("object_id"),
        "object_type": evidence.get("object_type"),
        "source_evidence_id": evidence.get("source_evidence_id"),
        "ticker": evidence.get("ticker"),
        "fiscal_year": evidence.get("fiscal_year"),
        "verifier_confidence": evidence.get("verifier_confidence"),
        "fact": _trim(str(evidence.get("fact") or ""), fact_chars),
        "metric": evidence.get("metric"),
    }
    metric_hint = _metric_hint_from_evidence(evidence)
    if metric_hint:
        compact["metric_hint"] = metric_hint
    return compact


def _metric_hint_from_evidence(evidence: dict[str, Any]) -> dict[str, Any] | None:
    text = str(evidence.get("object_text") or evidence.get("preview") or evidence.get("fact") or "")
    if str(evidence.get("object_type") or "") != "metric":
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 11:
        return None
    metric_label = lines[6] if len(lines) > 6 else ""
    raw_value = lines[7] if len(lines) > 7 else ""
    numeric_value = lines[8] if len(lines) > 8 else ""
    unit = lines[9] if len(lines) > 9 else ""
    period = lines[10] if len(lines) > 10 else ""
    subject = lines[11] if len(lines) > 11 else ""
    source_statement = " ".join(lines[12:14]) if len(lines) > 12 else ""
    metric_role = _infer_metric_role(metric_label, raw_value, unit, source_statement)
    return {
        "metric_label": metric_label,
        "raw_value_text": raw_value,
        "numeric_value": numeric_value,
        "unit": unit,
        "period": period,
        "subject": subject,
        "metric_role": metric_role,
        "allowed_claim_roles": _allowed_claim_roles(metric_role),
        "disallowed_claim_roles": _disallowed_claim_roles(metric_role),
        "numeric_use_rule": _numeric_use_rule(metric_role, source_statement),
    }


def _infer_metric_role(metric_label: str, raw_value: str, unit: str, source_statement: str) -> str:
    text = f"{metric_label} {raw_value} {unit} {source_statement}".lower()
    if unit.lower() in {"percent", "%"} or "%" in raw_value or any(term in text for term in ("margin", "rate")):
        return "percentage_rate"
    if _raw_value_is_period_change(raw_value, source_statement):
        return "period_change_amount"
    if any(term in text for term in ("remaining performance obligations", "revenue", "sales", "income", "cash flow")):
        return "total_value"
    return "unknown"


def _raw_value_is_period_change(raw_value: str, source_statement: str) -> bool:
    number_match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", raw_value)
    if not number_match:
        return False
    number = re.escape(number_match.group(0).replace(",", ""))
    normalized_statement = source_statement.replace(",", "").lower()
    return bool(re.search(rf"\b(?:by|or)\s+\$?\s*{number}\b", normalized_statement))


def _numeric_use_rule(metric_role: str, source_statement: str) -> str:
    if metric_role == "period_change_amount":
        return "This value is a period change amount, not the period total. Do not state it as total revenue/sales."
    if metric_role == "percentage_rate":
        return "This value is a rate or margin. Keep the percent unit and do not convert it to a dollar amount."
    if "in millions" in source_statement.lower():
        return "Source scale is in millions. If converting to billions, state the conversion explicitly and keep the raw value in numeric_claims."
    return "Use the raw value text and unit from this evidence; do not change metric role or segment scope."


def _allowed_claim_roles(metric_role: str) -> list[str]:
    if metric_role == "period_change_amount":
        return ["period_change_amount"]
    if metric_role == "percentage_rate":
        return ["percentage_rate", "ratio"]
    if metric_role == "total_value":
        return ["total_value"]
    return ["unknown"]


def _disallowed_claim_roles(metric_role: str) -> list[str]:
    if metric_role == "period_change_amount":
        return ["total_value"]
    if metric_role == "percentage_rate":
        return ["total_value", "period_change_amount"]
    return []


def _output_contract(query: dict[str, Any]) -> str:
    return "metric_table_cells_v0.1" if query.get("scoring_profile") == "metric_table_stability" else "analyst_summary_v0.1"


def _answer_policy(query: dict[str, Any]) -> dict[str, Any]:
    policy = {
        "language": "zh-CN",
        "hard_citation_rule": "Only cite object_id values from citation_evidence for final factual claims. Use background_evidence only as context.",
        "missing_rule": "If an aspect has missing_aspect=true, mention the specific uncertainty instead of filling the gap from background text.",
        "context_budget_rule": "If context_budget_note or memory_summary reports omitted or missing aspects, state the uncertainty instead of implying full coverage.",
        "no_investment_advice": True,
    }
    if query.get("scoring_profile") == "metric_table_stability":
        policy["cell_table_rule"] = (
            "Populate cell_table.cells with one row per company/year/metric when evidence is available or missing. "
            "Use status=reported only when value, unit, and citation_object_id are supported by citation_evidence. "
            "For qualitative risk/caveat cells, use value=null and unit=qualitative with a claim citation. "
            "For capex or PP&E purchase cash outflows, report positive cash-outflow magnitude and explain the sign in note. "
            "For derived cells such as YoY growth, put all source ids in citation_object_ids and state the formula in derivation."
        )
    return policy


def _make_prompt(package: dict[str, Any], tokenizer) -> str:
    if package.get("package_type") == "driver_pack":
        return _make_driver_pack_prompt(package, tokenizer)
    system = (
        "You are a senior financial analyst. Use only the provided SEC 10-K evidence package. "
        "Write in Simplified Chinese. Do not invent facts. Return only valid JSON."
    )
    table_instruction = ""
    schema_hint = (
        "{\"answer_zh\":\"...\",\"conclusion_quality\":\"good|mixed|weak\","
        "\"thesis_zh\":\"一句主判断\","
        "\"decision_drivers\":[{\"rank\":1,\"driver_zh\":\"...\",\"decision_impact_zh\":\"...\","
        "\"evidence_strength\":\"strong|moderate|weak\",\"cited_object_ids\":[\"...\"]}],"
        "\"secondary_context\":[{\"context_zh\":\"...\",\"why_secondary_zh\":\"...\",\"cited_object_ids\":[\"...\"]}],"
        "\"limiting_caveats\":[{\"caveat_type\":\"missing_evidence|comparability|metric_role|counter_evidence|scope_limit\","
        "\"caveat_zh\":\"...\",\"impact_on_thesis_zh\":\"...\",\"cited_object_ids\":[\"...\"]}],"
        "\"facet_findings\":[{\"facet_zh\":\"...\",\"coverage_status\":\"covered|partial|missing|conflicted\","
        "\"importance\":\"primary|supporting|caveat_only\",\"takeaway_zh\":\"...\",\"cited_object_ids\":[\"...\"]}],"
        "\"numeric_claims\":[{\"claim_location\":\"answer|thesis|decision_driver|secondary_context|limiting_caveat|facet_finding\","
        "\"metric_id\":\"...\",\"metric_label_zh\":\"...\",\"raw_value_text\":\"...\",\"display_value_zh\":\"...\",\"unit\":\"...\","
        "\"metric_role\":\"total_value|period_change_amount|percentage_rate|ratio|derived|qualitative_context|unknown\","
        "\"role_check_zh\":\"...\",\"cited_object_ids\":[\"...\"]}],"
        "\"missing_or_uncertain_zh\":[\"...\"],\"evidence_use_notes_zh\":\"...\"}"
    )
    length_instruction = (
        "5. complex insight 必须先判断再辅证：thesis_zh 是一句主判断；decision_drivers 最多 3 条且必须按重要性排序，"
        "只放会支配结论的证据；secondary_context 最多 3 条，只能补充不能改变主结论；"
        "limiting_caveats 写会削弱结论的缺证、口径、metric role 或反证；facet_findings 作为 supporting appendix，不能主导答案。\n"
        "6. 数值纪律：凡在 answer_zh/thesis/driver/context/caveat/facet 中使用精确数字，必须在 numeric_claims 中逐项登记。"
        "如果存在 Exact-Value Ledger，numeric_claims 必须填写 metric_id，display_value_zh 必须逐字复制 ledger display_value_zh。"
        "raw_value_text 必须从被引用 metric evidence 的 metric_hint.raw_value_text 或原文逐字符复制；unit 必须保留原单位。"
        "如果 metric_hint.metric_role=period_change_amount，只能写成增量/变动额，不能写成总收入/总额。"
        "如果 metric_hint.disallowed_claim_roles 包含 total_value，则绝不能把该 object_id 用来支持总收入、期末余额或总额。"
        "例如 evidence 写 'increased ... or $7.1 billion'，只能表述为增加 71 亿美元，不能表述为收入为 71 亿美元；"
        "也不能把 period_change_amount 和 total_value 放进同一个'从 X 增长至 Y'的总额趋势句。"
        "如果要比较趋势，必须分别标明 X 是增量/变动额、Y 是总额，或干脆不用 X 做总额基点。"
        "thesis_zh 和 decision_drivers 优先写判断，不要堆精确货币数；精确数字主要放入 numeric_claims。"
        "如果 driver/context/facet 中必须出现精确数字，则数字附近必须写明 metric role："
        "period_change_amount 附近必须有'增加/减少/增量/变动额'，total_value 附近必须有'总收入/总额/期末余额/规模'，"
        "percentage_rate 附近必须有'率/占比/比例'。返回 JSON 前自查：凡 period_change_amount 的 display_value_zh 出现在正文，"
        "如果该句还包含'从/至/到/增长至/达到'等总额趋势词，必须重写或删除该数字。"
        "如果找不到 total_value evidence，就把该总额标为 limiting_caveat/missing_or_uncertain。"
        "如果 source scale 是 usd_millions，正文可以换算为 billion/亿美元，但 numeric_claims 必须保留 raw_value_text，并在 role_check_zh 说明换算。"
        "不得把 segment revenue、cloud aggregate、company total、deferred revenue、RPO/ARR 混成同一个 metric。"
        "limiting_caveats 如果只是基于 missing_aspect 或缺证，不需要引用；cited_object_ids 可为空。"
        "绝不能把 aspect_id、facet 名、missing aspect id 当成 object_id 引用。\n"
    )
    if package.get("output_contract") == "metric_table_cells_v0.1":
        schema_hint = (
            "{\"answer_zh\":\"...\",\"conclusion_quality\":\"good|mixed|weak\","
            "\"cell_table\":{\"unit_policy\":\"...\",\"cells\":[{\"ticker\":\"...\",\"fiscal_year\":2025,"
            "\"metric\":\"...\",\"value\":123.0,\"unit\":\"usd_millions\",\"status\":\"reported|missing|unsupported\","
            "\"citation_object_id\":\"...\",\"citation_object_ids\":[\"...\"],\"derivation\":null,\"note\":\"...\"}]},"
            "\"key_findings\":[{\"claim_zh\":\"...\",\"cited_object_ids\":[\"...\"]}],"
            "\"missing_or_uncertain_zh\":[\"...\"],\"evidence_use_notes_zh\":\"...\"}"
        )
        table_instruction = (
            "7. 这是表格/指标任务，必须填充 cell_table.cells。每个 reported cell 必须包含 ticker、fiscal_year、metric、value、unit、citation_object_id；"
            "无法从 citation_evidence 支持的 cell 用 status=missing 或 unsupported，value=null。"
            "定性风险/口径 caveat 可用 status=reported、value=null、unit=qualitative，并引用 claim object。"
            "capex/PP&E purchases 以正的现金流出额展示，note 说明原表可能用括号/负号表示现金流出。"
            "YoY growth、FCF proxy 等派生 cell 必须在 citation_object_ids 放入全部来源 object_id，并在 derivation 写公式；"
            "如果只有单个当前值证据，不要把它当成增长率或 FCF。\n"
        )
        length_instruction = (
            "5. 必须简洁：answer_zh 不超过 500 个中文字符；key_findings 最多 4 条；"
            "每条 finding 最多引用 4 个 object_id；missing_or_uncertain_zh 最多 6 条。\n"
        )
    user = (
        "请基于下面的校准证据池生成最终中文回答。\n"
        "要求：\n"
        "1. 只把 citation_evidence 里的 object_id 作为结论引用；必须逐字符复制 object_id，不要改年份、ticker、前缀或后缀；background_evidence 只能做上下文，不能当硬证据。\n"
        "2. 如果某个 aspect 标记 missing_aspect=true，必须在不确定项中说明，不要用背景证据补成确定结论。\n"
        "3. 回答要体现财务专业判断：区分增长、利润/成本压力、收入可见性、合同/风险 caveat 和公司披露口径差异。\n"
        "4. 不给投资建议，不预测股价。\n"
        f"{length_instruction}"
        f"7. 输出 JSON schema: {schema_hint}\n"
        f"{table_instruction}\n"
        f"Evidence package JSON:\n{json.dumps(package, ensure_ascii=False)}"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think\n"
    return f"System:\n{system}\n\nUser:\n{user}\n/no_think\n\nAssistant:\n"


def _make_driver_pack_prompt(package: dict[str, Any], tokenizer) -> str:
    system = (
        "You are a senior financial analyst. Use only the normalized Decision Driver Evidence Pack and Exact-Value Ledger rows. "
        "Write in Simplified Chinese. Return only valid JSON."
    )
    schema_hint = (
        "{\"answer_zh\":\"...\",\"conclusion_quality\":\"good|mixed|weak\","
        "\"thesis_zh\":\"一句主判断\","
        "\"decision_drivers\":[{\"rank\":1,\"driver_zh\":\"...\",\"decision_impact_zh\":\"...\","
        "\"evidence_strength\":\"strong|moderate|weak\",\"cited_object_ids\":[\"object_id\"]}],"
        "\"secondary_context\":[{\"context_zh\":\"...\",\"why_secondary_zh\":\"...\",\"cited_object_ids\":[\"object_id\"]}],"
        "\"limiting_caveats\":[{\"caveat_type\":\"missing_evidence|comparability|metric_role|counter_evidence|scope_limit\","
        "\"caveat_zh\":\"...\",\"impact_on_thesis_zh\":\"...\",\"cited_object_ids\":[\"object_id\"]}],"
        "\"facet_findings\":[{\"facet_zh\":\"...\",\"coverage_status\":\"covered|partial|missing|conflicted\","
        "\"importance\":\"primary|supporting|caveat_only\",\"takeaway_zh\":\"...\",\"cited_object_ids\":[\"object_id\"]}],"
        "\"numeric_claims\":[{\"claim_location\":\"answer|thesis|decision_driver|secondary_context|limiting_caveat|facet_finding\","
        "\"metric_id\":\"ledger metric_id\",\"metric_label_zh\":\"...\",\"raw_value_text\":\"ledger raw_value_text\","
        "\"display_value_zh\":\"ledger display_value_zh\",\"unit\":\"ledger unit\","
        "\"metric_role\":\"total_value|period_change_amount|percentage_rate|ratio|derived|qualitative_context|unknown\","
        "\"role_check_zh\":\"...\",\"cited_object_ids\":[\"ledger object_id\"]}],"
        "\"missing_or_uncertain_zh\":[\"...\"],\"evidence_use_notes_zh\":\"...\"}"
    )
    user = (
        "请基于下面的 normalized Driver Pack 生成最终中文回答。\n"
        "硬规则：\n"
        "1. 只使用 decision_drivers / secondary_context / limiting_caveats 中提供的 supporting_evidence 和 authorized_ledger_metrics。不要引用任何未出现在输入中的 object_id 或 metric_id。\n"
        "2. 精确数字只能来自 authorized_ledger_metrics。凡在 answer_zh、thesis_zh、driver_zh、decision_impact_zh、context_zh、caveat_zh、takeaway_zh 中出现精确数字，必须在 numeric_claims 中登记，并且 metric_id、raw_value_text、display_value_zh、unit、metric_role 必须逐字复制对应 ledger row。\n"
        "3. 如果某个判断没有 authorized_ledger_metrics 支撑，不要写精确数字；只能写方向性判断或 caveat。\n"
        "4. metric_role 不可改写：period_change_amount 只能表述为增加/减少/变动额，不能写成总收入/总额；percentage_rate 只能表述为率/比例；total_value 才能表述为总额/规模。\n"
        "5. driver 的顺序应继承输入 pack 的 rank。不要平均铺开 facet；先写最能支配 thesis 的 driver，再写辅助和限制。\n"
        "6. 如果 global_claim_allowed=false，只能写局部判断，不能把该 driver 升级成全局排序或全公司结论。\n"
        "7. missing_primary_facets 和 limiting_caveats 必须真的影响 thesis strength；不要把缺证写成无关备注。\n"
        "8. 输出 JSON schema: "
        f"{schema_hint}\n"
        f"Driver Pack + Ledger package JSON:\n{json.dumps(package, ensure_ascii=False)}"
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think\n"
    return f"System:\n{system}\n\nUser:\n{user}\n/no_think\n\nAssistant:\n"


def _run_synthesis(
    *,
    llm,
    prompt: str,
    max_tokens: int,
    structured_schema: dict[str, Any] | None,
) -> tuple[dict[str, Any], str, str]:
    if llm is None:
        return (
            {
                "answer_zh": "未加载常驻模型，已跳过最终 synthesis。",
                "conclusion_quality": "weak",
                "thesis_zh": "未加载常驻模型，无法形成主判断。",
                "decision_drivers": [],
                "secondary_context": [],
                "limiting_caveats": [],
                "key_findings": [],
                "facet_findings": [],
                "numeric_claims": [],
                "comparability_caveats_zh": [],
                "missing_evidence_by_facet": [],
                "missing_or_uncertain_zh": ["resident_model_disabled"],
                "evidence_use_notes_zh": "dry-run only",
            },
            "",
            "skipped_no_model",
        )
    raw = _generate_one(
        llm,
        prompt,
        max_tokens=max_tokens,
        temperature=0.0,
        structured_schema=structured_schema,
    )
    try:
        return _extract_json(raw), raw, "parsed"
    except Exception as exc:
        return (
            {
                "answer_zh": raw,
                "conclusion_quality": "mixed",
                "thesis_zh": "JSON 解析失败，主判断保留在原始输出中。",
                "decision_drivers": [],
                "secondary_context": [],
                "limiting_caveats": [],
                "key_findings": [],
                "facet_findings": [],
                "numeric_claims": [],
                "comparability_caveats_zh": [],
                "missing_evidence_by_facet": [],
                "missing_or_uncertain_zh": [f"json_parse_failed: {type(exc).__name__}: {exc}"],
                "evidence_use_notes_zh": "raw model output was retained because JSON parsing failed",
            },
            raw,
            "invalid_json",
        )


def _evaluate_output_use(package_metrics: dict[str, Any], synthesis: dict[str, Any]) -> dict[str, Any]:
    input_citation_ids = set(package_metrics.get("input_citation_object_ids", []))
    input_background_ids = set(package_metrics.get("input_background_object_ids", []))
    valid_input_ids = input_citation_ids | input_background_ids
    background_only_ids = input_background_ids - input_citation_ids
    cited_ids = _cited_ids_from_synthesis(synthesis)
    cited_set = set(cited_ids)
    missing_signal_count = len(synthesis.get("missing_or_uncertain_zh", []) or []) + len(
        synthesis.get("missing_evidence_by_facet", []) or []
    ) + len(synthesis.get("limiting_caveats", []) or [])
    return {
        "decision_driver_count": len(synthesis.get("decision_drivers", []) or []),
        "secondary_context_count": len(synthesis.get("secondary_context", []) or []),
        "limiting_caveat_count": len(synthesis.get("limiting_caveats", []) or []),
        "key_finding_count": len(synthesis.get("key_findings", []) or []),
        "facet_finding_count": len(synthesis.get("facet_findings", []) or []),
        "comparability_caveat_count": len(synthesis.get("comparability_caveats_zh", []) or []),
        "numeric_claim_count": len(synthesis.get("numeric_claims", []) or []),
        "cited_object_count": len(cited_set),
        "cited_citation_object_count": len(cited_set & input_citation_ids),
        "cited_background_object_count": len(cited_set & background_only_ids),
        "valid_cited_object_count": len(cited_set & valid_input_ids),
        "invalid_cited_object_ids": sorted(cited_set - valid_input_ids),
        "unused_input_citation_count": len(input_citation_ids - cited_set),
        "missing_aspect_count_in_input": package_metrics.get("missing_aspect_count", 0),
        "model_missing_or_uncertain_count": missing_signal_count,
    }


def _repair_metric_id_citations(synthesis: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    metric_to_object_id: dict[str, str] = {}
    for driver in package.get("decision_drivers") or []:
        for metric in driver.get("authorized_ledger_metrics") or []:
            metric_id = str(metric.get("metric_id") or "")
            object_id = str(metric.get("object_id") or "")
            if metric_id and object_id:
                metric_to_object_id[metric_id] = object_id
    if not metric_to_object_id:
        return synthesis

    repaired = json.loads(json.dumps(synthesis, ensure_ascii=False))
    for section_name in (
        "decision_drivers",
        "secondary_context",
        "limiting_caveats",
        "key_findings",
        "facet_findings",
        "numeric_claims",
    ):
        for item in repaired.get(section_name) or []:
            if isinstance(item.get("cited_object_ids"), list):
                item["cited_object_ids"] = [
                    metric_to_object_id.get(str(cited_id), str(cited_id))
                    for cited_id in item.get("cited_object_ids") or []
                ]
    return repaired


def _schema_for_package(package: dict[str, Any]) -> dict[str, Any]:
    if package.get("output_contract") == "metric_table_cells_v0.1":
        return METRIC_TABLE_SYNTHESIS_JSON_SCHEMA
    return SYNTHESIS_JSON_SCHEMA


def _cited_ids_from_synthesis(synthesis: dict[str, Any]) -> list[str]:
    cited_ids: list[str] = []
    for finding in synthesis.get("decision_drivers", []) or []:
        cited_ids.extend(str(item) for item in finding.get("cited_object_ids", []) or [] if str(item).strip())
    for finding in synthesis.get("secondary_context", []) or []:
        cited_ids.extend(str(item) for item in finding.get("cited_object_ids", []) or [] if str(item).strip())
    for finding in synthesis.get("limiting_caveats", []) or []:
        cited_ids.extend(str(item) for item in finding.get("cited_object_ids", []) or [] if str(item).strip())
    for finding in synthesis.get("key_findings", []) or []:
        cited_ids.extend(str(item) for item in finding.get("cited_object_ids", []) or [] if str(item).strip())
    for finding in synthesis.get("facet_findings", []) or []:
        cited_ids.extend(str(item) for item in finding.get("cited_object_ids", []) or [] if str(item).strip())
    for finding in synthesis.get("numeric_claims", []) or []:
        cited_ids.extend(str(item) for item in finding.get("cited_object_ids", []) or [] if str(item).strip())
    cell_table = synthesis.get("cell_table") or {}
    for cell in cell_table.get("cells") or []:
        object_ids = list(cell.get("citation_object_ids") or [])
        if cell.get("citation_object_id"):
            object_ids.append(cell.get("citation_object_id"))
        for object_id in object_ids:
            if object_id:
                cited_ids.append(str(object_id))
    return cited_ids


def _summarize(
    results: list[dict[str, Any]],
    pool_report: dict[str, Any],
    human_gold_eval: dict[str, Any],
) -> dict[str, Any]:
    parse_counts = Counter(result.get("parse_status") for result in results)
    quality_counts = Counter(result.get("synthesis", {}).get("conclusion_quality") for result in results)
    citation_counts = Counter()
    totals = Counter()
    for result in results:
        package = result.get("package_metrics", {})
        output = result.get("output_metrics", {})
        totals["facets"] += int(package.get("facet_count") or 0)
        totals["aspects"] += int(package.get("aspect_count") or 0)
        totals["citation_evidence"] += int(package.get("citation_evidence_count") or 0)
        totals["background_evidence"] += int(package.get("background_evidence_count") or 0)
        totals["missing_aspects"] += int(package.get("missing_aspect_count") or 0)
        totals["cited_objects"] += int(output.get("cited_object_count") or 0)
        totals["cited_citation_objects"] += int(output.get("cited_citation_object_count") or 0)
        totals["cited_background_objects"] += int(output.get("cited_background_object_count") or 0)
        totals["valid_cited_objects"] += int(output.get("valid_cited_object_count") or 0)
        totals["invalid_citations"] += len(output.get("invalid_cited_object_ids") or [])
        citation_counts.update(package.get("input_object_type_counts", {}))
    cited_objects = totals["cited_objects"]
    return {
        "query_count": len(results),
        "parse_status_counts": dict(parse_counts),
        "conclusion_quality_counts": dict(quality_counts),
        "evaluated_facets": totals["facets"],
        "evaluated_aspects": totals["aspects"],
        "input_citation_evidence": totals["citation_evidence"],
        "input_background_evidence": totals["background_evidence"],
        "input_missing_aspects": totals["missing_aspects"],
        "model_cited_objects": cited_objects,
        "model_cited_citation_objects": totals["cited_citation_objects"],
        "model_cited_background_objects": totals["cited_background_objects"],
        "invalid_cited_object_ids": totals["invalid_citations"],
        "citation_object_use_rate": round(totals["cited_citation_objects"] / totals["citation_evidence"], 4)
        if totals["citation_evidence"]
        else 0.0,
        "cited_object_precision_against_input": round(
            totals["valid_cited_objects"] / cited_objects,
            4,
        )
        if cited_objects
        else 0.0,
        "input_object_type_counts": dict(sorted(citation_counts.items())),
        "upstream_pool_metrics": {
            "aspects": pool_report.get("aspects"),
            "citation_evidence": pool_report.get("citation_evidence"),
            "background_evidence": pool_report.get("background_evidence"),
            "missing_aspects": pool_report.get("missing_aspects"),
        }
        if pool_report
        else {},
        "human_gold_citation_precision": (
            human_gold_eval.get("citation_evidence", {}).get("citation_precision")
            if human_gold_eval
            else None
        ),
    }


def _load_vllm(args: argparse.Namespace):
    from transformers import AutoTokenizer
    from vllm import LLM

    model_path = str((REPO_ROOT / args.model_path).resolve())
    python_bin = str(Path(sys.executable).resolve().parent)
    os.environ["PATH"] = python_bin + os.pathsep + os.environ.get("PATH", "")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    llm_kwargs = {
        "model": model_path,
        "tokenizer": model_path,
        "trust_remote_code": True,
        "dtype": args.dtype,
        "max_model_len": args.max_model_len,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "cpu_offload_gb": args.cpu_offload_gb,
        "enforce_eager": True,
        "max_num_seqs": args.max_num_seqs,
    }
    if args.quantization and args.quantization.lower() not in {"none", "null", "auto"}:
        llm_kwargs["quantization"] = args.quantization
    if args.language_model_only:
        llm_kwargs["language_model_only"] = True
    if args.skip_mm_profiling:
        llm_kwargs["skip_mm_profiling"] = True
    return LLM(**llm_kwargs), tokenizer


def _generate_one(
    llm,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    structured_schema: dict[str, Any] | None,
) -> str:
    from vllm import SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    sampling_kwargs: dict[str, Any] = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 1.0,
    }
    if structured_schema is not None:
        sampling_kwargs["structured_outputs"] = StructuredOutputsParams(
            json=structured_schema,
            disable_additional_properties=True,
        )
    outputs = llm.generate([prompt], SamplingParams(**sampling_kwargs))
    return outputs[0].outputs[0].text.strip()


def _prompt_token_count(tokenizer, prompt: str) -> int | None:
    if tokenizer is None or not hasattr(tokenizer, "encode"):
        # Conservative smoke-test estimate for local dry-runs without model files.
        return max(1, (len(prompt) + 2) // 3)
    return len(tokenizer.encode(prompt, add_special_tokens=False))


def _extract_json(text: str) -> dict[str, Any]:
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _read_jsonl_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            records[str(row.get("query_id"))] = row
    return records


def _trim(text: str, max_chars: int) -> str:
    compact = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    if max_chars <= 0:
        return ""
    return compact[:max_chars] + ("\n...[truncated]" if len(compact) > max_chars else "")


if __name__ == "__main__":
    main()
