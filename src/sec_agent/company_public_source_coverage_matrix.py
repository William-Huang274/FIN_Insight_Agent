from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.source_coverage_gate import (
    INDUSTRY_REQUIREMENT_IDS,
    REQUIREMENT_TEMPLATES,
    SOURCE_CLASS_TO_SOURCE_ID,
    SourceCoverageRequirement,
    normalize_industry_schema,
)
from sec_agent.vertical_source_lane_registry import LANE_BY_ID


COMPANY_PUBLIC_SOURCE_COVERAGE_MATRIX_SCHEMA_VERSION = "finsight_company_public_source_coverage_matrix_v0_1"
COMPANY_PUBLIC_SOURCE_REPAIR_QUEUE_SCHEMA_VERSION = "finsight_company_public_source_repair_queue_v0_1"

DYNAMIC_OBSERVED_REQUIREMENT_IDS = {
    "technical_product_spec",
    "product_generation_edge",
    "product_benchmark_proxy",
    "customer_deployment_proxy",
    "official_customer_order_or_deployment_event",
    "capital_structure_disclosure",
    "lagged_ownership_context",
    "working_capital_liquidity",
    "securities_offering_filing_event",
    "insider_transaction_filing_event",
    "beneficial_ownership_filing_event",
    "proxy_governance_filing_event",
}

STRONG_ISSUER_BINDING_STATUSES = {
    "issuer_mentioned_in_snapshot",
    "company_domain_bound",
    "issuer_subsidiary_official_domain_bound",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
    "macro_exposure_bridge_context",
    "family_assignment_exposure_context",
}
STRONG_PRODUCT_BINDING_STATUSES = {
    "product_mentioned_in_snapshot",
    "technology_topic_bound",
}
STRONG_COUNTERPARTY_BINDING_STATUSES = {
    "counterparty_mentioned_in_snapshot",
    "relationship_context_candidate",
    "counterparty_keyword_context_candidate",
}
PASSING_PARSER_MARKERS = {
    "parser_pass",
    "projector_pass",
    "value_unit_period_product_citation_parser_pass",
    "source_specific_context_parser_pass",
    "public_context_probe_parser_pass",
    "normalized_record_projector_pass",
}
MATERIALIZED_FACT_STATUSES = {
    "exact_fact_materialized",
    "bounded_context_fact_materialized",
    "context_rows_ready",
    "candidate_rows_ready",
}
SOURCE_ROLE_EXEMPTIONS_BY_TICKER: dict[str, dict[str, str]] = {
    "FIVN": {
        "app_rank_store_proxy": (
            "Five9 is a B2B contact-center SaaS issuer; iTunes/App Store probing found no seller-bound "
            "issuer app rows. App-store rank is not a required source role for this product-family assignment."
        ),
    },
    "GTLB": {
        "app_rank_store_proxy": (
            "GitLab is a developer platform/SaaS issuer; official docs/repo and developer ecosystem routes are "
            "the relevant public proxies. App-store rank probing found no seller-bound issuer app rows."
        ),
    },
    "OMC": {
        "app_rank_store_proxy": (
            "Omnicom is an agency/marketing-services issuer, not a consumer app publisher; app-store rank is "
            "not a required public proxy after seller-bound probing found no issuer app rows."
        ),
        "platform_review_proxy": (
            "Omnicom's platform-review route was inherited from a broad digital-media family assignment; public "
            "app/platform review rows are not a required source role for agency-services analysis."
        ),
    },
    "ROST": {
        "platform_review_proxy": (
            "Ross Stores is off-price retail; platform-review rows are not a required source role for store "
            "traffic, merchandising, or operating-metric analysis without a seller-bound app/review surface."
        ),
    },
    "TTD": {
        "app_rank_store_proxy": (
            "The Trade Desk is B2B ad-tech; app-store rank is not a required proxy for its platform adoption "
            "after seller-bound iTunes probing found no issuer app rows."
        ),
        "platform_review_proxy": (
            "The Trade Desk's relevant public proxies are disclosure, partner/customer context, developer/docs, "
            "hiring, and trusted industry sources; public app/platform reviews are not applicable."
        ),
    },
    "APH": {
        "developer_ecosystem_proxy": (
            "Amphenol is a connector/interconnect hardware issuer. Official-domain and GitHub/package locator "
            "attempts found no issuer-bound developer repo/package/docs seed; product pages, distributor routes, "
            "and filings are the applicable public product evidence, not a GitHub/npm developer ecosystem route."
        ),
    },
    "CDW": {
        "developer_ecosystem_proxy": (
            "CDW is a channel/reseller and services issuer. Official-domain and GitHub/package locator attempts "
            "found no issuer-bound developer repo/package/docs seed; channel, customer/order, hiring, and filing "
            "routes are applicable instead."
        ),
    },
    "COHR": {
        "developer_ecosystem_proxy": (
            "Coherent is an optical/photonics hardware issuer. Source probing found no verified issuer-bound "
            "developer repo/package/docs seed; official product/spec pages and disclosure routes are the relevant "
            "public product evidence."
        ),
    },
    "DIOD": {
        "developer_ecosystem_proxy": (
            "Diodes is a discrete/analog semiconductor issuer. Official-domain and GitHub/package locator attempts "
            "found no verified issuer-bound software developer ecosystem seed; datasheets/product pages belong to "
            "official product surface, not GitHub/npm developer activity."
        ),
    },
    "FN": {
        "developer_ecosystem_proxy": (
            "Fabrinet is an optical/electronics contract manufacturing issuer. Source probing found no issuer-bound "
            "developer repo/package/docs seed; supply-chain, customer/order, hiring, and filing routes are applicable."
        ),
    },
    "GLW": {
        "developer_ecosystem_proxy": (
            "Corning is a materials/specialty glass issuer. Locator attempts found no verified issuer-bound developer "
            "repo/package/docs seed; official product/spec, customer, and filing evidence are applicable instead."
        ),
    },
    "IT": {
        "developer_ecosystem_proxy": (
            "Gartner is a research/advisory services issuer, not a developer platform. Official-domain and "
            "GitHub/package probing found no issuer-bound developer ecosystem seed; filings, hiring, and trusted "
            "external context are the applicable public routes."
        ),
    },
    "LITE": {
        "developer_ecosystem_proxy": (
            "Lumentum is an optical components issuer. Source probing found no verified issuer-bound developer "
            "repo/package/docs seed; official product/spec and supply-chain routes are the relevant public evidence."
        ),
    },
    "MTSI": {
        "developer_ecosystem_proxy": (
            "MACOM is an RF/analog semiconductor issuer. Official-domain and GitHub/package probing found no verified "
            "issuer-bound software developer ecosystem seed; product documentation/spec pages should be treated as "
            "official product surface rather than GitHub/npm developer activity."
        ),
    },
    "Q": {
        "developer_ecosystem_proxy": (
            "Qnity Electronics does not currently expose a verified issuer-bound developer repo/package/docs seed in "
            "official-domain or GitHub/package probing; product/filing routes remain applicable."
        ),
    },
    "RMBS": {
        "developer_ecosystem_proxy": (
            "Rambus is semiconductor IP/security hardware issuer. Locator attempts found no verified issuer-bound "
            "public developer repo/package seed; official product/technology pages and filings are applicable instead."
        ),
    },
    "ROP": {
        "developer_ecosystem_proxy": (
            "Roper is a diversified vertical-software/industrial issuer with multiple subsidiaries. The issuer-level "
            "official-domain and GitHub/package locator did not find a stable, Roper-bound developer repo/package seed; "
            "subsidiary-specific routes should be handled as targeted product/company evidence, not a generic issuer "
            "developer ecosystem requirement."
        ),
    },
    "WOLF": {
        "developer_ecosystem_proxy": (
            "Wolfspeed is a silicon-carbide power/RF hardware issuer. Source probing found no verified issuer-bound "
            "software developer ecosystem seed; official product/spec and technology routes are applicable instead."
        ),
    },
}


def build_company_public_source_coverage_matrix(
    *,
    company_assignments: Iterable[Mapping[str, Any]],
    observed_rows: Iterable[Mapping[str, Any]],
    source_capability_rows: Iterable[Mapping[str, Any]] | None = None,
    repair_seed_rows: Iterable[Mapping[str, Any]] | None = None,
    family_source_route_plan_rows: Iterable[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
    input_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build issuer-level public-source coverage matrix from lane assignments and runtime rows.

    The vertical lane closeout answers whether a lane has at least one materialized
    route per required source class. This matrix answers a stricter question:
    for each company in the 600+ universe, which lane-specific source roles have
    parser-backed, entity-bound runtime rows, and which gaps are still repairable.
    """

    generated_at = generated_at or _utc_now()
    assignments = [dict(row) for row in company_assignments if isinstance(row, Mapping)]
    observed = [dict(row) for row in observed_rows if isinstance(row, Mapping)]
    source_capability = [dict(row) for row in source_capability_rows or [] if isinstance(row, Mapping)]
    repair_seeds = [dict(row) for row in repair_seed_rows or [] if isinstance(row, Mapping)]
    family_route_requirements = _family_route_requirements_by_ticker(family_source_route_plan_rows or [])
    source_route_status = _source_route_status(source_capability)

    rows = [
        _company_coverage_row(
            assignment,
            observed_rows=observed,
            source_route_status=source_route_status,
            family_route_requirement_ids=family_route_requirements.get(str(assignment.get("ticker") or "").upper(), set()),
            generated_at=generated_at,
        )
        for assignment in sorted(assignments, key=lambda row: str(row.get("ticker") or ""))
    ]
    repair_queue = build_company_public_source_repair_queue(rows, generated_at=generated_at, repair_seed_rows=repair_seeds)
    validation = validate_company_public_source_coverage_matrix(rows)
    status = "fail" if validation["status"] == "fail" else "gap" if any(row["status"] == "gap" for row in rows) else "pass"
    summary = _matrix_summary(rows, repair_queue=repair_queue)
    return {
        "schema_version": COMPANY_PUBLIC_SOURCE_COVERAGE_MATRIX_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "policy": "issuer_product_source_role_parser_binding_gap_matrix_v0_1",
        "input_paths": dict(input_paths or {}),
        "company_count": len(rows),
        "summary": summary,
        "rows": rows,
        "repair_queue": repair_queue,
        "validation": validation,
        "boundary": (
            "A company-level pass means all lane-required source roles for that issuer have "
            "parser-backed runtime rows with required entity binding. It does not mean every "
            "SKU/model/indication/product metric is covered, and it does not close commercial tracker gaps."
        ),
    }


def build_company_public_source_repair_queue(
    company_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str | None = None,
    repair_seed_rows: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    seed_index = _repair_seed_index(repair_seed_rows or [])
    queue: list[dict[str, Any]] = []
    for company in company_rows:
        ticker = str(company.get("ticker") or "").upper()
        lane_id = str(company.get("primary_lane_id") or "").upper()
        for req in company.get("source_role_matrix") or []:
            if not isinstance(req, Mapping) or req.get("status") == "pass":
                continue
            gap_class = str(req.get("gap_class") or "")
            if gap_class in {"commercial_gap", "known_public_ceiling"}:
                continue
            seeds = _repair_seeds_for_request(seed_index, ticker=ticker, source_ids=req.get("source_ids") or [])
            queue.append(
                {
                    "schema_version": COMPANY_PUBLIC_SOURCE_REPAIR_QUEUE_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "repair_request_id": _stable_id(
                        "company_source_repair",
                        [
                            ticker,
                            lane_id,
                            str(req.get("requirement_id") or ""),
                            str(req.get("gap_type") or ""),
                        ],
                    ),
                    "ticker": ticker,
                    "company_name": company.get("company_name") or "",
                    "primary_lane_id": lane_id,
                    "primary_lane_name": company.get("primary_lane_name") or "",
                    "requirement_id": req.get("requirement_id") or "",
                    "dimension": req.get("dimension") or "",
                    "gap_class": gap_class,
                    "gap_type": req.get("gap_type") or "",
                    "target_source_ids": req.get("source_ids") or [],
                    "target_layer_ids": req.get("layer_ids") or [],
                    "target_entity_binding_kinds": req.get("entity_binding_kinds") or [],
                    "repair_priority": req.get("repair_priority") or "medium",
                    "next_action": req.get("next_action") or "",
                    "claim_boundary": req.get("claim_boundary") or "",
                    "public_data_ceiling": company.get("public_data_ceiling") or [],
                    "expected_commercial_gaps": company.get("expected_commercial_gaps") or [],
                    "repair_seed_status": "seed_available" if seeds else "seed_missing",
                    "repair_seed_count": sum(seed["count"] for seed in seeds),
                    "repair_seed_source_ids": [seed["source_id"] for seed in seeds],
                    "sample_repair_seed_refs": [
                        ref
                        for seed in seeds
                        for ref in seed.get("sample_refs", [])
                    ][:5],
                }
            )
    return sorted(
        queue,
        key=lambda row: (
            _priority_rank(row.get("repair_priority")),
            str(row.get("primary_lane_id") or ""),
            str(row.get("ticker") or ""),
            str(row.get("requirement_id") or ""),
        ),
    )


def write_company_public_source_coverage_matrix(
    payload: Mapping[str, Any],
    *,
    output_json_path: str | Path,
    output_jsonl_path: str | Path,
    output_repair_queue_path: str | Path,
    output_report_path: str | Path,
) -> dict[str, str]:
    output_json = Path(output_json_path)
    output_jsonl = Path(output_jsonl_path)
    output_queue = Path(output_repair_queue_path)
    output_report = Path(output_report_path)
    for path in (output_json, output_jsonl, output_queue, output_report):
        path.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for row in payload.get("rows") or []:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with output_queue.open("w", encoding="utf-8", newline="\n") as handle:
        for row in payload.get("repair_queue") or []:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    output_report.write_text(render_company_public_source_coverage_report(payload), encoding="utf-8")
    return {
        "matrix_json": str(output_json),
        "matrix_jsonl": str(output_jsonl),
        "repair_queue_jsonl": str(output_queue),
        "report": str(output_report),
    }


def render_company_public_source_coverage_report(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# Company Public Source Coverage Matrix",
        "",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- status: `{payload.get('status')}`",
        f"- company_count: `{payload.get('company_count')}`",
        f"- public_interface_ready_company_count: `{summary.get('public_interface_ready_company_count')}`",
        f"- repair_queue_count: `{summary.get('repair_queue_count')}`",
        "",
        "## Lane Summary",
        "",
        "| lane | companies | ready | partial | gap | requirements | pass | source gaps | parser gaps | resolver gaps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for lane_id, row in sorted((summary.get("by_lane") or {}).items()):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(lane_id),
                    str(row.get("company_count") or 0),
                    str(row.get("ready_company_count") or 0),
                    str(row.get("partial_company_count") or 0),
                    str(row.get("gap_company_count") or 0),
                    str(row.get("requirement_count") or 0),
                    str(row.get("pass_requirement_count") or 0),
                    str(row.get("source_gap_count") or 0),
                    str(row.get("parser_gap_count") or 0),
                    str(row.get("resolver_gap_count") or 0),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Gap Class Summary",
            "",
            "| gap_class | count |",
            "| --- | ---: |",
        ]
    )
    for gap_class, count in sorted((summary.get("by_gap_class") or {}).items()):
        lines.append(f"| {gap_class} | {count} |")
    lines.extend(["", "## Repair Seed Summary", "", "| seed_status | count |", "| --- | ---: |"])
    for seed_status, count in sorted((summary.get("repair_queue_by_seed_status") or {}).items()):
        lines.append(f"| {seed_status} | {count} |")
    lines.extend(["", "## Top Repair Requests", ""])
    for request in (payload.get("repair_queue") or [])[:30]:
        if not isinstance(request, Mapping):
            continue
        lines.append(
            f"- `{request.get('repair_priority')}` `{request.get('ticker')}` "
            f"`{request.get('requirement_id')}`: `{request.get('gap_type')}`; "
            f"sources={', '.join(request.get('target_source_ids') or [])}; "
            f"seed={request.get('repair_seed_status')}({request.get('repair_seed_count')}); "
            f"next={request.get('next_action')}"
        )
    lines.extend(["", "## Boundary", "", str(payload.get("boundary") or ""), ""])
    return "\n".join(lines)


def validate_company_public_source_coverage_matrix(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            errors.append({"type": "missing_ticker"})
        elif ticker in seen:
            errors.append({"type": "duplicate_ticker", "ticker": ticker})
        seen.add(ticker)
        if not row.get("primary_lane_id"):
            errors.append({"type": "missing_primary_lane", "ticker": ticker})
        if not row.get("source_role_matrix"):
            errors.append({"type": "missing_source_role_matrix", "ticker": ticker})
        for req in row.get("source_role_matrix") or []:
            if not isinstance(req, Mapping):
                continue
            if req.get("status") not in {"pass", "gap", "fail"}:
                errors.append(
                    {
                        "type": "invalid_requirement_status",
                        "ticker": ticker,
                        "requirement_id": req.get("requirement_id"),
                        "status": req.get("status"),
                    }
                )
            if req.get("exact_authority_violation_count"):
                errors.append(
                    {
                        "type": "non_l1_exact_authority_violation",
                        "ticker": ticker,
                        "requirement_id": req.get("requirement_id"),
                        "count": req.get("exact_authority_violation_count"),
                    }
                )
    return {
        "schema_version": "finsight_company_public_source_coverage_matrix_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _company_coverage_row(
    assignment: Mapping[str, Any],
    *,
    observed_rows: Sequence[Mapping[str, Any]],
    source_route_status: Mapping[str, dict[str, Any]],
    family_route_requirement_ids: set[str] | None = None,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(assignment.get("ticker") or "").upper()
    lane_id = str(assignment.get("primary_lane_id") or "").upper()
    secondary_lane_ids = [str(item).upper() for item in assignment.get("secondary_lane_ids") or []]
    lane = LANE_BY_ID.get(lane_id)
    industry_schema = normalize_industry_schema(lane.industry_schema if lane else "")
    compatible_lanes = {lane_id, *secondary_lane_ids}
    company_rows = [
        dict(row)
        for row in observed_rows
        if _row_ticker(row) == ticker and _row_lane_compatible(row, compatible_lanes)
    ]
    source_role_exemptions = _source_role_exemptions_for_assignment(assignment)
    exempted_requirement_ids = {
        str(item.get("requirement_id") or "")
        for item in source_role_exemptions
        if str(item.get("requirement_id") or "")
    }
    requirements = [
        req
        for req in _requirements_for_industry(
            industry_schema,
            family_route_requirement_ids=family_route_requirement_ids,
            observed_dynamic_requirement_ids=_observed_dynamic_requirement_ids(company_rows),
        )
        if req.requirement_id not in exempted_requirement_ids
    ]
    source_role_matrix = [
        _requirement_coverage(
            req,
            company_rows=company_rows,
            source_route_status=source_route_status,
            assignment=assignment,
        )
        for req in requirements
    ]
    requirement_counts = Counter(str(row.get("status") or "") for row in source_role_matrix)
    gap_counts = Counter(str(row.get("gap_class") or "pass") for row in source_role_matrix if row.get("status") != "pass")
    product_families = _product_family_summary(company_rows)
    product_coverage = assignment.get("product_coverage") if isinstance(assignment.get("product_coverage"), Mapping) else {}
    ready = requirement_counts.get("gap", 0) == 0 and requirement_counts.get("fail", 0) == 0
    status = "fail" if requirement_counts.get("fail", 0) else "gap" if not ready else "pass"
    coverage_status = "public_interface_ready" if ready else "partial_public_interface" if requirement_counts.get("pass", 0) else "public_interface_gap"
    return {
        "schema_version": "finsight_company_public_source_coverage_row_v0_1",
        "generated_at": generated_at,
        "ticker": ticker,
        "provider_symbol": assignment.get("provider_symbol") or "",
        "company_name": assignment.get("company_name") or "",
        "country": assignment.get("country") or "",
        "sector": assignment.get("sector") or "",
        "category": assignment.get("category") or "",
        "market_region": assignment.get("market_region") or "",
        "universe_tier": assignment.get("universe_tier") or "",
        "sec_download_eligible": bool(assignment.get("sec_download_eligible")),
        "global_public_download_eligible": bool(assignment.get("global_public_download_eligible")),
        "primary_lane_id": lane_id,
        "primary_lane_name": assignment.get("primary_lane_name") or (lane.lane_name if lane else ""),
        "secondary_lane_ids": secondary_lane_ids,
        "industry_schema": industry_schema,
        "product_taxonomy_status": assignment.get("product_taxonomy_status") or "unknown",
        "product_coverage": {
            "product_node_count": int(product_coverage.get("product_node_count") or 0),
            "product_kpi_ready": bool(product_coverage.get("product_kpi_ready")),
            "official_surface_ready": bool(product_coverage.get("official_surface_ready")),
            "commercial_gap_count": int(product_coverage.get("commercial_gap_count") or 0),
            "missing_metrics": dict(product_coverage.get("missing_metrics") or {}),
            "product_sources": dict(product_coverage.get("product_sources") or {}),
            "node_layers": dict(product_coverage.get("node_layers") or {}),
        },
        "runtime_observed_row_count": len(company_rows),
        "runtime_parser_row_count": sum(1 for row in company_rows if _row_parser_backed(row)),
        "runtime_exact_authority_row_count": sum(1 for row in company_rows if _exact_value_authority(row)),
        "runtime_product_family_count": len(product_families["families"]),
        "runtime_source_ids": sorted({source for row in company_rows for source in _row_source_ids(row)}),
        "runtime_source_layers": dict(sorted(Counter(_row_source_layer(row) for row in company_rows).items())),
        "product_family_summary": product_families,
        "source_role_exemptions": source_role_exemptions,
        "source_role_matrix": source_role_matrix,
        "status": status,
        "coverage_status": coverage_status,
        "summary": {
            "requirement_count": len(source_role_matrix),
            "pass_requirement_count": requirement_counts.get("pass", 0),
            "gap_requirement_count": requirement_counts.get("gap", 0),
            "fail_requirement_count": requirement_counts.get("fail", 0),
            "by_gap_class": dict(sorted(gap_counts.items())),
        },
        "gap_ledger": [
            _company_gap_entry(ticker, lane_id, req)
            for req in source_role_matrix
            if req.get("status") != "pass"
        ],
        "expected_commercial_gaps": list(assignment.get("expected_commercial_gaps") or []),
        "public_data_ceiling": list(assignment.get("public_data_ceiling") or []),
        "boundary": (
            "Issuer-level runtime coverage row; public proxies remain bounded and commercial tracker gaps remain explicit."
        ),
    }


def _requirement_coverage(
    req: SourceCoverageRequirement,
    *,
    company_rows: Sequence[Mapping[str, Any]],
    source_route_status: Mapping[str, dict[str, Any]],
    assignment: Mapping[str, Any],
) -> dict[str, Any]:
    source_ids = set(req.source_ids)
    observed_for_req = [dict(row) for row in company_rows if _row_matches_sources(row, source_ids)]
    parser_rows = [row for row in observed_for_req if _row_parser_backed(row)]
    entity_bound_rows = [row for row in parser_rows if _row_entity_bound(row, req.entity_binding_kinds)]
    exact_violations = [
        row
        for row in parser_rows
        if _exact_value_authority(row) and _row_source_layer(row) not in {"L1", ""}
    ]
    route_sources = {
        source_id: source_route_status.get(source_id) or {"status": "not_registered"}
        for source_id in sorted(source_ids)
    }
    if exact_violations:
        status = "fail"
        gap_class = "source_boundary_violation"
        gap_type = "non_l1_exact_authority_violation"
    elif len(parser_rows) >= req.min_parser_rows and (
        not req.min_entity_bound_rows or len(entity_bound_rows) >= req.min_entity_bound_rows
    ):
        status = "pass"
        gap_class = "pass"
        gap_type = ""
    elif not observed_for_req:
        status = "gap"
        gap_class = "source_gap"
        gap_type = _missing_source_gap_type(req, route_sources=route_sources, assignment=assignment)
    elif len(parser_rows) < req.min_parser_rows:
        status = "gap"
        gap_class = "parser_gap"
        gap_type = "company_rows_observed_but_parser_backed_rows_missing"
    else:
        status = "gap"
        gap_class = "resolver_gap"
        gap_type = "parser_rows_observed_but_required_entity_binding_missing"
    return {
        "requirement_id": req.requirement_id,
        "dimension": req.dimension,
        "status": status,
        "gap_class": gap_class,
        "gap_type": gap_type,
        "source_ids": sorted(source_ids),
        "layer_ids": list(req.layer_ids),
        "specialist_roles": list(req.specialist_roles),
        "entity_binding_kinds": list(req.entity_binding_kinds),
        "claim_boundary": req.claim_boundary,
        "next_action": req.next_action,
        "repair_priority": _repair_priority(req),
        "route_sources": route_sources,
        "observed_row_count": len(observed_for_req),
        "parser_row_count": len(parser_rows),
        "entity_bound_row_count": len(entity_bound_rows),
        "exact_authority_row_count": sum(1 for row in parser_rows if _exact_value_authority(row)),
        "exact_authority_violation_count": len(exact_violations),
        "product_family_count": len({str(row.get("product_family") or row.get("product_or_segment") or "").strip() for row in parser_rows if str(row.get("product_family") or row.get("product_or_segment") or "").strip()}),
        "observed_source_ids": sorted({source for row in observed_for_req for source in _row_source_ids(row)}),
        "observed_source_layers": dict(sorted(Counter(_row_source_layer(row) for row in observed_for_req).items())),
        "parser_statuses": dict(sorted(Counter(str(row.get("parser_status") or "") for row in observed_for_req).items())),
        "issuer_binding_statuses": dict(sorted(Counter(_binding_status(row, "issuer") for row in observed_for_req).items())),
        "product_binding_statuses": dict(sorted(Counter(_binding_status(row, "product") for row in observed_for_req).items())),
        "counterparty_binding_statuses": dict(sorted(Counter(_binding_status(row, "counterparty") for row in observed_for_req).items())),
        "sample_evidence_refs": _sample_refs(parser_rows),
        "sample_urls": _sample_urls(parser_rows),
    }


def _missing_source_gap_type(
    req: SourceCoverageRequirement,
    *,
    route_sources: Mapping[str, Mapping[str, Any]],
    assignment: Mapping[str, Any],
) -> str:
    connected = [
        source_id
        for source_id, row in route_sources.items()
        if str(row.get("status") or "") in {"exact_authority_ready", "runtime_ready_context", "structured_not_promoted"}
    ]
    if not connected:
        return "source_route_not_connected"
    if req.requirement_id == "primary_company_disclosure":
        if not bool(assignment.get("sec_download_eligible")) and bool(assignment.get("global_public_download_eligible")):
            return "non_us_public_filing_or_company_ir_runtime_row_missing"
        if bool(assignment.get("sec_download_eligible")):
            return "sec_or_company_disclosure_runtime_row_missing"
    return "company_specific_runtime_row_missing"


def _family_route_requirements_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        route_id = str(row.get("route_id") or "").strip()
        if ticker and route_id in REQUIREMENT_TEMPLATES:
            out[ticker].add(route_id)
    return out


def _matrix_summary(rows: Sequence[Mapping[str, Any]], *, repair_queue: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_lane: dict[str, dict[str, Any]] = {}
    by_status = Counter(str(row.get("status") or "") for row in rows)
    by_gap_class: Counter[str] = Counter()
    for row in rows:
        lane_id = str(row.get("primary_lane_id") or "UNKNOWN")
        lane = by_lane.setdefault(
            lane_id,
            {
                "company_count": 0,
                "ready_company_count": 0,
                "partial_company_count": 0,
                "gap_company_count": 0,
                "requirement_count": 0,
                "pass_requirement_count": 0,
                "source_gap_count": 0,
                "parser_gap_count": 0,
                "resolver_gap_count": 0,
                "fail_count": 0,
            },
        )
        lane["company_count"] += 1
        status = str(row.get("coverage_status") or "")
        if status == "public_interface_ready":
            lane["ready_company_count"] += 1
        elif status == "partial_public_interface":
            lane["partial_company_count"] += 1
        else:
            lane["gap_company_count"] += 1
        for req in row.get("source_role_matrix") or []:
            if not isinstance(req, Mapping):
                continue
            lane["requirement_count"] += 1
            if req.get("status") == "pass":
                lane["pass_requirement_count"] += 1
            elif req.get("status") == "fail":
                lane["fail_count"] += 1
            gap_class = str(req.get("gap_class") or "pass")
            if gap_class != "pass":
                by_gap_class[gap_class] += 1
            if gap_class == "source_gap":
                lane["source_gap_count"] += 1
            elif gap_class == "parser_gap":
                lane["parser_gap_count"] += 1
            elif gap_class == "resolver_gap":
                lane["resolver_gap_count"] += 1
    return {
        "by_status": dict(sorted(by_status.items())),
        "public_interface_ready_company_count": sum(1 for row in rows if row.get("coverage_status") == "public_interface_ready"),
        "partial_public_interface_company_count": sum(1 for row in rows if row.get("coverage_status") == "partial_public_interface"),
        "public_interface_gap_company_count": sum(1 for row in rows if row.get("coverage_status") == "public_interface_gap"),
        "requirement_count": sum(len(row.get("source_role_matrix") or []) for row in rows),
        "pass_requirement_count": sum(
            1
            for row in rows
            for req in row.get("source_role_matrix") or []
            if isinstance(req, Mapping) and req.get("status") == "pass"
        ),
        "gap_requirement_count": sum(
            1
            for row in rows
            for req in row.get("source_role_matrix") or []
            if isinstance(req, Mapping) and req.get("status") == "gap"
        ),
        "fail_requirement_count": sum(
            1
            for row in rows
            for req in row.get("source_role_matrix") or []
            if isinstance(req, Mapping) and req.get("status") == "fail"
        ),
        "by_gap_class": dict(sorted(by_gap_class.items())),
        "by_lane": dict(sorted(by_lane.items())),
        "repair_queue_count": len(repair_queue),
        "repair_queue_by_priority": dict(sorted(Counter(str(row.get("repair_priority") or "") for row in repair_queue).items())),
        "repair_queue_by_gap_class": dict(sorted(Counter(str(row.get("gap_class") or "") for row in repair_queue).items())),
        "repair_queue_by_seed_status": dict(sorted(Counter(str(row.get("repair_seed_status") or "") for row in repair_queue).items())),
    }


def _source_route_status(source_capability_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in source_capability_rows:
        source_id = str(row.get("source_id") or row.get("underlying_source_id") or "").strip()
        if not source_id:
            continue
        status = str(row.get("evidence_graph_status") or row.get("status") or "").strip() or "unknown"
        rows[source_id] = {
            "status": status,
            "layer_id": row.get("layer_id") or row.get("source_layer_id") or "",
            "runtime_ready_context": bool(row.get("runtime_ready_context")),
            "exact_value_authority_ready": bool(row.get("exact_value_authority_ready") or row.get("can_support_company_exact_fact")),
        }
    return rows


def _repair_seed_index(repair_seed_rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in repair_seed_rows:
        ticker = _row_ticker(row)
        source_id = str(row.get("source_id") or row.get("underlying_source_id") or "").strip()
        if not ticker or not source_id:
            continue
        index[(ticker, source_id)].append(dict(row))
    return index


def _repair_seeds_for_request(
    seed_index: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    ticker: str,
    source_ids: Sequence[str],
) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for source_id in sorted({str(item) for item in source_ids if str(item).strip()}):
        rows = list(seed_index.get((ticker, source_id)) or [])
        if not rows:
            continue
        seeds.append(
            {
                "source_id": source_id,
                "count": len(rows),
                "sample_refs": [
                    str(row.get("node_id") or row.get("evidence_ref") or row.get("snapshot_id") or "")
                    for row in rows[:3]
                    if str(row.get("node_id") or row.get("evidence_ref") or row.get("snapshot_id") or "")
                ],
            }
        )
    return seeds


def _requirements_for_industry(
    industry_schema: str,
    *,
    family_route_requirement_ids: set[str] | None = None,
    observed_dynamic_requirement_ids: set[str] | None = None,
) -> list[SourceCoverageRequirement]:
    template_ids = list(INDUSTRY_REQUIREMENT_IDS.get(industry_schema) or INDUSTRY_REQUIREMENT_IDS["generic_public_research"])
    dynamic_ids = {item for item in (observed_dynamic_requirement_ids or set()) if item in REQUIREMENT_TEMPLATES}
    if family_route_requirement_ids or dynamic_ids:
        route_ids = {item for item in (family_route_requirement_ids or set()) if item in REQUIREMENT_TEMPLATES}
        route_ids.update(dynamic_ids)
        ordered = [item for item in template_ids if item in route_ids]
        ordered.extend(sorted(route_ids - set(ordered)))
        req_ids = tuple(ordered)
    else:
        req_ids = tuple(template_ids)
    return [REQUIREMENT_TEMPLATES[item] for item in req_ids if item in REQUIREMENT_TEMPLATES]


def _observed_dynamic_requirement_ids(company_rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("source_role") or row.get("requirement_id") or "")
        for row in company_rows
        if str(row.get("source_role") or row.get("requirement_id") or "") in DYNAMIC_OBSERVED_REQUIREMENT_IDS
    }


def _source_role_exemptions_for_assignment(assignment: Mapping[str, Any]) -> list[dict[str, Any]]:
    ticker = str(assignment.get("ticker") or "").upper()
    exemptions = SOURCE_ROLE_EXEMPTIONS_BY_TICKER.get(ticker) or {}
    return [
        {
            "schema_version": "finsight_company_source_role_exemption_v0_1",
            "ticker": ticker,
            "requirement_id": requirement_id,
            "status": "not_applicable_after_source_probe",
            "reason": reason,
            "claim_boundary": (
                "This is not a pass for missing data. It removes an inapplicable source role after source probing; "
                "analysts must use the company's applicable disclosure, product, developer, hiring, customer/order, "
                "trusted external, or macro routes instead."
            ),
            "not_a_data_gap": True,
        }
        for requirement_id, reason in sorted(exemptions.items())
    ]


def _company_gap_entry(ticker: str, lane_id: str, req: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gap_id": _stable_id("company_source_gap", [ticker, lane_id, str(req.get("requirement_id") or ""), str(req.get("gap_type") or "")]),
        "ticker": ticker,
        "lane_id": lane_id,
        "requirement_id": req.get("requirement_id") or "",
        "gap_class": req.get("gap_class") or "",
        "gap_type": req.get("gap_type") or "",
        "source_ids": req.get("source_ids") or [],
        "next_action": req.get("next_action") or "",
        "claim_boundary": req.get("claim_boundary") or "",
    }


def _product_family_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    for row in rows:
        family = str(row.get("product_family") or row.get("product_or_segment") or row.get("topic") or "").strip()
        if not family:
            continue
        item = by_family.setdefault(
            family,
            {
                "row_count": 0,
                "source_ids": set(),
                "source_layers": Counter(),
                "exact_authority_row_count": 0,
                "context_row_count": 0,
            },
        )
        item["row_count"] += 1
        item["source_ids"].update(_row_source_ids(row))
        item["source_layers"][_row_source_layer(row)] += 1
        if _exact_value_authority(row):
            item["exact_authority_row_count"] += 1
        else:
            item["context_row_count"] += 1
    families = [
        {
            "product_family": family,
            "row_count": item["row_count"],
            "source_ids": sorted(item["source_ids"]),
            "source_layers": dict(sorted(item["source_layers"].items())),
            "exact_authority_row_count": item["exact_authority_row_count"],
            "context_row_count": item["context_row_count"],
        }
        for family, item in sorted(by_family.items())
    ]
    return {
        "family_count": len(families),
        "families": families[:50],
        "truncated_family_count": max(0, len(families) - 50),
    }


def _row_ticker(row: Mapping[str, Any]) -> str:
    direct = str(row.get("ticker") or row.get("issuer_ticker") or "").strip().upper()
    if direct:
        return direct
    binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    return str(binding.get("issuer_ticker") or "").strip().upper()


def _row_lane_compatible(row: Mapping[str, Any], compatible_lanes: set[str]) -> bool:
    if not compatible_lanes:
        return True
    row_lane = str(row.get("lane_id") or row.get("vertical_lane_id") or "").strip().upper()
    if not row_lane:
        return True
    return row_lane in compatible_lanes


def _row_matches_sources(row: Mapping[str, Any], source_ids: set[str]) -> bool:
    return bool(_row_source_ids(row).intersection(source_ids))


def _row_source_ids(row: Mapping[str, Any]) -> set[str]:
    values = {
        str(row.get("source_id") or "").strip(),
        str(row.get("underlying_source_id") or "").strip(),
    }
    source_class = str(row.get("source_class") or "").strip()
    if source_class:
        values.add(SOURCE_CLASS_TO_SOURCE_ID.get(source_class, source_class))
    return {value for value in values if value}


def _row_source_layer(row: Mapping[str, Any]) -> str:
    return str(row.get("source_layer_id") or row.get("source_layer") or row.get("layer_id") or "").strip() or "UNKNOWN"


def _row_parser_backed(row: Mapping[str, Any]) -> bool:
    parser = str(row.get("parser_status") or "").strip()
    if parser in PASSING_PARSER_MARKERS or parser.endswith("_pass"):
        return True
    if str(row.get("structured_fact_status") or "") in MATERIALIZED_FACT_STATUSES:
        return True
    return bool(row.get("source_specific_parser")) and bool(row.get("runtime_ready_context") or row.get("bounded_structured_context"))


def _row_entity_bound(row: Mapping[str, Any], kinds: Sequence[str]) -> bool:
    for kind in kinds:
        if kind == "issuer" and _binding_status(row, "issuer") not in STRONG_ISSUER_BINDING_STATUSES:
            return False
        if kind == "product" and _binding_status(row, "product") not in STRONG_PRODUCT_BINDING_STATUSES:
            return False
        if kind == "counterparty" and _binding_status(row, "counterparty") not in STRONG_COUNTERPARTY_BINDING_STATUSES:
            return False
    return True


def _binding_status(row: Mapping[str, Any], kind: str) -> str:
    key = f"{kind}_binding_status"
    direct = str(row.get(key) or "").strip()
    if direct:
        return direct
    binding = row.get("entity_binding") if isinstance(row.get("entity_binding"), Mapping) else {}
    return str(binding.get(key) or "").strip()


def _exact_value_authority(row: Mapping[str, Any]) -> bool:
    return bool(row.get("exact_value_authority") or row.get("can_support_company_exact_fact"))


def _sample_refs(rows: Sequence[Mapping[str, Any]], limit: int = 5) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ref = str(row.get("evidence_ref") or row.get("evidence_id") or row.get("snapshot_id") or "").strip()
        if not ref or ref in seen:
            continue
        refs.append(ref)
        seen.add(ref)
        if len(refs) >= limit:
            break
    return refs


def _sample_urls(rows: Sequence[Mapping[str, Any]], limit: int = 5) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for row in rows:
        citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
        url = str(row.get("url") or row.get("source_url") or row.get("snapshot_url") or citation.get("url") or "").strip()
        if not url or url in seen:
            continue
        urls.append(url)
        seen.add(url)
        if len(urls) >= limit:
            break
    return urls


def _repair_priority(req: SourceCoverageRequirement) -> str:
    if req.requirement_id in {"primary_company_disclosure", "official_product_surface"}:
        return "high"
    if req.dimension in {"product_and_production", "industry_supply_chain"}:
        return "medium"
    return "low"


def _priority_rank(priority: Any) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(priority or ""), 3)


def _stable_id(prefix: str, parts: Sequence[str]) -> str:
    digest = hashlib.sha1("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
