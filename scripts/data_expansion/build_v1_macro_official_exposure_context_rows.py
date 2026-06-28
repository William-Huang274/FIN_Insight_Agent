from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_v1_macro_official_exposure_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_v1_macro_official_exposure_context_summary_v0_1"

DEFAULT_INPUT_ROWS = REPO_ROOT / "data" / "manifests" / "public_official_api_context_rows_v0_1.jsonl"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "v1_macro_official_exposure_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "v1_macro_official_exposure_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "v1_macro_official_exposure_runtime_coverage_gate_v0_1.json"

MACRO_SOURCE_IDS = {"fred_api", "fred_graph_csv", "eia_open_data"}
DEFAULT_ROUTING_TICKERS = ("NVDA", "AMD", "ASML", "TSM", "QCOM", "AMAT", "LRCX", "KLAC", "DELL", "HPE")
DRIVER_EXPOSURE_MAP = {
    "FEDFUNDS": {
        "driver_name": "Federal funds effective rate",
        "exposure_type": "cost_of_capital_discount_rate_and_capex_cycle_context",
        "exposure_basis": (
            "Semiconductors / AI infrastructure lane is capital-intensive and valuation/capex-cycle sensitive; "
            "FRED rate series is macro context only."
        ),
        "routing_tickers": DEFAULT_ROUTING_TICKERS,
    },
    "EIA_OPEN_DATA": {
        "driver_name": "EIA energy / electricity official context",
        "exposure_type": "power_and_energy_input_context_for_ai_infrastructure_and_fabs",
        "exposure_basis": (
            "AI infrastructure and semiconductor fabs are power-sensitive; EIA rows are official energy context only "
            "and require separate company/facility linkage for issuer-specific claims."
        ),
        "routing_tickers": ("NVDA", "AMD", "TSM", "ASML", "DELL", "HPE"),
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V1 macro official exposure bridge rows from public official API context.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional routing ticker allowlist.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no macro exposure rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    official_rows = _load_jsonl(args.input_rows)
    rows = build_v1_macro_official_exposure_context_rows(
        official_rows,
        generated_at=generated_at,
        tickers=args.tickers,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_gate = build_v1_macro_official_exposure_coverage_gate(
        context_rows=rows,
        source_layer_rows=source_layer_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        input_rows=official_rows,
        rows=rows,
        coverage_gate=coverage_gate,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_gate)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["context_row_count"] <= 0:
        return 1
    return 0


def build_v1_macro_official_exposure_context_rows(
    official_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
    tickers: Iterable[str] = (),
) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    latest_rows = latest_macro_driver_rows(official_rows)
    out: list[dict[str, Any]] = []
    for driver_key, source_row in latest_rows.items():
        exposure = DRIVER_EXPOSURE_MAP.get(driver_key)
        if not exposure:
            continue
        source_id = str(source_row.get("source_id") or "")
        for ticker in exposure["routing_tickers"]:
            routing_ticker = str(ticker).upper()
            if ticker_filter and routing_ticker not in ticker_filter:
                continue
            evidence_ref = _stable_ref("v1_macro_exposure", [routing_ticker, driver_key, source_row.get("evidence_ref")])
            summary = (
                f"Official macro driver exposure bridge for {routing_ticker}: {exposure['driver_name']} "
                f"({source_row.get('metric_name') or source_row.get('product_or_segment')}) value={source_row.get('value')} "
                f"period={source_row.get('period') or source_row.get('observation_date')}; "
                f"basis={exposure['exposure_basis']} This row is macro/industry context only."
            )
            out.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "evidence_ref": evidence_ref,
                    "evidence_id": evidence_ref,
                    "parent_evidence_ref": source_row.get("evidence_ref") or source_row.get("evidence_id"),
                    "source_family": "public_source_context",
                    "runtime_source_family": "public_source_context",
                    "source_id": source_id,
                    "underlying_source_id": source_id,
                    "source_class": source_id,
                    "source_layer_id": "L2",
                    "source_layer": "L2",
                    "layer_id": "L2",
                    "source_specific_parser": "v1_macro_official_exposure_bridge_v0_1",
                    "source_specific_resolver": "v1_lane_macro_driver_exposure_resolver_v0_1",
                    "parser_status": "macro_driver_exposure_bridge_pass",
                    "structured_fact_status": "bounded_context_fact_materialized",
                    "evidence_graph_status": "runtime_ready_context",
                    "runtime_ready_context": True,
                    "bounded_structured_context": True,
                    "structured_context_type": "macro_official_context",
                    "claim_types": ["macro_industry_context", "official_series_context", "company_exposure_to_driver_context"],
                    "allowed_claims": ["macro_industry_context", "official_series_context", "company_exposure_to_driver_context", "verification_lead"],
                    "forbidden_claims": ["issuer_revenue", "product_sales", "shipments", "market_share", "margin", "demand_proof"],
                    "ticker": routing_ticker,
                    "company": routing_ticker,
                    "context_scope": "v1_company_exposure_to_macro_driver_bridge",
                    "routing_ticker_binding_status": "macro_exposure_bridge_not_issuer_fact",
                    "macro_driver_id": driver_key,
                    "macro_driver_name": exposure["driver_name"],
                    "exposure_type": exposure["exposure_type"],
                    "exposure_basis": exposure["exposure_basis"],
                    "source_entity_name": source_row.get("source_entity_name"),
                    "topic": exposure["driver_name"],
                    "product_or_segment": source_row.get("product_or_segment") or driver_key,
                    "product_family": source_row.get("product_or_segment") or driver_key,
                    "metric_name": source_row.get("metric_name") or driver_key,
                    "value": source_row.get("value"),
                    "unit": source_row.get("unit"),
                    "period": source_row.get("period") or source_row.get("observation_date") or source_row.get("as_of_date"),
                    "observation_date": source_row.get("observation_date"),
                    "as_of_datetime": generated_at,
                    "api_route": source_row.get("api_route"),
                    "citation": source_row.get("citation") or {"url": source_row.get("api_route"), "record_id": source_row.get("evidence_ref")},
                    "issuer_binding_status": "macro_exposure_bridge_context",
                    "product_binding_status": "product_mentioned_in_snapshot" if source_row.get("product_or_segment") else "not_bound",
                    "counterparty_binding_status": "not_bound",
                    "entity_binding": {
                        "schema_version": "finsight_public_web_entity_binding_v0_1",
                        "issuer_ticker": routing_ticker,
                        "issuer_binding_status": "macro_exposure_bridge_context",
                        "product_binding_status": "product_mentioned_in_snapshot" if source_row.get("product_or_segment") else "not_bound",
                        "counterparty_binding_status": "not_bound",
                        "source_entity_role": "macro_driver_exposure_bridge",
                        "resolver_status": "macro_driver_to_lane_exposure_bridge",
                        "binding_claim_boundary": "Ticker is exposed to a macro driver by V1 lane rule only; this is not issuer-specific financial evidence.",
                    },
                    "resolver_status": "macro_driver_to_lane_exposure_bridge",
                    "resolver_reason": "official_macro_driver_mapped_to_v1_lane_exposure",
                    "context_only": True,
                    "exact_value_authority": False,
                    "can_support_company_exact_fact": False,
                    "claim_boundary": "Official macro/industry context and company exposure bridge only; no issuer revenue, margin, demand, sales, shipment, or share inference.",
                    "authority_boundary": "L2 official macro context; never issuer exact metric authority.",
                    "preview": _compact_text(summary, 620),
                    "text": _compact_text(summary, 620),
                }
            )
    return _dedupe_rows(out)


def latest_macro_driver_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        source_id = str(row.get("source_id") or "")
        if source_id not in MACRO_SOURCE_IDS:
            continue
        driver_key = macro_driver_key(row)
        if not driver_key:
            continue
        grouped[driver_key].append(dict(row))
    latest: dict[str, dict[str, Any]] = {}
    for driver_key, values in grouped.items():
        values.sort(key=lambda row: str(row.get("period") or row.get("observation_date") or row.get("as_of_date") or ""))
        latest[driver_key] = values[-1]
    return latest


def macro_driver_key(row: Mapping[str, Any]) -> str:
    source_id = str(row.get("source_id") or "")
    metric = str(row.get("metric_name") or row.get("product_or_segment") or row.get("identifier") or "")
    if metric.upper() == "FEDFUNDS":
        return "FEDFUNDS"
    if source_id == "eia_open_data":
        return "EIA_OPEN_DATA"
    return ""


def build_v1_macro_official_exposure_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "market_valuation_analyst": context_rows,
        "capital_ownership_macro_analyst": context_rows,
        "industry_supply_chain_analyst": context_rows,
    }
    return build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        case_id="v1_macro_official_exposure_bridge",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["macro_official_context"],
        generated_at=generated_at,
    )


def build_summary(
    *,
    input_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    coverage_gate: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_coverage: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_row_count": len(input_rows),
        "context_row_count": len(rows),
        "parser_backed_row_count": len([row for row in rows if row.get("source_specific_parser")]),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "source_id_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "macro_driver_counts": dict(sorted(Counter(str(row.get("macro_driver_id") or "") for row in rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "macro_official_context_requirement": _requirement_summary(coverage_gate, "macro_official_context"),
        "outputs": {"rows": str(output_rows), "coverage_gate": str(output_coverage)},
        "boundary": "Macro exposure bridge rows connect official macro drivers to V1 lane exposure only; they cannot support issuer exact financial, sales, demand, shipment, margin, or share claims.",
    }


def _requirement_summary(payload: Mapping[str, Any], requirement_id: str) -> dict[str, Any]:
    for row in payload.get("requirements") or []:
        if isinstance(row, Mapping) and str(row.get("requirement_id") or "") == requirement_id:
            return {
                "status": str(row.get("status") or ""),
                "observed_row_count": int(row.get("observed_row_count") or 0),
                "parser_row_count": int(row.get("parser_row_count") or 0),
                "entity_bound_row_count": int(row.get("entity_bound_row_count") or 0),
                "specialist_visible_row_count": int(row.get("specialist_visible_row_count") or 0),
                "gaps": list(row.get("gaps") or []),
            }
    return {}


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
        if not key:
            key = hashlib.sha1(json.dumps(dict(row), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _compact_text(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: max(0, limit - 3)].rstrip() + "..."


if __name__ == "__main__":
    raise SystemExit(main())
