from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_r18_vertical_source_route_gate_v0_1"

DEFAULT_COMPANY_COVERAGE_PATH = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_DATA_MART_PATH = REPO_ROOT / "data" / "manifests" / "r18_source_authority_data_mart_rows_v0_1.jsonl"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "manifests" / "r18_source_route_registry_v2.json"
DEFAULT_OUTPUT_ROWS_PATH = REPO_ROOT / "data" / "manifests" / "r18_vertical_source_route_gate_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY_PATH = REPO_ROOT / "data" / "manifests" / "r18_vertical_source_route_gate_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT_PATH = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "r18_vertical_source_route_gate.zh-CN.md"

SOURCE_ROLE_ALTERNATE_EVIDENCE: dict[str, tuple[str, ...]] = {
    # Official customer/order/deployment event rows are a more precise alternate
    # validation source for the "public order / customer relationship" question
    # when procurement award rows are unavailable. Their claim boundary still
    # forbids revenue, backlog, ASP, shipment, sell-through, share, and complete
    # order-book promotion.
    "public_order_proxy": ("official_customer_order_or_deployment_event",),
}


def build_vertical_source_route_gate(
    *,
    company_coverage_rows: Sequence[Mapping[str, Any]],
    data_mart_rows: Sequence[Mapping[str, Any]],
    registry_payload: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    registered_roles = _registered_source_roles(registry_payload or {})
    mart_by_ticker_role = _mart_by_ticker_role(data_mart_rows)
    rows: list[dict[str, Any]] = []
    for company in company_coverage_rows:
        ticker = _ticker(company)
        requirement_results = []
        for req in company.get("source_role_matrix") or []:
            if not isinstance(req, Mapping) or not str(req.get("requirement_id") or ""):
                continue
            role = str(req.get("requirement_id") or "")
            candidate_roles = _candidate_source_roles(role)
            candidate_rows = [
                mart_row
                for candidate_role in candidate_roles
                for mart_row in mart_by_ticker_role.get((ticker, candidate_role), [])
            ]
            requirement_results.append(
                _evaluate_requirement(
                    ticker=ticker,
                    company=company,
                    requirement=req,
                    candidate_source_roles=candidate_roles,
                    mart_rows=candidate_rows,
                    registered_roles=registered_roles,
                )
            )
        missing = [row for row in requirement_results if row["status"] != "pass"]
        lane_id = str(company.get("primary_lane_id") or "")
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": str(company.get("company_name") or ""),
                "primary_lane_id": lane_id,
                "primary_lane_name": str(company.get("primary_lane_name") or ""),
                "market_region": str(company.get("market_region") or ""),
                "sector": str(company.get("sector") or ""),
                "industry_schema": str(company.get("industry_schema") or ""),
                "coverage_status": str(company.get("coverage_status") or ""),
                "status": "pass" if not missing else "action_required",
                "requirement_count": len(requirement_results),
                "passed_requirement_count": len(requirement_results) - len(missing),
                "missing_requirement_count": len(missing),
                "missing_source_roles": [row["source_role"] for row in missing],
                "requirement_results": requirement_results,
                "public_data_ceiling": company.get("public_data_ceiling") or [],
                "expected_commercial_gaps": company.get("expected_commercial_gaps") or [],
                "claim_boundary": str(company.get("boundary") or ""),
            }
        )
    rows.sort(key=lambda row: (row["primary_lane_id"], row["ticker"]))
    summary = build_summary(rows, generated_at=generated_at)
    return rows, summary


def build_summary(rows: Sequence[Mapping[str, Any]], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    action_rows = [row for row in rows if row.get("status") != "pass"]
    missing_results = [
        result
        for row in rows
        for result in row.get("requirement_results") or []
        if result.get("status") != "pass"
    ]
    hard_flags = Counter(
        flag
        for row in rows
        for result in row.get("requirement_results") or []
        for flag in result.get("hard_gate_flags") or []
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not action_rows and not hard_flags else "action_required",
        "company_count": len(rows),
        "pass_company_count": len(rows) - len(action_rows),
        "action_required_company_count": len(action_rows),
        "requirement_count": sum(int(row.get("requirement_count") or 0) for row in rows),
        "passed_requirement_count": sum(int(row.get("passed_requirement_count") or 0) for row in rows),
        "missing_requirement_count": sum(int(row.get("missing_requirement_count") or 0) for row in rows),
        "by_lane_status": _by_lane_status(rows),
        "by_missing_source_role": dict(Counter(str(result.get("source_role") or "") for result in missing_results).most_common()),
        "by_root_cause": dict(Counter(str(result.get("root_cause") or "") for result in missing_results).most_common()),
        "by_gap_class": dict(Counter(str(result.get("gap_class") or "") for result in missing_results).most_common()),
        "hard_gate": {
            "flag_count": sum(hard_flags.values()),
            "by_flag": dict(hard_flags),
        },
        "policy": (
            "Cross-lane diagnostic source-route gate. A pass means each company lane-required source role has at least one "
            "parser-backed source-authority row admitted to evidence bundle. Action-required rows remain route/parser/resolver work, "
            "not memo evidence."
        ),
    }
    return summary


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
    for path in (rows_path, summary_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    rows_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(rows, summary), encoding="utf-8")
    return {"rows": str(rows_path), "summary": str(summary_path), "report": str(report_path)}


def render_report(rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# R18 Vertical Source-Route Gate",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Companies: `{summary.get('company_count', 0)}`",
        f"- Pass companies: `{summary.get('pass_company_count', 0)}`",
        f"- Action-required companies: `{summary.get('action_required_company_count', 0)}`",
        f"- Requirements: `{summary.get('requirement_count', 0)}`",
        f"- Passed requirements: `{summary.get('passed_requirement_count', 0)}`",
        f"- Missing requirements: `{summary.get('missing_requirement_count', 0)}`",
        "",
        "## Missing Source Roles",
        "",
    ]
    for key, value in (summary.get("by_missing_source_role") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Root Causes", ""])
    for key, value in (summary.get("by_root_cause") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Lane Status", ""])
    for lane_id, payload in sorted((summary.get("by_lane_status") or {}).items()):
        lines.append(
            f"- `{lane_id}`: pass `{payload.get('pass', 0)}`, action_required `{payload.get('action_required', 0)}`"
        )
    lines.extend(["", "## Action Required Companies", ""])
    for row in [item for item in rows if item.get("status") != "pass"][:120]:
        missing = ", ".join(row.get("missing_source_roles") or [])
        lines.append(f"- `{row.get('ticker')}` `{row.get('primary_lane_id')}`: {missing}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a diagnostic gate over required source roles. It does not mean every product/SKU/KPI is complete.",
            "- Missing requirements are not hidden as fallback evidence; they remain source-route, parser, resolver, or public-boundary work.",
            "",
        ]
    )
    return "\n".join(lines)


def _evaluate_requirement(
    *,
    ticker: str,
    company: Mapping[str, Any],
    requirement: Mapping[str, Any],
    candidate_source_roles: Sequence[str],
    mart_rows: Sequence[Mapping[str, Any]],
    registered_roles: set[str],
) -> dict[str, Any]:
    role = str(requirement.get("requirement_id") or "")
    evidence_rows = [row for row in mart_rows if row.get("can_enter_evidence_bundle")]
    source_ids = _str_list(requirement.get("source_ids"))
    evidence_source_ids = sorted({str(row.get("source_id") or "") for row in evidence_rows if str(row.get("source_id") or "")})
    gap_class = str(requirement.get("gap_class") or "")
    req_status = str(requirement.get("status") or "")
    hard_flags: list[str] = []
    if role not in registered_roles:
        hard_flags.append("required_source_role_not_registered")
    if req_status == "pass" and not evidence_rows:
        hard_flags.append("coverage_matrix_pass_without_data_mart_evidence")

    if evidence_rows:
        status = "pass"
        root_cause = ""
    elif role not in registered_roles:
        status = "action_required"
        root_cause = "source_role_contract_missing"
    elif req_status == "pass":
        status = "action_required"
        root_cause = "mart_sync_or_authority_mapping_debt"
    elif any(str(row.get("availability_status") or "") == "route_or_parser_debt" for row in mart_rows):
        status = "action_required"
        root_cause = "route_or_parser_debt"
    elif gap_class == "resolver_gap":
        status = "action_required"
        root_cause = "entity_or_product_resolver_gap"
    elif gap_class == "source_gap":
        status = "action_required"
        root_cause = "source_or_adapter_gap"
    else:
        status = "action_required"
        root_cause = str(requirement.get("gap_type") or "source_role_not_evidence_ready")

    return {
        "ticker": ticker,
        "requirement_id": role,
        "source_role": role,
        "candidate_source_roles": list(candidate_source_roles),
        "satisfied_source_roles": sorted({str(row.get("source_role") or "") for row in evidence_rows if str(row.get("source_role") or "")}),
        "status": status,
        "root_cause": root_cause,
        "requirement_status": req_status,
        "dimension": str(requirement.get("dimension") or ""),
        "gap_class": gap_class,
        "gap_type": str(requirement.get("gap_type") or ""),
        "source_ids": source_ids,
        "evidence_source_ids": evidence_source_ids,
        "evidence_row_count": len(evidence_rows),
        "observed_row_count": int(requirement.get("observed_row_count") or 0),
        "parser_row_count": int(requirement.get("parser_row_count") or 0),
        "entity_bound_row_count": int(requirement.get("entity_bound_row_count") or 0),
        "exact_authority_violation_count": int(requirement.get("exact_authority_violation_count") or 0),
        "claim_boundary": str(requirement.get("claim_boundary") or company.get("boundary") or ""),
        "next_action": str(requirement.get("next_action") or ""),
        "hard_gate_flags": hard_flags,
    }


def _candidate_source_roles(role: str) -> list[str]:
    return [role, *SOURCE_ROLE_ALTERNATE_EVIDENCE.get(role, ())]


def _mart_by_ticker_role(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = _ticker(row)
        role = str(row.get("source_role") or "")
        if ticker and role:
            out[(ticker, role)].append(dict(row))
    return out


def _by_lane_status(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        out[str(row.get("primary_lane_id") or "")][str(row.get("status") or "")] += 1
    return {key: dict(value) for key, value in sorted(out.items())}


def _registered_source_roles(payload: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("source_role") or "")
        for row in payload.get("contracts") or []
        if isinstance(row, Mapping) and str(row.get("source_role") or "")
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _str_list(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    items = value if isinstance(value, list) else [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("provider_symbol") or "").upper()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cross-lane R18 source route readiness gate.")
    parser.add_argument("--company-coverage-path", type=Path, default=DEFAULT_COMPANY_COVERAGE_PATH)
    parser.add_argument("--data-mart-path", type=Path, default=DEFAULT_DATA_MART_PATH)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--output-rows-path", type=Path, default=DEFAULT_OUTPUT_ROWS_PATH)
    parser.add_argument("--output-summary-path", type=Path, default=DEFAULT_OUTPUT_SUMMARY_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    rows, summary = build_vertical_source_route_gate(
        company_coverage_rows=_read_jsonl(args.company_coverage_path),
        data_mart_rows=_read_jsonl(args.data_mart_path),
        registry_payload=_read_json(args.registry_path),
        generated_at=generated_at,
    )
    outputs = write_outputs(
        rows,
        summary,
        output_rows_path=args.output_rows_path,
        output_summary_path=args.output_summary_path,
        output_report_path=args.output_report_path,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "company_count": summary["company_count"],
                "pass_company_count": summary["pass_company_count"],
                "action_required_company_count": summary["action_required_company_count"],
                "missing_requirement_count": summary["missing_requirement_count"],
                "hard_gate": summary["hard_gate"],
                **outputs,
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
