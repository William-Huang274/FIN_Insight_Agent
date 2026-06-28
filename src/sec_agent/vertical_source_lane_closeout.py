from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.source_coverage_gate import (
    REQUIREMENT_TEMPLATES,
    SOURCE_CLASS_TO_SOURCE_ID,
    build_source_coverage_gate,
)


VERTICAL_LANE_SOURCE_COVERAGE_CLOSEOUT_SCHEMA_VERSION = "finsight_vertical_lane_source_coverage_closeout_v0_1"
V1_SOURCE_COVERAGE_CLOSEOUT_SCHEMA_VERSION = "finsight_v1_source_coverage_closeout_v0_1"

STRONG_BINDING_STATUSES = {
    "issuer_mentioned_in_snapshot",
    "company_domain_bound",
    "product_mentioned_in_snapshot",
    "technology_topic_bound",
    "counterparty_mentioned_in_snapshot",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
}


def build_v1_source_coverage_closeout(
    *,
    v1_coverage: Mapping[str, Any],
    source_layer_capability_rows: Iterable[Mapping[str, Any]],
    observed_rows: Iterable[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible V1 wrapper around the generic lane closeout."""
    if not v1_coverage.get("industry_schema"):
        v1_coverage = {**dict(v1_coverage), "industry_schema": "semiconductors_hardware"}
    payload = build_lane_source_coverage_closeout(
        lane_coverage=v1_coverage,
        source_layer_capability_rows=source_layer_capability_rows,
        observed_rows=observed_rows,
        generated_at=generated_at,
    )
    payload["schema_version"] = V1_SOURCE_COVERAGE_CLOSEOUT_SCHEMA_VERSION
    return payload


def build_lane_source_coverage_closeout(
    *,
    lane_coverage: Mapping[str, Any],
    source_layer_capability_rows: Iterable[Mapping[str, Any]],
    observed_rows: Iterable[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Close out a vertical lane source profile against real materialized rows.

    The lane registry gate is a source-profile gate. This closeout adds the
    runtime check that matters before lane cases: whether real L1/L2/L3 rows for
    primary lane tickers exist, are parser-backed, are entity-bound where needed,
    and remain bounded by their source layer.
    """
    generated_at = generated_at or _utc_now()
    lane_id = str(lane_coverage.get("lane_id") or "UNKNOWN").upper()
    lane_name = str(lane_coverage.get("lane_name") or lane_id)
    industry_schema = str(lane_coverage.get("industry_schema") or "generic_public_research")
    primary_tickers = {str(ticker).upper() for ticker in lane_coverage.get("primary_ticker_universe") or []}
    inclusive_tickers = {str(ticker).upper() for ticker in lane_coverage.get("ticker_universe") or []} | primary_tickers
    source_rows = [dict(row) for row in source_layer_capability_rows if isinstance(row, Mapping)]
    lane_observed_rows = [
        dict(row)
        for row in observed_rows
        if isinstance(row, Mapping) and _ticker(row) in inclusive_tickers and _row_lane_compatible(row, lane_id)
    ]
    specialist_visible_rows = _specialist_visible_rows(lane_observed_rows)
    runtime_gate = build_source_coverage_gate(
        industry_schema=industry_schema,
        phase="runtime_case",
        source_layer_capability={"rows": source_rows},
        observed_rows=lane_observed_rows,
        specialist_visible_rows=specialist_visible_rows,
        generated_at=generated_at,
    )
    registry_gate = lane_coverage.get("lane_source_coverage_gate") if isinstance(lane_coverage.get("lane_source_coverage_gate"), Mapping) else {}
    registry_by_req = {
        str(row.get("requirement_id")): dict(row)
        for row in registry_gate.get("requirements") or []
        if isinstance(row, Mapping)
    }
    closeout_rows = [
        _requirement_closeout(
            runtime_req=dict(row),
            registry_req=registry_by_req.get(str(row.get("requirement_id"))) or {},
            observed_rows=lane_observed_rows,
            primary_tickers=primary_tickers,
            inclusive_tickers=inclusive_tickers,
            lane_id=lane_id,
        )
        for row in runtime_gate.get("requirements") or []
        if isinstance(row, Mapping)
    ]
    source_gap_ledger = [
        _source_gap_from_requirement(row, lane_id=lane_id)
        for row in closeout_rows
        if row.get("closeout_status") != "pass"
    ]
    commercial_gap_ledger = _commercial_gap_ledger(lane_coverage, lane_id=lane_id)
    primary_ticker_coverage = _ticker_coverage(
        observed_rows=lane_observed_rows,
        tickers=primary_tickers,
    )
    inclusive_ticker_coverage = _ticker_coverage(
        observed_rows=lane_observed_rows,
        tickers=inclusive_tickers,
    )
    validation = _validate_closeout(
        closeout_rows=closeout_rows,
        observed_rows=lane_observed_rows,
        runtime_gate=runtime_gate,
    )
    status = "fail" if validation["status"] == "fail" else "gap" if source_gap_ledger else "pass"
    return {
        "schema_version": VERTICAL_LANE_SOURCE_COVERAGE_CLOSEOUT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "lane_id": lane_id,
        "lane_name": lane_name,
        "industry_schema": industry_schema,
        "status": status,
        "registry_gate_status": registry_gate.get("status") or "not_run",
        "runtime_gate_status": runtime_gate.get("status") or "not_run",
        "summary": {
            "requirement_count": len(closeout_rows),
            "pass_requirement_count": sum(1 for row in closeout_rows if row.get("closeout_status") == "pass"),
            "source_gap_requirement_count": len(source_gap_ledger),
            "commercial_gap_count": len(commercial_gap_ledger),
            "primary_ticker_count": len(primary_tickers),
            "inclusive_ticker_count": len(inclusive_tickers),
            "observed_runtime_row_count": len(lane_observed_rows),
            "observed_primary_ticker_count": len(primary_ticker_coverage["covered_tickers"]),
            "observed_inclusive_ticker_count": len(inclusive_ticker_coverage["covered_tickers"]),
            "by_closeout_status": dict(sorted(Counter(str(row.get("closeout_status")) for row in closeout_rows).items())),
        },
        "requirement_closeouts": closeout_rows,
        "source_gap_ledger": source_gap_ledger,
        "commercial_gap_ledger": commercial_gap_ledger,
        "primary_ticker_coverage": primary_ticker_coverage,
        "inclusive_ticker_coverage": inclusive_ticker_coverage,
        "runtime_gate": runtime_gate,
        "validation": validation,
        "boundary": (
            f"{lane_id} source closeout resolves the registry/package ambiguity by checking real materialized rows. "
            f"A pass means the lane has at least one primary {lane_id} ticker with parser-backed coverage for that requirement. "
            f"It does not mean every {lane_id} issuer or every product has complete coverage."
        ),
    }


def write_v1_source_coverage_closeout(
    payload: Mapping[str, Any],
    *,
    output_path: str | Path,
    report_path: str | Path,
) -> dict[str, str]:
    return write_lane_source_coverage_closeout(payload, output_path=output_path, report_path=report_path)


def write_lane_source_coverage_closeout(
    payload: Mapping[str, Any],
    *,
    output_path: str | Path,
    report_path: str | Path,
) -> dict[str, str]:
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(render_lane_source_coverage_closeout_report(payload), encoding="utf-8")
    return {"closeout": str(output), "report": str(report)}


def render_v1_source_coverage_closeout_report(payload: Mapping[str, Any]) -> str:
    return render_lane_source_coverage_closeout_report(payload)


def render_lane_source_coverage_closeout_report(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lane_id = str(payload.get("lane_id") or "")
    lane_name = str(payload.get("lane_name") or "")
    lines = [
        f"# {lane_id} Source Coverage Closeout",
        "",
        f"- lane_name: `{lane_name}`",
        f"- industry_schema: `{payload.get('industry_schema') or ''}`",
        f"- status: `{payload.get('status')}`",
        f"- registry_gate_status: `{payload.get('registry_gate_status')}`",
        f"- runtime_gate_status: `{payload.get('runtime_gate_status')}`",
        f"- requirement_count: `{summary.get('requirement_count')}`",
        f"- pass_requirement_count: `{summary.get('pass_requirement_count')}`",
        f"- source_gap_requirement_count: `{summary.get('source_gap_requirement_count')}`",
        f"- commercial_gap_count: `{summary.get('commercial_gap_count')}`",
        f"- observed_runtime_row_count: `{summary.get('observed_runtime_row_count')}`",
        f"- observed_primary_ticker_count: `{summary.get('observed_primary_ticker_count')}` / `{summary.get('primary_ticker_count')}`",
        "",
        "## Requirement Closeouts",
        "",
        "| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload.get("requirement_closeouts") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("requirement_id") or ""),
                    str(row.get("closeout_status") or ""),
                    str(row.get("registry_status") or ""),
                    str(row.get("runtime_status") or ""),
                    str(row.get("primary_ticker_covered_count") or 0),
                    str(row.get("inclusive_ticker_covered_count") or 0),
                    _table_text(row.get("next_action") or ""),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Gap Ledger", ""])
    source_gaps = [row for row in payload.get("source_gap_ledger") or [] if isinstance(row, Mapping)]
    if source_gaps:
        for gap in source_gaps:
            lines.append(
                f"- `{gap.get('requirement_id')}`: `{gap.get('gap_type')}`; "
                f"primary={gap.get('primary_ticker_covered_count')}, inclusive={gap.get('inclusive_ticker_covered_count')}; "
                f"next={gap.get('next_action')}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Commercial Gap Ledger", ""])
    for gap in payload.get("commercial_gap_ledger") or []:
        if not isinstance(gap, Mapping):
            continue
        lines.append(
            f"- `{gap.get('gap_id')}`: {gap.get('description')} "
            f"(boundary={gap.get('claim_boundary')})"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            str(payload.get("boundary") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _requirement_closeout(
    *,
    runtime_req: Mapping[str, Any],
    registry_req: Mapping[str, Any],
    observed_rows: Sequence[Mapping[str, Any]],
    primary_tickers: set[str],
    inclusive_tickers: set[str],
    lane_id: str,
) -> dict[str, Any]:
    requirement_id = str(runtime_req.get("requirement_id") or "")
    source_ids = tuple(str(item) for item in runtime_req.get("source_ids") or [])
    primary_rows = [
        row for row in observed_rows
        if _ticker(row) in primary_tickers and _row_matches_sources(row, source_ids)
    ]
    inclusive_rows = [
        row for row in observed_rows
        if _ticker(row) in inclusive_tickers and _row_matches_sources(row, source_ids)
    ]
    primary_parser_rows = [row for row in primary_rows if _row_parser_backed(row)]
    inclusive_parser_rows = [row for row in inclusive_rows if _row_parser_backed(row)]
    requirement_template = REQUIREMENT_TEMPLATES.get(requirement_id)
    entity_kinds = tuple(requirement_template.entity_binding_kinds) if requirement_template else ()
    primary_bound_rows = [row for row in primary_parser_rows if _row_entity_bound(row, entity_kinds)]
    inclusive_bound_rows = [row for row in inclusive_parser_rows if _row_entity_bound(row, entity_kinds)]
    requires_entity_binding = bool(entity_kinds)
    primary_covered = bool(primary_parser_rows) and (not requires_entity_binding or bool(primary_bound_rows))
    inclusive_covered = bool(inclusive_parser_rows) and (not requires_entity_binding or bool(inclusive_bound_rows))
    runtime_status = str(runtime_req.get("status") or "unknown")
    registry_status = str(registry_req.get("status") or "unknown")
    if runtime_status == "fail" or registry_status == "fail":
        closeout_status = "fail"
        closeout_reason = "source coverage gate detected an exact-authority or source-policy failure."
    elif primary_covered:
        closeout_status = "pass"
        closeout_reason = f"parser-backed primary {lane_id} ticker rows are materialized and bound enough for this requirement."
    elif inclusive_covered:
        closeout_status = "adjacent_or_secondary_route_only_gap"
        closeout_reason = f"route has parser-backed rows only for secondary/adjacent tickers, not primary {lane_id} tickers."
    elif runtime_status == "pass":
        closeout_status = "runtime_route_pass_without_primary_lane_rows"
        closeout_reason = f"runtime gate passed on available rows, but no primary {lane_id} ticker row coverage was found."
    elif registry_status == "pass":
        closeout_status = "route_ready_no_lane_runtime_rows_gap"
        closeout_reason = f"source profile is ready, but no {lane_id} materialized runtime rows were observed."
    else:
        gap_types = [str(gap.get("gap_type") or "") for gap in runtime_req.get("gaps") or [] if isinstance(gap, Mapping)]
        closeout_status = gap_types[0] if gap_types else "source_parser_or_mapping_gap"
        closeout_reason = "source route is not complete for V1 runtime use."
    return {
        "schema_version": "finsight_vertical_lane_source_requirement_closeout_v0_1",
        "lane_id": lane_id,
        "requirement_id": requirement_id,
        "dimension": runtime_req.get("dimension"),
        "closeout_status": closeout_status,
        "closeout_reason": closeout_reason,
        "registry_status": registry_status,
        "runtime_status": runtime_status,
        "source_ids": list(source_ids),
        "primary_row_count": len(primary_rows),
        "primary_parser_row_count": len(primary_parser_rows),
        "primary_entity_bound_row_count": len(primary_bound_rows),
        "primary_ticker_covered_count": len({_ticker(row) for row in primary_parser_rows}),
        "primary_entity_bound_ticker_count": len({_ticker(row) for row in primary_bound_rows}),
        "inclusive_row_count": len(inclusive_rows),
        "inclusive_parser_row_count": len(inclusive_parser_rows),
        "inclusive_entity_bound_row_count": len(inclusive_bound_rows),
        "inclusive_ticker_covered_count": len({_ticker(row) for row in inclusive_parser_rows}),
        "inclusive_entity_bound_ticker_count": len({_ticker(row) for row in inclusive_bound_rows}),
        "sample_primary_tickers": sorted({_ticker(row) for row in primary_parser_rows})[:12],
        "sample_inclusive_tickers": sorted({_ticker(row) for row in inclusive_parser_rows})[:12],
        "claim_boundary": runtime_req.get("claim_boundary"),
        "next_action": runtime_req.get("next_action"),
        "runtime_gaps": runtime_req.get("gaps") or [],
    }


def _source_gap_from_requirement(row: Mapping[str, Any], *, lane_id: str) -> dict[str, Any]:
    return {
        "schema_version": "finsight_vertical_lane_source_gap_v0_1",
        "gap_id": f"{lane_id}_SOURCE_GAP::{row.get('requirement_id')}",
        "lane_id": lane_id,
        "requirement_id": row.get("requirement_id"),
        "gap_type": row.get("closeout_status"),
        "dimension": row.get("dimension"),
        "source_ids": row.get("source_ids") or [],
        "primary_ticker_covered_count": row.get("primary_ticker_covered_count") or 0,
        "inclusive_ticker_covered_count": row.get("inclusive_ticker_covered_count") or 0,
        "claim_boundary": row.get("claim_boundary"),
        "next_action": row.get("next_action"),
        "reason": row.get("closeout_reason"),
    }


def _commercial_gap_ledger(lane_coverage: Mapping[str, Any], *, lane_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, description in enumerate(lane_coverage.get("expected_commercial_gaps") or [], start=1):
        rows.append(
            {
                "schema_version": "finsight_vertical_lane_commercial_gap_v0_1",
                "gap_id": f"{lane_id}_COMMERCIAL_GAP::EXPECTED::{idx}",
                "lane_id": lane_id,
                "description": str(description),
                "gap_type": "commercial_gap",
                "claim_boundary": "public sources cannot fill this as company sales/share/order/inventory authority",
                "required_commercial_sources": _commercial_sources_for_description(str(description)),
            }
        )
    gap_summary = lane_coverage.get("gap_summary") if isinstance(lane_coverage.get("gap_summary"), Mapping) else {}
    for source, count in (gap_summary.get("commercial_sources_top") or {}).items():
        rows.append(
            {
                "schema_version": "finsight_vertical_lane_commercial_gap_v0_1",
                "gap_id": f"{lane_id}_COMMERCIAL_GAP::PRODUCT_GRAPH::{source}",
                "lane_id": lane_id,
                "description": f"{source} appears in product evidence graph commercial gap ledger for {count} {lane_id}-related missing product/market metrics.",
                "gap_type": "commercial_gap_from_product_evidence_graph",
                "claim_boundary": "must remain bounded/commercial gap unless licensed tracker data is added",
                "required_commercial_sources": [str(source)],
            }
        )
    return rows


def _ticker_coverage(
    *,
    observed_rows: Sequence[Mapping[str, Any]],
    tickers: set[str],
) -> dict[str, Any]:
    by_source: dict[str, set[str]] = defaultdict(set)
    row_counts = Counter()
    for row in observed_rows:
        ticker = _ticker(row)
        if ticker not in tickers:
            continue
        for source_id in _row_source_ids(row):
            by_source[source_id].add(ticker)
            row_counts[source_id] += 1
    covered = sorted({ticker for tickers_by_source in by_source.values() for ticker in tickers_by_source})
    return {
        "schema_version": "finsight_vertical_lane_ticker_coverage_summary_v0_1",
        "ticker_count": len(tickers),
        "covered_ticker_count": len(covered),
        "covered_tickers": covered,
        "missing_tickers": sorted(tickers - set(covered)),
        "by_source": {
            source_id: {
                "row_count": int(row_counts[source_id]),
                "ticker_count": len(source_tickers),
                "sample_tickers": sorted(source_tickers)[:20],
            }
            for source_id, source_tickers in sorted(by_source.items())
        },
    }


def _specialist_visible_rows(observed_rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    visible: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observed_rows:
        item = dict(row)
        source_ids = _row_source_ids(item)
        dimension = str(item.get("analysis_dimension") or item.get("dimension") or "")
        if str(item.get("source_layer_id") or item.get("source_layer") or item.get("layer_id") or "") == "L1":
            visible["fundamental_analyst"].append(item)
            visible["product_technology_analyst"].append(item)
            visible["capital_ownership_macro_analyst"].append(item)
        if dimension == "product_and_production" or source_ids.intersection(
            {
                "company_product_pages",
                "company_reported_product_operating_metrics",
                "developer_ecosystem_github_npm_pypi_huggingface",
                "channel_pricing_quotations",
                "job_postings_hiring_signals",
                "app_store_rankings",
                "platform_reviews_rankings_downloads",
                "openalex_api",
                "patentsview_api",
            }
        ):
            visible["product_technology_analyst"].append(item)
        if dimension == "industry_supply_chain" or source_ids.intersection({"public_tenders_contracts_orders", "supplier_customer_official_news"}):
            visible["industry_supply_chain_analyst"].append(item)
            visible["capital_ownership_macro_analyst"].append(item)
        if source_ids.intersection({"mainstream_financial_news", "industry_association_reports", "channel_pricing_quotations", "app_store_rankings"}):
            visible["market_valuation_analyst"].append(item)
        if source_ids.intersection({"mainstream_financial_news", "job_postings_hiring_signals", "openalex_api", "patentsview_api"}):
            visible["risk_counterevidence_analyst"].append(item)
        if source_ids.intersection({"fred_api", "fred_graph_csv", "bls_public_api", "bea_data_api", "census_data_api", "eia_open_data"}):
            visible["capital_ownership_macro_analyst"].append(item)
            visible["industry_supply_chain_analyst"].append(item)
            visible["market_valuation_analyst"].append(item)
    return dict(visible)


def _validate_closeout(
    *,
    closeout_rows: Sequence[Mapping[str, Any]],
    observed_rows: Sequence[Mapping[str, Any]],
    runtime_gate: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if runtime_gate.get("exact_authority_violations"):
        errors.append({"type": "runtime_gate_exact_authority_violation", "violations": runtime_gate.get("exact_authority_violations")})
    for row in observed_rows:
        layer_id = str(row.get("source_layer_id") or row.get("source_layer") or row.get("layer_id") or "")
        if layer_id in {"L2", "L3", "L4"} and (
            bool(row.get("exact_value_authority"))
            or bool(row.get("exact_value_authority_ready"))
            or bool(row.get("can_support_company_exact_fact"))
        ):
            errors.append({"type": "non_l1_exact_authority_row", "evidence_ref": row.get("evidence_ref"), "layer_id": layer_id})
    seen = {str(row.get("requirement_id") or "") for row in closeout_rows}
    if len(seen) != len(closeout_rows):
        errors.append({"type": "duplicate_requirement_closeout"})
    return {
        "schema_version": "finsight_vertical_lane_source_coverage_closeout_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def _row_matches_sources(row: Mapping[str, Any], source_ids: Sequence[str]) -> bool:
    return not _row_source_ids(row).isdisjoint(set(source_ids))


def _row_source_ids(row: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("source_id", "underlying_source_id", "source_layer_source_id", "provider_source_id"):
        value = str(row.get(key) or "").strip()
        if value:
            values.add(SOURCE_CLASS_TO_SOURCE_ID.get(value, value))
    source_class = str(row.get("source_class") or "").strip()
    if source_class:
        values.add(SOURCE_CLASS_TO_SOURCE_ID.get(source_class, source_class))
    return values


def _row_lane_compatible(row: Mapping[str, Any], lane_id: str) -> bool:
    """Prevent lane-specific bridge rows from leaking into other lanes."""
    lane_id = str(lane_id or "").upper()
    explicit_values = {
        str(row.get(key) or "").upper()
        for key in ("lane_id", "source_lane_id", "vertical_lane_id")
        if str(row.get(key) or "").strip()
    }
    if explicit_values:
        return lane_id in explicit_values
    for key in ("context_scope", "evidence_ref", "evidence_id"):
        value = str(row.get(key) or "").lower().strip()
        if not value:
            continue
        for idx in range(1, 9):
            prefix = f"v{idx}_"
            if value.startswith(prefix) or f":{prefix}" in value:
                return lane_id == f"V{idx}"
    return True


def _row_parser_backed(row: Mapping[str, Any]) -> bool:
    if row.get("bounded_structured_context") or row.get("source_specific_parser") or row.get("structured_context_type"):
        return True
    return str(row.get("structured_fact_status") or "") in {
        "bounded_context_fact_materialized",
        "context_rows_ready",
        "candidate_rows_ready",
        "exact_fact_materialized",
    }


def _row_entity_bound(row: Mapping[str, Any], kinds: Sequence[str]) -> bool:
    if not kinds:
        return any(
            str(row.get(key) or "") in STRONG_BINDING_STATUSES
            for key in ("issuer_binding_status", "product_binding_status", "counterparty_binding_status")
        )
    checks = {
        "issuer": str(row.get("issuer_binding_status") or ""),
        "product": str(row.get("product_binding_status") or ""),
        "counterparty": str(row.get("counterparty_binding_status") or ""),
    }
    return all(checks.get(kind, "") in STRONG_BINDING_STATUSES for kind in kinds)


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("issuer_ticker") or "").upper().strip()


def _commercial_sources_for_description(description: str) -> list[str]:
    text = description.lower()
    sources: list[str] = []
    if any(term in text for term in ("shipment", "share", "forecast", "tracker")):
        sources.extend(["IDC", "Counterpoint", "Omdia", "Gartner"])
    if any(term in text for term in ("allocation", "hyperscaler", "purchase order", "order")):
        sources.extend(["commercial supply-chain tracker", "channel checks"])
    if "inventory" in text:
        sources.extend(["channel inventory tracker", "retail/POS tracker"])
    return sources or ["commercial market tracker"]


def _table_text(value: Any) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
