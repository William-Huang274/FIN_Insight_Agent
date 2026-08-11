from __future__ import annotations

import argparse
import json
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


SCHEMA_VERSION = "fin_agent_company_reported_product_operating_metric_runtime_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_company_reported_product_operating_metric_runtime_summary_v0_1"

DEFAULT_INPUT_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_quality_operating_repair_v0_1.jsonl"
)
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "company_reported_product_operating_metric_runtime_coverage_gate_v0_1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project verified company-disclosed product KPI facts into runtime source rows.")
    parser.add_argument("--input-facts", type=Path, default=DEFAULT_INPUT_FACTS)
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless exact parser-backed rows and runtime coverage pass.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fact_rows = _load_jsonl(args.input_facts)
    runtime_rows, rejection_rows = build_company_reported_product_operating_metric_runtime_rows(
        fact_rows,
        generated_at=generated_at,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    visible_rows = {
        "fundamental_analyst": runtime_rows,
        "product_technology_analyst": runtime_rows,
        "capital_ownership_macro_analyst": runtime_rows[:50],
    }
    coverage_gate = build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        case_id="company_reported_product_operating_metric_runtime_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=runtime_rows,
        specialist_visible_rows=visible_rows,
        required_dimensions=["fundamentals", "product_and_production"],
        generated_at=generated_at,
    )
    summary = build_summary(
        fact_rows=fact_rows,
        runtime_rows=runtime_rows,
        rejection_rows=rejection_rows,
        coverage_gate=coverage_gate,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, runtime_rows)
    _write_jsonl(args.output_rejections, rejection_rows)
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_gate)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and (summary["exact_runtime_row_count"] <= 0 or summary["coverage_gate_status"] != "pass"):
        return 1
    return 0


def build_company_reported_product_operating_metric_runtime_rows(
    fact_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for raw in fact_rows:
        fact = dict(raw)
        reason = _fact_rejection_reason(fact)
        if reason:
            rejections.append(_rejection_row(fact, reason, generated_at))
            continue
        evidence_ref = str(fact.get("fact_id") or "").strip()
        if evidence_ref in seen_refs:
            rejections.append(_rejection_row(fact, "duplicate_fact_id", generated_at))
            continue
        seen_refs.add(evidence_ref)
        rows.append(_runtime_row(fact, generated_at=generated_at))
    return rows, rejections


def build_summary(
    *,
    fact_rows: list[dict[str, Any]],
    runtime_rows: list[dict[str, Any]],
    rejection_rows: list[dict[str, Any]],
    coverage_gate: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_rejections: Path,
    output_coverage: Path,
) -> dict[str, Any]:
    exact_rows = [row for row in runtime_rows if bool(row.get("exact_value_authority"))]
    requirement_statuses = {
        str(row.get("requirement_id") or ""): str(row.get("status") or "")
        for row in coverage_gate.get("requirements") or []
        if isinstance(row, Mapping)
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if exact_rows and coverage_gate.get("status") == "pass" else "gap",
        "input_fact_count": len(fact_rows),
        "runtime_row_count": len(runtime_rows),
        "exact_runtime_row_count": len(exact_rows),
        "runtime_ticker_count": len({str(row.get("ticker") or "") for row in runtime_rows if row.get("ticker")}),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in runtime_rows).items())),
        "repair_promotion_status_counts": dict(sorted(Counter(str(row.get("repair_promotion_status") or "baseline_parser") for row in runtime_rows).items())),
        "rejection_count": len(rejection_rows),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejection_rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "requirement_statuses": requirement_statuses,
        "outputs": {
            "rows": str(output_rows),
            "rejections": str(output_rejections),
            "coverage_gate": str(output_coverage),
        },
        "claim_boundary": (
            "Rows may support company-disclosed product KPI facts only for the disclosed product/segment, metric, "
            "period, unit, value, and cited filing span. They do not prove market share, channel inventory, "
            "sell-through, undisclosed SKU economics, or commercial tracker estimates."
        ),
    }


def _fact_rejection_reason(fact: Mapping[str, Any]) -> str:
    required = ("fact_id", "ticker", "product_or_segment", "metric_family", "period", "unit", "value", "source_url", "citation_span")
    missing = [key for key in required if fact.get(key) in (None, "")]
    if missing:
        return "missing_" + "_".join(missing[:4])
    if str(fact.get("fact_status") or "") != "parser_verified_fact":
        return "not_parser_verified_fact"
    try:
        float(fact.get("value"))
    except (TypeError, ValueError):
        return "value_not_numeric"
    return ""


def _runtime_row(fact: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    evidence_ref = str(fact.get("fact_id") or "").strip()
    metric_family = str(fact.get("metric_family") or "").strip()
    metric_name = str(fact.get("metric_name") or metric_family).strip()
    product = str(fact.get("product_or_segment") or "").strip()
    period = str(fact.get("period") or "").strip()
    unit = str(fact.get("unit") or "").strip()
    value = fact.get("value")
    repair_status = str(fact.get("repair_promotion_status") or "baseline_parser_verified").strip()
    boundary = str(fact.get("runtime_use_boundary") or "").strip() or (
        "May support company-disclosed product KPI facts for this disclosed metric only; no market share, "
        "sell-through, channel inventory, or undisclosed product economics."
    )
    text = f"{fact.get('ticker')} disclosed {product} {metric_name} of {value} {unit} for {period}."
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "company_reported_product_operating_metrics",
        "underlying_source_id": str(fact.get("source_id") or ""),
        "source_class": "company_reported_product_operating_metric",
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "evidence_graph_status": "exact_authority_ready",
        "runtime_ready_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "promotion_status": "runtime_fact_allowed",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "source_specific_parser": "company_product_kpi_value_unit_period_product_parser_v0_1",
        "structured_fact_status": "exact_fact_materialized",
        "bounded_structured_context": True,
        "structured_context_type": "company_reported_product_operating_metric_fact",
        "claim_types": ["company_disclosed_product_kpi", "company_reported_product_operating_fact"],
        "allowed_claims": ["company_disclosed_product_kpi", metric_family],
        "forbidden_claims": ["market_share", "channel_inventory", "sell_through", "undisclosed_sku_economics", "commercial_tracker_estimate"],
        "authority_boundary": boundary,
        "claim_boundary": boundary,
        "runtime_use_boundary": boundary,
        "ticker": str(fact.get("ticker") or "").strip().upper(),
        "company": fact.get("company"),
        "industry_schema": fact.get("industry_schema"),
        "product_or_segment": product,
        "product_family": product,
        "product_node_id": fact.get("product_node_id"),
        "product_node_type": fact.get("product_node_type"),
        "metric_family": metric_family,
        "metric_name": metric_name,
        "canonical_metric_id": f"product_kpi:{metric_family}",
        "value": value,
        "unit": unit,
        "unit_category": fact.get("unit_category"),
        "raw_value_text": fact.get("raw_value_text"),
        "scale": fact.get("scale"),
        "period": period,
        "period_end": fact.get("period_end"),
        "period_type": fact.get("period_type"),
        "period_role": fact.get("period_role"),
        "fiscal_year": fact.get("fiscal_year"),
        "citation_span": fact.get("citation_span"),
        "citation": {"url": fact.get("source_url"), "span": fact.get("citation_span")},
        "source_url": fact.get("source_url"),
        "snapshot_url": fact.get("source_url"),
        "source_document_id": fact.get("source_document_id"),
        "source_metric_object_id": fact.get("source_metric_object_id"),
        "source_candidate_id": fact.get("source_candidate_id"),
        "matched_product_alias": fact.get("matched_product_alias"),
        "product_link_method": fact.get("product_link_method"),
        "product_link_score": fact.get("product_link_score"),
        "row_label": fact.get("row_label"),
        "column_label": fact.get("column_label"),
        "cell_kind": fact.get("cell_kind"),
        "repair_promotion_status": repair_status,
        "repair_promotion_gate": fact.get("repair_promotion_gate"),
        "source_repair_fact_id": fact.get("source_repair_fact_id"),
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "schema_version": "finsight_public_web_entity_binding_v0_1",
            "issuer_ticker": str(fact.get("ticker") or "").strip().upper(),
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "product_matched_terms": [product],
            "source_entity_role": "company_disclosed_product_metric",
            "binding_claim_boundary": "SEC/company-disclosed product KPI parser row; binding does not extend beyond the disclosed product/metric/period/value.",
        },
        "text": text,
        "preview": text,
        "as_of_datetime": generated_at,
    }


def _rejection_row(fact: Mapping[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": "fin_agent_company_reported_product_operating_metric_runtime_rejection_v0_1",
        "generated_at": generated_at,
        "rejection_reason": reason,
        "fact_id": fact.get("fact_id"),
        "ticker": fact.get("ticker"),
        "product_or_segment": fact.get("product_or_segment"),
        "metric_family": fact.get("metric_family"),
        "period": fact.get("period"),
        "unit": fact.get("unit"),
        "value": fact.get("value"),
        "source_url": fact.get("source_url"),
    }


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
