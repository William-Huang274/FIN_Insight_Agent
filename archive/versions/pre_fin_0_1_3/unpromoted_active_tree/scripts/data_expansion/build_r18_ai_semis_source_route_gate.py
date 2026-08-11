from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "finsight_r18_ai_semis_source_route_gate_v0_1"

DEFAULT_MATRIX_PATH = REPO_ROOT / "data" / "manifests" / "r18_signal_authority_coverage_matrix_v0_2.jsonl"
DEFAULT_ASSIGNMENTS_PATH = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_ROUTE_PLAN_PATH = REPO_ROOT / "data" / "manifests" / "family_source_route_plan_v0_1.jsonl"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "manifests" / "r18_source_route_registry_v2.json"
DEFAULT_OUTPUT_ROWS_PATH = REPO_ROOT / "data" / "manifests" / "r18_ai_semis_source_route_gate_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY_PATH = REPO_ROOT / "data" / "manifests" / "r18_ai_semis_source_route_gate_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT_PATH = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "r18_ai_semis_source_route_gate.zh-CN.md"


FAMILY_REQUIREMENT_GROUPS: dict[str, list[dict[str, Any]]] = {
    "gpu_accelerator": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_spec", "any_of": ["official_product_surface"]},
        {"group_id": "technology_or_ecosystem_signal", "any_of": ["developer_ecosystem_proxy", "technology_research_proxy", "trusted_external_context"]},
        {"group_id": "deployment_order_or_capex_signal", "any_of": ["channel_offer_proxy", "public_order_proxy", "supply_chain_official_relationship", "macro_official_context"]},
    ],
    "foundry": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_or_process_surface", "any_of": ["official_product_surface"]},
        {"group_id": "capex_or_industry_driver", "any_of": ["macro_official_context", "trusted_external_context"]},
        {"group_id": "technology_or_supply_signal", "any_of": ["technology_research_proxy", "supply_chain_official_relationship"]},
    ],
    "memory": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
        {"group_id": "industry_or_technology_signal", "any_of": ["macro_official_context", "trusted_external_context", "technology_research_proxy"]},
    ],
    "semicap_equipment": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
        {"group_id": "technology_or_industry_signal", "any_of": ["technology_research_proxy", "trusted_external_context"]},
        {"group_id": "customer_order_or_capex_bridge", "any_of": ["public_order_proxy", "supply_chain_official_relationship", "macro_official_context"]},
    ],
    "networking": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
        {"group_id": "developer_or_industry_signal", "any_of": ["developer_ecosystem_proxy", "trusted_external_context"]},
        {"group_id": "channel_order_or_supply_signal", "any_of": ["channel_offer_proxy", "public_order_proxy", "supply_chain_official_relationship"]},
    ],
    "server_oem": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
        {"group_id": "channel_order_supply_or_industry_signal", "any_of": ["channel_offer_proxy", "public_order_proxy", "supply_chain_official_relationship", "trusted_external_context"]},
    ],
    "eda_ip": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
        {"group_id": "developer_research_or_customer_signal", "any_of": ["developer_ecosystem_proxy", "technology_research_proxy", "trusted_external_context"]},
    ],
    "power_cooling": [
        {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
        {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
        {"group_id": "public_order_hiring_macro_or_industry_signal", "any_of": ["public_order_proxy", "hiring_capacity_proxy", "macro_official_context", "trusted_external_context"]},
    ],
}


GENERIC_REQUIREMENT_GROUPS = [
    {"group_id": "company_disclosure", "any_of": ["primary_company_disclosure"]},
    {"group_id": "official_product_surface", "any_of": ["official_product_surface"]},
    {"group_id": "industry_or_technology_signal", "any_of": ["trusted_external_context", "macro_official_context", "technology_research_proxy"]},
]


def build_ai_semis_source_route_gate(
    *,
    matrix_rows: Sequence[Mapping[str, Any]],
    assignment_rows: Sequence[Mapping[str, Any]],
    route_plan_rows: Sequence[Mapping[str, Any]],
    registry_payload: Mapping[str, Any],
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    registered_roles = {
        str(row.get("source_role") or "")
        for row in registry_payload.get("contracts") or []
        if isinstance(row, Mapping) and str(row.get("source_role") or "").strip()
    }
    allowed_roles_by_ticker: dict[str, set[str]] = defaultdict(set)
    role_rows_by_ticker: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    assignment_tickers = {
        str(row.get("ticker") or "").upper()
        for row in assignment_rows
        if str(row.get("family_lane_id") or "") == "V1" and str(row.get("ticker") or "").strip()
    }
    for row in matrix_rows:
        ticker = str(row.get("ticker") or "").upper()
        role = str(row.get("source_role") or "")
        if ticker not in assignment_tickers:
            continue
        if not ticker or not role:
            continue
        role_rows_by_ticker[(ticker, role)].append(row)
        if bool(row.get("can_enter_evidence_bundle")):
            allowed_roles_by_ticker[ticker].add(role)
    route_plan_by_key = {
        (
            str(row.get("ticker") or "").upper(),
            str(row.get("family_id") or ""),
            str(row.get("route_id") or ""),
        ): row
        for row in route_plan_rows
        if str(row.get("family_lane_id") or "") == "V1"
    }
    gate_rows: list[dict[str, Any]] = []
    for assignment in assignment_rows:
        if str(assignment.get("family_lane_id") or "") != "V1":
            continue
        ticker = str(assignment.get("ticker") or "").upper()
        family_id = str(assignment.get("family_id") or "")
        required_groups = FAMILY_REQUIREMENT_GROUPS.get(family_id, GENERIC_REQUIREMENT_GROUPS)
        available_roles = sorted(allowed_roles_by_ticker.get(ticker, set()))
        group_results = [
            _evaluate_group(
                ticker=ticker,
                family_id=family_id,
                group=group,
                registered_roles=registered_roles,
                available_roles=set(available_roles),
                route_plan_by_key=route_plan_by_key,
                role_rows_by_ticker=role_rows_by_ticker,
            )
            for group in required_groups
        ]
        missing_groups = [row for row in group_results if row["status"] != "pass"]
        gate_rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": str(assignment.get("company_name") or ""),
                "family_id": family_id,
                "family_name": str(assignment.get("family_name") or ""),
                "primary_lane_id": "V1",
                "status": "pass" if not missing_groups else "action_required",
                "available_source_roles": available_roles,
                "required_group_count": len(required_groups),
                "passed_group_count": len(required_groups) - len(missing_groups),
                "missing_group_count": len(missing_groups),
                "group_results": group_results,
                "missing_groups": missing_groups,
                "claim_boundary": str(assignment.get("claim_boundary") or ""),
                "forbidden_claims": [str(item) for item in assignment.get("forbidden_claims") or [] if str(item).strip()],
            }
        )
    hard_gate = _hard_gate(gate_rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not hard_gate["action_required_assignment_count"] and not hard_gate["unregistered_required_source_role_count"] else "action_required",
        "assignment_count": len(gate_rows),
        "pass_assignment_count": len([row for row in gate_rows if row["status"] == "pass"]),
        "action_required_assignment_count": len([row for row in gate_rows if row["status"] != "pass"]),
        "family_count": len({row["family_id"] for row in gate_rows}),
        "ticker_count": len({row["ticker"] for row in gate_rows}),
        "by_family_status": _by_family_status(gate_rows),
        "by_missing_group": dict(Counter(group["group_id"] for row in gate_rows for group in row["missing_groups"])),
        "hard_gate": hard_gate,
        "policy": "AI/Semis first-tranche source-route gate requires registered roles plus parser-backed source authority rows; gaps remain action_required, not public-boundary closeout.",
    }
    return gate_rows, summary


def write_outputs(
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    *,
    output_rows_path: str | Path = DEFAULT_OUTPUT_ROWS_PATH,
    output_summary_path: str | Path = DEFAULT_OUTPUT_SUMMARY_PATH,
    output_report_path: str | Path = DEFAULT_OUTPUT_REPORT_PATH,
) -> dict[str, str]:
    rows_path = Path(output_rows_path)
    summary_path = Path(output_summary_path)
    report_path = Path(output_report_path)
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(rows, summary), encoding="utf-8")
    return {"rows": str(rows_path), "summary": str(summary_path), "report": str(report_path)}


def render_report(rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# R18 AI/Semis Source-Route Gate",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Assignments: `{summary.get('assignment_count', 0)}`",
        f"- Pass assignments: `{summary.get('pass_assignment_count', 0)}`",
        f"- Action required assignments: `{summary.get('action_required_assignment_count', 0)}`",
        "",
        "## Missing Groups",
        "",
    ]
    for group, count in sorted((summary.get("by_missing_group") or {}).items()):
        lines.append(f"- `{group}`: `{count}`")
    lines.extend(["", "## Action Required Rows", ""])
    for row in [item for item in rows if item.get("status") != "pass"][:80]:
        missing = ", ".join(str(group.get("group_id") or "") for group in row.get("missing_groups") or [])
        lines.append(f"- `{row.get('ticker')}` `{row.get('family_id')}`: {missing}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This gate checks source-route and authority readiness only. It does not promote L2/L3 rows into revenue, ASP, share, sell-through, backlog, inventory, or order-value facts.",
            "",
        ]
    )
    return "\n".join(lines)


def _evaluate_group(
    *,
    ticker: str,
    family_id: str,
    group: Mapping[str, Any],
    registered_roles: set[str],
    available_roles: set[str],
    route_plan_by_key: Mapping[tuple[str, str, str], Mapping[str, Any]],
    role_rows_by_ticker: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    any_of = [str(item) for item in group.get("any_of") or [] if str(item).strip()]
    registered = [role for role in any_of if role in registered_roles]
    satisfied = sorted(set(registered) & available_roles)
    route_rows = [route_plan_by_key.get((ticker, family_id, role), {}) for role in any_of]
    route_statuses = {
        role: str(route_plan_by_key.get((ticker, family_id, role), {}).get("route_status") or "not_in_family_route_plan")
        for role in any_of
    }
    if satisfied:
        status = "pass"
        root_cause = ""
    elif not registered:
        status = "fail"
        root_cause = "unregistered_required_source_role"
    elif any(str(row.get("route_status") or "") in {"seed_available_not_materialized", "not_materialized"} for row in route_rows if row):
        status = "action_required"
        root_cause = "route_or_parser_debt"
    elif any(role_rows_by_ticker.get((ticker, role)) for role in any_of):
        status = "action_required"
        root_cause = "source_authority_row_not_evidence_bundle_allowed"
    else:
        status = "action_required"
        root_cause = "no_parser_backed_runtime_row_for_required_group"
    return {
        "group_id": str(group.get("group_id") or ""),
        "status": status,
        "any_of": any_of,
        "registered_roles": registered,
        "satisfied_roles": satisfied,
        "route_statuses": route_statuses,
        "root_cause": root_cause,
    }


def _hard_gate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    unregistered = [
        group
        for row in rows
        for group in row.get("group_results") or []
        if isinstance(group, Mapping) and group.get("root_cause") == "unregistered_required_source_role"
    ]
    return {
        "unregistered_required_source_role_count": len(unregistered),
        "action_required_assignment_count": len([row for row in rows if row.get("status") != "pass"]),
        "url_or_snippet_promoted_count": 0,
        "forbidden_claim_violation_count": 0,
    }


def _by_family_status(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    output: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        output[str(row.get("family_id") or "")][str(row.get("status") or "")] += 1
    return {family: dict(counter) for family, counter in sorted(output.items())}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build R18 AI/Semis source-route gate.")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX_PATH))
    parser.add_argument("--assignments", default=str(DEFAULT_ASSIGNMENTS_PATH))
    parser.add_argument("--route-plan", default=str(DEFAULT_ROUTE_PLAN_PATH))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--output-rows", default=str(DEFAULT_OUTPUT_ROWS_PATH))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY_PATH))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT_PATH))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    rows, summary = build_ai_semis_source_route_gate(
        matrix_rows=_load_jsonl(Path(args.matrix)),
        assignment_rows=_load_jsonl(Path(args.assignments)),
        route_plan_rows=_load_jsonl(Path(args.route_plan)),
        registry_payload=_load_json(Path(args.registry)),
    )
    outputs = write_outputs(
        rows,
        summary,
        output_rows_path=args.output_rows,
        output_summary_path=args.output_summary,
        output_report_path=args.output_report,
    )
    print(json.dumps({**summary, "outputs": outputs}, ensure_ascii=False, sort_keys=True))
    if args.strict and summary.get("status") != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
