from __future__ import annotations

import argparse
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


SCHEMA_VERSION = "finsight_source_route_attempt_ledger_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_source_route_attempt_ledger_summary_v0_1"

DEFAULT_EXACT_CLOSEOUT = REPO_ROOT / "data" / "manifests" / "exact_slot_gap_closeout_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_DIAGNOSTIC = REPO_ROOT / "data" / "manifests" / "product_kpi_deep_gap_diagnostic_v0_1.jsonl"
DEFAULT_PRODUCT_FAMILY_EVIDENCE = (
    REPO_ROOT / "data" / "manifests" / "r17_product_family_evidence_runtime_rows_v0_1.jsonl"
)
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "source_route_attempt_ledger_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "source_route_attempt_ledger_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT
    / "docs"
    / "internal"
    / "vnext_20260610"
    / "vertical_lanes"
    / "r17_source_route_attempt_ledger.zh-CN.md"
)


RETRYABLE_ATTEMPT_STATUSES = {
    "fetch_failed",
    "unusable_response",
    "rate_limited",
    "blocked",
    "http_403",
    "http_429",
    "js_required",
    "pdf_required",
    "parser_failed",
}

CURRENT_CONTRACT_CANARIES = [
    {
        "ticker": "DECK",
        "scope": "product_kpi",
        "expected_route": "earnings_release_or_10k_brand_table",
        "expected_role": "financial_product_kpi",
        "why": "Deckers publishes UGG/HOKA brand net sales in official earnings/filing materials.",
    },
]

NEW_CONTRACT_CANARIES = [
    {
        "ticker": "NVDA",
        "scope": "technical_product_spec",
        "expected_route": "official_product_datasheet",
        "expected_role": "technical_product_spec",
        "why": "H100/Blackwell official product specs should support product comparison, not product revenue.",
    },
    {
        "ticker": "NVDA",
        "scope": "customer_deployment_proxy",
        "expected_route": "official_customer_deployment_news",
        "expected_role": "deployment_proxy",
        "why": "Named customer GPU deployments should support demand proxy with strict no-revenue inference.",
    },
    {
        "ticker": "MSFT",
        "scope": "cloud_operating_metric",
        "expected_route": "annual_report_cloud_rpo_and_cloud_metric",
        "expected_role": "industry_operating_metric",
        "why": "Azure/cloud disclosures should route to SaaS/cloud operating metrics, not SKU product KPI.",
    },
    {
        "ticker": "ASML",
        "scope": "semicap_system_units",
        "expected_route": "annual_report_system_sales_units_and_installed_base",
        "expected_role": "industry_operating_metric",
        "why": "EUV/DUV/system unit disclosures should support semicap operating metrics.",
    },
    {
        "ticker": "8035.T",
        "scope": "semicap_ir_operating_metric",
        "expected_route": "jp_ir_transcript_and_annual_report_table",
        "expected_role": "industry_operating_metric",
        "why": "Tokyo Electron IR/transcript data should route to SPE/field-solution operating metrics.",
    },
    {
        "ticker": "2317.TW",
        "scope": "business_mix_operating_metric",
        "expected_route": "company_ir_revenue_mix_and_cloud_networking_category",
        "expected_role": "business_segment_or_operating_metric",
        "why": "Hon Hai official IR can support business mix/AI server exposure, not SKU revenue.",
    },
]


PRODUCT_PARSER_DEBT_CLASSES = {
    "verifier_business_segment_column_group_required",
    "verifier_sentence_relation_insufficient",
    "verifier_period_or_version_conflict",
    "verifier_product_table_context_insufficient",
    "non_us_local_or_ir_parser_required",
    "product_surface_or_taxonomy_available_no_company_kpi_candidate",
    "no_product_kpi_candidate_in_current_public_scan",
    "parser_candidate_found_but_not_runtime_promotable",
}

PRODUCT_REROUTE_CLASSES = {
    "verifier_business_segment_only_candidates",
    "verifier_operating_metric_requires_industry_slot",
}

PRODUCT_BOUNDARY_CLASSES = {
    "verifier_percentage_or_change_only_candidates",
    "verifier_region_or_geography_only_candidates",
    "verifier_non_product_or_total_candidates",
    "geographic_or_non_product_only",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build R17 auditable source-route attempt ledger and known-public canary gate."
    )
    parser.add_argument("--exact-closeout", type=Path, default=DEFAULT_EXACT_CLOSEOUT)
    parser.add_argument("--product-kpi-diagnostic", type=Path, default=DEFAULT_PRODUCT_KPI_DIAGNOSTIC)
    parser.add_argument("--product-family-evidence", type=Path, default=DEFAULT_PRODUCT_FAMILY_EVIDENCE)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    exact_rows = _load_jsonl(args.exact_closeout)
    product_rows = _load_jsonl(args.product_kpi_diagnostic)
    product_family_evidence_rows = _load_jsonl(args.product_family_evidence)
    ledger_rows = build_source_route_attempt_ledger_rows(
        exact_closeout_rows=exact_rows,
        product_kpi_diagnostic_rows=product_rows,
        product_family_evidence_rows=product_family_evidence_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=ledger_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, ledger_rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["unclassified_count"]:
        return 1
    return 0


def build_source_route_attempt_ledger_rows(
    *,
    exact_closeout_rows: Iterable[Mapping[str, Any]],
    product_kpi_diagnostic_rows: Iterable[Mapping[str, Any]],
    product_family_evidence_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str,
) -> list[dict[str, Any]]:
    exact_rows = [dict(row) for row in exact_closeout_rows]
    product_rows = [dict(row) for row in product_kpi_diagnostic_rows]
    evidence_rows = [dict(row) for row in product_family_evidence_rows or []]
    product_by_ticker = {str(row.get("ticker") or "").upper(): row for row in product_rows if row.get("ticker")}
    out: list[dict[str, Any]] = []
    for row in sorted(exact_rows, key=lambda item: (str(item.get("ticker") or ""), str(item.get("requirement_id") or ""))):
        out.append(_classify_exact_closeout(row, generated_at=generated_at))
    for row in sorted(product_rows, key=lambda item: str(item.get("ticker") or "")):
        out.append(_classify_product_kpi_diagnostic(row, generated_at=generated_at))
    for canary in CURRENT_CONTRACT_CANARIES:
        out.append(_classify_current_contract_canary(canary, product_by_ticker, generated_at=generated_at))
    for canary in NEW_CONTRACT_CANARIES:
        out.append(_classify_new_contract_canary(canary, product_by_ticker, evidence_rows, generated_at=generated_at))
    return out


def build_summary(*, rows: list[dict[str, Any]], generated_at: str, output_rows: Path, output_report: Path) -> dict[str, Any]:
    row_type_counts = Counter(str(row.get("ledger_row_type") or "") for row in rows)
    gate_counts = Counter(str(row.get("gate_status") or "") for row in rows)
    debt_counts = Counter(str(row.get("debt_class") or "") for row in rows)
    action_required_rows = [row for row in rows if _is_action_required(row)]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "action_required" if action_required_rows else "pass",
        "row_count": len(rows),
        "row_type_counts": dict(sorted(row_type_counts.items())),
        "gate_status_counts": dict(sorted(gate_counts.items())),
        "debt_class_counts": dict(sorted(debt_counts.items())),
        "action_required_count": len(action_required_rows),
        "unclassified_count": gate_counts.get("unclassified", 0),
        "known_public_canary_count": row_type_counts.get("known_public_canary", 0),
        "known_public_current_contract_failure_count": sum(
            1
            for row in rows
            if row.get("ledger_row_type") == "known_public_canary"
            and row.get("gate_status") == "current_contract_route_or_parser_failure"
        ),
        "known_public_new_contract_required_count": sum(
            1
            for row in rows
            if row.get("ledger_row_type") == "known_public_canary"
            and row.get("gate_status") == "new_contract_required"
        ),
        "final_boundary_blocked_count": sum(
            1 for row in rows if row.get("final_boundary_allowed") is False and row.get("ledger_row_type") != "known_public_canary"
        ),
        "top_action_required_reasons": dict(
            Counter(str(row.get("gate_reason") or "") for row in action_required_rows).most_common(15)
        ),
        "outputs": {"rows": str(output_rows), "report": str(output_report)},
        "policy": (
            "R17 ledger is an audit/control artifact. Rows with parser/source-route debt must be repaired or explicitly "
            "closed before they are treated as final public-source boundaries. Known-public canaries prevent disclosed "
            "facts from being hidden behind generic gap labels."
        ),
    }


def _classify_exact_closeout(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    requirement_id = str(row.get("requirement_id") or "")
    closeout_class = str(row.get("closeout_class") or "")
    closeout_reason = str(row.get("closeout_reason") or "")
    attempts = list(row.get("sample_attempts") or [])
    attempt_statuses = {str(attempt.get("status") or "") for attempt in attempts if isinstance(attempt, Mapping)}
    has_retryable_attempt = bool(attempt_statuses.intersection(RETRYABLE_ATTEMPT_STATUSES))
    attempt_count = int(row.get("attempt_count") or 0)
    gate_status = "unclassified"
    debt_class = "unclassified"
    final_boundary_allowed = False
    if closeout_class == "public_source_exhausted_gap":
        if has_retryable_attempt:
            gate_status = "source_route_retry_required"
            debt_class = "fetch_or_parser_retry_debt"
        elif attempt_count > 0:
            gate_status = "attempt_backed_public_boundary"
            debt_class = "public_source_exhausted"
            final_boundary_allowed = True
        else:
            gate_status = "source_route_attempt_missing"
            debt_class = "missing_attempt_debt"
    elif closeout_class in {"adapter_or_locator_deep_repair_needed", "parser_gap", "resolver_gap"}:
        gate_status = "route_or_parser_debt"
        debt_class = closeout_class
    elif closeout_class == "not_applicable_or_source_gap":
        gate_status = "not_applicable_or_source_gap"
        debt_class = "not_applicable"
        final_boundary_allowed = True
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ledger_id": f"source_route_attempt_ledger:{ticker}:{requirement_id}:{row.get('gap_id') or ''}",
        "ledger_row_type": "source_role_exact_gap",
        "ticker": ticker,
        "company_name": row.get("company_name") or "",
        "primary_lane_id": row.get("primary_lane_id") or "",
        "source_layer": _source_layer_for_requirement(requirement_id),
        "source_role": requirement_id,
        "represented_contract": "source_role_exact_slot",
        "current_status": closeout_class,
        "source_closeout_reason": closeout_reason,
        "gate_status": gate_status,
        "gate_reason": _exact_gate_reason(gate_status, closeout_reason, attempt_statuses),
        "debt_class": debt_class,
        "attempt_count": attempt_count,
        "attempt_statuses": sorted(attempt_statuses),
        "sample_attempts": attempts[:5],
        "final_boundary_allowed": final_boundary_allowed,
        "next_action": row.get("next_action") or "",
        "claim_boundary": row.get("claim_boundary") or "",
    }


def _classify_product_kpi_diagnostic(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    diagnostic_class = str(row.get("diagnostic_class") or "")
    status = str(row.get("product_kpi_status") or "")
    if diagnostic_class == "ready_product_kpi_exact":
        gate_status = "ready"
        debt_class = "none"
        final_boundary_allowed = True
    elif diagnostic_class == "ready_business_segment_metric_only":
        gate_status = "ready_but_not_product_kpi"
        debt_class = "business_segment_not_product_exact"
        final_boundary_allowed = True
    elif diagnostic_class in PRODUCT_REROUTE_CLASSES:
        gate_status = "reroute_required"
        debt_class = "industry_or_business_metric_reroute_debt"
        final_boundary_allowed = False
    elif diagnostic_class in PRODUCT_PARSER_DEBT_CLASSES:
        gate_status = "route_or_parser_debt"
        debt_class = "product_kpi_source_route_or_parser_debt"
        final_boundary_allowed = False
    elif diagnostic_class in PRODUCT_BOUNDARY_CLASSES:
        gate_status = "not_product_kpi_boundary"
        debt_class = "not_product_kpi"
        final_boundary_allowed = True
    else:
        gate_status = "unclassified"
        debt_class = "unclassified"
        final_boundary_allowed = False
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ledger_id": f"source_route_attempt_ledger:{ticker}:product_kpi:{diagnostic_class}",
        "ledger_row_type": "product_kpi_gap_or_ready",
        "ticker": ticker,
        "company_name": row.get("company_name") or "",
        "primary_lane_id": row.get("primary_lane_id") or "",
        "source_layer": "L1",
        "source_role": "product_kpi_exact",
        "represented_contract": "company_disclosed_product_kpi_exact",
        "current_status": status,
        "source_closeout_reason": row.get("diagnostic_reason") or row.get("product_kpi_closeout_reason") or "",
        "gate_status": gate_status,
        "gate_reason": _product_gate_reason(gate_status, row),
        "debt_class": debt_class,
        "attempt_count": int(row.get("final_repair_closeout_count") or 0) + int(row.get("source_specific_verifier_candidate_count") or 0),
        "attempt_statuses": [],
        "sample_attempts": [],
        "runtime_row_count": int(row.get("runtime_row_count") or 0),
        "strict_candidate_count": int(row.get("strict_candidate_count") or 0),
        "final_boundary_allowed": final_boundary_allowed,
        "next_action": row.get("next_action") or "",
        "claim_boundary": row.get("claim_boundary") or "",
    }


def _classify_current_contract_canary(
    canary: Mapping[str, str], product_by_ticker: Mapping[str, Mapping[str, Any]], *, generated_at: str
) -> dict[str, Any]:
    ticker = str(canary["ticker"]).upper()
    row = product_by_ticker.get(ticker, {})
    status = str(row.get("product_kpi_status") or "")
    diagnostic_class = str(row.get("diagnostic_class") or "")
    covered = status == "product_kpi_exact_ready" or diagnostic_class == "ready_product_kpi_exact"
    gate_status = "canary_covered" if covered else "current_contract_route_or_parser_failure"
    return _canary_row(
        canary,
        generated_at=generated_at,
        current_status=status or diagnostic_class or "missing",
        gate_status=gate_status,
        debt_class="none" if covered else "known_public_current_contract_debt",
        final_boundary_allowed=covered,
        gate_reason=(
            "Known-public company-disclosed product KPI is already represented."
            if covered
            else "Known-public company-disclosed fact is not represented by the current product KPI runtime contract."
        ),
    )


def _classify_new_contract_canary(
    canary: Mapping[str, str],
    product_by_ticker: Mapping[str, Mapping[str, Any]],
    product_family_evidence_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(canary["ticker"]).upper()
    row = product_by_ticker.get(ticker, {})
    status = str(row.get("product_kpi_status") or row.get("diagnostic_class") or "not_modeled")
    covered = _product_family_evidence_covers_canary(canary, product_family_evidence_rows)
    if covered:
        return _canary_row(
            canary,
            generated_at=generated_at,
            current_status="modeled_by_r17_product_family_evidence_contract",
            gate_status="canary_covered",
            debt_class="none",
            final_boundary_allowed=True,
            gate_reason=(
                "Known-public fact is represented by R17 product-family evidence runtime rows under a bounded "
                "non-Product-KPI or industry-operating-metric contract."
            ),
        )
    return _canary_row(
        canary,
        generated_at=generated_at,
        current_status=status,
        gate_status="new_contract_required",
        debt_class="product_spec_or_proxy_contract_debt",
        final_boundary_allowed=False,
        gate_reason="Known-public fact belongs to a required evidence role that the current Product-KPI exact contract does not model.",
    )


def _product_family_evidence_covers_canary(
    canary: Mapping[str, str], product_family_evidence_rows: Iterable[Mapping[str, Any]]
) -> bool:
    ticker = str(canary["ticker"]).upper()
    scope = str(canary["scope"])
    for row in product_family_evidence_rows:
        if str(row.get("ticker") or "").upper() != ticker:
            continue
        source_role = str(row.get("source_role") or "")
        runtime_contract = str(row.get("runtime_contract") or "")
        structured_context_type = str(row.get("structured_context_type") or "")
        slot_id = str(row.get("slot_id") or "")
        metric_family = str(row.get("metric_family") or "")
        claim_types = {str(value) for value in row.get("claim_types") or []}
        if scope == "technical_product_spec" and (
            source_role == "technical_product_spec"
            or runtime_contract == "ProductSpecSlot"
            or "technical_product_spec" in claim_types
        ):
            return True
        if scope == "customer_deployment_proxy" and (
            source_role == "customer_deployment_proxy"
            or runtime_contract == "CustomerDeploymentProxy"
            or "customer_deployment_proxy" in claim_types
        ):
            return True
        if scope == "cloud_operating_metric" and (
            slot_id == "cloud_revenue"
            or metric_family == "cloud_revenue"
            or "cloud_operating_metric" in claim_types
        ):
            return True
        if scope == "semicap_system_units" and (
            slot_id in {"semicap_system_sales_units", "semicap_euv_system_sales_units", "semicap_duv_system_sales_units"}
            or metric_family == "semicap_system_sales_units"
        ):
            return True
        if scope == "semicap_ir_operating_metric" and (
            slot_id == "semicap_field_solutions_sales"
            or metric_family == "semicap_field_solutions_sales"
            or structured_context_type == "industry_operating_metric_exact_slot"
        ):
            return True
        if scope == "business_mix_operating_metric" and (
            source_role == "business_mix_operating_metric"
            or slot_id == "cloud_networking_largest_product_category_q4"
            or metric_family == "business_mix_rank"
        ):
            return True
    return False


def _canary_row(
    canary: Mapping[str, str],
    *,
    generated_at: str,
    current_status: str,
    gate_status: str,
    debt_class: str,
    final_boundary_allowed: bool,
    gate_reason: str,
) -> dict[str, Any]:
    ticker = str(canary["ticker"]).upper()
    scope = str(canary["scope"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ledger_id": f"source_route_attempt_ledger:{ticker}:known_public_canary:{scope}",
        "ledger_row_type": "known_public_canary",
        "ticker": ticker,
        "company_name": "",
        "primary_lane_id": "",
        "source_layer": "canary",
        "source_role": scope,
        "represented_contract": str(canary.get("expected_role") or ""),
        "current_status": current_status,
        "source_closeout_reason": str(canary.get("why") or ""),
        "gate_status": gate_status,
        "gate_reason": gate_reason,
        "debt_class": debt_class,
        "attempt_count": 0,
        "attempt_statuses": [],
        "sample_attempts": [],
        "expected_route": str(canary.get("expected_route") or ""),
        "final_boundary_allowed": final_boundary_allowed,
        "next_action": _canary_next_action(scope),
        "claim_boundary": "Canary rows are control rows only; they do not become evidence or ClaimCards.",
    }


def _source_layer_for_requirement(requirement_id: str) -> str:
    if requirement_id in {"primary_company_disclosure"}:
        return "L1"
    if requirement_id in {
        "official_product_surface",
        "financial_regulatory_context",
        "energy_utility_context",
        "regulated_product_context",
        "auto_product_identity_context",
    }:
        return "L2"
    return "L3"


def _exact_gate_reason(gate_status: str, closeout_reason: str, attempt_statuses: set[str]) -> str:
    if gate_status == "source_route_retry_required":
        return f"Closeout includes retryable fetch/parser status: {','.join(sorted(attempt_statuses.intersection(RETRYABLE_ATTEMPT_STATUSES)))}"
    if gate_status == "attempt_backed_public_boundary":
        return f"Attempt-backed public boundary: {closeout_reason}"
    if gate_status == "route_or_parser_debt":
        return f"Closeout still requires route/parser/resolver repair: {closeout_reason}"
    if gate_status == "source_route_attempt_missing":
        return "No attempt rows recorded for a purported public-source boundary."
    if gate_status == "not_applicable_or_source_gap":
        return f"Requirement is not applicable or source-specific gap: {closeout_reason}"
    return f"Unclassified exact-slot closeout: {closeout_reason}"


def _product_gate_reason(gate_status: str, row: Mapping[str, Any]) -> str:
    reason = str(row.get("diagnostic_reason") or row.get("product_kpi_closeout_reason") or "")
    if gate_status == "route_or_parser_debt":
        return f"Product KPI source route/parser debt remains: {reason}"
    if gate_status == "reroute_required":
        return f"Fact is useful but must be rerouted outside Product-KPI exact: {reason}"
    if gate_status == "not_product_kpi_boundary":
        return f"Candidate is not Product-KPI exact and must remain bounded: {reason}"
    if gate_status == "ready_but_not_product_kpi":
        return f"Business/segment metric is ready but not SKU/product-family KPI: {reason}"
    if gate_status == "ready":
        return f"Product KPI exact ready: {reason}"
    return f"Unclassified product KPI diagnostic: {reason}"


def _canary_next_action(scope: str) -> str:
    if scope == "product_kpi":
        return "Repair current L1 earnings-release/filing product table route before allowing a final Product-KPI gap."
    if scope == "technical_product_spec":
        return "Add ProductSpecSlot contract and official datasheet/product-page parser."
    if scope == "customer_deployment_proxy":
        return "Add CustomerDeploymentProxy contract and official customer-deployment/news parser with no revenue inference."
    if scope.endswith("operating_metric") or scope in {"cloud_operating_metric", "semicap_system_units"}:
        return "Add industry operating metric slot and source-specific IR/annual-report parser."
    return "Add source-role specific contract before declaring this public fact out of scope."


def _is_action_required(row: Mapping[str, Any]) -> bool:
    return str(row.get("gate_status") or "") in {
        "source_route_retry_required",
        "source_route_attempt_missing",
        "route_or_parser_debt",
        "reroute_required",
        "current_contract_route_or_parser_failure",
        "new_contract_required",
        "unclassified",
    }


def render_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# R17 Source Route Attempt Ledger",
            "",
            f"- schema_version: `{summary.get('schema_version')}`",
            f"- generated_at: `{summary.get('generated_at')}`",
            f"- status: `{summary.get('status')}`",
            f"- row_count: `{summary.get('row_count')}`",
            f"- action_required_count: `{summary.get('action_required_count')}`",
            f"- final_boundary_blocked_count: `{summary.get('final_boundary_blocked_count')}`",
            f"- known_public_current_contract_failure_count: `{summary.get('known_public_current_contract_failure_count')}`",
            f"- known_public_new_contract_required_count: `{summary.get('known_public_new_contract_required_count')}`",
            "",
            "## Gate Status Counts",
            "",
            "```json",
            json.dumps(summary.get("gate_status_counts") or {}, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Top Action Required Reasons",
            "",
            "```json",
            json.dumps(summary.get("top_action_required_reasons") or {}, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Policy",
            "",
            str(summary.get("policy") or ""),
            "",
        ]
    )


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
