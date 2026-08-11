from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_r15_public_source_gap_exhaustion_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_r15_public_source_gap_exhaustion_summary_v0_1"

DEFAULT_DOCKET = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_EXACT_ROWS = REPO_ROOT / "data" / "manifests" / "exact_slot_rows_v0_1.jsonl"
DEFAULT_ATTEMPT_PATHS = [
    REPO_ROOT / "data" / "manifests" / "broad_hiring_capacity_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_official_careers_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_channel_offer_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "family_channel_distributor_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_public_contract_award_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "local_public_tender_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "targeted_supply_chain_official_relationship_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "broad_app_store_platform_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "targeted_regulated_auto_official_api_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "v1_openalex_technology_research_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "v1_patentsview_technology_research_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "developer_ecosystem_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_locator_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r15_manual_public_source_attempts_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "r15_product_kpi_exhaustion_attempts_v0_1.jsonl",
]
DEFAULT_PRODUCT_KPI_DIAGNOSTIC = REPO_ROOT / "data" / "manifests" / "product_kpi_deep_gap_diagnostic_v0_1.jsonl"
DEFAULT_EXACT_GAP_CLOSEOUT = REPO_ROOT / "data" / "manifests" / "exact_slot_gap_closeout_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "r15_public_source_gap_exhaustion_ledger_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "r15_public_source_gap_exhaustion_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "r15_public_source_gap_exhaustion.zh-CN.md"
)

SOURCE_ROLE_REQUIREMENTS = {
    "app_rank_store_proxy",
    "auto_product_identity_context",
    "channel_offer_proxy",
    "developer_ecosystem_proxy",
    "hiring_capacity_proxy",
    "platform_review_proxy",
    "public_order_proxy",
    "supply_chain_official_relationship",
    "technology_research_proxy",
}

PRODUCT_KPI_R15_2_CLUSTERS = {
    "product_kpi_non_us_ir_local_exchange_parser",
    "product_kpi_column_group_schema_verifier",
    "product_kpi_period_version_schema_verifier",
    "product_kpi_sentence_relation_verifier",
    "product_kpi_ir_deck_annual_report_locator",
}

PRODUCT_KPI_R15_3_CLUSTERS = {
    "product_kpi_business_segment_boundary",
    "product_kpi_industry_operating_metric_slot_router",
    "product_kpi_percentage_change_rejection_gate",
    "product_kpi_region_dimension_or_rejection_gate",
    "product_kpi_non_product_total_rejection_gate",
}

TERMINAL_COMPLETION_STATES = {
    "attempt_backed_public_boundary_after_local_tender_attempt",
    "attempt_backed_public_boundary_or_make_alias_repair",
    "region_exposure_only_or_needs_product_table",
    "reject_or_find_product_family_table",
    "reject_or_pair_with_currency_level_value",
    "route_to_business_mix_or_remain_product_kpi_gap",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R15 public-source gap exhaustion ledger.")
    parser.add_argument("--docket", type=Path, default=DEFAULT_DOCKET)
    parser.add_argument("--exact-rows", type=Path, default=DEFAULT_EXACT_ROWS)
    parser.add_argument("--product-kpi-diagnostic", type=Path, default=DEFAULT_PRODUCT_KPI_DIAGNOSTIC)
    parser.add_argument("--exact-gap-closeout", type=Path, default=DEFAULT_EXACT_GAP_CLOSEOUT)
    parser.add_argument("--attempt-path", dest="attempt_paths", type=Path, action="append", default=None)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--stage", choices=["all", "r15_1", "r15_2", "r15_3", "r15_4", "r15_5"], default="all")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    if args.attempt_paths is None:
        args.attempt_paths = DEFAULT_ATTEMPT_PATHS
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    attempts = [row for path in args.attempt_paths for row in _load_jsonl(path)]
    rows = build_r15_public_source_gap_exhaustion_rows(
        docket_rows=_load_jsonl(args.docket),
        exact_rows=_load_jsonl(args.exact_rows),
        attempt_rows=attempts,
        product_kpi_diagnostic_rows=_load_jsonl(args.product_kpi_diagnostic),
        exact_gap_closeout_rows=_load_jsonl(args.exact_gap_closeout),
        generated_at=generated_at,
    )
    summary = build_summary(rows=rows, generated_at=generated_at, output_rows=args.output_rows, output_report=args.output_report)
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not _stage_pass(summary, args.stage):
        return 1
    return 0


def build_r15_public_source_gap_exhaustion_rows(
    *,
    docket_rows: Iterable[Mapping[str, Any]],
    exact_rows: Iterable[Mapping[str, Any]],
    attempt_rows: Iterable[Mapping[str, Any]],
    product_kpi_diagnostic_rows: Iterable[Mapping[str, Any]],
    exact_gap_closeout_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    exact_by_ticker_req = _index_exact_rows(exact_rows)
    attempts_by_ticker_req = _index_attempt_rows(attempt_rows)
    product_diag_by_ticker = {_ticker(row): dict(row) for row in product_kpi_diagnostic_rows if _ticker(row)}
    closeout_by_ticker_req = _index_closeout_rows(exact_gap_closeout_rows)
    out: list[dict[str, Any]] = []
    for docket in sorted(docket_rows, key=lambda row: (str(row.get("docket_type") or ""), str(row.get("ticker") or ""), str(row.get("requirement_id") or ""))):
        ticker = _ticker(docket)
        requirement_id = str(docket.get("requirement_id") or "")
        cluster_id = str(docket.get("cluster_id") or "")
        r15_stage = _r15_stage(docket)
        exact_count = len(exact_by_ticker_req.get((ticker, requirement_id), []))
        attempts = attempts_by_ticker_req.get((ticker, requirement_id), [])
        terminal_state = _terminal_state(
            docket=docket,
            exact_count=exact_count,
            attempts=attempts,
            attempt_count=len(attempts),
            product_diag=product_diag_by_ticker.get(ticker, {}),
            closeout=closeout_by_ticker_req.get((ticker, requirement_id), {}),
        )
        closeout = closeout_by_ticker_req.get((ticker, requirement_id), {})
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": docket.get("company_name") or "",
                "primary_lane_id": docket.get("primary_lane_id") or "",
                "docket_type": docket.get("docket_type") or "",
                "requirement_id": requirement_id,
                "cluster_id": cluster_id,
                "r15_stage": r15_stage,
                "priority": docket.get("priority") or "",
                "completion_state": docket.get("completion_state") or "",
                "closeout_class": closeout.get("closeout_class") or "",
                "closeout_reason": closeout.get("closeout_reason") or "",
                "terminal_state": terminal_state,
                "terminal_reason": _terminal_reason(
                    docket,
                    terminal_state=terminal_state,
                    attempts=attempts,
                    closeout=closeout,
                ),
                "source_ladder": list(docket.get("source_ladder") or []),
                "pass_condition": docket.get("pass_condition") or "",
                "next_action": docket.get("next_action") or "",
                "final_gap_allowed_only_after": docket.get("final_gap_allowed_only_after") or "",
                "exact_row_count": exact_count,
                "attempt_count": len(attempts),
                "attempt_status_counts": dict(Counter(str(row.get("attempt_status") or row.get("status") or "") for row in attempts).most_common(8)),
                "sample_attempts": [_sample_attempt(row) for row in attempts[:5]],
                "product_kpi_diagnostic_class": (product_diag_by_ticker.get(ticker, {}) or {}).get("diagnostic_class") or "",
                "product_kpi_diagnostic_reason": (product_diag_by_ticker.get(ticker, {}) or {}).get("diagnostic_reason") or "",
                "public_data_ceiling": docket.get("public_data_ceiling") or "",
                "claim_boundary": docket.get("claim_boundary") or "",
                "repair_contract": (
                    "Only parser-backed runtime rows can close data gaps as ready. Attempt-backed closeout rows are audit context, "
                    "not evidence. Rerouted Product-KPI rows must stay in their typed slots."
                ),
            }
        )
    return out


def build_summary(*, rows: list[dict[str, Any]], generated_at: str, output_rows: Path, output_report: Path) -> dict[str, Any]:
    by_stage = Counter(str(row.get("r15_stage") or "") for row in rows)
    by_terminal = Counter(str(row.get("terminal_state") or "") for row in rows)
    open_rows = [row for row in rows if row.get("terminal_state") == "open_gap_needs_repair"]
    pending_rows = [
        row
        for row in rows
        if row.get("terminal_state") in {"open_gap_needs_repair", "attempted_not_exhausted"}
    ]
    source_role_rows = [row for row in rows if row.get("docket_type") == "source_role"]
    product_rows = [row for row in rows if row.get("docket_type") == "product_kpi"]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not [row for row in rows if row.get("terminal_state") == "unclassified_terminal_state"] else "gap",
        "row_count": len(rows),
        "source_role_row_count": len(source_role_rows),
        "product_kpi_row_count": len(product_rows),
        "by_stage": dict(sorted(by_stage.items())),
        "by_terminal_state": dict(sorted(by_terminal.items())),
        "open_gap_count": len(open_rows),
        "pending_gap_count": len(pending_rows),
        "open_gap_by_stage": dict(sorted(Counter(str(row.get("r15_stage") or "") for row in open_rows).items())),
        "open_gap_by_cluster": dict(sorted(Counter(str(row.get("cluster_id") or "") for row in open_rows).items())),
        "pending_gap_by_stage": dict(sorted(Counter(str(row.get("r15_stage") or "") for row in pending_rows).items())),
        "pending_gap_by_cluster": dict(sorted(Counter(str(row.get("cluster_id") or "") for row in pending_rows).items())),
        "source_role_open_gap_without_attempt_count": len(
            [row for row in source_role_rows if row.get("terminal_state") == "open_gap_needs_repair" and not row.get("attempt_count")]
        ),
        "r15_1_open_gap_count": len([row for row in rows if row.get("r15_stage") == "r15_1" and row.get("terminal_state") == "open_gap_needs_repair"]),
        "r15_2_open_gap_count": len([row for row in rows if row.get("r15_stage") == "r15_2" and row.get("terminal_state") == "open_gap_needs_repair"]),
        "r15_3_open_gap_count": len([row for row in rows if row.get("r15_stage") == "r15_3" and row.get("terminal_state") == "open_gap_needs_repair"]),
        "r15_4_open_gap_count": len([row for row in rows if row.get("r15_stage") == "r15_4" and row.get("terminal_state") == "open_gap_needs_repair"]),
        "r15_1_pending_gap_count": len([row for row in pending_rows if row.get("r15_stage") == "r15_1"]),
        "r15_2_pending_gap_count": len([row for row in pending_rows if row.get("r15_stage") == "r15_2"]),
        "r15_3_pending_gap_count": len([row for row in pending_rows if row.get("r15_stage") == "r15_3"]),
        "r15_4_pending_gap_count": len([row for row in pending_rows if row.get("r15_stage") == "r15_4"]),
        "outputs": {"rows": str(output_rows), "report": str(output_report)},
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# R15 Public Source Gap Exhaustion",
        "",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- row_count: `{summary.get('row_count')}`",
        f"- source_role_row_count: `{summary.get('source_role_row_count')}`",
        f"- product_kpi_row_count: `{summary.get('product_kpi_row_count')}`",
        f"- open_gap_count: `{summary.get('open_gap_count')}`",
        f"- pending_gap_count: `{summary.get('pending_gap_count')}`",
        f"- source_role_open_gap_without_attempt_count: `{summary.get('source_role_open_gap_without_attempt_count')}`",
        "",
        "## By Stage",
        "",
        "| stage | count | open |",
        "| --- | ---: | ---: |",
    ]
    by_stage = dict(summary.get("by_stage") or {})
    open_by_stage = dict(summary.get("open_gap_by_stage") or {})
    for stage, count in sorted(by_stage.items()):
        pending_by_stage = dict(summary.get("pending_gap_by_stage") or {})
        lines.append(f"| `{stage}` | {count} | {pending_by_stage.get(stage, open_by_stage.get(stage, 0))} |")
    lines.extend(["", "## Terminal States", "", "| state | count |", "| --- | ---: |"])
    for state, count in sorted((summary.get("by_terminal_state") or {}).items()):
        lines.append(f"| `{state}` | {count} |")
    lines.extend(["", "## Open Gap Clusters", "", "| cluster | count |", "| --- | ---: |"])
    for cluster, count in sorted((summary.get("pending_gap_by_cluster") or {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{cluster}` | {count} |")
    lines.append("")
    return "\n".join(lines)


def _r15_stage(row: Mapping[str, Any]) -> str:
    docket_type = str(row.get("docket_type") or "")
    requirement_id = str(row.get("requirement_id") or "")
    cluster_id = str(row.get("cluster_id") or "")
    if docket_type == "source_role" or requirement_id in SOURCE_ROLE_REQUIREMENTS:
        return "r15_1"
    if cluster_id in PRODUCT_KPI_R15_2_CLUSTERS:
        return "r15_2"
    if cluster_id in PRODUCT_KPI_R15_3_CLUSTERS:
        return "r15_3"
    return "r15_4"


def _terminal_state(
    *,
    docket: Mapping[str, Any],
    exact_count: int,
    attempts: list[Mapping[str, Any]],
    attempt_count: int,
    product_diag: Mapping[str, Any],
    closeout: Mapping[str, Any],
) -> str:
    if exact_count:
        return "runtime_ready"
    manual_terminal = _manual_terminal_state_from_attempts(attempts)
    if manual_terminal:
        return manual_terminal
    closeout_class = str(closeout.get("closeout_class") or "")
    if closeout_class in {"public_source_exhausted_gap", "resolver_gap"}:
        return "final_public_boundary"
    if closeout_class == "not_applicable_or_source_gap":
        return "not_applicable"
    completion_state = str(docket.get("completion_state") or "")
    cluster_id = str(docket.get("cluster_id") or "")
    if completion_state in TERMINAL_COMPLETION_STATES:
        if cluster_id in PRODUCT_KPI_R15_3_CLUSTERS:
            return "rerouted"
        return "final_public_boundary"
    if cluster_id in PRODUCT_KPI_R15_3_CLUSTERS:
        return "rerouted"
    if str(docket.get("docket_type") or "") == "product_kpi" and product_diag:
        diag_class = str(product_diag.get("diagnostic_class") or "")
        if diag_class in {"ready_product_kpi_exact", "ready_business_segment_metric_only", "geographic_or_non_product_only"}:
            return "rerouted" if diag_class != "ready_product_kpi_exact" else "runtime_ready"
    if attempt_count:
        return "attempted_not_exhausted"
    return "open_gap_needs_repair"


def _manual_terminal_state_from_attempts(attempts: Iterable[Mapping[str, Any]]) -> str:
    allowed = {"final_public_boundary", "not_applicable"}
    for attempt in attempts:
        state = str(attempt.get("r15_terminal_state") or attempt.get("terminal_state") or "")
        if state in allowed:
            return state
    return ""


def _terminal_reason(
    docket: Mapping[str, Any],
    *,
    terminal_state: str,
    attempts: list[Mapping[str, Any]],
    closeout: Mapping[str, Any],
) -> str:
    if terminal_state == "runtime_ready":
        return "parser_backed_exact_row_exists_for_ticker_requirement"
    if terminal_state == "rerouted":
        return str(docket.get("next_action") or docket.get("completion_state") or "rerouted_to_typed_non_product_kpi_slot")
    if terminal_state == "final_public_boundary":
        manual_reason = _manual_terminal_reason_from_attempts(attempts)
        if manual_reason:
            return manual_reason
        if closeout:
            return str(closeout.get("closeout_reason") or closeout.get("closeout_class") or "attempt_backed_public_boundary")
        return str(docket.get("completion_state") or "attempt_backed_public_boundary")
    if terminal_state == "not_applicable":
        if closeout:
            return str(closeout.get("closeout_reason") or closeout.get("closeout_class") or "not_applicable")
        return "not_applicable"
    if terminal_state == "attempted_not_exhausted":
        statuses = Counter(str(row.get("attempt_status") or row.get("status") or "") for row in attempts)
        return "attempts_exist_but_cluster_not_terminal:" + ",".join(f"{key}={value}" for key, value in statuses.most_common(5))
    if terminal_state == "open_gap_needs_repair":
        return "no_runtime_row_and_no_attempt_backed_terminal_closeout"
    return "unclassified"


def _manual_terminal_reason_from_attempts(attempts: Iterable[Mapping[str, Any]]) -> str:
    for attempt in attempts:
        state = str(attempt.get("r15_terminal_state") or attempt.get("terminal_state") or "")
        if state in {"final_public_boundary", "not_applicable"}:
            return str(
                attempt.get("r15_terminal_reason")
                or attempt.get("reason")
                or attempt.get("failure_reason")
                or attempt.get("status")
                or state
            )
    return ""


def _stage_pass(summary: Mapping[str, Any], stage: str) -> bool:
    if stage == "all":
        return int(summary.get("pending_gap_count") or 0) == 0
    return int(summary.get(f"{stage}_pending_gap_count") or 0) == 0


def _index_exact_rows(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = _ticker(row)
        req = str(row.get("requirement_id") or "")
        if ticker and req:
            out[(ticker, req)].append(dict(row))
    return out


def _index_attempt_rows(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = _ticker(row)
        for req in _attempt_requirements(row):
            if ticker:
                out[(ticker, req)].append(dict(row))
    return out


def _index_closeout_rows(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        ticker = _ticker(row)
        req = str(row.get("requirement_id") or "")
        if ticker and req:
            out[(ticker, req)] = dict(row)
    return out


def _attempt_requirements(row: Mapping[str, Any]) -> set[str]:
    req = str(row.get("requirement_id") or "")
    if req:
        return {req}
    source_ids = {
        str(row.get(key) or "")
        for key in ("source_id", "source_role", "provider", "source_provider", "attempt_provider")
        if row.get(key)
    }
    out: set[str] = set()
    joined = " ".join(source_ids).lower()
    if "job" in joined or "workday" in joined or "greenhouse" in joined or "lever" in joined or "ashby" in joined:
        out.add("hiring_capacity_proxy")
    if "channel" in joined or "cdw" in joined or "mouser" in joined or "arrow" in joined or "official_channel" in joined:
        out.add("channel_offer_proxy")
    if "usaspending" in joined or "tender" in joined or "contract" in joined or "award" in joined:
        out.add("public_order_proxy")
    if "supply_chain" in joined or "supplier_customer" in joined:
        out.add("supply_chain_official_relationship")
    if "itunes" in joined or "app_store" in joined:
        out.update({"app_rank_store_proxy", "platform_review_proxy"})
    if "nhtsa" in joined:
        out.add("auto_product_identity_context")
    if "openalex" in joined or "patentsview" in joined:
        out.add("technology_research_proxy")
    if "github" in joined or "npm" in joined or "pypi" in joined or "huggingface" in joined or "developer" in joined:
        out.add("developer_ecosystem_proxy")
    if "product_kpi" in joined or "ir_deck" in joined or "annual_report" in joined or "column_group" in joined:
        out.add("product_kpi_exact_slot")
    return out


def _sample_attempt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": row.get("source_id") or row.get("provider") or row.get("attempt_provider") or "",
        "status": row.get("attempt_status") or row.get("status") or "",
        "url": row.get("source_url") or row.get("url") or row.get("api_url") or "",
        "reason": row.get("reason") or row.get("failure_reason") or row.get("message") or "",
    }


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


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").strip().upper()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
