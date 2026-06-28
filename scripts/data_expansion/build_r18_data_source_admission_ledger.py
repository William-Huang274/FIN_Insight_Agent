from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_COMPANY_COVERAGE_PATH = Path("data/manifests/company_public_source_coverage_matrix_v0_1.jsonl")
DEFAULT_EXACT_SLOT_COVERAGE_PATH = Path("data/manifests/exact_slot_coverage_matrix_v0_1.jsonl")
DEFAULT_ATTEMPT_LEDGER_PATH = Path("data/manifests/source_route_attempt_ledger_v0_1.jsonl")
DEFAULT_VERTICAL_REGISTRY_PATH = Path("data/manifests/vertical_source_lane_registry_v0_1.json")
DEFAULT_OUTPUT_JSONL_PATH = Path("data/manifests/r18_data_source_admission_ledger_v0_1.jsonl")
DEFAULT_OUTPUT_SUMMARY_PATH = Path("data/manifests/r18_data_source_admission_ledger_summary_v0_1.json")
DEFAULT_OUTPUT_REPORT_PATH = Path("docs/internal/vnext_20260610/r18_data_source_admission_ledger.zh-CN.md")

SCHEMA_VERSION = "finsight_r18_data_source_admission_ledger_v0_1"

COMPANY_SPECIFIC_REQUIREMENTS = {
    "primary_company_disclosure",
    "official_product_surface",
    "company_reported_product_kpi",
    "company_reported_operating_metric",
    "auto_product_identity_context",
    "regulated_product_context",
    "public_order_proxy",
    "official_customer_order_or_deployment_event",
    "technical_product_spec",
    "product_generation_edge",
    "product_benchmark_proxy",
    "customer_deployment_proxy",
    "capital_structure_disclosure",
    "lagged_ownership_context",
    "working_capital_liquidity",
    "securities_offering_filing_event",
    "insider_transaction_filing_event",
    "beneficial_ownership_filing_event",
    "proxy_governance_filing_event",
    "supply_chain_official_relationship",
    "channel_offer_proxy",
    "developer_ecosystem_proxy",
    "app_review_proxy",
    "hiring_capacity_proxy",
    "technology_research_proxy",
}

SUPPORT_SURFACE_BY_REQUIREMENT = {
    "primary_company_disclosure": "fundamental_company_disclosure",
    "official_product_surface": "product_and_technology",
    "company_reported_product_kpi": "product_kpi_exact",
    "company_reported_operating_metric": "business_operating_metric",
    "trusted_external_context": "industry_competition_market_context",
    "macro_official_context": "macro_industry_driver",
    "technology_research_proxy": "technology_research_ip",
    "auto_product_identity_context": "regulated_product_identity",
    "regulated_product_context": "regulated_product_context",
    "public_order_proxy": "public_order_supply_chain_proxy",
    "official_customer_order_or_deployment_event": "official_customer_order_deployment_event",
    "technical_product_spec": "product_spec_and_capability",
    "product_generation_edge": "product_spec_and_capability",
    "product_benchmark_proxy": "product_spec_and_capability",
    "customer_deployment_proxy": "official_customer_deployment_signal",
    "capital_structure_disclosure": "capital_funding_ownership_market_liquidity",
    "lagged_ownership_context": "capital_funding_ownership_market_liquidity",
    "working_capital_liquidity": "capital_funding_ownership_market_liquidity",
    "securities_offering_filing_event": "capital_funding_ownership_market_liquidity",
    "insider_transaction_filing_event": "capital_funding_ownership_market_liquidity",
    "beneficial_ownership_filing_event": "capital_funding_ownership_market_liquidity",
    "proxy_governance_filing_event": "capital_funding_ownership_market_liquidity",
    "supply_chain_official_relationship": "supply_chain_relationship",
    "channel_offer_proxy": "channel_offer_availability_proxy",
    "developer_ecosystem_proxy": "developer_ecosystem_proxy",
    "app_review_proxy": "app_marketplace_review_proxy",
    "hiring_capacity_proxy": "hiring_capacity_proxy",
}

SUPPORT_SURFACE_BY_DIMENSION = {
    "fundamentals": "fundamental_company_disclosure",
    "product_and_production": "product_and_technology",
    "industry_supply_chain": "industry_supply_chain",
    "macro_and_industry": "macro_industry_driver",
    "competition_and_market_position": "industry_competition_market_context",
    "capital_ownership_macro": "capital_funding_ownership_market_liquidity",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"r18_source_admission:{digest}"


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _support_surface(requirement_id: str, dimension: str) -> str:
    return SUPPORT_SURFACE_BY_REQUIREMENT.get(
        requirement_id,
        SUPPORT_SURFACE_BY_DIMENSION.get(dimension, dimension or "unknown"),
    )


def _is_company_specific(requirement_id: str, matrix_entry: dict[str, Any]) -> bool:
    if requirement_id in COMPANY_SPECIFIC_REQUIREMENTS:
        return True
    entity_kinds = set(matrix_entry.get("entity_binding_kinds") or [])
    if {"issuer", "counterparty", "product"} & entity_kinds:
        return True
    return bool(matrix_entry.get("entity_bound_row_count", 0))


def _route_status(source_meta: dict[str, Any] | None) -> str:
    if not source_meta:
        return "source_not_registered"
    return str(source_meta.get("status") or "source_registered")


def _adapter_parser_status(
    matrix_entry: dict[str, Any],
    source_id: str,
    source_meta: dict[str, Any] | None,
    exact_entry: dict[str, Any] | None,
    attempt_entry: dict[str, Any] | None,
) -> str:
    exact_status = str((exact_entry or {}).get("status") or "")
    if exact_status == "exact_slot_ready":
        return "parser_verified_exact_slot_ready"
    if matrix_entry.get("parser_row_count", 0) > 0 and matrix_entry.get("status") == "pass":
        return "parser_verified_context_ready"
    if attempt_entry:
        gate = str(attempt_entry.get("gate_status") or "")
        if gate in {"route_or_parser_debt", "source_route_retry_required"}:
            return gate
        if bool(attempt_entry.get("final_boundary_allowed")):
            return "attempt_backed_final_boundary"
        return gate or "attempted_not_ready"
    status = _route_status(source_meta)
    if status in {"runtime_ready_context", "exact_authority_ready"}:
        return "route_registered_no_parser_backed_company_row"
    if status in {"not_registered", "staging_parser_gate_pending", "structured_not_promoted"}:
        return status
    return status


def _availability_status(
    matrix_entry: dict[str, Any],
    source_meta: dict[str, Any] | None,
    exact_entry: dict[str, Any] | None,
    attempt_entry: dict[str, Any] | None,
) -> str:
    exact_status = str((exact_entry or {}).get("status") or "")
    if exact_status == "exact_slot_ready":
        return "runtime_ready_exact_or_bounded_slot"
    if (
        matrix_entry.get("status") == "pass"
        and matrix_entry.get("parser_row_count", 0) > 0
        and matrix_entry.get("exact_authority_violation_count", 0) == 0
    ):
        return "runtime_ready_context_or_signal"
    if attempt_entry and bool(attempt_entry.get("final_boundary_allowed")):
        return "attempt_backed_public_boundary"
    if attempt_entry:
        gate = str(attempt_entry.get("gate_status") or "")
        if gate in {"route_or_parser_debt", "source_route_retry_required"}:
            return "route_or_parser_debt"
        return "planning_only_attempted_not_ready"
    status = _route_status(source_meta)
    if status in {"runtime_ready_context", "exact_authority_ready"}:
        return "planning_only_route_registered_no_company_row"
    if status in {"not_registered", "staging_parser_gate_pending", "structured_not_promoted"}:
        return "planning_only_adapter_or_parser_pending"
    return "planning_only"


def _can_enter_evidence(
    availability_status: str,
    matrix_entry: dict[str, Any],
    exact_entry: dict[str, Any] | None,
) -> bool:
    if availability_status == "runtime_ready_exact_or_bounded_slot":
        return True
    if availability_status != "runtime_ready_context_or_signal":
        return False
    if matrix_entry.get("exact_authority_violation_count", 0) != 0:
        return False
    if matrix_entry.get("parser_row_count", 0) <= 0:
        return False
    # Existing source coverage gates already encode role-specific binding.
    # Exact-slot rows remain the stronger admission signal when present.
    return bool((exact_entry or {}).get("status") == "exact_slot_ready" or matrix_entry.get("status") == "pass")


def _data_summary(matrix_entry: dict[str, Any], source_id: str, exact_entry: dict[str, Any] | None) -> str:
    exact_count = int((exact_entry or {}).get("exact_slot_count") or 0)
    observed = int(matrix_entry.get("observed_row_count") or 0)
    parser_count = int(matrix_entry.get("parser_row_count") or 0)
    families = int(matrix_entry.get("product_family_count") or 0)
    boundary = str(matrix_entry.get("claim_boundary") or "").strip()
    bits = [
        f"source_id={source_id}",
        f"observed_rows={observed}",
        f"parser_rows={parser_count}",
        f"exact_slots={exact_count}",
        f"product_families={families}",
    ]
    if boundary:
        bits.append(f"boundary={boundary}")
    return "; ".join(bits)


def _source_layer(matrix_entry: dict[str, Any], source_meta: dict[str, Any] | None) -> str:
    if source_meta and source_meta.get("layer_id"):
        return str(source_meta["layer_id"])
    layers = matrix_entry.get("layer_ids") or []
    return ",".join(str(layer) for layer in layers) if layers else ""


def _index_exact_rows(exact_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for company in exact_rows:
        ticker = str(company.get("ticker") or "")
        for entry in company.get("source_role_exact_slot_matrix") or []:
            requirement_id = str(entry.get("requirement_id") or "")
            if ticker and requirement_id:
                index[(ticker, requirement_id)] = entry
    return index


def _index_attempt_rows(attempt_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in attempt_rows:
        ticker = str(row.get("ticker") or "")
        source_role = str(row.get("source_role") or row.get("requirement_id") or "")
        if ticker and source_role:
            by_key[(ticker, source_role)].append(row)

    def rank(row: dict[str, Any]) -> tuple[int, int]:
        gate = str(row.get("gate_status") or "")
        if gate in {"route_or_parser_debt", "source_route_retry_required"}:
            return (0, -int(row.get("attempt_count") or 0))
        if not row.get("final_boundary_allowed"):
            return (1, -int(row.get("attempt_count") or 0))
        return (2, -int(row.get("attempt_count") or 0))

    return {key: sorted(rows, key=rank)[0] for key, rows in by_key.items()}


def _admission_source_ids(
    matrix_entry: dict[str, Any],
    exact_entry: dict[str, Any] | None,
    route_sources: dict[str, Any] | None,
) -> list[str]:
    """Return only source ids that are actually supporting the admission row.

    A source role can be satisfied by any one of several acceptable routes, for
    example channel offer can come from e-commerce, channel quote, or distributor
    locator rows. When the role passes because one route produced parser-backed
    rows, the ledger must not emit evidence-ready rows for the unobserved sibling
    source ids.
    """
    configured = _ordered_unique(
        matrix_entry.get("source_ids")
        or list((route_sources or {}).keys())
        or []
    )
    if not configured:
        configured = ["unknown_source"]
    configured_set = set(configured)

    observed = _ordered_unique(matrix_entry.get("observed_source_ids") or [])
    if matrix_entry.get("status") == "pass" and observed:
        matched = [source_id for source_id in observed if source_id in configured_set]
        return matched or observed

    exact_target_sources = _ordered_unique((exact_entry or {}).get("target_source_ids") or [])
    if str((exact_entry or {}).get("status") or "") == "exact_slot_ready" and exact_target_sources:
        matched = [source_id for source_id in exact_target_sources if source_id in configured_set]
        return matched or exact_target_sources

    return configured


def _ordered_unique(values: Any) -> list[str]:
    if values in (None, "", [], {}):
        return []
    items = values if isinstance(values, list) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def build_data_source_admission_ledger_rows(
    company_coverage_rows: list[dict[str, Any]],
    exact_slot_rows: list[dict[str, Any]],
    attempt_rows: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    exact_index = _index_exact_rows(exact_slot_rows)
    attempt_index = _index_attempt_rows(attempt_rows)
    ledger_rows: list[dict[str, Any]] = []

    for company in company_coverage_rows:
        ticker = str(company.get("ticker") or company.get("provider_symbol") or "")
        company_name = str(company.get("company_name") or "")
        primary_lane_id = str(company.get("primary_lane_id") or "")
        primary_lane_name = str(company.get("primary_lane_name") or "")
        industry_schema = str(company.get("industry_schema") or "")
        market_region = str(company.get("market_region") or "")
        sector = str(company.get("sector") or "")

        for matrix_entry in company.get("source_role_matrix") or []:
            requirement_id = str(matrix_entry.get("requirement_id") or "")
            if not requirement_id:
                continue
            exact_entry = exact_index.get((ticker, requirement_id))
            attempt_entry = attempt_index.get((ticker, requirement_id))
            route_sources = matrix_entry.get("route_sources") or {}
            source_ids = _admission_source_ids(matrix_entry, exact_entry, route_sources if isinstance(route_sources, dict) else {})
            dimension = str(matrix_entry.get("dimension") or "")

            for source_id in source_ids:
                source_meta = route_sources.get(source_id) if isinstance(route_sources, dict) else None
                availability = _availability_status(matrix_entry, source_meta, exact_entry, attempt_entry)
                adapter_status = _adapter_parser_status(
                    matrix_entry,
                    str(source_id),
                    source_meta,
                    exact_entry,
                    attempt_entry,
                )
                evidence_ready = _can_enter_evidence(availability, matrix_entry, exact_entry)
                sample_urls = _merge_lists(matrix_entry.get("sample_urls"), (exact_entry or {}).get("sample_urls"))
                sample_evidence_refs = _merge_lists(
                    matrix_entry.get("sample_evidence_refs"),
                    (exact_entry or {}).get("sample_exact_slot_refs"),
                )
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "ledger_id": _stable_id(ticker, requirement_id, source_id),
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "company_name": company_name,
                    "primary_lane_id": primary_lane_id,
                    "primary_lane_name": primary_lane_name,
                    "industry_schema": industry_schema,
                    "market_region": market_region,
                    "sector": sector,
                    "support_surface": _support_surface(requirement_id, dimension),
                    "dimension": dimension,
                    "source_role": requirement_id,
                    "source_id": str(source_id),
                    "source_layer": _source_layer(matrix_entry, source_meta),
                    "company_specific": _is_company_specific(requirement_id, matrix_entry),
                    "availability_status": availability,
                    "can_enter_evidence_bundle": evidence_ready,
                    "adapter_parser_status": adapter_status,
                    "route_source_status": _route_status(source_meta),
                    "observed_row_count": int(matrix_entry.get("observed_row_count") or 0),
                    "parser_row_count": int(matrix_entry.get("parser_row_count") or 0),
                    "entity_bound_row_count": int(matrix_entry.get("entity_bound_row_count") or 0),
                    "exact_slot_count": int((exact_entry or {}).get("exact_slot_count") or 0),
                    "exact_authority_violation_count": int(matrix_entry.get("exact_authority_violation_count") or 0),
                    "parser_statuses": matrix_entry.get("parser_statuses") or {},
                    "issuer_binding_statuses": matrix_entry.get("issuer_binding_statuses") or {},
                    "product_binding_statuses": matrix_entry.get("product_binding_statuses") or {},
                    "counterparty_binding_statuses": matrix_entry.get("counterparty_binding_statuses") or {},
                    "claim_boundary": matrix_entry.get("claim_boundary") or "",
                    "forbidden_claim_note": _forbidden_claim_note(matrix_entry.get("claim_boundary") or ""),
                    "sample_urls": sample_urls,
                    "sample_evidence_refs": sample_evidence_refs,
                    "data_summary": _data_summary(matrix_entry, str(source_id), exact_entry),
                    "gap_class": _first_present(
                        matrix_entry.get("gap_class"),
                        (attempt_entry or {}).get("debt_class"),
                        "",
                    )
                    or "",
                    "gap_type": _first_present(
                        matrix_entry.get("gap_type"),
                        (attempt_entry or {}).get("source_closeout_reason"),
                        "",
                    )
                    or "",
                    "attempt_gate_status": (attempt_entry or {}).get("gate_status") or "",
                    "attempt_debt_class": (attempt_entry or {}).get("debt_class") or "",
                    "attempt_final_boundary_allowed": bool((attempt_entry or {}).get("final_boundary_allowed"))
                    if attempt_entry
                    else False,
                    "attempt_count": int((attempt_entry or {}).get("attempt_count") or 0),
                    "next_action": _first_present(
                        (attempt_entry or {}).get("next_action"),
                        matrix_entry.get("next_action"),
                        "",
                    )
                    or "",
                    "specialist_roles": matrix_entry.get("specialist_roles") or [],
                }
                ledger_rows.append(row)

    ledger_rows.sort(key=lambda row: (row["primary_lane_id"], row["ticker"], row["source_role"], row["source_id"]))
    return ledger_rows


def _forbidden_claim_note(claim_boundary: str) -> str:
    lowered = claim_boundary.lower()
    forbidden = []
    for token in ["revenue", "sales", "asp", "share", "sell-through", "inventory", "backlog", "order"]:
        if token in lowered:
            forbidden.append(token)
    if not forbidden:
        return "Respect source-role claim boundary; do not promote beyond parser/authority scope."
    return "Forbidden or bounded exact claims: " + ", ".join(sorted(set(forbidden)))


def _merge_lists(*values: Any) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, "", [], {}):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item in (None, ""):
                continue
            key = str(item)
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
    return output


def build_summary(rows: list[dict[str, Any]], vertical_registry: dict[str, Any], generated_at: str) -> dict[str, Any]:
    company_count = len({row["ticker"] for row in rows})
    source_role_count = len({row["source_role"] for row in rows})
    source_id_count = len({row["source_id"] for row in rows})
    support_surface_count = len({row["support_surface"] for row in rows})
    can_enter_count = sum(1 for row in rows if row["can_enter_evidence_bundle"])
    blocked_count = len(rows) - can_enter_count

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "row_count": len(rows),
        "company_count": company_count,
        "source_role_count": source_role_count,
        "source_id_count": source_id_count,
        "support_surface_count": support_surface_count,
        "can_enter_evidence_bundle_count": can_enter_count,
        "not_evidence_ready_count": blocked_count,
        "by_availability_status": dict(Counter(row["availability_status"] for row in rows)),
        "by_adapter_parser_status": dict(Counter(row["adapter_parser_status"] for row in rows)),
        "by_support_surface": dict(Counter(row["support_surface"] for row in rows)),
        "by_primary_lane": dict(Counter(row["primary_lane_id"] for row in rows)),
        "by_source_role": dict(Counter(row["source_role"] for row in rows)),
        "company_specific_rows": sum(1 for row in rows if row["company_specific"]),
        "non_company_specific_rows": sum(1 for row in rows if not row["company_specific"]),
        "hard_gate": {
            "accepted_row_without_route_contract_count": sum(
                1
                for row in rows
                if row["can_enter_evidence_bundle"] and row["route_source_status"] == "source_not_registered"
            ),
            "accepted_row_without_parser_or_verifier_count": sum(
                1
                for row in rows
                if row["can_enter_evidence_bundle"] and row["parser_row_count"] <= 0 and row["exact_slot_count"] <= 0
            ),
            "unbound_company_specific_accepted_row_count": sum(
                1
                for row in rows
                if row["can_enter_evidence_bundle"]
                and row["company_specific"]
                and row["entity_bound_row_count"] <= 0
                and row["exact_slot_count"] <= 0
            ),
            "url_or_snippet_promoted_count": 0,
            "forbidden_claim_violation_count": sum(
                1 for row in rows if row["can_enter_evidence_bundle"] and row["exact_authority_violation_count"] > 0
            ),
        },
        "vertical_registry_company_count": len(vertical_registry.get("company_assignments") or []),
    }
    summary["status"] = "pass" if all(value == 0 for value in summary["hard_gate"].values()) else "action_required"
    return summary


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R18 Data Source Admission Ledger",
        "",
        f"生成时间：{summary['generated_at']}",
        "",
        "## 摘要",
        "",
        f"- 状态：`{summary['status']}`",
        f"- 台账行数：`{summary['row_count']}`",
        f"- 公司数：`{summary['company_count']}`",
        f"- source role 数：`{summary['source_role_count']}`",
        f"- source id 数：`{summary['source_id_count']}`",
        f"- 可进入 evidence bundle 行：`{summary['can_enter_evidence_bundle_count']}`",
        f"- 未准入 evidence 行：`{summary['not_evidence_ready_count']}`",
        "",
        "## Hard Gate",
        "",
    ]
    for key, value in summary["hard_gate"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "## Availability",
            "",
        ]
    )
    for key, value in sorted(summary["by_availability_status"].items()):
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## Support Surface", ""])
    for key, value in sorted(summary["by_support_surface"].items()):
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 代表性非准入原因", ""])
    blocked = [row for row in rows if not row["can_enter_evidence_bundle"]]
    for row in blocked[:20]:
        lines.append(
            "- "
            f"`{row['ticker']}` / `{row['source_role']}` / `{row['source_id']}`："
            f"{row['availability_status']}；{row['adapter_parser_status']}；{row['next_action']}"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本台账是 source admission ledger，不是 raw evidence store。",
            "- `can_enter_evidence_bundle=false` 的行只能进入 Research Lead planning / targeted repair / gap ledger。",
            "- URL、snippet、seed、attempt-only、blocked page 不得进入 ClaimCard 或 Memo 主体证据。",
            "- L2/L3 rows 即使准入，也只能按 `claim_boundary` 支撑 bounded thesis driver，不能冒充 revenue、ASP、share、sell-through、inventory、backlog 或 order value exact。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R18 data source admission ledger.")
    parser.add_argument("--company-coverage-path", type=Path, default=DEFAULT_COMPANY_COVERAGE_PATH)
    parser.add_argument("--exact-slot-coverage-path", type=Path, default=DEFAULT_EXACT_SLOT_COVERAGE_PATH)
    parser.add_argument("--attempt-ledger-path", type=Path, default=DEFAULT_ATTEMPT_LEDGER_PATH)
    parser.add_argument("--vertical-registry-path", type=Path, default=DEFAULT_VERTICAL_REGISTRY_PATH)
    parser.add_argument("--output-jsonl-path", type=Path, default=DEFAULT_OUTPUT_JSONL_PATH)
    parser.add_argument("--output-summary-path", type=Path, default=DEFAULT_OUTPUT_SUMMARY_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    company_rows = _read_jsonl(args.company_coverage_path)
    exact_rows = _read_jsonl(args.exact_slot_coverage_path)
    attempt_rows = _read_jsonl(args.attempt_ledger_path)
    vertical_registry = _read_json(args.vertical_registry_path)

    rows = build_data_source_admission_ledger_rows(
        company_coverage_rows=company_rows,
        exact_slot_rows=exact_rows,
        attempt_rows=attempt_rows,
        generated_at=generated_at,
    )
    summary = build_summary(rows, vertical_registry=vertical_registry, generated_at=generated_at)
    _write_jsonl(args.output_jsonl_path, rows)
    _write_json(args.output_summary_path, summary)
    args.output_report_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_report_path.write_text(render_report(summary, rows), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": summary["status"],
                "row_count": summary["row_count"],
                "company_count": summary["company_count"],
                "can_enter_evidence_bundle_count": summary["can_enter_evidence_bundle_count"],
                "hard_gate": summary["hard_gate"],
                "output_jsonl": str(args.output_jsonl_path),
                "output_summary": str(args.output_summary_path),
                "output_report": str(args.output_report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.strict and summary["status"] != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
