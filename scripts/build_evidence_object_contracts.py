from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


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


FAMILY_PATTERNS: list[tuple[str, str]] = [
    ("advertising_revenue", r"\badvertis|google advertising|family of apps"),
    ("arr_or_recurring_proxy", r"\barr\b|annual recurring"),
    ("billings", r"\bbillings?\b"),
    ("capex", r"capex|capital expenditure|capital expenditures|property and equipment|technical infrastructure|ppe|pp&e|data center|datacenter|servers"),
    ("cash_flow", r"free cash flow|cash flow|net cash provided|operating activities|investing activities"),
    ("cloud_revenue", r"cloud|azure|aws|google cloud"),
    ("customer_concentration", r"customer concentration|direct customers|indirect customers|cloud service providers|csp|customer [a-z]\b|accounted for .*revenue"),
    ("customer_retention", r"net revenue retention|\bnrr\b|remaining customers|customer retention|customers?"),
    ("datacenter_revenue", r"data center|datacenter|compute|accelerator|gpu"),
    ("deferred_revenue", r"deferred revenue"),
    ("depreciation_amortization", r"depreciation|amortization"),
    ("gross_margin", r"gross margin|gross profit"),
    ("infrastructure_cost", r"infrastructure cost|usage cost|technical infrastructure|cost of revenues?|cost of revenue|servers|data centers?"),
    ("inventory", r"\binventory\b|inventories"),
    ("operating_income", r"operating income|income from operations|segment income|operating profit"),
    ("operating_margin", r"operating margin|margin pressure"),
    ("product_cycle", r"product transition|product cycle|new products|accelerator|blackwell|mi300"),
    ("rpo", r"remaining performance obligations|\brpo\b"),
    ("services_revenue", r"\bservices?\b|app store|support revenue"),
    ("subscription_revenue", r"subscription|subscriptions|recognized ratably|subscription and support"),
    ("supply_chain_risk", r"supply|foundry|supplier|contract manufacturer|capacity|guaranteed supply|manufacturing"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic Evidence Object Contracts for Query Contracts.")
    parser.add_argument(
        "--query-contract-path",
        default="reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json",
    )
    parser.add_argument(
        "--grouped-pool-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument(
        "--metrics-path",
        default="data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl",
    )
    parser.add_argument(
        "--tables-path",
        default="data/processed_private/structured_objects/sec_tech_10k_tables.jsonl",
    )
    parser.add_argument(
        "--claims-path",
        default="data/processed_private/structured_objects/sec_tech_10k_claims.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json",
    )
    parser.add_argument(
        "--report-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contract_validation.json",
    )
    parser.add_argument("--max-metrics-per-table", type=int, default=24)
    parser.add_argument("--citation-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query_contract_payload = _read_json(REPO_ROOT / args.query_contract_path)
    grouped_pool = _read_json(REPO_ROOT / args.grouped_pool_path)
    metrics = _read_jsonl(REPO_ROOT / args.metrics_path)
    tables = _read_jsonl(REPO_ROOT / args.tables_path)
    claims = _read_jsonl(REPO_ROOT / args.claims_path)

    metric_by_id = {row["object_id"]: row for row in metrics}
    table_by_id = {row["object_id"]: row for row in tables}
    claim_by_id = {row["object_id"]: row for row in claims}
    metrics_by_table = defaultdict(list)
    for metric in metrics:
        table_id = metric.get("table_object_id")
        if table_id:
            metrics_by_table[str(table_id)].append(metric)

    query_contracts = {
        str(row.get("query_id")): row.get("query_contract") or row
        for row in query_contract_payload.get("results", [])
    }
    selected_query_ids = set(query_contracts)
    grouped_queries = [query for query in grouped_pool.get("queries") or [] if str(query.get("query_id")) in selected_query_ids]

    query_results = []
    all_contracts = []
    for grouped_query in grouped_queries:
        query_id = str(grouped_query.get("query_id"))
        query_contract = query_contracts[query_id]
        contracts = _build_query_contracts(
            grouped_query,
            query_contract,
            metric_by_id,
            table_by_id,
            claim_by_id,
            metrics_by_table,
            max_metrics_per_table=args.max_metrics_per_table,
            citation_only=args.citation_only,
        )
        all_contracts.extend(contracts)
        query_results.append(
            {
                "query_id": query_id,
                "contract_count": len(contracts),
                "facet_coverage": _query_facet_coverage(query_contract, contracts),
                "contracts": contracts,
            }
        )

    report = _report(
        all_contracts,
        query_results,
        args=args,
        query_contracts=query_contracts,
        metrics_path=REPO_ROOT / args.metrics_path,
        tables_path=REPO_ROOT / args.tables_path,
        claims_path=REPO_ROOT / args.claims_path,
    )
    output = {
        "schema_version": "evidence_object_contracts_v0.1",
        "inputs": {
            "query_contract_path": str((REPO_ROOT / args.query_contract_path).resolve()),
            "grouped_pool_path": str((REPO_ROOT / args.grouped_pool_path).resolve()),
            "metrics_path": str((REPO_ROOT / args.metrics_path).resolve()),
            "tables_path": str((REPO_ROOT / args.tables_path).resolve()),
            "claims_path": str((REPO_ROOT / args.claims_path).resolve()),
        },
        "policy": {
            "citation_only": args.citation_only,
            "max_metrics_per_table": args.max_metrics_per_table,
            "background_core_fact_allowed": False,
            "numeric_narrative_source": "exact_value_ledger_only",
        },
        "summary": report["summary"],
        "queries": query_results,
    }
    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = REPO_ROOT / args.report_path
    report["output_path"] = str(output_path.resolve())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))


def _build_query_contracts(
    grouped_query: dict[str, Any],
    query_contract: dict[str, Any],
    metric_by_id: dict[str, dict[str, Any]],
    table_by_id: dict[str, dict[str, Any]],
    claim_by_id: dict[str, dict[str, Any]],
    metrics_by_table: dict[str, list[dict[str, Any]]],
    *,
    max_metrics_per_table: int,
    citation_only: bool,
) -> list[dict[str, Any]]:
    contracts = []
    query_id = str(grouped_query.get("query_id"))
    query_families = _valid_families(query_contract.get("required_metric_families") or [])
    for facet_index, grouped_facet in enumerate(grouped_query.get("facets") or [], start=1):
        contract_facet = _match_contract_facet(grouped_facet, query_contract)
        facet_families = _valid_families(
            ((contract_facet.get("required_coverage") or {}).get("metric_families") or [])
        ) or query_families
        for aspect in grouped_facet.get("aspects") or []:
            role_names = ["citation_evidence"] if citation_only else ["citation_evidence", "background_evidence"]
            for role_name in role_names:
                evidence_role = "citation" if role_name == "citation_evidence" else "background"
                for evidence_index, evidence in enumerate(aspect.get(role_name) or [], start=1):
                    contracts.append(
                        _contract_for_evidence(
                            query_id=query_id,
                            grouped_facet=grouped_facet,
                            contract_facet=contract_facet,
                            aspect=aspect,
                            evidence=evidence,
                            evidence_index=evidence_index,
                            evidence_role=evidence_role,
                            query_families=query_families,
                            facet_families=facet_families,
                            metric_by_id=metric_by_id,
                            table_by_id=table_by_id,
                            claim_by_id=claim_by_id,
                            metrics_by_table=metrics_by_table,
                            max_metrics_per_table=max_metrics_per_table,
                        )
                    )
    return contracts


def _contract_for_evidence(
    *,
    query_id: str,
    grouped_facet: dict[str, Any],
    contract_facet: dict[str, Any],
    aspect: dict[str, Any],
    evidence: dict[str, Any],
    evidence_index: int,
    evidence_role: str,
    query_families: list[str],
    facet_families: list[str],
    metric_by_id: dict[str, dict[str, Any]],
    table_by_id: dict[str, dict[str, Any]],
    claim_by_id: dict[str, dict[str, Any]],
    metrics_by_table: dict[str, list[dict[str, Any]]],
    max_metrics_per_table: int,
) -> dict[str, Any]:
    object_id = str(evidence.get("object_id") or "")
    object_type = str(evidence.get("object_type") or "")
    structured = _structured_record(object_id, object_type, metric_by_id, table_by_id, claim_by_id)
    ticker, fiscal_year = _ticker_year(evidence, structured)
    source_text = str(evidence.get("object_text") or evidence.get("preview") or "")
    allowed_families = facet_families or query_families
    numeric_candidates = _numeric_candidates(
        evidence=evidence,
        structured=structured,
        object_type=object_type,
        evidence_role=evidence_role,
        allowed_families=allowed_families,
        metrics_by_table=metrics_by_table,
        max_metrics_per_table=max_metrics_per_table,
    )
    metric_families = _unique(
        [
            family
            for candidate in numeric_candidates
            for family in candidate.get("metric_families") or []
            if family != "unknown"
        ]
    )
    if not metric_families:
        metric_families = _metric_families_for_text(
            " ".join(
                [
                    str(grouped_facet.get("facet") or ""),
                    str(aspect.get("aspect") or ""),
                    str(evidence.get("preview") or ""),
                    source_text[:1000],
                ]
            ),
            allowed_families,
        )
    claim_roles = _object_allowed_claim_roles(evidence_role, object_type, numeric_candidates, structured)
    disallowed = _object_disallowed_claim_roles(evidence_role, object_type, numeric_candidates)
    contract_id = _stable_id(query_id, str(contract_facet.get("facet_id")), str(aspect.get("aspect_id")), object_id, evidence_role, evidence_index)
    return {
        "contract_id": contract_id,
        "query_id": query_id,
        "contract_facet_id": contract_facet.get("facet_id"),
        "source_facet": grouped_facet.get("facet"),
        "facet_priority": contract_facet.get("priority"),
        "aspect_id": aspect.get("aspect_id"),
        "aspect": aspect.get("aspect"),
        "aspect_label": aspect.get("aspect_label"),
        "evidence_role": evidence_role,
        "core_fact_allowed": evidence_role == "citation",
        "object_id": object_id,
        "object_type": object_type,
        "source_evidence_id": evidence.get("source_evidence_id"),
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "section": evidence.get("section") or (structured or {}).get("section"),
        "subsection": evidence.get("subsection") or (structured or {}).get("subsection"),
        "source_url": evidence.get("source_url") or (structured or {}).get("source_url"),
        "local_path": evidence.get("local_path") or (structured or {}).get("local_path"),
        "verifier_label": evidence.get("verifier_label"),
        "verifier_confidence": evidence.get("verifier_confidence"),
        "rerank_score": evidence.get("rerank_score"),
        "structured_object_found": structured is not None,
        "metric_families": metric_families or ["unknown"],
        "claim_scope": {
            "companies": [ticker] if ticker else [],
            "years": [fiscal_year] if fiscal_year else [],
            "metric_families": metric_families,
        },
        "allowed_claim_roles": claim_roles,
        "disallowed_claim_roles": disallowed,
        "numeric_candidates": numeric_candidates,
        "source_text_preview": _trim(source_text, 700),
        "boundary_notes_zh": _boundary_notes(evidence_role, object_type, metric_families, numeric_candidates),
    }


def _numeric_candidates(
    *,
    evidence: dict[str, Any],
    structured: dict[str, Any] | None,
    object_type: str,
    evidence_role: str,
    allowed_families: list[str],
    metrics_by_table: dict[str, list[dict[str, Any]]],
    max_metrics_per_table: int,
) -> list[dict[str, Any]]:
    if object_type == "metric" and structured:
        return [_metric_candidate(structured, evidence, evidence_role, allowed_families, source_trace_type="direct_metric")]
    if object_type == "table" and structured:
        candidates = [
            _metric_candidate(metric, evidence, evidence_role, allowed_families, source_trace_type="table_metric")
            for metric in metrics_by_table.get(str(structured.get("object_id")), [])
        ]
        candidates = sorted(candidates, key=lambda item: _candidate_sort_key(item, allowed_families), reverse=True)
        return candidates[:max_metrics_per_table]
    return []


def _metric_candidate(
    metric: dict[str, Any],
    evidence: dict[str, Any],
    evidence_role: str,
    allowed_families: list[str],
    *,
    source_trace_type: str,
) -> dict[str, Any]:
    text = _metric_text(metric, evidence)
    metric_families = _metric_families_for_text(text, allowed_families)
    metric_role = _infer_metric_role(metric, text)
    unit = _unit_key(metric.get("unit"), metric.get("raw_value"))
    display = _display_value_zh(metric.get("value"), unit, metric.get("raw_value"))
    allowed_roles = _allowed_claim_roles(metric_role)
    disallowed_roles = _disallowed_claim_roles(metric_role)
    rejection_reasons = _narrative_rejection_reasons(
        evidence_role=evidence_role,
        metric_families=metric_families,
        metric_role=metric_role,
        unit=unit,
        display_value=display,
        metric=metric,
    )
    return {
        "metric_object_id": metric.get("object_id"),
        "source_trace_type": source_trace_type,
        "metric_label": metric.get("metric_name"),
        "row_label": metric.get("row_label"),
        "column_label": metric.get("column_label"),
        "segment": metric.get("segment"),
        "period": metric.get("period"),
        "period_year": _extract_year(metric.get("period")) or metric.get("fiscal_year"),
        "raw_value_text": metric.get("raw_value"),
        "value": metric.get("value"),
        "unit": unit,
        "display_value_zh": display,
        "metric_families": metric_families or ["unknown"],
        "metric_role": metric_role,
        "allowed_claim_roles": allowed_roles,
        "disallowed_claim_roles": disallowed_roles,
        "allowed_in_narrative": not rejection_reasons,
        "narrative_rejection_reasons": rejection_reasons,
        "narrative_guard_zh": _narrative_guard(metric_families, metric_role, metric, unit),
        "source_statement": _trim(str(metric.get("context") or evidence.get("preview") or ""), 420),
        "confidence": metric.get("confidence"),
    }


def _narrative_rejection_reasons(
    *,
    evidence_role: str,
    metric_families: list[str],
    metric_role: str,
    unit: str,
    display_value: str | None,
    metric: dict[str, Any],
) -> list[str]:
    reasons = []
    if evidence_role != "citation":
        reasons.append("not_citation_evidence")
    if not metric_families:
        reasons.append("metric_family_unknown")
    if metric_role == "unknown":
        reasons.append("metric_role_unknown")
    if not display_value:
        reasons.append("display_value_unavailable")
    if metric.get("value") is None:
        reasons.append("numeric_value_missing")
    if unit in {"unitless", "unknown"}:
        reasons.append("unit_unknown")
    if unit == "usd" and not re.search(r"\b(million|billion)\b", str(metric.get("raw_value") or ""), flags=re.I):
        reasons.append("usd_source_scale_ambiguous")
    return reasons


def _metric_families_for_text(text: str, allowed_families: list[str]) -> list[str]:
    lower = text.lower()
    families = []
    for family, pattern in FAMILY_PATTERNS:
        if re.search(pattern, lower):
            families.append(family)
    if "revenue" in lower or "sales" in lower:
        if not set(families).intersection(
            {"advertising_revenue", "services_revenue", "subscription_revenue", "cloud_revenue", "datacenter_revenue"}
        ):
            families.append("operating_income")
    if allowed_families:
        ordered = [family for family in allowed_families if family in families]
        if ordered:
            return _unique(ordered)
    return _unique([family for family in families if family in METRIC_FAMILY_ALLOWLIST])


def _infer_metric_role(metric: dict[str, Any], text: str) -> str:
    lower = text.lower()
    raw = str(metric.get("raw_value") or "")
    unit = _unit_key(metric.get("unit"), raw)
    label_text = " ".join(
        str(part or "").lower()
        for part in [
            metric.get("metric_name"),
            metric.get("row_label"),
            metric.get("column_label"),
            raw,
            metric.get("unit"),
        ]
    )
    if unit == "percent" or "%" in raw or re.search(r"\b(percent|percentage|rate)\b", label_text):
        return "percentage_rate"
    if re.search(r"\b(increase|increased|decrease|decreased|decline|declined|change|changed|grew|growth|higher|lower)\b", lower):
        if _raw_value_is_period_change(raw, lower) or re.search(r"\b(increase|decrease|change|growth)\b", label_text):
            return "period_change_amount"
    if any(term in lower for term in ("remaining performance obligations", "revenue", "sales", "income", "cash flow", "capital expenditure", "property and equipment", "deferred revenue", "billings", "arr")):
        return "total_value"
    if unit in {"usd_millions", "usd_thousands", "usd_billions"}:
        return "total_value"
    return "unknown"


def _raw_value_is_period_change(raw_value: str, normalized_text: str) -> bool:
    match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", raw_value)
    if not match:
        return False
    number = re.escape(match.group(0).replace(",", ""))
    text = normalized_text.replace(",", "")
    return bool(
        re.search(rf"\b(?:by|of|or)\s+\$?\s*{number}\b", text)
        or re.search(rf"\b(?:increased|decreased|declined|grew|higher|lower)\s+\$?\s*{number}\b", text)
        or re.search(rf"\$?\s*{number}\s*(?:million|billion)?\s+(?:higher|lower|increase|decrease)\b", text)
    )


def _allowed_claim_roles(metric_role: str) -> list[str]:
    if metric_role == "period_change_amount":
        return ["period_change_amount", "increase_amount", "decrease_amount"]
    if metric_role == "percentage_rate":
        return ["percentage_rate", "ratio"]
    if metric_role == "total_value":
        return ["total_value", "trend_point"]
    if metric_role == "ratio":
        return ["ratio"]
    return ["supporting_context"]


def _disallowed_claim_roles(metric_role: str) -> list[str]:
    if metric_role == "period_change_amount":
        return ["total_value", "trend_start_value", "trend_end_value"]
    if metric_role == "percentage_rate":
        return ["total_value", "period_change_amount"]
    if metric_role == "total_value":
        return ["period_change_amount"]
    return ["exact_numeric_claim"]


def _object_allowed_claim_roles(
    evidence_role: str,
    object_type: str,
    numeric_candidates: list[dict[str, Any]],
    structured: dict[str, Any] | None,
) -> list[str]:
    if evidence_role != "citation":
        return ["supporting_context"]
    if object_type == "claim":
        claim_type = str((structured or {}).get("claim_type") or "other")
        if claim_type == "risk":
            return ["caveat_driver", "supporting_context"]
        return ["qualitative_context", "supporting_context"]
    roles = [role for candidate in numeric_candidates for role in candidate.get("allowed_claim_roles") or []]
    return _unique(roles) or ["supporting_context"]


def _object_disallowed_claim_roles(
    evidence_role: str,
    object_type: str,
    numeric_candidates: list[dict[str, Any]],
) -> list[str]:
    roles = []
    if evidence_role != "citation":
        roles.extend(["core_driver", "exact_numeric_claim"])
    if object_type == "claim":
        roles.extend(["exact_numeric_claim"])
    for candidate in numeric_candidates:
        roles.extend(candidate.get("disallowed_claim_roles") or [])
    return _unique(roles)


def _boundary_notes(
    evidence_role: str,
    object_type: str,
    metric_families: list[str],
    numeric_candidates: list[dict[str, Any]],
) -> list[str]:
    notes = []
    if evidence_role != "citation":
        notes.append("background evidence can only provide supporting context; it cannot support core factual claims.")
    if object_type == "claim":
        notes.append("qualitative claim object: use for caveat/context unless paired with ledger-backed numeric evidence.")
    if "capex" in metric_families:
        notes.append("company-level capex cannot be attributed to AI/cloud segment without explicit disclosure.")
    if set(metric_families).intersection({"rpo", "arr_or_recurring_proxy", "deferred_revenue", "billings"}):
        notes.append("visibility proxy metrics are not interchangeable; do not compare them as the same metric.")
    if any(not item.get("allowed_in_narrative") for item in numeric_candidates):
        notes.append("some numeric candidates are blocked from final narrative; use Exact-Value Ledger only.")
    return notes


def _narrative_guard(metric_families: list[str], metric_role: str, metric: dict[str, Any], unit: str) -> str:
    label = str(metric.get("metric_name") or metric.get("row_label") or "该指标")
    if metric_role == "period_change_amount":
        return f"{label} 是期间变动额，只能表述为增加/减少金额，不能写成期末或全年总额。"
    if metric_role == "percentage_rate":
        return f"{label} 是百分比/比率，只能保留百分比口径，不能转换成金额。"
    if "capex" in metric_families:
        return f"{label} 可用于公司层面资本开支/基础设施投入判断，不能直接归因于 AI 或云业务 ROI。"
    if set(metric_families).intersection({"rpo", "arr_or_recurring_proxy", "deferred_revenue", "billings"}):
        return f"{label} 只能作为收入可见性 proxy，不能与 ARR/RPO/递延收入/账单额互相等同。"
    if unit in {"usd_millions", "usd_thousands"}:
        return f"{label} 可按源单位换算展示，但必须保留 ledger 中的 raw_value_text 和 unit。"
    return f"{label} 只能在相同公司、年份、披露口径下使用。"


def _display_value_zh(value: Any, unit: str, raw_value: Any) -> str | None:
    number = _to_float(value)
    if number is None:
        return None
    raw = str(raw_value or "").lower()
    if unit == "percent":
        return f"{_format_number(number)}%"
    if unit == "usd_millions":
        return f"{_format_number(number / 100)} 亿美元"
    if unit == "usd_thousands":
        return f"{_format_number(number / 100000)} 亿美元"
    if unit == "usd_billions" or "billion" in raw:
        return f"{_format_number(number * 10)} 亿美元"
    if "million" in raw:
        return f"{_format_number(number / 100)} 亿美元"
    if unit == "usd":
        return f"{str(raw_value).strip()}"
    return None


def _unit_key(unit: Any, raw_value: Any = "") -> str:
    text = f"{unit or ''} {raw_value or ''}".lower()
    if "%" in text or "percent" in text:
        return "percent"
    if "usd_millions" in text:
        return "usd_millions"
    if "usd_thousands" in text:
        return "usd_thousands"
    if "usd_billions" in text:
        return "usd_billions"
    if "billion" in text and ("$" in text or "usd" in text):
        return "usd_billions"
    if "million" in text and ("$" in text or "usd" in text):
        return "usd_millions"
    if "usd" in text or "$" in text:
        return "usd"
    return "unitless" if not unit else str(unit).lower()


def _format_number(value: float) -> str:
    if abs(value) >= 100:
        text = f"{value:.2f}"
    elif abs(value) >= 10:
        text = f"{value:.2f}"
    else:
        text = f"{value:.4f}"
    return text.rstrip("0").rstrip(".")


def _match_contract_facet(grouped_facet: dict[str, Any], query_contract: dict[str, Any]) -> dict[str, Any]:
    facets = query_contract.get("facets") or []
    source = str(grouped_facet.get("facet") or "")
    source_tokens = _tokens(" ".join([source, " ".join(grouped_facet.get("facet_must_find") or [])]))
    best = None
    best_score = -1.0
    for facet in facets:
        facet_id = str(facet.get("facet_id") or "")
        if source and source == facet_id:
            return facet
        target_tokens = _tokens(" ".join([facet_id, str(facet.get("facet_zh") or "")]))
        score = len(source_tokens & target_tokens) / max(len(source_tokens | target_tokens), 1)
        if source and (source in facet_id or facet_id in source):
            score += 0.5
        if score > best_score:
            best = facet
            best_score = score
    return best or {
        "facet_id": source or "unmatched_facet",
        "priority": "supporting",
        "required_coverage": {"metric_families": query_contract.get("required_metric_families") or []},
    }


def _query_facet_coverage(query_contract: dict[str, Any], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citation_by_facet = Counter(
        str(contract.get("contract_facet_id"))
        for contract in contracts
        if contract.get("evidence_role") == "citation"
    )
    rows = []
    for facet in query_contract.get("facets") or []:
        facet_id = str(facet.get("facet_id"))
        rows.append(
            {
                "facet_id": facet_id,
                "priority": facet.get("priority"),
                "citation_contract_count": int(citation_by_facet.get(facet_id, 0)),
                "covered": int(citation_by_facet.get(facet_id, 0)) > 0,
            }
        )
    return rows


def _report(
    contracts: list[dict[str, Any]],
    query_results: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    query_contracts: dict[str, dict[str, Any]],
    metrics_path: Path,
    tables_path: Path,
    claims_path: Path,
) -> dict[str, Any]:
    role_counts = Counter(contract.get("evidence_role") for contract in contracts)
    object_type_counts = Counter(contract.get("object_type") for contract in contracts)
    family_counts = Counter(
        family
        for contract in contracts
        for family in contract.get("metric_families") or []
    )
    numeric_candidates = [
        candidate
        for contract in contracts
        for candidate in contract.get("numeric_candidates") or []
    ]
    rejection_counts = Counter(
        reason
        for candidate in numeric_candidates
        for reason in candidate.get("narrative_rejection_reasons") or []
    )
    primary_facets = []
    for query in query_results:
        primary_facets.extend([row for row in query.get("facet_coverage") or [] if row.get("priority") == "primary"])
    structured_hit_count = sum(1 for contract in contracts if contract.get("structured_object_found"))
    citation_contracts = [contract for contract in contracts if contract.get("evidence_role") == "citation"]
    summary = {
        "query_count": len(query_results),
        "contract_count": len(contracts),
        "unique_object_count": len({contract.get("object_id") for contract in contracts}),
        "role_counts": dict(sorted(role_counts.items())),
        "object_type_counts": dict(sorted(object_type_counts.items())),
        "structured_hit_count": structured_hit_count,
        "structured_hit_rate": _ratio(structured_hit_count, len(contracts)),
        "metric_family_counts": dict(sorted(family_counts.items())),
        "numeric_candidate_count": len(numeric_candidates),
        "narrative_allowed_numeric_count": sum(1 for item in numeric_candidates if item.get("allowed_in_narrative")),
        "citation_numeric_candidate_count": sum(
            len(contract.get("numeric_candidates") or []) for contract in citation_contracts
        ),
        "citation_narrative_allowed_numeric_count": sum(
            1
            for contract in citation_contracts
            for item in contract.get("numeric_candidates") or []
            if item.get("allowed_in_narrative")
        ),
        "numeric_rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "primary_facet_count": len(primary_facets),
        "primary_facet_with_citation_count": sum(1 for row in primary_facets if row.get("covered")),
        "primary_facet_citation_coverage_rate": _ratio(sum(1 for row in primary_facets if row.get("covered")), len(primary_facets)),
    }
    return {
        "schema_version": "evidence_object_contract_validation_v0.1",
        "inputs": {
            "query_contract_path": str((REPO_ROOT / args.query_contract_path).resolve()),
            "grouped_pool_path": str((REPO_ROOT / args.grouped_pool_path).resolve()),
            "metrics_path": str(metrics_path.resolve()),
            "tables_path": str(tables_path.resolve()),
            "claims_path": str(claims_path.resolve()),
        },
        "summary": summary,
        "query_facet_coverage": [
            {"query_id": query["query_id"], "facets": query.get("facet_coverage") or []}
            for query in query_results
        ],
        "hard_failures": [],
        "warnings": _report_warnings(summary, query_results),
    }


def _report_warnings(summary: dict[str, Any], query_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings = []
    if summary["structured_hit_rate"] < 0.95:
        warnings.append({"type": "low_structured_hit_rate", "value": summary["structured_hit_rate"]})
    for query in query_results:
        for facet in query.get("facet_coverage") or []:
            if facet.get("priority") == "primary" and not facet.get("covered"):
                warnings.append({"type": "primary_facet_without_citation_contract", "query_id": query["query_id"], "facet_id": facet["facet_id"]})
    return warnings


def _structured_record(
    object_id: str,
    object_type: str,
    metric_by_id: dict[str, dict[str, Any]],
    table_by_id: dict[str, dict[str, Any]],
    claim_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if object_type == "metric":
        return metric_by_id.get(object_id)
    if object_type == "table":
        return table_by_id.get(object_id)
    if object_type == "claim":
        return claim_by_id.get(object_id)
    return metric_by_id.get(object_id) or table_by_id.get(object_id) or claim_by_id.get(object_id)


def _metric_text(metric: dict[str, Any], evidence: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in [
            metric.get("ticker"),
            metric.get("fiscal_year"),
            metric.get("metric_name"),
            metric.get("row_label"),
            metric.get("column_label"),
            metric.get("segment"),
            metric.get("period"),
            metric.get("raw_value"),
            metric.get("unit"),
            metric.get("context"),
            evidence.get("preview"),
        ]
    )


def _ticker_year(evidence: dict[str, Any], structured: dict[str, Any] | None) -> tuple[str | None, int | None]:
    ticker = evidence.get("ticker") or evidence.get("object_ticker") or (structured or {}).get("ticker")
    year = evidence.get("fiscal_year") or evidence.get("object_fiscal_year") or (structured or {}).get("fiscal_year")
    if not ticker or not year:
        text = " ".join(str(part or "") for part in [evidence.get("object_id"), evidence.get("source_evidence_id"), evidence.get("object_text")])
        match = re.search(r"\b([A-Z]{2,5})_(20\d{2})_", text)
        if match:
            ticker = ticker or match.group(1)
            year = year or int(match.group(2))
    return (str(ticker).upper() if ticker else None, _to_int(year))


def _candidate_sort_key(candidate: dict[str, Any], allowed_families: list[str]) -> tuple[int, int, int, float]:
    families = set(candidate.get("metric_families") or [])
    family_match = bool(families & set(allowed_families))
    allowed = bool(candidate.get("allowed_in_narrative"))
    role_known = candidate.get("metric_role") != "unknown"
    confidence = float(candidate.get("confidence") or 0.0)
    return (int(family_match), int(allowed), int(role_known), confidence)


def _valid_families(items: list[Any]) -> list[str]:
    return _unique([str(item) for item in items if str(item) in METRIC_FAMILY_ALLOWLIST])


def _tokens(text: str) -> set[str]:
    return {item for item in re.split(r"[^a-z0-9]+", text.lower()) if len(item) >= 2}


def _stable_id(*parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]
    prefix = re.sub(r"[^a-z0-9_]+", "_", str(parts[0]).lower()).strip("_")[:48]
    return f"{prefix}_{digest}"


def _extract_year(value: Any) -> int | None:
    match = re.search(r"(20\d{2}|19\d{2})", str(value or ""))
    return int(match.group(1)) if match else None


def _trim(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except ValueError:
        return None


def _unique(items: list[Any]) -> list[Any]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    main()
