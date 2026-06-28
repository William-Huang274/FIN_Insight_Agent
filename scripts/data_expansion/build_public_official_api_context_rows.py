from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_public_official_api_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_official_api_context_summary_v0_1"

DEFAULT_INPUT = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_sources/public_source_normalized_materialized_v0_3/normalized_records.jsonl"
)
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_UNIVERSE = REPO_ROOT / "data" / "manifests" / "tier1_tier2_market_universe_v0_1.csv"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "public_official_api_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_official_api_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "public_official_api_context_coverage_gate_v0_1.json"

INCLUDED_SOURCE_IDS = {
    "clinicaltrials_api",
    "openfda_api",
    "cms_public_data",
    "nhtsa_vpic_api",
    "fdic_bankfind_api",
    "eia_open_data",
    "fred_api",
    "fred_graph_csv",
    "openalex_api",
    "patentsview_api",
}

SOURCE_LAYER = {
    "openalex_api": "L3",
    "patentsview_api": "L3",
}

SOURCE_CONTEXT_TYPE = {
    "clinicaltrials_api": "clinical_trial_status_context",
    "openfda_api": "fda_product_status_context",
    "cms_public_data": "healthcare_payer_dataset_context",
    "nhtsa_vpic_api": "vehicle_model_identity_context",
    "fdic_bankfind_api": "financial_institution_reference_context",
    "eia_open_data": "energy_utility_official_context",
    "fred_api": "macro_official_context",
    "fred_graph_csv": "macro_official_context",
    "openalex_api": "technology_research_proxy_context",
    "patentsview_api": "patent_data_access_metadata_context",
}

COVERAGE_SMOKES = (
    ("generic_public_research", "macro_official_context"),
    ("auto_mobility", "auto_product_identity_context"),
    ("healthcare_pharma_medtech", "regulated_product_context"),
    ("financials_banks", "financial_regulatory_context"),
    ("energy_utilities", "energy_utility_context"),
    ("semiconductors_hardware", "technology_research_proxy"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project normalized public official API records into bounded runtime context rows.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    normalized_records = _load_jsonl(args.input)
    issuer_index = load_issuer_alias_index(args.universe)
    context_rows = build_public_official_api_context_rows(
        normalized_records,
        generated_at=generated_at,
        issuer_index=issuer_index,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_payload = build_coverage_smoke(
        context_rows=context_rows,
        source_layer_rows=source_layer_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        normalized_records=normalized_records,
        context_rows=context_rows,
        coverage_payload=coverage_payload,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, context_rows)
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["parser_backed_row_count"] <= 0:
        return 1
    return 0


def build_public_official_api_context_rows(
    records: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
    issuer_index: Mapping[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        row = dict(record)
        source_id = str(row.get("source_id") or "").strip()
        if source_id not in INCLUDED_SOURCE_IDS:
            continue
        evidence_ref = str(row.get("record_id") or "").strip()
        if not evidence_ref:
            continue
        layer_id = SOURCE_LAYER.get(source_id, "L2")
        context_type = SOURCE_CONTEXT_TYPE.get(source_id, "public_official_context")
        entity_name = str(row.get("entity_name") or "").strip()
        source_binding = resolve_source_binding(row, issuer_index or {})
        product_name = source_binding["product_name"]
        issuer_match = source_binding["issuer_match"]
        issuer_binding_status = source_binding["issuer_binding_status"]
        product_binding_status = source_binding["product_binding_status"]
        context_row = {
            "schema_version": SCHEMA_VERSION,
            "evidence_ref": evidence_ref,
            "evidence_id": evidence_ref,
            "snapshot_id": row.get("snapshot_id"),
            "record_type": row.get("record_type"),
            "source_id": source_id,
            "underlying_source_id": source_id,
            "source_class": source_id,
            "source_family": "public_source_context",
            "runtime_source_family": "public_source_context",
            "source_layer_id": layer_id,
            "source_layer": layer_id,
            "layer_id": layer_id,
            "bounded_structured_context": True,
            "structured_context_type": context_type,
            "structured_fact_status": "bounded_context_fact_materialized",
            "source_specific_parser": "public_official_api_normalized_record_projector_v0_1",
            "parser_status": "normalized_record_projector_pass",
            "evidence_graph_status": "runtime_ready_context",
            "runtime_ready_context": True,
            "exact_value_authority": False,
            "can_support_company_exact_fact": False,
            "context_only": True,
            "claim_types": [context_type, "public_official_context"],
            "allowed_claims": allowed_claims_for_source(source_id),
            "forbidden_claims": forbidden_claims_for_source(source_id),
            "claim_boundary": row.get("claim_boundary") or default_claim_boundary(source_id),
            "authority_boundary": row.get("claim_boundary") or default_claim_boundary(source_id),
            "source_policy": row.get("source_policy"),
            "claim_scope": row.get("claim_scope"),
            "provider": row.get("provider"),
            "ticker": issuer_match.get("ticker") if issuer_match else "",
            "company": issuer_match.get("company_name") if issuer_match else "",
            "source_entity_name": entity_name,
            "product_or_segment": product_name,
            "product_family": product_name,
            "metric_name": row.get("metric_name") or row.get("series_id") or row.get("identifier_type"),
            "value": row.get("value"),
            "unit": row.get("unit"),
            "period": row.get("period") or row.get("observation_date"),
            "observation_date": row.get("observation_date"),
            "as_of_date": row.get("as_of_date"),
            "as_of_datetime": generated_at,
            "identifier": row.get("identifier"),
            "identifier_type": row.get("identifier_type"),
            "status": row.get("status"),
            "api_route": row.get("api_route"),
            "citation": {"url": row.get("api_route"), "record_id": evidence_ref},
            "issuer_binding_status": issuer_binding_status,
            "product_binding_status": product_binding_status,
            "counterparty_binding_status": "not_bound",
            "source_specific_resolver": source_binding["source_specific_resolver"],
            "resolver_status": source_binding["resolver_status"],
            "resolver_reason": source_binding["resolver_reason"],
            "entity_binding": {
                "schema_version": "finsight_public_web_entity_binding_v0_1",
                "issuer_ticker": issuer_match.get("ticker") if issuer_match else "",
                "issuer_binding_status": issuer_binding_status,
                "product_binding_status": product_binding_status,
                "counterparty_binding_status": "not_bound",
                "issuer_matched_terms": source_binding["issuer_matched_terms"],
                "product_matched_terms": source_binding["product_matched_terms"],
                "source_entity_role": source_binding["source_entity_role"],
                "resolver_status": source_binding["resolver_status"],
                "resolver_reason": source_binding["resolver_reason"],
                "binding_claim_boundary": "Official API context row; issuer/product binding only supports bounded context, not company exact facts.",
            },
            "text": render_context_text(row, context_type=context_type, issuer_match=issuer_match, source_binding=source_binding),
            "preview": render_context_text(row, context_type=context_type, issuer_match=issuer_match, source_binding=source_binding),
        }
        out.append(context_row)
    return out


def build_coverage_smoke(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    gates = []
    for industry_schema, requirement_id in COVERAGE_SMOKES:
        visible = {
            "fundamental_analyst": context_rows,
            "product_technology_analyst": context_rows,
            "industry_supply_chain_analyst": context_rows,
            "market_valuation_analyst": context_rows,
            "risk_counterevidence_analyst": context_rows,
            "capital_ownership_macro_analyst": context_rows,
        }
        gates.append(
            build_source_coverage_gate(
                industry_schema=industry_schema,
                phase="runtime_case",
                case_id=f"public_official_api_context:{industry_schema}:{requirement_id}",
                source_layer_capability={"rows": source_layer_rows},
                observed_rows=context_rows,
                specialist_visible_rows=visible,
                required_dimensions=[requirement_id],
                generated_at=generated_at,
            )
        )
    return {
        "schema_version": "fin_agent_public_official_api_context_coverage_smoke_v0_1",
        "generated_at": generated_at,
        "status": "fail" if any(gate.get("status") == "fail" for gate in gates) else "gap" if any(gate.get("status") == "gap" for gate in gates) else "pass",
        "gates": gates,
        "requirement_statuses": {
            f"{gate.get('industry_schema')}:{req.get('requirement_id')}": req.get("status")
            for gate in gates
            for req in gate.get("requirements") or []
            if isinstance(req, Mapping)
        },
    }


def build_summary(
    *,
    normalized_records: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    coverage_payload: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_coverage: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if context_rows else "gap",
        "input_record_count": len(normalized_records),
        "context_row_count": len(context_rows),
        "parser_backed_row_count": len([row for row in context_rows if row.get("source_specific_parser")]),
        "source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in context_rows).items())),
        "context_type_counts": dict(sorted(Counter(str(row.get("structured_context_type") or "") for row in context_rows).items())),
        "issuer_bound_row_count": len([row for row in context_rows if row.get("issuer_binding_status") == "issuer_mentioned_in_snapshot"]),
        "product_bound_row_count": len([row for row in context_rows if product_binding_strong(str(row.get("product_binding_status") or ""))]),
        "resolver_status_counts": dict(sorted(Counter(str(row.get("resolver_status") or "unknown") for row in context_rows).items())),
        "resolver_reason_counts": dict(sorted(Counter(str(row.get("resolver_reason") or "unknown") for row in context_rows).items())),
        "coverage_status": coverage_payload.get("status"),
        "requirement_statuses": dict(coverage_payload.get("requirement_statuses") or {}),
        "outputs": {
            "rows": str(output_rows),
            "coverage_gate": str(output_coverage),
        },
        "claim_boundary": "Official API rows are bounded context/proxy rows. They do not prove company revenue, market share, sales volume, approval success, commercial uptake, or durable moat without source-specific issuer/product resolver and exact-authority gates.",
    }


def load_issuer_alias_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("ticker") or "").strip().upper()
            company = str(row.get("company_name") or row.get("company") or "").strip()
            if not ticker or not company:
                continue
            payload = {"ticker": ticker, "company_name": company}
            for alias in {ticker, company, simplify_company_name(company)}:
                norm = normalize_name(alias)
                if norm:
                    out[norm] = payload
    return out


def resolve_source_binding(row: Mapping[str, Any], issuer_index: Mapping[str, dict[str, str]]) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "").strip()
    attributes = parse_attributes_json(row.get("attributes_json"))
    issuer_match, issuer_term = resolve_issuer_candidates(issuer_candidates_for_source(row, attributes), issuer_index)
    product_name, product_terms, product_binding_status = resolve_product_for_source(row, attributes)

    issuer_binding_status = "issuer_mentioned_in_snapshot" if issuer_match else "regulatory_entity_unresolved"
    source_entity_role = source_entity_role_for_source(source_id)
    resolver_status, resolver_reason = classify_resolver_status(
        source_id=source_id,
        issuer_match=issuer_match,
        product_binding_status=product_binding_status,
        product_name=product_name,
        row=row,
        attributes=attributes,
    )
    return {
        "issuer_match": issuer_match,
        "issuer_binding_status": issuer_binding_status,
        "issuer_matched_terms": [issuer_term] if issuer_match and issuer_term else [],
        "product_name": product_name,
        "product_binding_status": product_binding_status,
        "product_matched_terms": product_terms,
        "source_specific_resolver": f"{source_id or 'public_official'}_entity_resolver_v0_1",
        "resolver_status": resolver_status,
        "resolver_reason": resolver_reason,
        "source_entity_role": source_entity_role,
    }


def issuer_candidates_for_source(row: Mapping[str, Any], attributes: Mapping[str, Any]) -> list[str]:
    source_id = str(row.get("source_id") or "").strip()
    candidates: list[str] = []
    _append_candidate(candidates, row.get("entity_name"))
    if source_id == "fdic_bankfind_api":
        for key in (
            "holding_company_name",
            "bank_holding_company_name",
            "top_holder_name",
            "rssd_name",
            "name",
        ):
            _append_candidate(candidates, attributes.get(key))
    elif source_id == "eia_open_data":
        for key in ("utility_name", "company_name", "operator_name", "plant_operator_name", "entity_name"):
            _append_candidate(candidates, attributes.get(key))
    elif source_id in {"clinicaltrials_api", "openfda_api", "cms_public_data"}:
        for key in ("sponsor_name", "lead_sponsor", "manufacturer_name", "applicant", "labeler_name", "organization_name"):
            _append_candidate(candidates, attributes.get(key))
    elif source_id == "nhtsa_vpic_api":
        for key in ("make_name", "manufacturer", "manufacturer_name"):
            _append_candidate(candidates, attributes.get(key))
    elif source_id in {"openalex_api", "patentsview_api"}:
        for key in (
            "assignee",
            "assignee_organization",
            "applicant",
            "institution",
            "institution_name",
            "organization_name",
            "display_name",
        ):
            _append_candidate(candidates, attributes.get(key))
        _append_nested_names(candidates, attributes.get("authorships"), ("institutions", "display_name"))
        _append_nested_names(candidates, attributes.get("institutions"), ("display_name",))
        _append_nested_names(candidates, attributes.get("assignees"), ("assignee_organization", "organization", "name"))
    return _dedupe_candidates(candidates)


def resolve_product_for_source(row: Mapping[str, Any], attributes: Mapping[str, Any]) -> tuple[str, list[str], str]:
    source_id = str(row.get("source_id") or "").strip()
    product_terms: list[str] = []
    if source_id == "fdic_bankfind_api":
        return "", [], "not_bound"
    if source_id in {"fred_api", "fred_graph_csv"}:
        product = str(row.get("series_id") or row.get("identifier") or "").strip()
        return product, [product] if product else [], "product_mentioned_in_snapshot" if product else "not_bound"
    if source_id == "eia_open_data":
        for key in ("product_name", "series_id", "metric_name"):
            _append_candidate(product_terms, row.get(key))
        for key in ("series_description", "fueltype", "fuel_type", "commodity", "sectorName", "sectorid", "stateid"):
            _append_candidate(product_terms, attributes.get(key))
        product = first_non_empty(product_terms)
        return product, _dedupe_candidates(product_terms), "product_mentioned_in_snapshot" if product else "not_bound"
    if source_id in {"openalex_api", "patentsview_api"}:
        for key in ("product_name", "title", "identifier"):
            _append_candidate(product_terms, row.get(key) or attributes.get(key))
        concepts = attributes.get("top_concepts")
        if isinstance(concepts, list):
            for concept in concepts[:5]:
                if isinstance(concept, Mapping):
                    _append_candidate(product_terms, concept.get("display_name"))
        product = first_non_empty(product_terms)
        if not product:
            return "", [], "not_bound"
        return product, _dedupe_candidates(product_terms), "technology_topic_bound"
    for key in ("product_name", "series_id", "identifier"):
        _append_candidate(product_terms, row.get(key))
    product = first_non_empty(product_terms)
    return product, _dedupe_candidates(product_terms), "product_mentioned_in_snapshot" if product else "not_bound"


def classify_resolver_status(
    *,
    source_id: str,
    issuer_match: Mapping[str, str],
    product_binding_status: str,
    product_name: str,
    row: Mapping[str, Any],
    attributes: Mapping[str, Any],
) -> tuple[str, str]:
    issuer_bound = bool(issuer_match)
    product_bound = product_binding_strong(product_binding_status)
    if issuer_bound and product_bound:
        return "issuer_product_bound", "issuer_and_product_or_topic_resolved_from_snapshot"
    if source_id == "fdic_bankfind_api" and issuer_bound:
        return "issuer_bound", "bank_or_holding_company_name_resolved_to_listed_issuer"
    if issuer_bound:
        return "issuer_bound_product_missing", "issuer_resolved_but_product_or_topic_missing"
    if source_id in {"openalex_api", "patentsview_api"} and product_bound:
        return "topic_only", "technology_topic_present_but_no_issuer_or_assignee_binding"
    if source_id in {"fred_api", "fred_graph_csv"}:
        return "macro_driver_only", "macro_series_has_no_issuer_binding_requirement"
    if source_id == "eia_open_data" and product_name:
        if not any(str(attributes.get(key) or "").strip() for key in ("utility_name", "company_name", "operator_name", "plant_operator_name")):
            return "driver_only", "eia_snapshot_has_driver_or_series_but_no_utility_or_asset_issuer_field"
        return "product_bound_issuer_unresolved", "utility_or_operator_field_not_resolved_to_listed_issuer"
    if product_bound:
        return "product_bound_issuer_unresolved", "product_or_identifier_present_but_issuer_unresolved"
    return "unresolved", "no_strong_issuer_product_or_topic_binding_fields"


def source_entity_role_for_source(source_id: str) -> str:
    if source_id == "fdic_bankfind_api":
        return "financial_institution_reference"
    if source_id == "eia_open_data":
        return "energy_series_or_utility_context"
    if source_id in {"openalex_api", "patentsview_api"}:
        return "technology_topic_or_ip_proxy"
    if source_id in {"clinicaltrials_api", "openfda_api", "cms_public_data"}:
        return "healthcare_regulatory_product_context"
    if source_id == "nhtsa_vpic_api":
        return "vehicle_product_identity_context"
    if source_id in {"fred_api", "fred_graph_csv"}:
        return "macro_series_context"
    return "public_official_api_context"


def resolve_issuer(entity_name: str, issuer_index: Mapping[str, dict[str, str]]) -> dict[str, str]:
    match, _ = resolve_issuer_candidates([entity_name], issuer_index)
    return match


def resolve_issuer_candidates(candidates: Iterable[str], issuer_index: Mapping[str, dict[str, str]]) -> tuple[dict[str, str], str]:
    for candidate in candidates:
        match = _resolve_issuer_one(candidate, issuer_index)
        if match:
            return match, candidate
    return {}, ""


def _resolve_issuer_one(entity_name: str, issuer_index: Mapping[str, dict[str, str]]) -> dict[str, str]:
    norm = normalize_name(entity_name)
    if not norm:
        return {}
    if norm in issuer_index:
        return dict(issuer_index[norm])
    for alias, payload in issuer_index.items():
        if min(len(norm), len(alias)) >= 6 and (norm in alias or alias in norm):
            return dict(payload)
    return {}


def product_binding_strong(status: str) -> bool:
    return status in {"product_mentioned_in_snapshot", "technology_topic_bound"}


def parse_attributes_json(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _append_candidate(out: list[str], value: Any) -> None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            out.append(text)
    elif isinstance(value, (int, float)) and value:
        out.append(str(value))


def _append_nested_names(out: list[str], value: Any, keys: tuple[str, ...]) -> None:
    if isinstance(value, Mapping):
        for key in keys:
            _append_candidate(out, value.get(key))
        for child in value.values():
            if isinstance(child, (Mapping, list)):
                _append_nested_names(out, child, keys)
    elif isinstance(value, list):
        for item in value:
            _append_nested_names(out, item, keys)


def _dedupe_candidates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = normalize_name(text) or text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def normalize_name(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    text = re.sub(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|sa|nv|ag|llc|class a|class b)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def simplify_company_name(value: str) -> str:
    return re.split(r"[,(-]", value, maxsplit=1)[0].strip()


def allowed_claims_for_source(source_id: str) -> list[str]:
    if source_id in {"fred_api", "fred_graph_csv", "eia_open_data"}:
        return ["macro_industry_context", "official_series_context", "demand_or_rate_proxy"]
    if source_id == "nhtsa_vpic_api":
        return ["vehicle_model_identity_context", "official_product_identity_context"]
    if source_id in {"clinicaltrials_api", "openfda_api", "cms_public_data"}:
        return ["regulated_product_context", "trial_or_regulatory_status_context", "payer_dataset_context"]
    if source_id == "fdic_bankfind_api":
        return ["financial_regulatory_context", "institution_reference_context"]
    if source_id in {"openalex_api", "patentsview_api"}:
        return ["technology_research_proxy", "ip_or_research_activity_context"]
    return ["public_official_context"]


def forbidden_claims_for_source(source_id: str) -> list[str]:
    base = ["issuer_revenue", "market_share", "sales_volume", "profitability", "commercial_uptake"]
    if source_id in {"clinicaltrials_api", "openfda_api", "cms_public_data"}:
        return [*base, "approval_success", "prescription_volume", "product_sales"]
    if source_id == "nhtsa_vpic_api":
        return [*base, "vehicle_deliveries", "registrations", "automotive_margin"]
    if source_id == "fdic_bankfind_api":
        return [*base, "listed_company_financials_without_resolver"]
    if source_id in {"openalex_api", "patentsview_api"}:
        return [*base, "product_launch", "durable_moat_proof"]
    return base


def default_claim_boundary(source_id: str) -> str:
    return "Official public source context only; exact issuer claims require source-specific resolver and exact-authority gates."


def render_context_text(
    row: Mapping[str, Any],
    *,
    context_type: str,
    issuer_match: Mapping[str, str],
    source_binding: Mapping[str, Any] | None = None,
) -> str:
    provider = str(row.get("provider") or row.get("source_id") or "official source")
    source_id = str(row.get("source_id") or "")
    identifier = str(row.get("identifier") or row.get("series_id") or row.get("record_id") or "")
    product = str((source_binding or {}).get("product_name") or row.get("product_name") or row.get("series_id") or "")
    status = str(row.get("status") or row.get("value") or "")
    issuer = issuer_match.get("ticker") if issuer_match else ""
    parts = [provider, context_type]
    if issuer:
        parts.append(f"issuer={issuer}")
    if product:
        parts.append(f"product={product}")
    if identifier:
        parts.append(f"id={identifier}")
    if status != "":
        parts.append(f"status/value={status}")
    resolver_status = str((source_binding or {}).get("resolver_status") or "")
    if resolver_status:
        parts.append(f"resolver={resolver_status}")
    parts.append(f"source={source_id}")
    return "; ".join(parts)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
