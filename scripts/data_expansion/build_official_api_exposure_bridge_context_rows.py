from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_official_api_exposure_bridge_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_official_api_exposure_bridge_context_summary_v0_1"

DEFAULT_OFFICIAL_API_ROWS = REPO_ROOT / "data" / "manifests" / "public_official_api_context_rows_v0_1.jsonl"
DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "official_api_exposure_bridge_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_api_exposure_bridge_context_summary_v0_1.json"


MACRO_REQUIREMENTS = {"macro_official_context"}
ENERGY_REQUIREMENTS = {"energy_utility_context"}
FINANCIAL_REQUIREMENTS = {"financial_regulatory_context"}
TECH_RESEARCH_REQUIREMENTS = {"technology_research_proxy"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Project seed-available official/API rows into company/product-family bounded exact-slot rows. "
            "These rows are exposure/proxy context only and never issuer exact financial or sales authority."
        )
    )
    parser.add_argument("--official-api-rows", type=Path, default=DEFAULT_OFFICIAL_API_ROWS)
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no bridge rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    official_rows = _load_jsonl(args.official_api_rows)
    matrix_rows = _load_jsonl(args.company_source_matrix)
    family_rows = _load_jsonl(args.family_assignments)
    rows = build_official_api_exposure_bridge_context_rows(
        official_rows=official_rows,
        company_source_matrix_rows=matrix_rows,
        family_assignment_rows=family_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=rows,
        official_rows=official_rows,
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
    )
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_official_api_exposure_bridge_context_rows(
    *,
    official_rows: Iterable[Mapping[str, Any]],
    company_source_matrix_rows: Iterable[Mapping[str, Any]],
    family_assignment_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    official = [dict(row) for row in official_rows if isinstance(row, Mapping)]
    matrix = [dict(row) for row in company_source_matrix_rows if isinstance(row, Mapping)]
    family_by_ticker = _family_assignments_by_ticker(family_assignment_rows)
    latest_fred = _latest_row(official, source_ids={"fred_api", "fred_graph_csv"}, metric_hint="FEDFUNDS")
    latest_eia = _latest_row(official, source_ids={"eia_open_data"})
    openalex_rows = _ranked_rows(official, source_ids={"openalex_api"}, max_rows=12)

    out: list[dict[str, Any]] = []
    for company in matrix:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        families = family_by_ticker.get(ticker) or []
        primary_family = families[0] if families else {}
        if requirements & MACRO_REQUIREMENTS and latest_fred:
            out.append(
                _official_driver_bridge_row(
                    company=company,
                    source_row=latest_fred,
                    requirement_id="macro_official_context",
                    structured_context_type="macro_official_context",
                    macro_driver_id="FEDFUNDS",
                    macro_driver_name="Federal funds effective rate",
                    exposure_basis=_macro_exposure_basis(company, primary_family),
                    generated_at=generated_at,
                )
            )
        if requirements & ENERGY_REQUIREMENTS and latest_eia:
            driver_id = str(latest_eia.get("product_or_segment") or latest_eia.get("metric_name") or "EIA_OPEN_DATA")
            out.append(
                _official_driver_bridge_row(
                    company=company,
                    source_row=latest_eia,
                    requirement_id="energy_utility_context",
                    structured_context_type="energy_utility_official_context",
                    macro_driver_id=driver_id,
                    macro_driver_name="EIA official energy context",
                    exposure_basis=_energy_exposure_basis(company, primary_family),
                    generated_at=generated_at,
                )
            )
        if requirements & FINANCIAL_REQUIREMENTS and latest_fred:
            out.append(
                _official_driver_bridge_row(
                    company=company,
                    source_row=latest_fred,
                    requirement_id="financial_regulatory_context",
                    structured_context_type="financial_regulatory_or_rate_context",
                    macro_driver_id="FEDFUNDS",
                    macro_driver_name="Federal funds effective rate",
                    exposure_basis=_financial_exposure_basis(company, primary_family),
                    generated_at=generated_at,
                )
            )
        if requirements & TECH_RESEARCH_REQUIREMENTS and openalex_rows:
            out.extend(
                _technology_research_bridge_rows(
                    company=company,
                    source_rows=openalex_rows,
                    families=families,
                    generated_at=generated_at,
                )
            )
    return _dedupe_rows(out)


def _official_driver_bridge_row(
    *,
    company: Mapping[str, Any],
    source_row: Mapping[str, Any],
    requirement_id: str,
    structured_context_type: str,
    macro_driver_id: str,
    macro_driver_name: str,
    exposure_basis: str,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").strip().upper()
    source_id = str(source_row.get("source_id") or "")
    period = source_row.get("period") or source_row.get("observation_date") or source_row.get("as_of_date")
    source_url = _source_url(source_row)
    evidence_ref = _stable_ref(
        "official_api_exposure_bridge",
        [ticker, requirement_id, source_id, macro_driver_id, period, source_row.get("evidence_ref")],
    )
    value = source_row.get("value")
    unit = source_row.get("unit") or ""
    text = (
        f"{ticker} {requirement_id} exposure bridge: {macro_driver_name} "
        f"value={value} unit={unit} period={period}; basis={exposure_basis}; "
        "bounded official context only, not issuer revenue/share/sales/margin evidence."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "parent_evidence_ref": source_row.get("evidence_ref") or source_row.get("evidence_id"),
        "source_id": source_id,
        "underlying_source_id": source_id,
        "source_class": source_id,
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L2",
        "source_layer": "L2",
        "layer_id": "L2",
        "source_specific_parser": "official_api_exposure_bridge_projector_v0_1",
        "source_specific_resolver": "company_lane_driver_exposure_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "evidence_graph_status": "runtime_ready_context",
        "bounded_structured_context": True,
        "structured_context_type": structured_context_type,
        "requirement_id": requirement_id,
        "claim_types": [requirement_id, "official_driver_exposure_context"],
        "allowed_claims": [requirement_id, "macro_driver_context", "official_industry_proxy", "verification_lead"],
        "forbidden_claims": ["issuer_revenue", "issuer_margin", "market_share", "product_sales", "shipments", "demand_proof"],
        "ticker": ticker,
        "company": company.get("company_name") or "",
        "company_name": company.get("company_name") or "",
        "primary_lane_id": company.get("primary_lane_id") or "",
        "primary_lane_name": company.get("primary_lane_name") or "",
        "source_url": source_url,
        "api_route": source_row.get("api_route") or source_url,
        "citation": {
            "url": source_url,
            "record_id": source_row.get("evidence_ref") or source_row.get("evidence_id"),
            "title": macro_driver_name,
        },
        "macro_driver_id": macro_driver_id,
        "macro_driver_name": macro_driver_name,
        "series_id": source_row.get("series_id") or source_row.get("metric_name") or macro_driver_id,
        "fact_label": macro_driver_name,
        "product_or_segment": source_row.get("product_or_segment") or macro_driver_id,
        "product_family": source_row.get("product_or_segment") or macro_driver_id,
        "metric_name": source_row.get("metric_name") or macro_driver_id,
        "value": value,
        "unit": unit,
        "period": period,
        "observation_date": source_row.get("observation_date"),
        "as_of_datetime": generated_at,
        "issuer_binding_status": "macro_exposure_bridge_context",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": ticker,
            "issuer_binding_status": "macro_exposure_bridge_context",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "source_entity_role": "official_driver_exposure_bridge",
            "resolver_status": "company_lane_driver_exposure_bridge",
            "binding_claim_boundary": "Ticker is connected to an official driver by lane/family exposure rule only; not issuer-specific exact financial evidence.",
        },
        "resolver_status": "company_lane_driver_exposure_bridge",
        "resolver_reason": "company_requirement_mapped_to_seed_available_official_driver",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "claim_boundary": "Official API exposure bridge only; no issuer revenue, margin, sales, shipment, share, or demand inference.",
        "authority_boundary": "L2 official driver/proxy context; never issuer exact metric authority.",
        "text": text,
        "preview": text,
    }


def _technology_research_bridge_rows(
    *,
    company: Mapping[str, Any],
    source_rows: list[dict[str, Any]],
    families: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    if not families:
        families = [
            {
                "family_id": str(company.get("industry_schema") or company.get("primary_lane_id") or "general"),
                "family_name": str(company.get("primary_lane_name") or company.get("industry_schema") or "General"),
                "query_terms": [str(company.get("primary_lane_name") or company.get("industry_schema") or "industry")],
            }
        ]
    out: list[dict[str, Any]] = []
    for family in families[:2]:
        query_terms = [str(term) for term in family.get("query_terms") or [] if str(term).strip()]
        family_name = str(family.get("family_name") or family.get("family_id") or "technology topic")
        selected = _select_openalex_rows_for_family(source_rows, query_terms=query_terms, family_name=family_name)
        for source_row in selected[:1]:
            source_url = _source_url(source_row)
            openalex_work_id = source_row.get("identifier") or source_row.get("evidence_ref") or source_url
            period = source_row.get("period") or source_row.get("observation_date") or source_row.get("as_of_date")
            evidence_ref = _stable_ref(
                "official_api_technology_bridge",
                [ticker, family.get("family_id"), openalex_work_id, source_row.get("value")],
            )
            product_or_segment = str(source_row.get("product_or_segment") or family_name)
            text = (
                f"{ticker} technology research proxy bridge for {family_name}: {product_or_segment}; "
                f"cited_by_count={source_row.get('value')} period={period}; "
                "family/topic exposure proxy only, not product launch, sales, moat, or market share proof."
            )
            out.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "evidence_ref": evidence_ref,
                    "evidence_id": evidence_ref,
                    "parent_evidence_ref": source_row.get("evidence_ref") or source_row.get("evidence_id"),
                    "source_id": "openalex_api",
                    "underlying_source_id": "openalex_api",
                    "source_class": "openalex_api",
                    "source_family": "public_source_context",
                    "runtime_source_family": "public_source_context",
                    "source_layer_id": "L3",
                    "source_layer": "L3",
                    "layer_id": "L3",
                    "source_specific_parser": "official_api_openalex_family_bridge_projector_v0_1",
                    "source_specific_resolver": "company_product_family_topic_exposure_resolver_v0_1",
                    "parser_status": "source_specific_context_parser_pass",
                    "structured_fact_status": "bounded_context_fact_materialized",
                    "runtime_ready_context": True,
                    "bounded_structured_context": True,
                    "structured_context_type": "technology_research_proxy_context",
                    "requirement_id": "technology_research_proxy",
                    "ticker": ticker,
                    "company": company.get("company_name") or "",
                    "company_name": company.get("company_name") or "",
                    "primary_lane_id": company.get("primary_lane_id") or "",
                    "primary_lane_name": company.get("primary_lane_name") or "",
                    "family_id": family.get("family_id") or "",
                    "family_name": family_name,
                    "source_url": source_url,
                    "api_route": source_row.get("api_route") or source_url,
                    "citation": {
                        "url": source_url,
                        "record_id": source_row.get("evidence_ref") or source_row.get("evidence_id"),
                        "title": product_or_segment,
                    },
                    "openalex_work_id": openalex_work_id,
                    "fact_label": product_or_segment,
                    "product_or_segment": product_or_segment,
                    "product_family": family_name,
                    "metric_name": source_row.get("metric_name") or "cited_by_count",
                    "value": source_row.get("value"),
                    "unit": source_row.get("unit") or "cited_by_count",
                    "period": period,
                    "as_of_datetime": generated_at,
                    "issuer_binding_status": "family_assignment_exposure_context",
                    "product_binding_status": "technology_topic_bound",
                    "counterparty_binding_status": "not_bound",
                    "entity_binding": {
                        "schema_version": "finsight_public_web_entity_binding_v0_1",
                        "issuer_ticker": ticker,
                        "issuer_binding_status": "family_assignment_exposure_context",
                        "product_binding_status": "technology_topic_bound",
                        "counterparty_binding_status": "not_bound",
                        "source_entity_role": "product_family_topic_exposure_bridge",
                        "resolver_status": "company_family_topic_exposure_bridge",
                        "binding_claim_boundary": "Ticker is connected to a research topic by company-product-family assignment only; not issuer-specific R&D or product success evidence.",
                    },
                    "resolver_status": "company_family_topic_exposure_bridge",
                    "resolver_reason": "company_product_family_assignment_mapped_to_openalex_topic",
                    "context_only": True,
                    "exact_value_authority": False,
                    "can_support_company_exact_fact": False,
                    "claim_types": ["technology_research_proxy", "official_research_topic_context"],
                    "allowed_claims": ["technology_research_proxy", "verification_lead"],
                    "forbidden_claims": ["product_sales", "market_share", "product_launch", "durable_moat_proof"],
                    "claim_boundary": "OpenAlex family/topic bridge only; no launch, sales, market share, or durable moat promotion.",
                    "authority_boundary": "L3 public research proxy exact snapshot.",
                    "text": text,
                    "preview": text,
                }
            )
    return out


def build_summary(
    *,
    rows: list[dict[str, Any]],
    official_rows: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_official_row_count": len(official_rows),
        "company_count": len(matrix_rows),
        "context_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "source_id_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "requirement_counts": dict(sorted(Counter(str(row.get("requirement_id") or "") for row in rows).items())),
        "issuer_binding_status_counts": dict(sorted(Counter(str(row.get("issuer_binding_status") or "") for row in rows).items())),
        "outputs": {"rows": str(output_rows)},
        "boundary": (
            "Bridge rows are bounded exact snapshots of official/API values or research proxy values routed through "
            "company/lane/family exposure rules. They cannot support issuer revenue, sales, shipments, market share, "
            "margin, commercial uptake, or moat claims."
        ),
    }


def _family_assignments_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        out.setdefault(ticker, []).append(dict(row))
    for values in out.values():
        values.sort(key=lambda row: (str(row.get("primary_lane_id") or ""), str(row.get("family_id") or "")))
    return out


def _latest_row(rows: Iterable[Mapping[str, Any]], *, source_ids: set[str], metric_hint: str = "") -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    hint = metric_hint.upper()
    for row in rows:
        source_id = str(row.get("source_id") or "")
        if source_id not in source_ids:
            continue
        if hint:
            haystack = " ".join(str(row.get(field) or "") for field in ("metric_name", "product_or_segment", "identifier", "series_id")).upper()
            if hint not in haystack:
                continue
        if row.get("value") is None:
            continue
        candidates.append(dict(row))
    candidates.sort(key=lambda row: str(row.get("period") or row.get("observation_date") or row.get("as_of_date") or ""))
    return candidates[-1] if candidates else {}


def _ranked_rows(rows: Iterable[Mapping[str, Any]], *, source_ids: set[str], max_rows: int) -> list[dict[str, Any]]:
    candidates = [dict(row) for row in rows if str(row.get("source_id") or "") in source_ids]
    candidates.sort(key=lambda row: float(row.get("value") or 0), reverse=True)
    return candidates[:max_rows]


def _select_openalex_rows_for_family(rows: list[dict[str, Any]], *, query_terms: list[str], family_name: str) -> list[dict[str, Any]]:
    terms = [term.lower() for term in [*query_terms, family_name] if term]
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        text = " ".join(str(row.get(field) or "") for field in ("product_or_segment", "text", "preview")).lower()
        score = sum(1 for term in terms if term and term.lower() in text)
        scored.append((score, row))
    scored.sort(key=lambda item: (item[0], float(item[1].get("value") or 0)), reverse=True)
    return [row for score, row in scored if score > 0] or [row for _, row in scored[:1]]


def _macro_exposure_basis(company: Mapping[str, Any], family: Mapping[str, Any]) -> str:
    lane = str(company.get("primary_lane_name") or company.get("primary_lane_id") or "company")
    family_name = str(family.get("family_name") or company.get("industry_schema") or lane)
    return f"{lane} / {family_name} may be rate, discount-rate, financing, or cycle sensitive; official rate row is context only."


def _energy_exposure_basis(company: Mapping[str, Any], family: Mapping[str, Any]) -> str:
    lane = str(company.get("primary_lane_name") or company.get("primary_lane_id") or "company")
    family_name = str(family.get("family_name") or company.get("industry_schema") or lane)
    return f"{lane} / {family_name} has energy, power, commodity, utility, datacenter, industrial, or facility exposure; EIA row is context only."


def _financial_exposure_basis(company: Mapping[str, Any], family: Mapping[str, Any]) -> str:
    lane = str(company.get("primary_lane_name") or company.get("primary_lane_id") or "company")
    family_name = str(family.get("family_name") or company.get("industry_schema") or lane)
    return f"{lane} / {family_name} has rate, spread, capital-market, deposit, insurance, or credit-cycle exposure; official rate row is context only."


def _source_url(row: Mapping[str, Any]) -> str:
    for key in ("source_url", "snapshot_url", "url", "api_url", "api_route"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    citation = row.get("citation")
    if isinstance(citation, Mapping):
        return str(citation.get("url") or citation.get("source_url") or "").strip()
    return ""


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
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
