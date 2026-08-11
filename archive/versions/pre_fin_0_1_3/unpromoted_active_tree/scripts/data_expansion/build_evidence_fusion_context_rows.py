from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA_VERSION = "fin_agent_evidence_fusion_context_rows_summary_v0.1"
ROW_SCHEMA_VERSION = "fin_agent_evidence_fusion_context_row_v0.1"

DEFAULT_PRODUCT_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_final_public_repair_v0_1.jsonl"
)
DEFAULT_PRODUCT_NODES = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/company_product_evidence_nodes_v0_1.jsonl"
)
DEFAULT_PRODUCT_GAPS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/company_product_evidence_gaps_v0_1.jsonl"
)
DEFAULT_PUBLIC_INVENTORY_ROWS = REPO_ROOT / (
    "data/processed_private/public_sources/public_source_inventory_adapter_v0_1/public_source_inventory_rows.jsonl"
)
DEFAULT_PUBLIC_NORMALIZED_EVIDENCE_ROWS = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_sources/public_source_normalized_materialized_v0_3/evidence_rows.jsonl"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/manifests/evidence_fusion_context_rows_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize product evidence graph and public-source context artifacts into Evidence Fusion context rows."
    )
    parser.add_argument("--product-facts", type=Path, default=DEFAULT_PRODUCT_FACTS)
    parser.add_argument("--product-nodes", type=Path, default=DEFAULT_PRODUCT_NODES)
    parser.add_argument("--product-gaps", type=Path, default=DEFAULT_PRODUCT_GAPS)
    parser.add_argument("--public-inventory-rows", type=Path, default=DEFAULT_PUBLIC_INVENTORY_ROWS)
    parser.add_argument("--public-normalized-evidence-rows", type=Path, default=DEFAULT_PUBLIC_NORMALIZED_EVIDENCE_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    product_rows = build_product_evidence_rows(
        fact_rows=list(_iter_jsonl(_resolve(args.product_facts))),
        node_rows=list(_iter_jsonl(_resolve(args.product_nodes))),
        gap_rows=list(_iter_jsonl(_resolve(args.product_gaps))),
        generated_at=generated_at,
    )
    public_rows = build_public_source_context_rows(
        inventory_rows=list(_iter_jsonl(_resolve(args.public_inventory_rows))),
        normalized_evidence_rows=list(_iter_jsonl(_resolve(args.public_normalized_evidence_rows))),
        generated_at=generated_at,
    )
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    product_output = output_dir / "product_evidence_rows.jsonl"
    public_output = output_dir / "public_source_context_rows.jsonl"
    summary_output = output_dir / "summary.json"
    summary = build_summary(
        product_rows=product_rows,
        public_rows=public_rows,
        paths={
            "product_facts": _repo_path(_resolve(args.product_facts)),
            "product_nodes": _repo_path(_resolve(args.product_nodes)),
            "product_gaps": _repo_path(_resolve(args.product_gaps)),
            "public_inventory_rows": _repo_path(_resolve(args.public_inventory_rows)),
            "public_normalized_evidence_rows": _repo_path(_resolve(args.public_normalized_evidence_rows)),
            "product_output": _repo_path(product_output),
            "public_output": _repo_path(public_output),
            "summary": _repo_path(summary_output),
        },
        generated_at=generated_at,
    )
    _write_jsonl(product_output, product_rows)
    _write_jsonl(public_output, public_rows)
    _write_json(summary_output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_product_evidence_rows(
    *,
    fact_rows: list[dict[str, Any]],
    node_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in fact_rows:
        rows.append(_product_fact_row(row, generated_at=generated_at))
    for row in node_rows:
        status = str(row.get("promotion_status") or "")
        if status == "runtime_fact_allowed":
            continue
        rows.append(_product_node_row(row, generated_at=generated_at))
    for row in gap_rows:
        rows.append(_product_gap_row(row, generated_at=generated_at))
    return rows


def build_public_source_context_rows(
    *,
    inventory_rows: list[dict[str, Any]],
    normalized_evidence_rows: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in inventory_rows:
        if bool(row.get("bounded_evidence_eligible")):
            rows.append(_public_inventory_context_row(row, generated_at=generated_at))
    for row in normalized_evidence_rows:
        rows.append(_public_normalized_evidence_row(row, generated_at=generated_at))
    return rows


def _product_fact_row(row: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    product = str(row.get("product_or_segment") or row.get("matched_product_alias") or "")
    metric = str(row.get("metric_family") or row.get("metric_name") or "")
    period = str(row.get("period") or row.get("fiscal_year") or "")
    raw_value = str(row.get("raw_value_text") or row.get("value") or "")
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": str(row.get("fact_id") or ""),
        "source_family": "company_product_evidence_graph",
        "source_tier": "company_product_evidence_graph",
        "source_id": str(row.get("source_id") or "company_product_kpi_facts_parser_verified"),
        "ticker": str(row.get("ticker") or "").upper(),
        "company": str(row.get("company") or ""),
        "fiscal_year": row.get("fiscal_year"),
        "period": period,
        "period_role": str(row.get("period_role") or row.get("period_type") or ""),
        "metric": metric,
        "metric_family": str(row.get("metric_family") or ""),
        "metric_name": str(row.get("metric_name") or ""),
        "product_or_segment": product,
        "product_node_id": str(row.get("product_node_id") or ""),
        "unit": str(row.get("unit") or ""),
        "value": row.get("value"),
        "raw_value_text": raw_value,
        "summary": _compact(
            f"{row.get('ticker')} disclosed {product} {metric} of {raw_value} for {period}."
        ),
        "source_statement": _compact(str(row.get("citation_span") or ""), limit=700),
        "source_url": str(row.get("source_url") or ""),
        "promotion_status": "runtime_fact_allowed",
        "evidence_layer": "company_disclosed_verified_product_kpi",
        "claim_scope": "company_disclosed_product_kpi_fact",
        "allowed_claims": [metric] if metric else ["company_disclosed_product_kpi"],
        "forbidden_claims": ["market_share", "channel_inventory", "undisclosed_product_economics"],
        "context_only": False,
        "exact_value_authority": True,
        "runtime_use_boundary": str(
            row.get("runtime_use_boundary")
            or "May support company-disclosed product KPI facts within product/value/period/unit citation scope."
        ),
    }


def _product_node_row(row: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    status = str(row.get("promotion_status") or "")
    evidence_layer = str(row.get("evidence_layer") or "")
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": str(row.get("node_id") or ""),
        "source_family": "company_product_evidence_graph",
        "source_tier": "company_product_evidence_graph",
        "source_id": str(row.get("source_id") or ""),
        "ticker": str(row.get("ticker") or "").upper(),
        "company": str(row.get("company") or ""),
        "metric": evidence_layer,
        "summary": _compact(
            f"{row.get('ticker')} product evidence node {evidence_layer}: {row.get('record_count') or 0} records; status={status}."
        ),
        "promotion_status": status,
        "evidence_layer": evidence_layer,
        "claim_scope": _product_node_claim_scope(status),
        "allowed_claims": _string_list(row.get("allowed_claims")),
        "forbidden_claims": _string_list(row.get("forbidden_claims")),
        "context_only": True,
        "exact_value_authority": False,
        "runtime_use_boundary": str(row.get("runtime_use_boundary") or ""),
    }


def _product_gap_row(row: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": str(row.get("gap_id") or ""),
        "source_family": "company_product_evidence_graph",
        "source_tier": "company_product_evidence_graph",
        "source_id": "company_product_evidence_gap",
        "ticker": str(row.get("ticker") or "").upper(),
        "company": str(row.get("company") or ""),
        "metric": str(row.get("missing_metric") or row.get("gap_type") or ""),
        "summary": _compact(
            f"{row.get('ticker')} gap: {row.get('missing_metric') or row.get('gap_type')} - {row.get('why_public_sources_do_not_fill') or ''}"
        ),
        "promotion_status": "gap_exposed_not_fallback",
        "evidence_layer": "product_evidence_gap",
        "claim_scope": "source_gap_only",
        "allowed_claims": ["evidence_gap", "missing_public_or_commercial_tracker_metric"],
        "forbidden_claims": ["proxy_filled_metric", "company_disclosed_product_kpi_fact"],
        "context_only": True,
        "exact_value_authority": False,
        "runtime_use_boundary": str(row.get("runtime_use_boundary") or ""),
    }


def _public_inventory_context_row(row: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    metric = str(attributes.get("metric_name") or row.get("record_type") or row.get("source_id") or "")
    value = attributes.get("value")
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": str(row.get("row_id") or ""),
        "source_family": "public_source_context",
        "source_tier": "public_source_context",
        "source_id": str(row.get("source_id") or ""),
        "underlying_source_family": str(row.get("source_family") or ""),
        "runtime_source_family": str(row.get("runtime_source_family") or ""),
        "ticker": str(row.get("ticker") or "").upper(),
        "company": str(row.get("company_name") or ""),
        "metric": metric,
        "value": value,
        "period": str(attributes.get("period") or attributes.get("year") or ""),
        "summary": _compact(f"{row.get('source_id')} context row {row.get('external_name') or row.get('external_id') or metric}."),
        "source_url": str(row.get("source_url") or ""),
        "promotion_status": str(row.get("promotion_status") or "public_source_context_promoted"),
        "claim_scope": str(row.get("claim_scope") or "public_context_only"),
        "allowed_claims": _string_list(row.get("allowed_claims")),
        "forbidden_claims": _string_list(row.get("forbidden_claims")),
        "context_only": True,
        "exact_value_authority": False,
        "runtime_use_boundary": "Public source context rows cannot prove company-reported product or financial facts.",
    }


def _public_normalized_evidence_row(row: dict[str, Any], *, generated_at: str) -> dict[str, Any]:
    source_claim_scope = str(row.get("claim_scope") or "")
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": str(row.get("evidence_id") or ""),
        "source_family": "public_source_context",
        "source_tier": "public_source_context",
        "source_id": str(row.get("source_id") or ""),
        "underlying_source_family": str(row.get("primary_source_family") or ""),
        "ticker": str(row.get("ticker") or "").upper(),
        "company": str(row.get("company") or row.get("entity_name") or ""),
        "metric": str(row.get("source_id") or row.get("collector_line") or ""),
        "period": str(row.get("latest_observation_or_period") or row.get("as_of_date") or ""),
        "summary": _compact(str(row.get("summary") or "")),
        "source_url": str(row.get("api_route") or ""),
        "snapshot_id": str(row.get("snapshot_id") or ""),
        "as_of_date": str(row.get("as_of_date") or ""),
        "promotion_status": "public_source_context_available",
        "claim_scope": "public_context_only",
        "source_claim_scope": source_claim_scope,
        "allowed_claims": ["public_context_only"],
        "forbidden_claims": [
            "company_reported_financial_fact",
            "company_product_sales_or_operating_metric",
            "commercial_tracker_replacement",
        ],
        "context_only": True,
        "exact_value_authority": False,
        "runtime_use_boundary": "Normalized public-source rows are context/resolver/lead evidence only.",
    }


def _product_node_claim_scope(status: str) -> str:
    if status == "runtime_context_taxonomy_only":
        return "product_taxonomy_context_only"
    if status == "context_or_lead_available":
        return "public_context_or_lead_only"
    if status == "review_queue_not_runtime_fact":
        return "review_queue_not_runtime_fact"
    return "product_evidence_context_only"


def build_summary(
    *,
    product_rows: list[dict[str, Any]],
    public_rows: list[dict[str, Any]],
    paths: dict[str, str],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "product_row_count": len(product_rows),
        "public_source_context_row_count": len(public_rows),
        "product_promotion_status_counts": dict(sorted(Counter(str(row.get("promotion_status") or "") for row in product_rows).items())),
        "public_claim_scope_counts": dict(sorted(Counter(str(row.get("claim_scope") or "") for row in public_rows).items())),
        "product_exact_value_authority_row_count": sum(1 for row in product_rows if row.get("exact_value_authority")),
        "public_exact_value_authority_row_count": sum(1 for row in public_rows if row.get("exact_value_authority")),
        "outputs": paths,
        "runtime_boundary": [
            "Only product rows with promotion_status=runtime_fact_allowed and exact_value_authority=true may support product KPI facts.",
            "Product taxonomy, context, review, and gap rows are context or missing-evidence rows only.",
            "Public-source rows are context/resolver/lead evidence only and cannot prove company product sales, market share, or profitability.",
        ],
    }


def _compact(value: str, *, limit: int = 900) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    yield item


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
