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


METRIC_FAMILY_ALLOWLIST = [
    "advertising_revenue",
    "arr_or_recurring_proxy",
    "billings",
    "capex",
    "cash_flow",
    "cloud_revenue",
    "customer_concentration",
    "customer_retention",
    "datacenter_revenue",
    "deferred_revenue",
    "depreciation_amortization",
    "gross_margin",
    "infrastructure_cost",
    "inventory",
    "operating_income",
    "operating_margin",
    "product_cycle",
    "rpo",
    "services_revenue",
    "subscription_revenue",
    "supply_chain_risk",
]


QUERY_CONTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "query_id",
        "task_profile",
        "target_judgment_zh",
        "required_companies",
        "required_years",
        "allowed_conclusion_strengths",
        "required_metric_families",
        "facets",
        "comparability_rules",
        "planner_confidence",
        "planner_caveats_zh",
    ],
    "properties": {
        "query_id": {"type": "string", "maxLength": 140},
        "task_profile": {"type": "string", "enum": ["complex_insight"]},
        "target_judgment_zh": {"type": "string", "maxLength": 260},
        "required_companies": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 12},
        },
        "required_years": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {"type": "integer", "minimum": 1990, "maximum": 2100},
        },
        "allowed_conclusion_strengths": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "string",
                "enum": [
                    "strong_with_caveats",
                    "moderate_with_caveats",
                    "weak_only",
                    "disclosure_quality_only",
                    "insufficient_evidence",
                ],
            },
        },
        "required_metric_families": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {"type": "string", "enum": METRIC_FAMILY_ALLOWLIST},
        },
        "facets": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "facet_id",
                    "facet_zh",
                    "priority",
                    "required_coverage",
                    "missing_downgrade_rule_zh",
                    "allowed_driver_roles",
                ],
                "properties": {
                    "facet_id": {"type": "string", "maxLength": 80},
                    "facet_zh": {"type": "string", "maxLength": 120},
                    "priority": {"type": "string", "enum": ["primary", "supporting", "caveat"]},
                    "required_coverage": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["companies", "years", "metric_families"],
                        "properties": {
                            "companies": {
                                "type": "array",
                                "maxItems": 8,
                                "items": {"type": "string", "maxLength": 12},
                            },
                            "years": {
                                "type": "array",
                                "maxItems": 5,
                                "items": {"type": "integer", "minimum": 1990, "maximum": 2100},
                            },
                            "metric_families": {
                                "type": "array",
                                "maxItems": 8,
                                "items": {"type": "string", "enum": METRIC_FAMILY_ALLOWLIST},
                            },
                        },
                    },
                    "missing_downgrade_rule_zh": {"type": "string", "maxLength": 260},
                    "allowed_driver_roles": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "string",
                            "enum": ["core_driver", "supporting_context", "caveat_driver"],
                        },
                    },
                },
            },
        },
        "comparability_rules": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rule_id", "metric_families", "rule_zh"],
                "properties": {
                    "rule_id": {"type": "string", "maxLength": 80},
                    "metric_families": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 6,
                        "items": {"type": "string", "enum": METRIC_FAMILY_ALLOWLIST},
                    },
                    "rule_zh": {"type": "string", "maxLength": 260},
                },
            },
        },
        "planner_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "planner_caveats_zh": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string", "maxLength": 220},
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan Query Contracts for complex insight synthesis.")
    parser.add_argument("--eval-path", default="eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl")
    parser.add_argument(
        "--grouped-pool-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument("--model-path", default="data/models_private/modelscope/Qwen/Qwen3___5-9B")
    parser.add_argument(
        "--output",
        default="reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json",
    )
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--max-tokens", type=int, default=2200)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--quantization", default="none")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--cpu-offload-gb", type=float, default=0.0)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--language-model-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-mm-profiling", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--structured-json", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--disable-vllm", action="store_true")
    vllm_hardware_profiles.add_hardware_profile_arg(parser)
    args = parser.parse_args()
    vllm_hardware_profiles.apply_hardware_profile(args, workload="query_contract_planner")
    return args


def main() -> None:
    args = parse_args()
    started = time.time()
    eval_rows = _read_jsonl(REPO_ROOT / args.eval_path)
    grouped = _read_json(REPO_ROOT / args.grouped_pool_path)
    grouped_by_id = {str(query.get("query_id")): query for query in grouped.get("queries") or []}
    selected = _select_rows(eval_rows, set(args.query_id), args.limit)
    output_path = REPO_ROOT / args.output

    llm = None
    tokenizer = None
    timings: dict[str, float] = {"load_inputs_sec": round(time.time() - started, 4)}
    if not args.disable_vllm:
        t_model = time.time()
        llm, tokenizer = _load_vllm(args)
        timings["load_model_sec"] = round(time.time() - t_model, 4)

    results: list[dict[str, Any]] = []
    for row in selected:
        query_started = time.time()
        query_id = str(row.get("query_id"))
        grouped_query = grouped_by_id.get(query_id, {})
        package = _planner_package(row, grouped_query)
        prompt = _make_prompt(package)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        if args.disable_vllm:
            contract = _heuristic_contract(package)
            raw_output = json.dumps(contract, ensure_ascii=False)
            parse_status = "heuristic"
        else:
            raw_output = _generate_one(
                llm,
                prompt,
                max_tokens=args.max_tokens,
                temperature=0.0,
                structured_schema=QUERY_CONTRACT_SCHEMA if args.structured_json else None,
            )
            try:
                contract = _extract_json(raw_output)
                parse_status = "parsed"
            except Exception as exc:  # noqa: BLE001
                contract = _heuristic_contract(package) | {
                    "planner_confidence": "low",
                    "planner_caveats_zh": [f"planner_parse_failed: {type(exc).__name__}: {exc}"],
                }
                parse_status = "parse_error_fallback"
        raw_contract = json.loads(json.dumps(contract, ensure_ascii=False))
        contract, normalization_notes = _sanitize_contract(contract, package)
        results.append(
            {
                "query_id": query_id,
                "query_zh": row.get("query_zh"),
                "scoring_profile": row.get("scoring_profile"),
                "planner_input_metrics": _package_metrics(package),
                "prompt_tokens": prompt_tokens,
                "prompt_chars": len(prompt),
                "parse_status": parse_status,
                "query_contract": contract,
                "raw_query_contract": raw_contract,
                "normalization_notes": normalization_notes,
                "raw_output": raw_output,
                "elapsed_sec": round(time.time() - query_started, 4),
            }
        )
        _write_report(output_path, args, results, timings, started, partial=True)
        print(
            json.dumps(
                {
                    "query_id": query_id,
                    "parse_status": parse_status,
                    "elapsed_sec": results[-1]["elapsed_sec"],
                    "facets": len(contract.get("facets") or []),
                    "normalization_note_count": len(normalization_notes),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    _write_report(output_path, args, results, timings, started, partial=False)
    print(json.dumps({"output": str(output_path), "queries": len(results)}, ensure_ascii=False), flush=True)


def _planner_package(eval_row: dict[str, Any], grouped_query: dict[str, Any]) -> dict[str, Any]:
    facets = []
    for facet in grouped_query.get("facets") or []:
        evidence_text = " ".join(
            str(item.get("preview") or item.get("object_text") or "")[:240]
            for aspect in facet.get("aspects") or []
            for item in (aspect.get("citation_evidence") or [])[:2]
        )
        facet_text = " ".join(
            [
                str(facet.get("facet") or ""),
                " ".join(str(item) for item in facet.get("facet_must_find") or []),
                evidence_text,
            ]
        )
        facets.append(
            {
                "facet": facet.get("facet"),
                "facet_must_find": facet.get("facet_must_find") or [],
                "aspect_count": len(facet.get("aspects") or []),
                "missing_aspect_count": len(facet.get("missing_aspects") or []),
                "metric_family_hints": sorted(_infer_metric_families(facet_text)),
            }
        )
    evidence_needs = eval_row.get("evidence_needs") or []
    for item in evidence_needs:
        item["metric_family_hints"] = sorted(
            _infer_metric_families(" ".join([str(item.get("facet") or ""), " ".join(item.get("must_find") or [])]))
        )
    return {
        "query_id": eval_row.get("query_id"),
        "query_zh": eval_row.get("query_zh") or grouped_query.get("query"),
        "query_en": eval_row.get("query_en"),
        "evaluation_intent": eval_row.get("evaluation_intent"),
        "tickers": eval_row.get("tickers") or grouped_query.get("tickers") or [],
        "fiscal_years": eval_row.get("fiscal_years") or grouped_query.get("fiscal_years") or [],
        "ideal_facets": eval_row.get("ideal_facets") or [],
        "evidence_needs": evidence_needs,
        "required_caveats": eval_row.get("required_caveats") or [],
        "common_failure_modes": eval_row.get("common_failure_modes") or [],
        "grouped_facets": facets[:12],
        "metric_family_allowlist": METRIC_FAMILY_ALLOWLIST,
    }


def _make_prompt(package: dict[str, Any]) -> str:
    compact = {
        key: package[key]
        for key in (
            "query_id",
            "query_zh",
            "evaluation_intent",
            "tickers",
            "fiscal_years",
            "ideal_facets",
            "evidence_needs",
            "required_caveats",
            "common_failure_modes",
            "grouped_facets",
            "metric_family_allowlist",
        )
    }
    return (
        "你是金融证据约束框架的 Query Contract planner。你的任务不是回答问题，而是定义后续模型必须遵守的评分和证据边界。\n"
        "只返回 JSON，必须符合 schema。不要输出最终答案，不要引用 object_id，不要写精确数值。\n"
        "要求：\n"
        "1. target_judgment_zh 写这题需要判断什么，不要包含数字。\n"
        "2. facets 必须 3-6 条，并标记 priority=primary/supporting/caveat。\n"
        "3. primary facet 必须有 missing_downgrade_rule_zh，说明缺证时如何降级结论。\n"
        "4. required_metric_families 只能从 metric_family_allowlist 里选。\n"
        "5. comparability_rules 写常见不可直接横比的 metric family 关系。\n"
        "6. allowed_conclusion_strengths 只能用 strong_with_caveats/moderate_with_caveats/weak_only/disclosure_quality_only/insufficient_evidence。\n"
        "7. required_coverage 里的 companies/years 必须是输入 tickers/fiscal_years 的子集；历史背景只能写进 caveat 或 downgrade rule，不能放进 required_coverage。\n"
        "8. 不要把 evidence_needs 或 ideal_facets 原样机械复制；需要合并成可执行的 Query Contract。\n\n"
        f"输入：\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
    )


def _sanitize_contract(contract: dict[str, Any], package: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    clean = json.loads(json.dumps(contract, ensure_ascii=False))
    expected_companies = _unique_strings([str(ticker).upper() for ticker in package.get("tickers") or []])
    expected_years = sorted({year for year in (_coerce_int(item) for item in package.get("fiscal_years") or []) if year})

    clean["query_id"] = str(package.get("query_id") or clean.get("query_id") or "")
    clean["task_profile"] = "complex_insight"
    clean["required_companies"] = expected_companies
    clean["required_years"] = expected_years

    strengths = [str(item) for item in clean.get("allowed_conclusion_strengths") or []]
    strengths = [item for item in strengths if item in QUERY_CONTRACT_SCHEMA["properties"]["allowed_conclusion_strengths"]["items"]["enum"]]
    if not strengths:
        strengths = ["moderate_with_caveats", "disclosure_quality_only", "insufficient_evidence"]
        notes.append("filled_allowed_conclusion_strengths")
    clean["allowed_conclusion_strengths"] = _unique_strings(strengths)[:4]

    fallback_families = _fallback_metric_families(clean, package)
    families = _valid_metric_families(clean.get("required_metric_families") or [])
    if not families:
        families = fallback_families
        notes.append("filled_required_metric_families")
    clean["required_metric_families"] = families[:12]

    facets = clean.get("facets") if isinstance(clean.get("facets"), list) else []
    if not isinstance(clean.get("facets"), list):
        notes.append("replaced_non_array_facets")
    normalized_facets: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for idx, facet in enumerate(facets[:6], start=1):
        if not isinstance(facet, dict):
            notes.append(f"dropped_non_object_facet_{idx}")
            continue
        normalized_facets.append(
            _sanitize_facet(
                facet,
                idx,
                expected_companies,
                expected_years,
                clean["required_metric_families"],
                used_ids,
                notes,
            )
        )
    while len(normalized_facets) < 3:
        idx = len(normalized_facets) + 1
        normalized_facets.append(
            _sanitize_facet(
                {
                    "facet_id": f"coverage_caveat_{idx}",
                    "facet_zh": "覆盖和披露口径 caveat",
                    "priority": "caveat" if idx == 3 else "supporting",
                    "required_coverage": {
                        "companies": expected_companies,
                        "years": expected_years,
                        "metric_families": clean["required_metric_families"][:4],
                    },
                    "missing_downgrade_rule_zh": "如果缺少同口径披露，只能比较披露质量或 proxy，不能给强排序。",
                    "allowed_driver_roles": ["caveat_driver"],
                },
                idx,
                expected_companies,
                expected_years,
                clean["required_metric_families"],
                used_ids,
                notes,
            )
        )
        notes.append(f"added_fallback_facet_{idx}")
    if not any(facet.get("priority") == "primary" for facet in normalized_facets):
        normalized_facets[0]["priority"] = "primary"
        normalized_facets[0]["allowed_driver_roles"] = ["core_driver", "supporting_context"]
        notes.append("promoted_first_facet_to_primary")
    if not any(facet.get("priority") == "caveat" for facet in normalized_facets):
        normalized_facets[-1]["priority"] = "caveat"
        normalized_facets[-1]["allowed_driver_roles"] = ["caveat_driver", "supporting_context"]
        notes.append("converted_last_facet_to_caveat")
    clean["facets"] = normalized_facets

    rules = []
    for idx, rule in enumerate(clean.get("comparability_rules") or [], start=1):
        if not isinstance(rule, dict):
            notes.append(f"dropped_non_object_comparability_rule_{idx}")
            continue
        rule_families = _valid_metric_families(rule.get("metric_families") or [])
        if not rule_families:
            notes.append(f"dropped_empty_comparability_rule_{idx}")
            continue
        rules.append(
            {
                "rule_id": _safe_id(str(rule.get("rule_id") or f"comparability_rule_{idx}"))[:80],
                "metric_families": rule_families[:6],
                "rule_zh": str(rule.get("rule_zh") or "相关指标口径不同，不能直接横比。")[:260],
            }
        )
    if not rules:
        rules = _heuristic_comparability_rules(clean["required_metric_families"])
    clean["comparability_rules"] = rules[:6]

    if clean.get("planner_confidence") not in {"high", "medium", "low"}:
        clean["planner_confidence"] = "medium"
        notes.append("filled_planner_confidence")
    caveats = [str(item)[:220] for item in clean.get("planner_caveats_zh") or [] if str(item).strip()]
    if notes:
        caveats.append("系统已将 planner coverage 约束回 eval metadata 范围；历史背景只能作为 caveat/secondary context，不能作为 required coverage。")
    clean["planner_caveats_zh"] = _unique_strings(caveats)[:6]
    return clean, notes


def _sanitize_facet(
    facet: dict[str, Any],
    idx: int,
    expected_companies: list[str],
    expected_years: list[int],
    fallback_families: list[str],
    used_ids: set[str],
    notes: list[str],
) -> dict[str, Any]:
    facet_id = _safe_id(str(facet.get("facet_id") or f"facet_{idx}"))[:80]
    if not facet_id:
        facet_id = f"facet_{idx}"
    base_id = facet_id
    suffix = 2
    while facet_id in used_ids:
        facet_id = f"{base_id}_{suffix}"[:80]
        suffix += 1
    used_ids.add(facet_id)

    priority = str(facet.get("priority") or "")
    if priority not in {"primary", "supporting", "caveat"}:
        priority = "primary" if idx <= 2 else "supporting"
        notes.append(f"filled_facet_priority_{idx}")
    coverage = facet.get("required_coverage") if isinstance(facet.get("required_coverage"), dict) else {}
    cov_companies = _unique_strings([str(item).upper() for item in coverage.get("companies") or []])
    kept_companies = [item for item in cov_companies if item in expected_companies]
    if len(kept_companies) != len(cov_companies):
        notes.append(f"clamped_facet_companies_{idx}")
    if not kept_companies:
        kept_companies = expected_companies
        notes.append(f"filled_facet_companies_{idx}")

    raw_years = [_coerce_int(item) for item in coverage.get("years") or []]
    cov_years = sorted({year for year in raw_years if year})
    kept_years = [year for year in cov_years if year in expected_years]
    if len(kept_years) != len(cov_years):
        notes.append(f"clamped_facet_years_{idx}")
    if not kept_years:
        kept_years = expected_years
        notes.append(f"filled_facet_years_{idx}")

    cov_families = _valid_metric_families(coverage.get("metric_families") or [])
    if not cov_families:
        cov_families = fallback_families[:4]
        notes.append(f"filled_facet_metric_families_{idx}")

    roles = [str(item) for item in facet.get("allowed_driver_roles") or []]
    roles = [item for item in roles if item in {"core_driver", "supporting_context", "caveat_driver"}]
    if not roles:
        roles = ["caveat_driver", "supporting_context"] if priority == "caveat" else ["core_driver", "supporting_context"]
        notes.append(f"filled_facet_driver_roles_{idx}")

    downgrade_rule = str(facet.get("missing_downgrade_rule_zh") or "").strip()
    if not downgrade_rule:
        downgrade_rule = "如果该 facet 缺少公司/年份/指标族覆盖，必须降低结论强度，不能写成无条件全局排序。"
        notes.append(f"filled_missing_downgrade_rule_{idx}")

    return {
        "facet_id": facet_id,
        "facet_zh": str(facet.get("facet_zh") or f"facet {idx}")[:120],
        "priority": priority,
        "required_coverage": {
            "companies": kept_companies,
            "years": kept_years,
            "metric_families": cov_families[:8],
        },
        "missing_downgrade_rule_zh": downgrade_rule[:260],
        "allowed_driver_roles": _unique_strings(roles)[:4],
    }


def _fallback_metric_families(contract: dict[str, Any], package: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    candidates.extend(_valid_metric_families(contract.get("required_metric_families") or []))
    for facet in contract.get("facets") or []:
        if isinstance(facet, dict):
            coverage = facet.get("required_coverage") if isinstance(facet.get("required_coverage"), dict) else {}
            candidates.extend(_valid_metric_families(coverage.get("metric_families") or []))
            candidates.extend(sorted(_infer_metric_families(" ".join([str(facet.get("facet_id") or ""), str(facet.get("facet_zh") or "")]))))
    for item in package.get("evidence_needs") or []:
        candidates.extend(_valid_metric_families(item.get("metric_family_hints") or []))
        candidates.extend(sorted(_infer_metric_families(" ".join([str(item.get("facet") or ""), " ".join(item.get("must_find") or [])]))))
    for facet in package.get("grouped_facets") or []:
        candidates.extend(_valid_metric_families(facet.get("metric_family_hints") or []))
    candidates.extend(sorted(_infer_metric_families(" ".join([str(package.get("query_zh") or ""), str(package.get("evaluation_intent") or "")]))))
    return _unique_strings(candidates)[:12] or ["operating_income"]


def _valid_metric_families(items: list[Any]) -> list[str]:
    return _unique_strings([str(item) for item in items if str(item) in METRIC_FAMILY_ALLOWLIST])


def _unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:
        if item and item not in seen:
            values.append(item)
            seen.add(item)
    return values


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _heuristic_contract(package: dict[str, Any]) -> dict[str, Any]:
    families = sorted(
        set().union(
            *[
                _infer_metric_families(" ".join([str(facet), str(package.get("query_zh") or "")]))
                for facet in package.get("ideal_facets") or []
            ],
            *[
                set(item.get("metric_family_hints") or [])
                for item in package.get("evidence_needs") or []
            ],
        )
    ) or ["operating_income"]
    facets = []
    source_items = package.get("evidence_needs") or [
        {"facet": _safe_id(item), "must_find": [item], "metric_family_hints": sorted(_infer_metric_families(item))}
        for item in (package.get("ideal_facets") or [])[:6]
    ]
    for idx, item in enumerate(source_items[:6], start=1):
        facet_id = _safe_id(str(item.get("facet") or f"facet_{idx}"))
        hints = list(dict.fromkeys(item.get("metric_family_hints") or sorted(_infer_metric_families(" ".join(item.get("must_find") or [])))))
        if not hints:
            hints = families[:2]
        priority = "primary" if idx <= 3 else "caveat" if "caveat" in facet_id or "compar" in facet_id else "supporting"
        facets.append(
            {
                "facet_id": facet_id[:80],
                "facet_zh": _facet_label(item, idx),
                "priority": priority,
                "required_coverage": {
                    "companies": [str(ticker).upper() for ticker in package.get("tickers") or []],
                    "years": [int(year) for year in package.get("fiscal_years") or []],
                    "metric_families": hints[:6],
                },
                "missing_downgrade_rule_zh": "如果该 facet 缺少公司/年份/指标族覆盖，必须降低结论强度，不能写成无条件全局排序。",
                "allowed_driver_roles": ["core_driver", "supporting_context"]
                if priority != "caveat"
                else ["caveat_driver", "supporting_context"],
            }
        )
    while len(facets) < 3:
        facets.append(
            {
                "facet_id": f"coverage_caveat_{len(facets) + 1}",
                "facet_zh": "覆盖和披露口径 caveat",
                "priority": "caveat",
                "required_coverage": {
                    "companies": [str(ticker).upper() for ticker in package.get("tickers") or []],
                    "years": [int(year) for year in package.get("fiscal_years") or []],
                    "metric_families": families[:4],
                },
                "missing_downgrade_rule_zh": "如果缺少同口径披露，只能比较披露质量或 proxy，不能给强排序。",
                "allowed_driver_roles": ["caveat_driver"],
            }
        )
    return {
        "query_id": str(package.get("query_id")),
        "task_profile": "complex_insight",
        "target_judgment_zh": str(package.get("evaluation_intent") or package.get("query_zh") or "")[:240],
        "required_companies": [str(ticker).upper() for ticker in package.get("tickers") or []],
        "required_years": [int(year) for year in package.get("fiscal_years") or []],
        "allowed_conclusion_strengths": ["strong_with_caveats", "moderate_with_caveats", "disclosure_quality_only"],
        "required_metric_families": families[:12],
        "facets": facets[:6],
        "comparability_rules": _heuristic_comparability_rules(families),
        "planner_confidence": "medium",
        "planner_caveats_zh": [
            "这是 Query Contract，不是最终答案；后续 Evidence Pack 必须用 citation evidence 和 exact-value ledger 证明每个 driver。"
        ],
    }


def _heuristic_comparability_rules(families: list[str]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    visibility = [item for item in ["rpo", "arr_or_recurring_proxy", "deferred_revenue", "billings"] if item in families]
    if len(visibility) >= 2:
        rules.append(
            {
                "rule_id": "visibility_proxy_not_same_metric",
                "metric_families": visibility,
                "rule_zh": "这些只能作为收入可见性的不同 proxy，不能当成同一个指标直接横比。",
            }
        )
    capex = [item for item in ["capex", "cash_flow", "depreciation_amortization"] if item in families]
    if len(capex) >= 2:
        rules.append(
            {
                "rule_id": "capex_cashflow_not_same_metric",
                "metric_families": capex,
                "rule_zh": "资本开支、现金流和折旧摊销属于不同口径，只能共同说明投入压力，不能互相替代。",
            }
        )
    profitability = [item for item in ["cloud_revenue", "operating_income", "operating_margin", "gross_margin"] if item in families]
    if len(profitability) >= 2:
        rules.append(
            {
                "rule_id": "growth_not_profitability",
                "metric_families": profitability,
                "rule_zh": "收入增长和利润率/经营利润需要分开判断，不能把增长直接当成盈利质量证据。",
            }
        )
    return rules[:6]


def _facet_label(item: dict[str, Any], idx: int) -> str:
    text = str(item.get("facet") or f"facet_{idx}").replace("_", " ")
    if item.get("must_find"):
        text = f"{text}: {', '.join(str(x) for x in item.get('must_find')[:2])}"
    return text[:120]


def _infer_metric_families(text: str) -> set[str]:
    lower = text.lower()
    families: set[str] = set()
    patterns = [
        ("advertising_revenue", r"\badvertis"),
        ("services_revenue", r"\bservices?\b|app store"),
        ("subscription_revenue", r"subscription|subscriptions"),
        ("cloud_revenue", r"cloud|azure|aws|google cloud"),
        ("datacenter_revenue", r"data center|datacenter|compute"),
        ("capex", r"capex|capital expenditure|property and equipment|technical infrastructure|ppe|pp&e"),
        ("infrastructure_cost", r"infrastructure cost|usage cost|technical infrastructure"),
        ("operating_income", r"operating income|income from operations|segment income"),
        ("operating_margin", r"operating margin|margin pressure"),
        ("gross_margin", r"gross margin|gross profit"),
        ("cash_flow", r"free cash flow|cash flow|net cash|operating activities|investing activities"),
        ("rpo", r"remaining performance obligations|\brpo\b"),
        ("arr_or_recurring_proxy", r"\barr\b|annual recurring"),
        ("deferred_revenue", r"deferred revenue"),
        ("billings", r"billings"),
        ("customer_retention", r"net revenue retention|\bnrr\b|customer"),
        ("customer_concentration", r"customer concentration|direct customers|indirect customers"),
        ("supply_chain_risk", r"supply|foundry|supplier|contract manufacturer|capacity"),
        ("product_cycle", r"product transition|product cycle|accelerator|new products"),
        ("inventory", r"inventory"),
        ("depreciation_amortization", r"depreciation|amortization"),
    ]
    for family, pattern in patterns:
        if re.search(pattern, lower):
            families.add(family)
    if "revenue" in lower or "sales" in lower:
        if not families.intersection(
            {"advertising_revenue", "services_revenue", "subscription_revenue", "cloud_revenue", "datacenter_revenue"}
        ):
            families.add("operating_income")
    return families


def _package_metrics(package: dict[str, Any]) -> dict[str, Any]:
    metric_counter = Counter(
        family for facet in package.get("grouped_facets") or [] for family in facet.get("metric_family_hints") or []
    )
    return {
        "ideal_facet_count": len(package.get("ideal_facets") or []),
        "evidence_need_count": len(package.get("evidence_needs") or []),
        "grouped_facet_count": len(package.get("grouped_facets") or []),
        "metric_family_hint_counts": dict(sorted(metric_counter.items())),
    }


def _write_report(
    output_path: Path,
    args: argparse.Namespace,
    results: list[dict[str, Any]],
    timings: dict[str, float],
    started: float,
    *,
    partial: bool,
) -> None:
    report = {
        "schema_version": "query_contract_planner_v0.1",
        "partial": partial,
        "run_profile": {
            "model_path": args.model_path,
            "hardware_profile": getattr(args, "hardware_profile_metadata", {}),
            "resident_model_enabled": not args.disable_vllm,
            "max_model_len": args.max_model_len,
            "max_tokens": args.max_tokens,
            "structured_json": args.structured_json,
            "dtype": args.dtype,
            "quantization": args.quantization,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "cpu_offload_gb": args.cpu_offload_gb,
            "max_num_seqs": args.max_num_seqs,
        },
        "inputs": {
            "eval_path": str((REPO_ROOT / args.eval_path).resolve()),
            "grouped_pool_path": str((REPO_ROOT / args.grouped_pool_path).resolve()),
        },
        "summary": {
            "query_count": len(results),
            "parse_status_counts": dict(Counter(str(row.get("parse_status")) for row in results)),
            "facet_count": sum(len((row.get("query_contract") or {}).get("facets") or []) for row in results),
        },
        "timings": timings | {"total_sec": round(time.time() - started, 4)},
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_rows(rows: list[dict[str, Any]], query_ids: set[str], limit: int) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if str(row.get("scoring_profile") or row.get("cohort")) == "complex_insight"
        and (not query_ids or str(row.get("query_id")) in query_ids)
    ]
    if limit > 0:
        selected = selected[:limit]
    return selected


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_") or "facet"


if __name__ == "__main__":
    main()
