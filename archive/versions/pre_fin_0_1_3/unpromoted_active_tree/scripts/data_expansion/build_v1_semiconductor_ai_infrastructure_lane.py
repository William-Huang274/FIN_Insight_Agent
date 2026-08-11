from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


DEFAULT_REGISTRY_PATH = Path("data/manifests/vertical_source_lane_registry_v0_1.json")
DEFAULT_OUTPUT_DIR = Path("docs/internal/vnext_20260610/vertical_lanes")
DEFAULT_COVERAGE_PATH = Path("data/manifests/v1_semiconductors_ai_infrastructure_lane_coverage_v0_1.json")
DEFAULT_CASES_PATH = Path("tests/fixtures/v1_semiconductors_ai_infrastructure_lane_cases_v0_1.json")


def main() -> int:
    args = parse_args()
    registry = json.loads(args.registry_path.read_text(encoding="utf-8"))
    package = build_v1_lane_package(registry)
    outputs = write_v1_lane_package(
        package,
        output_dir=args.output_dir,
        coverage_path=args.coverage_path,
        cases_path=args.cases_path,
    )
    summary = {
        "status": package["validation"]["status"],
        "lane_id": package["lane"]["lane_id"],
        "primary_ticker_count": package["lane"]["primary_ticker_count"],
        "case_count": len(package["representative_cases"]),
        "source_coverage_gate_status": (package["lane"].get("lane_source_coverage_gate") or {}).get("status"),
        "outputs": outputs,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V1 Semiconductors / AI Infrastructure vertical lane package.")
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--coverage-path", type=Path, default=DEFAULT_COVERAGE_PATH)
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    return parser.parse_args()


def build_v1_lane_package(registry: Mapping[str, Any]) -> dict[str, Any]:
    lane = _find_lane(registry, "V1")
    assignments = [
        dict(item)
        for item in registry.get("company_assignments") or []
        if isinstance(item, Mapping)
        and (item.get("primary_lane_id") == "V1" or "V1" in (item.get("secondary_lane_ids") or []))
    ]
    primary_assignments = [item for item in assignments if item.get("primary_lane_id") == "V1"]
    representative_cases = _representative_cases(lane)
    coverage = {
        "schema_version": "finsight_v1_semiconductors_ai_infrastructure_lane_coverage_v0_1",
        "lane_id": "V1",
        "lane_name": lane.get("lane_name"),
        "registry_digest": registry.get("registry_digest"),
        "primary_ticker_count": lane.get("primary_ticker_count"),
        "secondary_inclusive_ticker_count": lane.get("ticker_count"),
        "representative_tickers": lane.get("representative_tickers") or [],
        "primary_ticker_universe": lane.get("primary_ticker_universe") or [],
        "ticker_universe": lane.get("ticker_universe") or [],
        "product_coverage_summary": lane.get("product_coverage_summary") or {},
        "gap_summary": lane.get("gap_summary") or {},
        "lane_source_coverage_gate": lane.get("lane_source_coverage_gate") or {},
        "l1_financial_statement_focus": lane.get("l1_financial_statement_focus") or [],
        "l1_company_disclosed_kpi_focus": lane.get("l1_company_disclosed_kpi_focus") or [],
        "l2_source_requirements": sorted(
            set((lane.get("l2_trusted_context_sources") or []) + (lane.get("l2_regulatory_or_official_sources") or []) + (lane.get("l2_official_product_surface_sources") or []))
        ),
        "l3_proxy_requirements": lane.get("l3_proxy_sources") or [],
        "l4_discovery_rules": [
            "L4 may only create WeakSignalLead / WeakSignalExclusionNote / L4PromotionAttempt.",
            "L4 cannot support shipment, share, sell-through, allocation, order volume, product success, or core thesis evidence.",
            "Forum/search/chart leads must route to L1/L2/L3 official/trusted/proxy repair before any memo use.",
        ],
        "public_data_ceiling": lane.get("public_data_ceiling") or [],
        "expected_commercial_gaps": lane.get("expected_commercial_gaps") or [],
        "representative_cases": representative_cases,
        "completion_boundary": (
            "This package makes V1 lane planning and deterministic eval cases runtime-ready. "
            "It does not claim all V1 L2/L3 source routes are complete; lane_source_coverage_gate remains authoritative."
        ),
    }
    package = {
        "schema_version": "finsight_v1_vertical_lane_package_v0_1",
        "lane": lane,
        "assignments": assignments,
        "primary_assignments": primary_assignments,
        "coverage": coverage,
        "representative_cases": representative_cases,
        "analyst_playbook": _render_analyst_playbook(lane, primary_assignments),
        "source_playbook": _render_source_playbook(lane),
    }
    package["validation"] = validate_v1_lane_package(package)
    return package


def validate_v1_lane_package(package: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    lane = package.get("lane") if isinstance(package.get("lane"), Mapping) else {}
    cases = [case for case in package.get("representative_cases") or [] if isinstance(case, Mapping)]
    if lane.get("lane_id") != "V1":
        errors.append({"type": "v1_lane_missing"})
    if int(lane.get("primary_ticker_count") or 0) <= 0:
        errors.append({"type": "v1_primary_ticker_universe_empty"})
    if len(cases) < 3:
        errors.append({"type": "v1_representative_case_count_lt_3", "case_count": len(cases)})
    required_dims = {"fundamentals", "product_and_production", "capital_and_financing", "industry_supply_chain", "competition_and_market_position", "risk_and_counterevidence"}
    for case in cases:
        dims = set(case.get("required_dimension_ids") or [])
        missing = sorted(required_dims - dims)
        if missing:
            errors.append({"type": "v1_case_missing_required_dimensions", "case_id": case.get("case_id"), "missing": missing})
        if "L4_direct_claim_forbidden" not in set(case.get("eval_gates") or []):
            errors.append({"type": "v1_case_missing_l4_forbidden_gate", "case_id": case.get("case_id")})
    return {
        "schema_version": "finsight_v1_lane_package_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def write_v1_lane_package(
    package: Mapping[str, Any],
    *,
    output_dir: Path,
    coverage_path: Path,
    cases_path: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    analyst_path = output_dir / "v1_analyst_playbook.zh-CN.md"
    source_path = output_dir / "v1_source_playbook.zh-CN.md"
    report_path = output_dir / "v1_lane_coverage_report.zh-CN.md"
    analyst_path.write_text(str(package["analyst_playbook"]), encoding="utf-8")
    source_path.write_text(str(package["source_playbook"]), encoding="utf-8")
    coverage_path.write_text(json.dumps(package["coverage"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cases_path.write_text(json.dumps({"schema_version": "finsight_v1_lane_cases_v0_1", "cases": package["representative_cases"]}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_render_coverage_report(package), encoding="utf-8")
    return {
        "analyst_playbook": str(analyst_path),
        "source_playbook": str(source_path),
        "coverage": str(coverage_path),
        "coverage_report": str(report_path),
        "representative_cases": str(cases_path),
    }


def _find_lane(registry: Mapping[str, Any], lane_id: str) -> dict[str, Any]:
    for lane in registry.get("lanes") or []:
        if isinstance(lane, Mapping) and lane.get("lane_id") == lane_id:
            return dict(lane)
    raise ValueError(f"lane_not_found: {lane_id}")


def _representative_cases(lane: Mapping[str, Any]) -> list[dict[str, Any]]:
    base_dimensions = [
        "fundamentals",
        "product_and_production",
        "capital_and_financing",
        "industry_supply_chain",
        "competition_and_market_position",
        "risk_and_counterevidence",
    ]
    gates = [
        "lane_registry_loaded",
        "source_coverage_gate_visible",
        "L1_exact_authority_required_for_company_financial_fact",
        "L2_L3_context_or_proxy_boundary_visible",
        "L4_direct_claim_forbidden",
        "commercial_gap_exposed_not_filled_by_proxy",
        "dimension_judgment_required",
    ]
    return [
        {
            "case_id": "v1_ai_infra_demand_transmission_nvda_dell_hyperscaler_001",
            "case_family": "V1_semiconductors_ai_infrastructure",
            "execution_mode": "deep_research",
            "prompt": "分析 NVDA、DELL 与 hyperscaler capex/AI server 需求传导：需要同时覆盖基本面、产品/产线、资本开支/投融资、供应链、竞争位置和风险反证。",
            "focus_tickers": ["NVDA", "DELL"],
            "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT", "SMCI", "HPE", "MSFT", "AMZN", "GOOGL"],
            "required_lane_ids": ["V1"],
            "allowed_secondary_lane_ids": ["V2", "V3", "V7"],
            "required_dimension_ids": base_dimensions,
            "required_source_requirements": ["primary_company_disclosure", "official_product_surface", "supply_chain_official_relationship", "channel_offer_proxy", "hiring_capacity_proxy", "public_order_proxy"],
            "expected_commercial_gaps": ["hyperscaler exact purchase orders", "allocation", "channel inventory", "IDC/Counterpoint/Omdia/Gartner shipments/share/forecast"],
            "eval_gates": gates,
        },
        {
            "case_id": "v1_semicap_nonus_local_filing_asml_tsm_amat_lrcx_002",
            "case_family": "V1_semiconductors_ai_infrastructure",
            "execution_mode": "deep_research",
            "prompt": "分析 ASML、TSM、AMAT、LRCX、KLAC 在先进制程和 AI capex 周期中的设备/产能/订单线索；非美公司优先走 20-F/6-K、当地交易所或公司 IR 公开文件。",
            "focus_tickers": ["ASML", "TSM"],
            "search_scope_tickers": ["ASML", "TSM", "AMAT", "LRCX", "KLAC", "NVDA", "AMD"],
            "required_lane_ids": ["V1"],
            "allowed_secondary_lane_ids": [],
            "required_dimension_ids": base_dimensions,
            "required_source_requirements": ["primary_company_disclosure", "official_product_surface", "trusted_external_context", "macro_official_context", "technology_research_proxy"],
            "expected_commercial_gaps": ["tool shipment/share tracker", "customer-specific allocation", "private order book detail"],
            "eval_gates": gates + ["non_us_official_filing_repair_before_bounded_gap"],
        },
        {
            "case_id": "v1_ai_server_channel_proxy_boundary_dell_hpe_smci_anet_003",
            "case_family": "V1_semiconductors_ai_infrastructure",
            "execution_mode": "standard_memo",
            "prompt": "比较 DELL、HPE、SMCI、ANET 的 AI server/networking 产品线、公开渠道/招聘/合同 proxy 和财务支撑，明确哪些只能作为方向性线索。",
            "focus_tickers": ["DELL", "HPE"],
            "search_scope_tickers": ["DELL", "HPE", "SMCI", "ANET", "NVDA"],
            "required_lane_ids": ["V1"],
            "allowed_secondary_lane_ids": ["V2"],
            "required_dimension_ids": base_dimensions,
            "required_source_requirements": ["primary_company_disclosure", "official_product_surface", "channel_offer_proxy", "public_order_proxy", "hiring_capacity_proxy"],
            "expected_commercial_gaps": ["sell-through", "ASP", "inventory", "server shipment share"],
            "eval_gates": gates + ["channel_offer_cannot_prove_sell_through_or_inventory"],
        },
    ]


def _render_analyst_playbook(lane: Mapping[str, Any], primary_assignments: list[Mapping[str, Any]]) -> str:
    tickers = ", ".join(str(item.get("ticker")) for item in primary_assignments[:80])
    return f"""# V1 Analyst Playbook: Semiconductors / AI Infrastructure

## Scope

- lane_id: `V1`
- industry_schema: `{lane.get('industry_schema')}`
- primary_ticker_count: `{lane.get('primary_ticker_count')}`
- representative_tickers: `{', '.join(lane.get('representative_tickers') or [])}`
- primary_ticker_sample: `{tickers}`

## How This Lane Makes Money

V1 companies monetize AI infrastructure through chips, systems, networking, semiconductor equipment, foundry/packaging capacity, and adjacent datacenter infrastructure. The analyst should connect product demand to disclosed revenue, margin, inventory, capex, backlog/order commentary, purchase commitments, and customer concentration rather than infer product success from public buzz.

## Product / Production Taxonomy

{_bullet_lines(lane.get('product_taxonomy_scope') or [])}

## Financial Statement Focus

{_bullet_lines(lane.get('l1_financial_statement_focus') or [])}

## Company-Disclosed KPI Focus

{_bullet_lines(lane.get('l1_company_disclosed_kpi_focus') or [])}

## Strong Facts

- SEC / 20-F / 6-K / company IR parser-backed revenue, margin, inventory, capex, commitments, backlog/orders, customer concentration, and product KPI rows.
- Company official product pages/spec sheets for product existence, taxonomy, specs, and generation context only.

## Proxy / Context Signals

- Channel offers can support price/configuration/availability context, not ASP, sell-through, inventory, shipment, or share.
- Hiring/public contracts/developer ecosystem can support direction and mechanism only after issuer/product binding.
- Patents/OpenAlex support technology/R&D topic context only after assignee/topic resolver.

## Typical Misreads To Block

- Treating hyperscaler capex as direct NVDA/DELL/ANET revenue without disclosed bridge.
- Treating channel price/availability as ASP or inventory.
- Treating forum allocation rumors as demand proof.
- Treating commercial tracker gaps as filled by public proxies.
"""


def _render_source_playbook(lane: Mapping[str, Any]) -> str:
    coverage = lane.get("lane_source_coverage_gate") if isinstance(lane.get("lane_source_coverage_gate"), Mapping) else {}
    return f"""# V1 Source Playbook: Semiconductors / AI Infrastructure

## L1 Required Facts

{_bullet_lines(lane.get('l1_required_facts') or [])}

## L2 Trusted / Official Sources

{_bullet_lines(sorted(set((lane.get('l2_trusted_context_sources') or []) + (lane.get('l2_regulatory_or_official_sources') or []) + (lane.get('l2_official_product_surface_sources') or []))))}

## L3 Proxy Sources

{_bullet_lines(lane.get('l3_proxy_sources') or [])}

## L4 Discovery Boundary

{_bullet_lines(lane.get('l4_discovery_sources') or [])}

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

{_bullet_lines(lane.get('public_data_ceiling') or [])}

## Expected Commercial Gaps

{_bullet_lines(lane.get('expected_commercial_gaps') or [])}

## Current Registry Coverage Gate

- status: `{coverage.get('status') or 'not_run'}`
- requirement_count: `{(coverage.get('summary') or {}).get('requirement_count') if isinstance(coverage.get('summary'), Mapping) else ''}`
- gap_requirement_count: `{(coverage.get('summary') or {}).get('gap_requirement_count') if isinstance(coverage.get('summary'), Mapping) else ''}`
- fail_requirement_count: `{(coverage.get('summary') or {}).get('fail_requirement_count') if isinstance(coverage.get('summary'), Mapping) else ''}`

The gate being `gap` is not a failure of this playbook. It means V1 source closeout must continue against lane-specific missing requirements.
"""


def _render_coverage_report(package: Mapping[str, Any]) -> str:
    coverage = package["coverage"]
    lane_gate = coverage.get("lane_source_coverage_gate") if isinstance(coverage.get("lane_source_coverage_gate"), Mapping) else {}
    product = coverage.get("product_coverage_summary") if isinstance(coverage.get("product_coverage_summary"), Mapping) else {}
    gaps = coverage.get("gap_summary") if isinstance(coverage.get("gap_summary"), Mapping) else {}
    lines = [
        "# V1 Semiconductors / AI Infrastructure Lane Coverage Report",
        "",
        f"- validation: `{package['validation']['status']}`",
        f"- source_coverage_gate: `{lane_gate.get('status') or 'not_run'}`",
        f"- primary_ticker_count: `{coverage.get('primary_ticker_count')}`",
        f"- inclusive_ticker_count: `{coverage.get('secondary_inclusive_ticker_count')}`",
        f"- product_kpi_ready_ticker_count: `{product.get('product_kpi_ready_ticker_count')}`",
        f"- official_product_surface_ticker_count: `{product.get('official_product_surface_ticker_count')}`",
        f"- commercial_gap_count: `{gaps.get('commercial_gap_count')}`",
        "",
        "## Representative Cases",
        "",
    ]
    for case in package.get("representative_cases") or []:
        lines.extend(
            [
                f"### {case['case_id']}",
                "",
                f"- execution_mode: `{case['execution_mode']}`",
                f"- focus_tickers: `{', '.join(case['focus_tickers'])}`",
                f"- search_scope_tickers: `{', '.join(case['search_scope_tickers'])}`",
                f"- required_dimensions: `{', '.join(case['required_dimension_ids'])}`",
                f"- expected_commercial_gaps: `{', '.join(case['expected_commercial_gaps'])}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            coverage["completion_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def _bullet_lines(values: list[Any]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- <none>"


if __name__ == "__main__":
    raise SystemExit(main())
