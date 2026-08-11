from __future__ import annotations

import argparse
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


SCHEMA_VERSION = "finsight_l3_minimum_coverage_gate_v0_1"
LOW_COVERAGE_SCHEMA_VERSION = "finsight_l3_minimum_coverage_gap_v0_1"

DEFAULT_COVERAGE_MATRIX = REPO_ROOT / "data" / "manifests" / "exact_slot_coverage_matrix_v0_1.jsonl"
DEFAULT_CASE_CATALOG = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "l3_minimum_coverage_gate_v0_1.json"
DEFAULT_OUTPUT_LOW_COVERAGE = REPO_ROOT / "data" / "manifests" / "l3_minimum_coverage_low_companies_v0_1.jsonl"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the R9 minimum L3 exact proxy coverage gate.")
    parser.add_argument("--coverage-matrix", type=Path, default=DEFAULT_COVERAGE_MATRIX)
    parser.add_argument("--case-catalog", type=Path, default=DEFAULT_CASE_CATALOG)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-low-coverage", type=Path, default=DEFAULT_OUTPUT_LOW_COVERAGE)
    parser.add_argument("--priority-tickers", nargs="*", default=[])
    parser.add_argument("--min-l3-rows", type=int, default=1)
    parser.add_argument("--priority-min-independent-roles", type=int, default=2)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = _load_jsonl(args.coverage_matrix)
    priority_tickers = _priority_tickers(args.priority_tickers, args.case_catalog)
    summary, low_rows = build_l3_minimum_coverage_gate(
        coverage_rows=rows,
        priority_tickers=priority_tickers,
        generated_at=_utc_now(),
        min_l3_rows=max(1, args.min_l3_rows),
        priority_min_independent_roles=max(1, args.priority_min_independent_roles),
    )
    _write_json(args.output_summary, summary)
    _write_jsonl(args.output_low_coverage, low_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["status"] != "pass":
        return 1
    return 0


def build_l3_minimum_coverage_gate(
    *,
    coverage_rows: Iterable[Mapping[str, Any]],
    priority_tickers: set[str],
    generated_at: str,
    min_l3_rows: int = 1,
    priority_min_independent_roles: int = 2,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [dict(row) for row in coverage_rows if isinstance(row, Mapping)]
    low_rows: list[dict[str, Any]] = []
    l3_counts: Counter[str] = Counter()
    independent_role_counts: Counter[str] = Counter()
    by_lane_zero: Counter[str] = Counter()
    by_lane_one: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        lane = str(row.get("primary_lane_id") or "")
        l3_count = _l3_exact_slot_count(row)
        role_ids = _l3_ready_role_ids(row)
        independent_count = len(role_ids)
        l3_counts[str(l3_count)] += 1
        independent_role_counts[str(independent_count)] += 1
        if l3_count == 0:
            by_lane_zero[lane] += 1
        if l3_count == 1:
            by_lane_one[lane] += 1
        reasons = _low_coverage_reasons(row, l3_count=l3_count, role_ids=role_ids)
        fails_base = l3_count < min_l3_rows
        fails_priority = ticker in priority_tickers and independent_count < priority_min_independent_roles
        if fails_base or fails_priority:
            for reason in reasons:
                by_reason[reason] += 1
            low_rows.append(
                {
                    "schema_version": LOW_COVERAGE_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "company_name": row.get("company_name") or "",
                    "primary_lane_id": lane,
                    "industry_schema": row.get("industry_schema") or "",
                    "l3_exact_slot_count": l3_count,
                    "l3_independent_source_role_count": independent_count,
                    "l3_ready_requirement_ids": sorted(role_ids),
                    "is_priority_ticker": ticker in priority_tickers,
                    "failed_base_min_l3": fails_base,
                    "failed_priority_independent_roles": fails_priority,
                    "low_coverage_reasons": reasons,
                    "l3_gap_requirements": _l3_gap_requirements(row),
                    "next_action": _next_action(reasons),
                }
            )

    zero_count = sum(1 for row in rows if _l3_exact_slot_count(row) == 0)
    one_count = sum(1 for row in rows if _l3_exact_slot_count(row) == 1)
    gt_one_count = len(rows) - zero_count - one_count
    priority_fail_count = sum(1 for row in low_rows if row["failed_priority_independent_roles"])
    base_fail_count = sum(1 for row in low_rows if row["failed_base_min_l3"])
    status = "pass" if base_fail_count == 0 and priority_fail_count == 0 else "gap"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "company_count": len(rows),
        "min_l3_rows": min_l3_rows,
        "priority_ticker_count": len(priority_tickers),
        "priority_min_independent_roles": priority_min_independent_roles,
        "l3_zero_company_count": zero_count,
        "l3_one_company_count": one_count,
        "l3_gt_one_company_count": gt_one_count,
        "base_fail_company_count": base_fail_count,
        "priority_fail_company_count": priority_fail_count,
        "low_coverage_company_count": len(low_rows),
        "l3_zero_by_lane": dict(sorted(by_lane_zero.items())),
        "l3_one_by_lane": dict(sorted(by_lane_one.items())),
        "independent_role_count_distribution": dict(sorted(independent_role_counts.items(), key=lambda item: int(item[0]))),
        "l3_exact_slot_count_distribution": dict(sorted(l3_counts.items(), key=lambda item: int(item[0]))),
        "low_coverage_reason_counts": dict(sorted(by_reason.items())),
        "sample_low_coverage_tickers": [
            {
                "ticker": row["ticker"],
                "lane": row["primary_lane_id"],
                "l3": row["l3_exact_slot_count"],
                "roles": row["l3_independent_source_role_count"],
                "reasons": row["low_coverage_reasons"],
            }
            for row in low_rows[:30]
        ],
        "boundary": (
            "This gate measures parser-backed L3 exact proxy rows only. It does not permit L3 rows to support "
            "issuer revenue, market share, sales volume, channel inventory, or other L1/product-KPI claims."
        ),
    }
    return summary, low_rows


def _l3_exact_slot_count(row: Mapping[str, Any]) -> int:
    layers = row.get("exact_slot_layers") if isinstance(row.get("exact_slot_layers"), Mapping) else {}
    try:
        return int(layers.get("L3") or 0)
    except (TypeError, ValueError):
        return 0


def _l3_ready_role_ids(row: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    for req in row.get("source_role_exact_slot_matrix") or []:
        if not isinstance(req, Mapping):
            continue
        target_layers = {str(layer) for layer in req.get("target_layer_ids") or []}
        if not (target_layers & {"L2", "L3"}):
            continue
        if str(req.get("requirement_id") or "") == "primary_company_disclosure":
            continue
        if str(req.get("status") or "") == "exact_slot_ready" and int(req.get("exact_slot_count") or 0) > 0:
            out.add(str(req.get("requirement_id") or ""))
    return out


def _l3_gap_requirements(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for req in row.get("source_role_exact_slot_matrix") or []:
        if not isinstance(req, Mapping):
            continue
        target_layers = {str(layer) for layer in req.get("target_layer_ids") or []}
        if "L3" not in target_layers or str(req.get("status") or "") == "exact_slot_ready":
            continue
        out.append(
            {
                "requirement_id": req.get("requirement_id") or "",
                "source_gate_status": req.get("source_gate_status") or "",
                "source_gate_gap_type": req.get("source_gate_gap_type") or "",
                "gap_class": req.get("gap_class") or "",
                "target_source_ids": req.get("target_source_ids") or [],
                "rejected_statuses": req.get("rejected_statuses") or {},
                "repair_seed_status": req.get("repair_seed_status") or "",
                "repair_seed_count": req.get("repair_seed_count") or 0,
            }
        )
    return out


def _low_coverage_reasons(row: Mapping[str, Any], *, l3_count: int, role_ids: set[str]) -> list[str]:
    reasons: set[str] = set()
    l3_reqs = [
        req
        for req in row.get("source_role_exact_slot_matrix") or []
        if isinstance(req, Mapping) and "L3" in {str(layer) for layer in req.get("target_layer_ids") or []}
    ]
    if not l3_reqs:
        reasons.add("no_applicable_l3_requirement_after_recalibration")
    if l3_count == 0 and l3_reqs:
        reasons.add("no_l3_exact_rows")
    if l3_count == 1:
        reasons.add("single_l3_row_only")
    if len(role_ids) <= 1 and l3_count > 0:
        reasons.add("single_independent_l3_source_role")
    for req in l3_reqs:
        gap_type = str(req.get("source_gate_gap_type") or "")
        gap_class = str(req.get("gap_class") or "")
        rejected = req.get("rejected_statuses") if isinstance(req.get("rejected_statuses"), Mapping) else {}
        if "parser" in gap_class or rejected:
            reasons.add("parser_or_structured_field_gap")
        elif "resolver" in gap_class or "binding" in gap_type:
            reasons.add("resolver_or_entity_binding_gap")
        elif "missing" in gap_type or gap_class == "source_gap":
            reasons.add("source_locator_or_public_data_gap")
    return sorted(reasons or {"low_l3_coverage_unclassified"})


def _next_action(reasons: Iterable[str]) -> str:
    reason_set = set(reasons)
    if "no_applicable_l3_requirement_after_recalibration" in reason_set:
        return "Review lane/product-family source policy; add applicable L3 requirement only if a public proxy source can be responsibly used."
    if "parser_or_structured_field_gap" in reason_set:
        return "Repair source-specific parser/backfill and rerun exact-slot matrix before declaring a source gap."
    if "resolver_or_entity_binding_gap" in reason_set:
        return "Repair issuer/product/counterparty resolver or write an audited resolver gap."
    return "Run lane-specific L3 adapters/locators; if public source remains unavailable, close as audited public-source gap."


def _priority_tickers(cli_tickers: Iterable[str], catalog_path: Path) -> set[str]:
    values = {str(ticker).strip().upper() for ticker in cli_tickers if str(ticker).strip()}
    if values:
        return values
    if not catalog_path.exists():
        return set()
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, Mapping) else []
    out: set[str] = set()
    for case in cases if isinstance(cases, list) else []:
        if not isinstance(case, Mapping):
            continue
        if str(case.get("priority") or "") != "P0":
            continue
        for key in ("focus_tickers", "search_scope_tickers"):
            for ticker in case.get(key) or []:
                text = str(ticker or "").strip().upper()
                if text:
                    out.add(text)
    return out


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
