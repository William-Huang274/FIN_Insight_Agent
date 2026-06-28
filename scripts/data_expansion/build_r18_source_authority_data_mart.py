from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_r18_source_authority_data_mart_v0_1"

DEFAULT_ADMISSION_LEDGER_PATH = REPO_ROOT / "data" / "manifests" / "r18_data_source_admission_ledger_v0_1.jsonl"
DEFAULT_AUTHORITY_MATRIX_PATH = REPO_ROOT / "data" / "manifests" / "r18_signal_authority_coverage_matrix_v0_2.jsonl"
DEFAULT_COMPANY_COVERAGE_PATH = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS_PATH = REPO_ROOT / "data" / "manifests" / "r18_source_authority_data_mart_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY_PATH = REPO_ROOT / "data" / "manifests" / "r18_source_authority_data_mart_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT_PATH = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "r18_source_authority_data_mart.zh-CN.md"


EXACT_SOURCE_ROLES = {
    "primary_company_disclosure",
    "company_reported_product_kpi",
    "company_reported_operating_metric",
    "financial_regulatory_context",
}


def build_source_authority_data_mart(
    *,
    admission_rows: Sequence[Mapping[str, Any]],
    authority_rows: Sequence[Mapping[str, Any]],
    company_coverage_rows: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    authority_by_key = _authority_index(authority_rows)
    company_by_ticker = {
        _ticker(row): dict(row)
        for row in company_coverage_rows or []
        if _ticker(row)
    }
    rows: list[dict[str, Any]] = []
    for admission in admission_rows:
        ticker = _ticker(admission)
        role = str(admission.get("source_role") or "")
        source_id = str(admission.get("source_id") or "")
        authority_row = _find_authority_row(authority_by_key, admission)
        authority = authority_row.get("authority") if isinstance(authority_row.get("authority"), Mapping) else {}
        company = company_by_ticker.get(ticker, {})
        can_enter = bool(admission.get("can_enter_evidence_bundle")) and bool(
            authority_row.get("can_enter_evidence_bundle", authority.get("can_enter_evidence_bundle", True))
        )
        authority_mode = str(authority.get("authority_mode") or authority_row.get("authority_mode") or "")
        signal_authority_type = str(authority.get("signal_authority_type") or authority_row.get("signal_authority_type") or "")
        exact_authority = bool(authority.get("exact_company_fact_authority") or authority_row.get("exact_company_fact_authority"))
        thesis_authority = bool(authority.get("thesis_driver_authority") or authority_row.get("thesis_driver_authority"))
        claim_boundary = str(admission.get("claim_boundary") or authority_row.get("claim_boundary") or "")
        sample_urls = _str_list(admission.get("sample_urls") or authority_row.get("sample_urls"))
        sample_refs = _str_list(admission.get("sample_evidence_refs") or authority_row.get("sample_evidence_refs"))
        mart_row = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "ledger_id": str(admission.get("ledger_id") or authority_row.get("ledger_id") or ""),
            "ticker": ticker,
            "company_name": str(admission.get("company_name") or authority_row.get("company_name") or ""),
            "primary_lane_id": str(admission.get("primary_lane_id") or authority_row.get("primary_lane_id") or ""),
            "primary_lane_name": str(admission.get("primary_lane_name") or ""),
            "industry_schema": str(admission.get("industry_schema") or ""),
            "market_region": str(admission.get("market_region") or ""),
            "sector": str(admission.get("sector") or ""),
            "company_coverage_status": str(company.get("status") or ""),
            "company_public_interface_status": str(company.get("coverage_status") or ""),
            "source_role": role,
            "source_id": source_id,
            "source_layer": str(admission.get("source_layer") or authority_row.get("source_layer") or ""),
            "support_surface": str(admission.get("support_surface") or authority_row.get("support_surface") or ""),
            "dimension": str(admission.get("dimension") or ""),
            "company_specific": bool(admission.get("company_specific")),
            "availability_status": str(admission.get("availability_status") or authority_row.get("availability_status") or ""),
            "adapter_parser_status": str(admission.get("adapter_parser_status") or authority_row.get("adapter_parser_status") or ""),
            "route_source_status": str(admission.get("route_source_status") or ""),
            "can_enter_evidence_bundle": can_enter,
            "admission_tier": _admission_tier(
                can_enter=can_enter,
                exact_authority=exact_authority,
                thesis_authority=thesis_authority,
                availability_status=str(admission.get("availability_status") or authority_row.get("availability_status") or ""),
                role=role,
            ),
            "authority_mode": authority_mode,
            "signal_authority_type": signal_authority_type,
            "exact_company_fact_authority": exact_authority,
            "thesis_driver_authority": thesis_authority,
            "claim_boundary": claim_boundary,
            "claim_scope": str(authority.get("claim_scope") or authority_row.get("claim_scope") or ""),
            "forbidden_claim_types": _str_list(authority.get("forbidden_claim_types") or authority_row.get("forbidden_claim_types")),
            "forbidden_claim_note": str(admission.get("forbidden_claim_note") or ""),
            "observed_row_count": int(admission.get("observed_row_count") or 0),
            "parser_row_count": int(admission.get("parser_row_count") or 0),
            "entity_bound_row_count": int(admission.get("entity_bound_row_count") or 0),
            "exact_slot_count": int(admission.get("exact_slot_count") or 0),
            "exact_authority_violation_count": int(admission.get("exact_authority_violation_count") or 0),
            "sample_urls": sample_urls[:5],
            "sample_evidence_refs": sample_refs[:8],
            "gap_class": str(admission.get("gap_class") or ""),
            "gap_type": str(admission.get("gap_type") or ""),
            "attempt_gate_status": str(admission.get("attempt_gate_status") or ""),
            "attempt_debt_class": str(admission.get("attempt_debt_class") or ""),
            "attempt_count": int(admission.get("attempt_count") or 0),
            "next_action": str(admission.get("next_action") or ""),
            "data_summary": str(admission.get("data_summary") or ""),
            "source_matrix_hard_gate_flags": _row_hard_gate_flags(
                can_enter=can_enter,
                ticker=ticker,
                role=role,
                source_id=source_id,
                source_layer=str(admission.get("source_layer") or authority_row.get("source_layer") or ""),
                authority_mode=authority_mode,
                signal_authority_type=signal_authority_type,
                claim_boundary=claim_boundary,
                sample_urls=sample_urls,
                sample_refs=sample_refs,
                parser_row_count=int(admission.get("parser_row_count") or 0),
                exact_slot_count=int(admission.get("exact_slot_count") or 0),
            ),
        }
        rows.append(mart_row)
    rows.sort(key=lambda row: (row["primary_lane_id"], row["ticker"], row["source_role"], row["source_id"]))
    summary = build_summary(rows, generated_at=generated_at)
    return rows, summary


def build_summary(rows: Sequence[Mapping[str, Any]], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    evidence_rows = [row for row in rows if row.get("can_enter_evidence_bundle")]
    flags = Counter(
        flag
        for row in rows
        for flag in row.get("source_matrix_hard_gate_flags") or []
    )
    source_role_gap = Counter(
        str(row.get("source_role") or "")
        for row in rows
        if not row.get("can_enter_evidence_bundle")
    )
    company_without_evidence = sorted(
        {
            str(row.get("ticker") or "")
            for row in rows
            if str(row.get("ticker") or "")
        }
        - {
            str(row.get("ticker") or "")
            for row in evidence_rows
            if str(row.get("ticker") or "")
        }
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not flags else "action_required",
        "row_count": len(rows),
        "company_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "evidence_bundle_allowed_count": len(evidence_rows),
        "planning_or_gap_only_count": len(rows) - len(evidence_rows),
        "exact_company_fact_authority_count": sum(1 for row in evidence_rows if row.get("exact_company_fact_authority")),
        "thesis_driver_authority_count": sum(1 for row in evidence_rows if row.get("thesis_driver_authority")),
        "company_without_evidence_source_count": len(company_without_evidence),
        "company_without_evidence_source_samples": company_without_evidence[:50],
        "by_primary_lane": dict(Counter(str(row.get("primary_lane_id") or "") for row in rows)),
        "by_source_layer": dict(Counter(str(row.get("source_layer") or "") for row in rows)),
        "by_source_role": dict(Counter(str(row.get("source_role") or "") for row in rows)),
        "by_source_id": dict(Counter(str(row.get("source_id") or "") for row in rows)),
        "by_support_surface": dict(Counter(str(row.get("support_surface") or "") for row in rows)),
        "by_availability_status": dict(Counter(str(row.get("availability_status") or "") for row in rows)),
        "by_adapter_parser_status": dict(Counter(str(row.get("adapter_parser_status") or "") for row in rows)),
        "by_admission_tier": dict(Counter(str(row.get("admission_tier") or "") for row in rows)),
        "by_authority_mode": dict(Counter(str(row.get("authority_mode") or "") for row in rows)),
        "by_signal_authority_type": dict(Counter(str(row.get("signal_authority_type") or "") for row in rows)),
        "top_gap_source_roles": dict(source_role_gap.most_common(30)),
        "hard_gate": {
            "flag_count": sum(flags.values()),
            "by_flag": dict(flags),
        },
        "policy": (
            "Canonical source-authority mart for Research Lead, eval, and frontend trace. "
            "Only can_enter_evidence_bundle=true rows can feed ClaimCards; all other rows remain targeted-repair or gap-ledger inputs."
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
        "# R18 Source Authority Data Mart",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Companies: `{summary.get('company_count', 0)}`",
        f"- Rows: `{summary.get('row_count', 0)}`",
        f"- Evidence bundle allowed rows: `{summary.get('evidence_bundle_allowed_count', 0)}`",
        f"- Planning/gap-only rows: `{summary.get('planning_or_gap_only_count', 0)}`",
        f"- Exact company fact authority rows: `{summary.get('exact_company_fact_authority_count', 0)}`",
        f"- Thesis driver authority rows: `{summary.get('thesis_driver_authority_count', 0)}`",
        "",
        "## Admission Tier",
        "",
    ]
    for key, value in sorted((summary.get("by_admission_tier") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Source Role Gaps", ""])
    for key, value in (summary.get("top_gap_source_roles") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Hard Gate", ""])
    hard_gate = summary.get("hard_gate") if isinstance(summary.get("hard_gate"), Mapping) else {}
    lines.append(f"- `flag_count`: `{hard_gate.get('flag_count', 0)}`")
    for key, value in sorted((hard_gate.get("by_flag") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Representative Planning / Gap Rows", ""])
    for row in [item for item in rows if not item.get("can_enter_evidence_bundle")][:40]:
        lines.append(
            "- "
            f"`{row.get('ticker')}` `{row.get('source_role')}` `{row.get('source_id')}`: "
            f"{row.get('availability_status')} / {row.get('adapter_parser_status')}; "
            f"{row.get('next_action')}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This mart is the canonical source-authority view, not a raw crawl dump.",
            "- Rows with `can_enter_evidence_bundle=false` must not feed ClaimCards or Memo claims.",
            "- L2/L3 rows can support bounded thesis drivers only according to `claim_boundary`; they must not be promoted into product revenue, ASP, market share, sell-through, inventory, backlog, or order value unless exact authority exists.",
            "",
        ]
    )
    return "\n".join(lines)


def _row_hard_gate_flags(
    *,
    can_enter: bool,
    ticker: str,
    role: str,
    source_id: str,
    source_layer: str,
    authority_mode: str,
    signal_authority_type: str,
    claim_boundary: str,
    sample_urls: Sequence[str],
    sample_refs: Sequence[str],
    parser_row_count: int,
    exact_slot_count: int,
) -> list[str]:
    if not can_enter:
        return []
    flags: list[str] = []
    if not ticker:
        flags.append("accepted_row_missing_ticker")
    if not role:
        flags.append("accepted_row_missing_source_role")
    if not source_id:
        flags.append("accepted_row_missing_source_id")
    if not source_layer:
        flags.append("accepted_row_missing_source_layer")
    if not claim_boundary:
        flags.append("accepted_row_missing_claim_boundary")
    if not authority_mode:
        flags.append("accepted_row_missing_authority_mode")
    if not signal_authority_type:
        flags.append("accepted_row_missing_signal_authority_type")
    if not sample_urls and not sample_refs:
        flags.append("accepted_row_missing_url_or_evidence_ref")
    if parser_row_count <= 0 and exact_slot_count <= 0:
        flags.append("accepted_row_missing_parser_or_exact_slot")
    return flags


def _admission_tier(
    *,
    can_enter: bool,
    exact_authority: bool,
    thesis_authority: bool,
    availability_status: str,
    role: str,
) -> str:
    if can_enter and (exact_authority or role in EXACT_SOURCE_ROLES):
        return "exact_company_fact_authority"
    if can_enter and thesis_authority:
        return "bounded_thesis_driver_authority"
    if can_enter:
        return "bounded_evidence_authority"
    if availability_status == "route_or_parser_debt":
        return "route_or_parser_debt"
    if availability_status == "attempt_backed_public_boundary":
        return "attempt_backed_public_boundary"
    if availability_status.startswith("planning_only"):
        return "planning_or_gap_only"
    return "not_evidence_ready"


def _authority_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ledger_id = str(row.get("ledger_id") or "")
        ticker = _ticker(row)
        role = str(row.get("source_role") or "")
        source_id = str(row.get("source_id") or "")
        if ledger_id:
            index[("ledger", ledger_id, "")] = dict(row)
        if ticker and role and source_id:
            index[("key", f"{ticker}\x1f{role}", source_id)] = dict(row)
    return index


def _find_authority_row(index: Mapping[tuple[str, str, str], dict[str, Any]], row: Mapping[str, Any]) -> dict[str, Any]:
    ledger_id = str(row.get("ledger_id") or "")
    if ledger_id and ("ledger", ledger_id, "") in index:
        return index[("ledger", ledger_id, "")]
    ticker = _ticker(row)
    role = str(row.get("source_role") or "")
    source_id = str(row.get("source_id") or "")
    return index.get(("key", f"{ticker}\x1f{role}", source_id), {})


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
    parser = argparse.ArgumentParser(description="Build canonical R18 source authority data mart.")
    parser.add_argument("--admission-ledger-path", type=Path, default=DEFAULT_ADMISSION_LEDGER_PATH)
    parser.add_argument("--authority-matrix-path", type=Path, default=DEFAULT_AUTHORITY_MATRIX_PATH)
    parser.add_argument("--company-coverage-path", type=Path, default=DEFAULT_COMPANY_COVERAGE_PATH)
    parser.add_argument("--output-rows-path", type=Path, default=DEFAULT_OUTPUT_ROWS_PATH)
    parser.add_argument("--output-summary-path", type=Path, default=DEFAULT_OUTPUT_SUMMARY_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    rows, summary = build_source_authority_data_mart(
        admission_rows=_read_jsonl(args.admission_ledger_path),
        authority_rows=_read_jsonl(args.authority_matrix_path),
        company_coverage_rows=_read_jsonl(args.company_coverage_path),
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
                "row_count": summary["row_count"],
                "company_count": summary["company_count"],
                "evidence_bundle_allowed_count": summary["evidence_bundle_allowed_count"],
                "planning_or_gap_only_count": summary["planning_or_gap_only_count"],
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
