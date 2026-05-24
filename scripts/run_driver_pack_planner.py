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


CONCLUSION_STRENGTHS = [
    "strong_with_caveats",
    "moderate_with_caveats",
    "weak_only",
    "disclosure_quality_only",
    "insufficient_evidence",
]
DRIVER_STRENGTHS = ["strong", "moderate", "weak", "caveated", "insufficient"]


DRIVER_PACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "query_id",
        "thesis_candidate_zh",
        "conclusion_strength",
        "decision_drivers",
        "secondary_context",
        "limiting_caveats",
        "missing_primary_facets",
    ],
    "properties": {
        "query_id": {"type": "string", "maxLength": 160},
        "thesis_candidate_zh": {"type": "string", "maxLength": 280},
        "conclusion_strength": {"type": "string", "enum": CONCLUSION_STRENGTHS},
        "decision_drivers": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "driver_id",
                    "rank",
                    "driver_claim_zh",
                    "why_it_matters_zh",
                    "supporting_contract_ids",
                    "supporting_metric_ids",
                    "covered_companies",
                    "covered_years",
                    "covered_facets",
                    "metric_families",
                    "counter_evidence_or_caveat_zh",
                    "conclusion_strength",
                    "global_claim_allowed",
                ],
                "properties": {
                    "driver_id": {"type": "string", "maxLength": 80},
                    "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                    "driver_claim_zh": {"type": "string", "maxLength": 240},
                    "why_it_matters_zh": {"type": "string", "maxLength": 240},
                    "supporting_contract_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 10,
                        "items": {"type": "string", "maxLength": 180},
                    },
                    "supporting_metric_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 180},
                    },
                    "covered_companies": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 12},
                    },
                    "covered_years": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {"type": "integer", "minimum": 1990, "maximum": 2100},
                    },
                    "covered_facets": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {"type": "string", "maxLength": 90},
                    },
                    "metric_families": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {"type": "string", "maxLength": 80},
                    },
                    "counter_evidence_or_caveat_zh": {"type": "string", "maxLength": 260},
                    "conclusion_strength": {"type": "string", "enum": DRIVER_STRENGTHS},
                    "global_claim_allowed": {"type": "boolean"},
                },
            },
        },
        "secondary_context": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["context_zh", "supporting_contract_ids", "why_secondary_zh"],
                "properties": {
                    "context_zh": {"type": "string", "maxLength": 240},
                    "supporting_contract_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 180},
                    },
                    "why_secondary_zh": {"type": "string", "maxLength": 220},
                },
            },
        },
        "limiting_caveats": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["caveat_zh", "affected_driver_ids", "downgrade_effect_zh", "supporting_contract_ids"],
                "properties": {
                    "caveat_zh": {"type": "string", "maxLength": 260},
                    "affected_driver_ids": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {"type": "string", "maxLength": 80},
                    },
                    "downgrade_effect_zh": {"type": "string", "maxLength": 240},
                    "supporting_contract_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {"type": "string", "maxLength": 180},
                    },
                },
            },
        },
        "missing_primary_facets": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["facet_id", "missing_coverage", "impact_on_conclusion_zh"],
                "properties": {
                    "facet_id": {"type": "string", "maxLength": 90},
                    "missing_coverage": {"type": "string", "maxLength": 260},
                    "impact_on_conclusion_zh": {"type": "string", "maxLength": 260},
                },
            },
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan Decision Driver Evidence Packs from compact candidates.")
    parser.add_argument(
        "--candidate-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json",
    )
    parser.add_argument(
        "--output",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs.json",
    )
    parser.add_argument("--model-path", default="data/models_private/modelscope/Qwen/Qwen3___5-9B")
    parser.add_argument("--query-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--max-tokens", type=int, default=2600)
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
    vllm_hardware_profiles.apply_hardware_profile(args, workload="driver_pack_planner")
    return args


def main() -> None:
    args = parse_args()
    started = time.time()
    candidate_payload = _read_json(REPO_ROOT / args.candidate_path)
    selected = _select_queries(candidate_payload.get("queries") or [], set(args.query_id), args.limit)
    output_path = REPO_ROOT / args.output

    llm = None
    tokenizer = None
    timings = {"load_inputs_sec": round(time.time() - started, 4)}
    if not args.disable_vllm:
        t_model = time.time()
        llm, tokenizer = _load_vllm(args)
        timings["load_model_sec"] = round(time.time() - t_model, 4)

    results = []
    for query in selected:
        query_started = time.time()
        prompt = _make_prompt(query)
        prompt_tokens = _prompt_token_count(tokenizer, prompt)
        if args.disable_vllm:
            pack = _heuristic_pack(query)
            raw_output = json.dumps(pack, ensure_ascii=False)
            parse_status = "heuristic"
        else:
            raw_output = _generate_one(
                llm,
                prompt,
                max_tokens=args.max_tokens,
                temperature=0.0,
                structured_schema=DRIVER_PACK_SCHEMA if args.structured_json else None,
            )
            try:
                pack = _extract_json(raw_output)
                parse_status = "parsed"
            except Exception as exc:  # noqa: BLE001
                pack = _heuristic_pack(query)
                pack["limiting_caveats"].append(
                    {
                        "caveat_zh": f"Driver Pack planner parse failed: {type(exc).__name__}",
                        "affected_driver_ids": [driver.get("driver_id") for driver in pack.get("decision_drivers") or []],
                        "downgrade_effect_zh": "本次 pack 使用 deterministic fallback，结论强度不得提升。",
                        "supporting_contract_ids": [],
                    }
                )
                parse_status = "parse_error_fallback"
        pack = _normalize_pack(pack, query, parse_status=parse_status)
        results.append(
            {
                "query_id": query.get("query_id"),
                "prompt_tokens": prompt_tokens,
                "prompt_chars": len(prompt),
                "parse_status": parse_status,
                "normalization_status": "normalized_v0.1",
                "driver_pack": pack,
                "raw_output": raw_output,
                "elapsed_sec": round(time.time() - query_started, 4),
            }
        )
        _write_report(output_path, args, candidate_payload, results, timings, started, partial=True)
        print(
            json.dumps(
                {
                    "query_id": query.get("query_id"),
                    "parse_status": parse_status,
                    "drivers": len(pack.get("decision_drivers") or []),
                    "elapsed_sec": results[-1]["elapsed_sec"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    _write_report(output_path, args, candidate_payload, results, timings, started, partial=False)
    print(json.dumps({"output": str(output_path), "queries": len(results)}, ensure_ascii=False), flush=True)


def _make_prompt(query: dict[str, Any]) -> str:
    compact = {
        "query_id": query.get("query_id"),
        "query_contract": query.get("query_contract"),
        "candidate_facets": query.get("candidate_facets"),
    }
    return (
        "你是金融证据约束框架的 Decision Driver Evidence Pack planner。你的任务不是写最终答案，而是从候选证据中选择最多 3 个支配结论的 driver。\n"
        "只返回 JSON，必须符合 schema。\n"
        "硬规则：\n"
        "1. decision_drivers 最多 3 条，必须按重要性排序。\n"
        "2. supporting_contract_ids 和 supporting_metric_ids 只能使用输入 candidate 中出现的 ID，不能编造。\n"
        "3. core driver 只能使用 citation evidence；background evidence 只能进入 secondary_context 或 caveat。\n"
        "4. driver_claim_zh / why_it_matters_zh / caveat_zh 不要写精确数字；精确数字只能通过 supporting_metric_ids 交给后续 synthesis。\n"
        "5. global_claim_allowed=true 只有在支撑证据覆盖 query required companies 和 required years 时才允许。\n"
        "6. RPO/ARR/deferred revenue/billings 等 proxy 不可互相等同；公司级 capex 不可直接推断 AI/cloud ROI。\n"
        "7. 如果 primary facet 缺公司、年份或关键 metric family 覆盖，必须写入 missing_primary_facets 或 limiting_caveats，并降低 conclusion_strength。\n"
        "8. thesis_candidate_zh 是一句候选判断，不是最终答案，不要堆证据细节。\n\n"
        f"输入：\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
    )


def _heuristic_pack(query: dict[str, Any]) -> dict[str, Any]:
    contract = query.get("query_contract") or {}
    facets = query.get("candidate_facets") or []
    primary_facets = [facet for facet in facets if facet.get("priority") == "primary" and facet.get("candidate_contracts")]
    if not primary_facets:
        primary_facets = [facet for facet in facets if facet.get("candidate_contracts")]
    drivers = []
    for rank, facet in enumerate(primary_facets[:3], start=1):
        contracts = [
            item
            for item in facet.get("candidate_contracts") or []
            if item.get("evidence_role") == "citation" and item.get("core_fact_allowed")
        ][:8]
        metrics = (facet.get("candidate_metrics") or [])[:6]
        companies = sorted({str(item.get("ticker")) for item in contracts if item.get("ticker")})
        years = sorted({_to_int(item.get("fiscal_year")) for item in contracts if _to_int(item.get("fiscal_year"))})
        families = sorted(
            {
                str(family)
                for item in contracts
                for family in item.get("metric_families") or []
                if family != "unknown"
            }
            | {str(item.get("metric_family")) for item in metrics if item.get("metric_family")}
        )
        missing = facet.get("missing_coverage") or {}
        global_claim_allowed = _covers_required(companies, years, contract)
        driver_id = f"driver_{rank}_{facet.get('facet_id')}"
        drivers.append(
            {
                "driver_id": driver_id[:80],
                "rank": rank,
                "driver_claim_zh": f"{facet.get('facet_zh') or facet.get('facet_id')} 是主判断中的关键证据维度。",
                "why_it_matters_zh": "该维度直接决定结论是否有足够的公司、年份和指标口径支撑。",
                "supporting_contract_ids": [item.get("contract_id") for item in contracts if item.get("contract_id")],
                "supporting_metric_ids": [item.get("metric_id") for item in metrics if item.get("metric_id")],
                "covered_companies": companies,
                "covered_years": years,
                "covered_facets": [facet.get("facet_id")],
                "metric_families": families[:12],
                "counter_evidence_or_caveat_zh": _facet_caveat_text(facet, missing),
                "conclusion_strength": "moderate" if contracts else "weak",
                "global_claim_allowed": bool(global_claim_allowed),
            }
        )
    secondary_context = []
    for facet in [item for item in facets if item.get("priority") == "supporting"][:3]:
        contracts = [item for item in facet.get("candidate_contracts") or [] if item.get("evidence_role") == "citation"][:4]
        if not contracts:
            continue
        secondary_context.append(
            {
                "context_zh": f"{facet.get('facet_zh') or facet.get('facet_id')} 可作为辅助背景。",
                "supporting_contract_ids": [item.get("contract_id") for item in contracts if item.get("contract_id")],
                "why_secondary_zh": "它补充主结论，但不足以单独改变 thesis。",
            }
        )
    limiting_caveats = []
    for facet in [item for item in facets if item.get("priority") == "caveat"][:4]:
        contracts = [item for item in facet.get("candidate_contracts") or [] if item.get("evidence_role") == "citation"][:4]
        limiting_caveats.append(
            {
                "caveat_zh": f"{facet.get('facet_zh') or facet.get('facet_id')} 限制结论强度。",
                "affected_driver_ids": [driver.get("driver_id") for driver in drivers],
                "downgrade_effect_zh": facet.get("missing_downgrade_rule_zh") or "如口径不可比或缺证，结论应降级。",
                "supporting_contract_ids": [item.get("contract_id") for item in contracts if item.get("contract_id")],
            }
        )
    missing_primary_facets = []
    for facet in [item for item in facets if item.get("priority") == "primary"]:
        missing = facet.get("missing_coverage") or {}
        if any(missing.get(key) for key in ("companies", "years", "metric_families")):
            missing_primary_facets.append(
                {
                    "facet_id": facet.get("facet_id"),
                    "missing_coverage": json.dumps(missing, ensure_ascii=False),
                    "impact_on_conclusion_zh": facet.get("missing_downgrade_rule_zh") or "缺少 primary facet 覆盖时必须降低结论强度。",
                }
            )
    return {
        "query_id": query.get("query_id"),
        "thesis_candidate_zh": str(contract.get("target_judgment_zh") or "证据支持谨慎判断，但需受覆盖和口径限制。")[:260],
        "conclusion_strength": _top_level_strength(contract, drivers, missing_primary_facets),
        "decision_drivers": drivers or [
            {
                "driver_id": "driver_1_insufficient_evidence",
                "rank": 1,
                "driver_claim_zh": "当前候选证据不足以形成稳定 driver。",
                "why_it_matters_zh": "缺少 citation evidence 或 metric ledger 支撑。",
                "supporting_contract_ids": [],
                "supporting_metric_ids": [],
                "covered_companies": [],
                "covered_years": [],
                "covered_facets": [],
                "metric_families": [],
                "counter_evidence_or_caveat_zh": "需要补充 citation evidence。",
                "conclusion_strength": "insufficient",
                "global_claim_allowed": False,
            }
        ],
        "secondary_context": secondary_context,
        "limiting_caveats": limiting_caveats,
        "missing_primary_facets": missing_primary_facets,
    }


def _normalize_pack(pack: dict[str, Any], query: dict[str, Any], *, parse_status: str) -> dict[str, Any]:
    """Trust model judgment text only; rebuild factual support from candidate facets."""

    contract = query.get("query_contract") or {}
    facets = query.get("candidate_facets") or []
    primary_facets = [facet for facet in facets if facet.get("priority") == "primary"]
    supporting_facets = [facet for facet in facets if facet.get("priority") == "supporting"]
    caveat_facets = [facet for facet in facets if facet.get("priority") == "caveat"]
    model_drivers = [driver for driver in pack.get("decision_drivers") or [] if isinstance(driver, dict)]
    driver_by_facet = _map_model_drivers_to_facets(model_drivers, primary_facets)
    ranked_facets = _rank_primary_facets(model_drivers, primary_facets, driver_by_facet)

    drivers: list[dict[str, Any]] = []
    for rank, facet in enumerate(ranked_facets[:3], start=1):
        model_driver = driver_by_facet.get(str(facet.get("facet_id"))) or {}
        drivers.append(_driver_from_facet(facet, model_driver, rank, contract))

    missing_primary_facets = _missing_primary_facets(primary_facets)
    secondary_context = _secondary_context_from_facets(supporting_facets)
    limiting_caveats = _limiting_caveats_from_facets(caveat_facets, drivers)
    if parse_status != "parsed":
        limiting_caveats.append(
            {
                "caveat_zh": "Driver Pack planner output did not parse cleanly; factual support was rebuilt from candidate evidence.",
                "affected_driver_ids": [str(driver.get("driver_id")) for driver in drivers],
                "downgrade_effect_zh": "Use this pack as diagnostic evidence; final synthesis should not upgrade conclusion strength based on planner prose alone.",
                "supporting_contract_ids": [],
            }
        )

    top_strength = _normalized_top_level_strength(pack, contract, missing_primary_facets)
    return {
        "query_id": query.get("query_id"),
        "thesis_candidate_zh": _sanitize_pack_text(
            str(pack.get("thesis_candidate_zh") or contract.get("target_judgment_zh") or "证据支持谨慎判断，但需受覆盖和口径限制。"),
            260,
        ),
        "conclusion_strength": top_strength,
        "decision_drivers": drivers or _heuristic_pack(query).get("decision_drivers", []),
        "secondary_context": secondary_context,
        "limiting_caveats": limiting_caveats[:6],
        "missing_primary_facets": missing_primary_facets,
    }


def _map_model_drivers_to_facets(model_drivers: list[dict[str, Any]], facets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for driver in model_drivers:
        for facet in _infer_driver_facets(driver, facets):
            facet_id = str(facet.get("facet_id"))
            mapping.setdefault(facet_id, driver)
    return mapping


def _rank_primary_facets(
    model_drivers: list[dict[str, Any]],
    primary_facets: list[dict[str, Any]],
    driver_by_facet: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for driver in model_drivers:
        for facet in _infer_driver_facets(driver, primary_facets):
            if facet not in ranked:
                ranked.append(facet)
    for facet in primary_facets:
        if str(facet.get("facet_id")) in driver_by_facet and facet not in ranked:
            ranked.append(facet)
    for facet in primary_facets:
        if facet not in ranked:
            ranked.append(facet)
    return ranked


def _infer_driver_facets(driver: dict[str, Any], facets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claimed = {str(item) for item in driver.get("covered_facets") or []}
    text = " ".join(
        str(item or "")
        for item in [
            driver.get("driver_id"),
            driver.get("driver_claim_zh"),
            driver.get("why_it_matters_zh"),
            driver.get("counter_evidence_or_caveat_zh"),
        ]
    ).lower()
    matches: list[tuple[int, dict[str, Any]]] = []
    for facet in facets:
        facet_id = str(facet.get("facet_id") or "")
        facet_zh = str(facet.get("facet_zh") or "")
        score = 0
        if facet_id in claimed:
            score += 100
        if facet_id and facet_id.lower() in text:
            score += 80
        if facet_zh and facet_zh in text:
            score += 80
        tokens = [token for token in facet_id.lower().split("_") if len(token) >= 4]
        token_hits = sum(1 for token in tokens if token in text)
        if tokens and token_hits == len(tokens):
            score += 20
        if score > 0:
            matches.append((score, facet))
    matches.sort(key=lambda item: item[0], reverse=True)
    return [facet for _, facet in matches]


def _driver_from_facet(
    facet: dict[str, Any],
    model_driver: dict[str, Any],
    rank: int,
    contract: dict[str, Any],
) -> dict[str, Any]:
    contracts = _core_contracts(facet, 10)
    metrics = _metrics(facet, 8)
    companies = sorted({str(item.get("ticker")) for item in contracts if item.get("ticker")})
    years = sorted({_to_int(item.get("fiscal_year")) for item in contracts if _to_int(item.get("fiscal_year"))})
    families = sorted(
        {
            str(family)
            for item in contracts
            for family in item.get("metric_families") or []
            if family != "unknown"
        }
        | {str(item.get("metric_family")) for item in metrics if item.get("metric_family")}
    )
    facet_id = str(facet.get("facet_id") or f"facet_{rank}")
    claim = model_driver.get("driver_claim_zh") or f"{facet.get('facet_zh') or facet_id} 是主判断中的关键证据维度。"
    why = model_driver.get("why_it_matters_zh") or "该维度决定结论是否有足够的公司、年份和指标口径支撑。"
    caveat = model_driver.get("counter_evidence_or_caveat_zh") or _facet_caveat_text(facet, facet.get("missing_coverage") or {})
    return {
        "driver_id": f"driver_{rank}_{facet_id}"[:80],
        "rank": rank,
        "driver_claim_zh": _sanitize_pack_text(str(claim), 220),
        "why_it_matters_zh": _sanitize_pack_text(str(why), 220),
        "supporting_contract_ids": [item.get("contract_id") for item in contracts if item.get("contract_id")],
        "supporting_metric_ids": [item.get("metric_id") for item in metrics if item.get("metric_id")],
        "covered_companies": companies,
        "covered_years": years,
        "covered_facets": [facet_id],
        "metric_families": families[:12],
        "counter_evidence_or_caveat_zh": _sanitize_pack_text(str(caveat), 240),
        "conclusion_strength": _normalized_driver_strength(model_driver, contracts),
        "global_claim_allowed": bool(_covers_required(companies, years, contract)),
    }


def _core_contracts(facet: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    contracts = [
        item
        for item in facet.get("candidate_contracts") or []
        if item.get("evidence_role") == "citation" and item.get("core_fact_allowed")
    ]
    required = facet.get("required_coverage") or {}
    contracts = _filter_by_required_scope(contracts, required)
    return _balanced_items(contracts, limit)


def _metrics(facet: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    metrics = [item for item in facet.get("candidate_metrics") or [] if item.get("metric_id")]
    required = facet.get("required_coverage") or {}
    metrics = _filter_by_required_scope(metrics, required)
    return _balanced_items(metrics, limit)


def _filter_by_required_scope(items: list[dict[str, Any]], required: dict[str, Any]) -> list[dict[str, Any]]:
    scoped = items
    required_companies = {str(item) for item in required.get("companies") or []}
    required_years = {_to_int(item) for item in required.get("years") or [] if _to_int(item)}
    required_families = {str(item) for item in required.get("metric_families") or []}
    if required_companies:
        filtered = [item for item in scoped if str(item.get("ticker")) in required_companies]
        if filtered:
            scoped = filtered
    if required_years:
        filtered = [item for item in scoped if _to_int(item.get("fiscal_year")) in required_years]
        if filtered:
            scoped = filtered
    if required_families:
        filtered = [
            item
            for item in scoped
            if str(item.get("metric_family")) in required_families
            or bool(required_families & {str(family) for family in item.get("metric_families") or []})
        ]
        if filtered:
            scoped = filtered
    return scoped


def _balanced_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int | None]] = set()
    for item in items:
        key = (str(item.get("ticker") or ""), _to_int(item.get("fiscal_year")))
        if key in seen_keys:
            continue
        selected.append(item)
        seen_keys.add(key)
        if len(selected) >= limit:
            return selected
    seen_ids = {str(item.get("contract_id") or item.get("metric_id") or id(item)) for item in selected}
    for item in items:
        item_id = str(item.get("contract_id") or item.get("metric_id") or id(item))
        if item_id in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(item_id)
        if len(selected) >= limit:
            break
    return selected


def _secondary_context_from_facets(facets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for facet in facets[:3]:
        contracts = _core_contracts(facet, 4)
        if not contracts:
            continue
        rows.append(
            {
                "context_zh": _sanitize_pack_text(f"{facet.get('facet_zh') or facet.get('facet_id')} 可作为辅助背景。", 220),
                "supporting_contract_ids": [item.get("contract_id") for item in contracts if item.get("contract_id")],
                "why_secondary_zh": "它补充主结论，但不足以单独改变 thesis。",
            }
        )
    return rows


def _limiting_caveats_from_facets(facets: list[dict[str, Any]], drivers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    affected = [str(driver.get("driver_id")) for driver in drivers]
    for facet in facets[:4]:
        contracts = _core_contracts(facet, 4)
        rows.append(
            {
                "caveat_zh": _sanitize_pack_text(f"{facet.get('facet_zh') or facet.get('facet_id')} 限制结论强度。", 240),
                "affected_driver_ids": affected[:3],
                "downgrade_effect_zh": _sanitize_pack_text(
                    str(facet.get("missing_downgrade_rule_zh") or "如口径不可比或缺证，结论应降级。"),
                    220,
                ),
                "supporting_contract_ids": [item.get("contract_id") for item in contracts if item.get("contract_id")],
            }
        )
    return rows


def _missing_primary_facets(primary_facets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for facet in primary_facets:
        missing = facet.get("missing_coverage") or {}
        if any(missing.get(key) for key in ("companies", "years", "metric_families")):
            rows.append(
                {
                    "facet_id": facet.get("facet_id"),
                    "missing_coverage": json.dumps(missing, ensure_ascii=False),
                    "impact_on_conclusion_zh": facet.get("missing_downgrade_rule_zh") or "缺少 primary facet 覆盖时必须降低结论强度。",
                }
            )
    return rows[:6]


def _normalized_top_level_strength(pack: dict[str, Any], contract: dict[str, Any], missing: list[dict[str, Any]]) -> str:
    allowed = set(contract.get("allowed_conclusion_strengths") or CONCLUSION_STRENGTHS)
    requested = str(pack.get("conclusion_strength") or "")
    if missing and "weak_only" in allowed:
        return "weak_only"
    if requested in allowed:
        return requested
    return _top_level_strength(contract, [], missing)


def _normalized_driver_strength(model_driver: dict[str, Any], contracts: list[dict[str, Any]]) -> str:
    requested = str(model_driver.get("conclusion_strength") or "")
    if requested in DRIVER_STRENGTHS and contracts:
        return requested
    return "moderate" if contracts else "weak"


def _sanitize_pack_text(text: str, max_len: int) -> str:
    text = re.sub(r"\$[\s\d,.]+(?:million|billion)?", "已授权金额", text, flags=re.I)
    text = re.sub(r"\b\d+(?:\.\d+)?%", "已授权比率", text)
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:亿美元|亿|million|billion)", "已授权金额", text, flags=re.I)
    text = re.sub(r"\b\d{1,3},\d{3}(?:,\d{3})*\b", "已授权数值", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _facet_caveat_text(facet: dict[str, Any], missing: dict[str, Any]) -> str:
    if any(missing.get(key) for key in ("companies", "years", "metric_families")):
        return f"该 driver 存在覆盖缺口：{json.dumps(missing, ensure_ascii=False)}。"
    return facet.get("missing_downgrade_rule_zh") or "需要注意披露口径和覆盖范围限制。"


def _top_level_strength(contract: dict[str, Any], drivers: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    allowed = contract.get("allowed_conclusion_strengths") or CONCLUSION_STRENGTHS
    preferred = "weak_only" if missing else "moderate_with_caveats"
    if preferred in allowed:
        return preferred
    return allowed[0] if allowed else preferred


def _covers_required(companies: list[str], years: list[int], contract: dict[str, Any]) -> bool:
    return set(companies) >= set(str(item) for item in contract.get("required_companies") or []) and set(years) >= set(
        _to_int(item) for item in contract.get("required_years") or [] if _to_int(item)
    )


def _write_report(
    output_path: Path,
    args: argparse.Namespace,
    candidate_payload: dict[str, Any],
    results: list[dict[str, Any]],
    timings: dict[str, float],
    started: float,
    *,
    partial: bool,
) -> None:
    report = {
        "schema_version": "driver_pack_planner_v0.1",
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
            "candidate_path": str((REPO_ROOT / args.candidate_path).resolve()),
            "candidate_summary": candidate_payload.get("summary"),
        },
        "summary": {
            "query_count": len(results),
            "parse_status_counts": dict(Counter(str(row.get("parse_status")) for row in results)),
            "driver_count": sum(len((row.get("driver_pack") or {}).get("decision_drivers") or []) for row in results),
        },
        "timings": timings | {"total_sec": round(time.time() - started, 4)},
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_queries(queries: list[dict[str, Any]], query_ids: set[str], limit: int) -> list[dict[str, Any]]:
    selected = [query for query in queries if not query_ids or str(query.get("query_id")) in query_ids]
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
    kwargs = {
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
        kwargs["quantization"] = args.quantization
    if args.language_model_only:
        kwargs["language_model_only"] = True
    if args.skip_mm_profiling:
        kwargs["skip_mm_profiling"] = True
    return LLM(**kwargs), tokenizer


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

    sampling_kwargs = {"max_tokens": max_tokens, "temperature": temperature, "top_p": 1.0}
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


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
