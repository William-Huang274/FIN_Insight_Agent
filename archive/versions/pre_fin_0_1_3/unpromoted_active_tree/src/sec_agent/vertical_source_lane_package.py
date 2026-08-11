from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


VERTICAL_LANE_PACKAGE_SCHEMA_VERSION = "finsight_vertical_lane_package_v0_1"
VERTICAL_LANE_CASES_SCHEMA_VERSION = "finsight_vertical_lane_cases_v0_1"

BASE_DIMENSIONS = (
    "fundamentals",
    "product_and_production",
    "capital_and_financing",
    "industry_supply_chain",
    "competition_and_market_position",
    "risk_and_counterevidence",
)

BASE_EVAL_GATES = (
    "lane_registry_loaded",
    "source_coverage_gate_visible",
    "L1_exact_authority_required_for_company_financial_fact",
    "L2_L3_context_or_proxy_boundary_visible",
    "L4_direct_claim_forbidden",
    "commercial_gap_exposed_not_filled_by_proxy",
    "dimension_judgment_required",
    "source_gap_classification_required",
)


def build_vertical_lane_package(registry: Mapping[str, Any], lane_id: str) -> dict[str, Any]:
    lane = _find_lane(registry, lane_id)
    assignments = [
        dict(item)
        for item in registry.get("company_assignments") or []
        if isinstance(item, Mapping)
        and (item.get("primary_lane_id") == lane_id or lane_id in (item.get("secondary_lane_ids") or []))
    ]
    primary_assignments = [item for item in assignments if item.get("primary_lane_id") == lane_id]
    representative_cases = _representative_cases(lane)
    coverage = _coverage_payload(registry=registry, lane=lane, representative_cases=representative_cases)
    package = {
        "schema_version": VERTICAL_LANE_PACKAGE_SCHEMA_VERSION,
        "lane": lane,
        "assignments": assignments,
        "primary_assignments": primary_assignments,
        "coverage": coverage,
        "representative_cases": representative_cases,
        "analyst_playbook": render_analyst_playbook(lane, primary_assignments),
        "source_playbook": render_source_playbook(lane),
    }
    package["validation"] = validate_vertical_lane_package(package)
    return package


def build_vertical_lane_packages(registry: Mapping[str, Any], lane_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    requested = [str(item).upper() for item in lane_ids] if lane_ids else [str(lane.get("lane_id")) for lane in registry.get("lanes") or []]
    return [build_vertical_lane_package(registry, lane_id) for lane_id in requested]


def validate_vertical_lane_package(package: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    lane = package.get("lane") if isinstance(package.get("lane"), Mapping) else {}
    lane_id = str(lane.get("lane_id") or "")
    cases = [case for case in package.get("representative_cases") or [] if isinstance(case, Mapping)]
    if not lane_id:
        errors.append({"type": "lane_id_missing"})
    if int(lane.get("primary_ticker_count") or 0) <= 0:
        errors.append({"type": "primary_ticker_universe_empty", "lane_id": lane_id})
    if len(cases) < 3:
        errors.append({"type": "representative_case_count_lt_3", "lane_id": lane_id, "case_count": len(cases)})
    required_dims = set(BASE_DIMENSIONS)
    for case in cases:
        dims = set(case.get("required_dimension_ids") or [])
        missing = sorted(required_dims - dims)
        if missing:
            errors.append({"type": "case_missing_required_dimensions", "lane_id": lane_id, "case_id": case.get("case_id"), "missing": missing})
        gates = set(case.get("eval_gates") or [])
        for gate in ("L4_direct_claim_forbidden", "commercial_gap_exposed_not_filled_by_proxy", "source_gap_classification_required"):
            if gate not in gates:
                errors.append({"type": "case_missing_eval_gate", "lane_id": lane_id, "case_id": case.get("case_id"), "gate": gate})
        if not case.get("required_source_requirements"):
            errors.append({"type": "case_missing_source_requirements", "lane_id": lane_id, "case_id": case.get("case_id")})
    coverage = package.get("coverage") if isinstance(package.get("coverage"), Mapping) else {}
    if not coverage.get("completion_boundary"):
        errors.append({"type": "coverage_missing_completion_boundary", "lane_id": lane_id})
    return {
        "schema_version": "finsight_vertical_lane_package_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
    }


def write_vertical_lane_package(
    package: Mapping[str, Any],
    *,
    output_dir: str | Path,
    manifests_dir: str | Path,
    fixtures_dir: str | Path,
) -> dict[str, str]:
    lane = package.get("lane") if isinstance(package.get("lane"), Mapping) else {}
    slug = lane_slug(lane)
    output = Path(output_dir)
    manifests = Path(manifests_dir)
    fixtures = Path(fixtures_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    fixtures.mkdir(parents=True, exist_ok=True)
    analyst_path = output / f"{slug}_analyst_playbook.zh-CN.md"
    source_path = output / f"{slug}_source_playbook.zh-CN.md"
    report_path = output / f"{slug}_lane_coverage_report.zh-CN.md"
    coverage_path = manifests / f"{slug}_lane_coverage_v0_1.json"
    cases_path = fixtures / f"{slug}_lane_cases_v0_1.json"
    analyst_path.write_text(str(package["analyst_playbook"]), encoding="utf-8")
    source_path.write_text(str(package["source_playbook"]), encoding="utf-8")
    report_path.write_text(render_coverage_report(package), encoding="utf-8")
    coverage_path.write_text(json.dumps(package["coverage"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cases_path.write_text(
        json.dumps(
            {
                "schema_version": VERTICAL_LANE_CASES_SCHEMA_VERSION,
                "lane_id": lane.get("lane_id"),
                "cases": package["representative_cases"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "analyst_playbook": str(analyst_path),
        "source_playbook": str(source_path),
        "coverage_report": str(report_path),
        "coverage": str(coverage_path),
        "representative_cases": str(cases_path),
    }


def write_vertical_lane_packages(
    packages: Sequence[Mapping[str, Any]],
    *,
    output_dir: str | Path,
    manifests_dir: str | Path,
    fixtures_dir: str | Path,
    summary_path: str | Path,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []
    for package in packages:
        lane = package.get("lane") if isinstance(package.get("lane"), Mapping) else {}
        lane_id = str(lane.get("lane_id") or "")
        outputs[lane_id] = write_vertical_lane_package(
            package,
            output_dir=output_dir,
            manifests_dir=manifests_dir,
            fixtures_dir=fixtures_dir,
        )
        coverage = package.get("coverage") if isinstance(package.get("coverage"), Mapping) else {}
        gate = coverage.get("lane_source_coverage_gate") if isinstance(coverage.get("lane_source_coverage_gate"), Mapping) else {}
        summary_rows.append(
            {
                "lane_id": lane_id,
                "lane_name": lane.get("lane_name"),
                "industry_schema": lane.get("industry_schema"),
                "validation_status": (package.get("validation") or {}).get("status"),
                "case_count": len(package.get("representative_cases") or []),
                "primary_ticker_count": coverage.get("primary_ticker_count"),
                "inclusive_ticker_count": coverage.get("secondary_inclusive_ticker_count"),
                "registry_source_coverage_status": gate.get("status") or "not_run",
            }
        )
    summary = {
        "schema_version": "finsight_vertical_lane_package_summary_v0_1",
        "lane_count": len(packages),
        "status": "fail" if any((pkg.get("validation") or {}).get("status") == "fail" for pkg in packages) else "pass",
        "lanes": summary_rows,
        "outputs": outputs,
    }
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def render_analyst_playbook(lane: Mapping[str, Any], primary_assignments: Sequence[Mapping[str, Any]]) -> str:
    lane_id = str(lane.get("lane_id") or "")
    lane_name = str(lane.get("lane_name") or "")
    tickers = ", ".join(str(item.get("ticker")) for item in primary_assignments[:100])
    return f"""# {lane_id} Analyst Playbook: {lane_name}

## Scope

- lane_id: `{lane_id}`
- industry_schema: `{lane.get('industry_schema')}`
- subvertical: `{lane.get('subvertical')}`
- primary_ticker_count: `{lane.get('primary_ticker_count')}`
- representative_tickers: `{', '.join(lane.get('representative_tickers') or [])}`
- primary_ticker_sample: `{tickers}`

## How This Lane Makes Money

{_lane_business_model(lane)}

## Product / Service Taxonomy

{_bullet_lines(lane.get('product_taxonomy_scope') or [])}

## Financial Statement Focus

{_bullet_lines(lane.get('l1_financial_statement_focus') or [])}

## Company-Disclosed KPI Focus

{_bullet_lines(lane.get('l1_company_disclosed_kpi_focus') or [])}

## Strong Facts

- Company filings, official annual/quarterly reports, SEC/FSD/company IR, and company-disclosed KPI rows are the only authority for issuer-level financial facts.
- Official product/service pages can support product existence, taxonomy, specs, pricing-page context, and product positioning, but not sales/share unless the company discloses it.

## Context / Proxy Signals

{_bullet_lines(_context_proxy_rules(lane))}

## Typical Misreads To Block

{_bullet_lines(_typical_misreads(lane))}
"""


def render_source_playbook(lane: Mapping[str, Any]) -> str:
    coverage = lane.get("lane_source_coverage_gate") if isinstance(lane.get("lane_source_coverage_gate"), Mapping) else {}
    summary = coverage.get("summary") if isinstance(coverage.get("summary"), Mapping) else {}
    return f"""# {lane.get('lane_id')} Source Playbook: {lane.get('lane_name')}

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
- requirement_count: `{summary.get('requirement_count')}`
- gap_requirement_count: `{summary.get('gap_requirement_count')}`
- fail_requirement_count: `{summary.get('fail_requirement_count')}`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
"""


def render_coverage_report(package: Mapping[str, Any]) -> str:
    coverage = package["coverage"]
    lane_id = str(coverage.get("lane_id") or "")
    lane_name = str(coverage.get("lane_name") or "")
    lane_gate = coverage.get("lane_source_coverage_gate") if isinstance(coverage.get("lane_source_coverage_gate"), Mapping) else {}
    product = coverage.get("product_coverage_summary") if isinstance(coverage.get("product_coverage_summary"), Mapping) else {}
    gaps = coverage.get("gap_summary") if isinstance(coverage.get("gap_summary"), Mapping) else {}
    lines = [
        f"# {lane_id} {lane_name} Lane Coverage Report",
        "",
        f"- validation: `{(package.get('validation') or {}).get('status')}`",
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
                f"- required_source_requirements: `{', '.join(case['required_source_requirements'])}`",
                f"- expected_commercial_gaps: `{', '.join(case['expected_commercial_gaps'])}`",
                "",
            ]
        )
    lines.extend(["## Boundary", "", str(coverage["completion_boundary"]), ""])
    return "\n".join(lines)


def lane_slug(lane: Mapping[str, Any]) -> str:
    lane_id = str(lane.get("lane_id") or "lane").lower()
    subvertical = str(lane.get("subvertical") or lane.get("lane_name") or "").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", subvertical).strip("_")
    return f"{lane_id}_{slug}" if slug else lane_id


def _coverage_payload(*, registry: Mapping[str, Any], lane: Mapping[str, Any], representative_cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "finsight_vertical_lane_coverage_v0_1",
        "lane_id": lane.get("lane_id"),
        "lane_name": lane.get("lane_name"),
        "industry_schema": lane.get("industry_schema"),
        "subvertical": lane.get("subvertical"),
        "registry_digest": registry.get("registry_digest"),
        "primary_ticker_count": lane.get("primary_ticker_count"),
        "secondary_inclusive_ticker_count": lane.get("ticker_count"),
        "representative_tickers": lane.get("representative_tickers") or [],
        "primary_ticker_universe": lane.get("primary_ticker_universe") or [],
        "ticker_universe": lane.get("ticker_universe") or [],
        "product_coverage_summary": lane.get("product_coverage_summary") or {},
        "gap_summary": lane.get("gap_summary") or {},
        "lane_source_coverage_gate": lane.get("lane_source_coverage_gate") or {},
        "l1_required_facts": lane.get("l1_required_facts") or [],
        "l1_financial_statement_focus": lane.get("l1_financial_statement_focus") or [],
        "l1_company_disclosed_kpi_focus": lane.get("l1_company_disclosed_kpi_focus") or [],
        "l2_source_requirements": sorted(
            set((lane.get("l2_trusted_context_sources") or []) + (lane.get("l2_regulatory_or_official_sources") or []) + (lane.get("l2_official_product_surface_sources") or []))
        ),
        "l3_proxy_requirements": lane.get("l3_proxy_sources") or [],
        "l4_discovery_rules": [
            "L4 may only create WeakSignalLead / WeakSignalExclusionNote / L4PromotionAttempt.",
            "L4 cannot support sales, share, sell-through, product success, customer adoption, or core thesis evidence.",
            "Search/forum/chart leads must route to L1/L2/L3 official/trusted/proxy repair before memo use.",
        ],
        "public_data_ceiling": lane.get("public_data_ceiling") or [],
        "expected_commercial_gaps": lane.get("expected_commercial_gaps") or [],
        "representative_cases": list(representative_cases),
        "completion_boundary": (
            f"This package makes {lane.get('lane_id')} lane planning and deterministic eval cases runtime-ready. "
            "Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap."
        ),
    }


def _representative_cases(lane: Mapping[str, Any]) -> list[dict[str, Any]]:
    lane_id = str(lane.get("lane_id") or "")
    slug = lane_slug(lane)
    reps = [str(item) for item in lane.get("representative_tickers") or []]
    focus_a = reps[:2] or [str(item) for item in lane.get("primary_ticker_universe") or []][:2]
    focus_b = reps[2:5] or reps[:3] or focus_a
    focus_c = reps[5:8] or reps[:3] or focus_a
    source_requirements = [
        str(req.get("requirement_id"))
        for req in ((lane.get("lane_source_coverage_gate") or {}).get("requirements") or [])
        if isinstance(req, Mapping) and req.get("requirement_id")
    ]
    return [
        {
            "case_id": f"{slug}_financial_product_bridge_001",
            "case_family": f"{lane_id}_{lane.get('subvertical')}",
            "execution_mode": "deep_research",
            "prompt": f"分析 {', '.join(focus_a)} 在 {lane.get('lane_name')} lane 中的产品/服务、财务三表、公开 KPI、资本投入、竞争位置和风险反证，要求区分 L1 强事实与 L2/L3 proxy。",
            "focus_tickers": focus_a,
            "search_scope_tickers": sorted(set(focus_a + reps[:8])),
            "required_lane_ids": [lane_id],
            "allowed_secondary_lane_ids": [],
            "required_dimension_ids": list(BASE_DIMENSIONS),
            "required_source_requirements": source_requirements,
            "expected_commercial_gaps": lane.get("expected_commercial_gaps") or [],
            "eval_gates": list(BASE_EVAL_GATES),
        },
        {
            "case_id": f"{slug}_external_source_repair_boundary_002",
            "case_family": f"{lane_id}_{lane.get('subvertical')}",
            "execution_mode": "deep_research",
            "prompt": f"针对 {', '.join(focus_b)} 检查当前公开源是否足以补齐产品、监管/行业、供应链或渠道 proxy；找不到时必须写出 retrievable/parser/bounded/commercial gap。",
            "focus_tickers": focus_b,
            "search_scope_tickers": sorted(set(focus_b + reps[:10])),
            "required_lane_ids": [lane_id],
            "allowed_secondary_lane_ids": [],
            "required_dimension_ids": list(BASE_DIMENSIONS),
            "required_source_requirements": source_requirements,
            "expected_commercial_gaps": lane.get("expected_commercial_gaps") or [],
            "eval_gates": list(BASE_EVAL_GATES) + ["targeted_repair_before_bounded_gap"],
        },
        {
            "case_id": f"{slug}_proxy_no_promotion_003",
            "case_family": f"{lane_id}_{lane.get('subvertical')}",
            "execution_mode": "standard_memo",
            "prompt": f"比较 {', '.join(focus_c)} 的公开 proxy 信号如何补充但不能替代公司披露；输出应包含判断、依据、反证、缺口和触发条件。",
            "focus_tickers": focus_c,
            "search_scope_tickers": sorted(set(focus_c + reps[:8])),
            "required_lane_ids": [lane_id],
            "allowed_secondary_lane_ids": [],
            "required_dimension_ids": list(BASE_DIMENSIONS),
            "required_source_requirements": source_requirements,
            "expected_commercial_gaps": lane.get("expected_commercial_gaps") or [],
            "eval_gates": list(BASE_EVAL_GATES) + ["proxy_cannot_prove_sales_share_or_margin"],
        },
    ]


def _find_lane(registry: Mapping[str, Any], lane_id: str) -> dict[str, Any]:
    lane_id = str(lane_id or "").upper()
    for lane in registry.get("lanes") or []:
        if isinstance(lane, Mapping) and str(lane.get("lane_id") or "").upper() == lane_id:
            return dict(lane)
    raise ValueError(f"lane_not_found: {lane_id}")


def _lane_business_model(lane: Mapping[str, Any]) -> str:
    products = ", ".join(str(item) for item in lane.get("key_products_or_services") or [])
    return (
        f"This lane monetizes through {products}. The analyst must connect those products or services to "
        "company-disclosed revenue/KPI/accounting lines first, then use L2/L3 rows only for mechanism, context, "
        "adoption/attention proxy, or gap repair."
    )


def _context_proxy_rules(lane: Mapping[str, Any]) -> list[str]:
    rules = []
    for source in lane.get("l3_proxy_sources") or []:
        rules.append(f"{source} can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.")
    for source in lane.get("l2_regulatory_or_official_sources") or []:
        rules.append(f"{source} can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.")
    return rules or ["No lane-specific proxy rules registered."]


def _typical_misreads(lane: Mapping[str, Any]) -> list[str]:
    return [
        "Using public proxy rows as if they were company revenue, sales volume, market share, ASP, or margin authority.",
        "Letting L4 search/forum/social leads enter ClaimCards or core thesis without L1/L2/L3 repair.",
        "Treating a commercial tracker gap as solved by a noisy public proxy.",
        "Ignoring the lane-specific financial statement focus and writing generic evidence summaries.",
    ]


def _bullet_lines(values: Sequence[Any]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- <none>"
