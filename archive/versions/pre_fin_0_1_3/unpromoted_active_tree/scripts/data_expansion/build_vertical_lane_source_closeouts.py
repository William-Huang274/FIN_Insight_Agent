from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.vertical_source_lane_closeout import (  # noqa: E402
    build_lane_source_coverage_closeout,
    load_jsonl_rows,
    render_lane_source_coverage_closeout_report,
    write_lane_source_coverage_closeout,
)
from sec_agent.vertical_source_lane_package import lane_slug  # noqa: E402


DEFAULT_REGISTRY_PATH = Path("data/manifests/vertical_source_lane_registry_v0_1.json")
DEFAULT_SOURCE_CAPABILITY_PATH = Path("data/manifests/source_layer_capability_audit_v0_1.jsonl")
DEFAULT_MANIFESTS_DIR = Path("data/manifests")
DEFAULT_REPORT_DIR = Path("docs/internal/vnext_20260610/vertical_lanes")
DEFAULT_SUMMARY_PATH = Path("data/manifests/vertical_lane_source_closeouts_v0_1.json")
DEFAULT_SUMMARY_REPORT_PATH = Path("docs/internal/vnext_20260610/vertical_lanes/vertical_lane_source_closeouts_summary.zh-CN.md")
DEFAULT_OBSERVED_PATHS = (
    Path("data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"),
    Path("data/manifests/official_product_surface_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_official_api_context_rows_v0_1.jsonl"),
    Path("data/manifests/developer_ecosystem_context_rows_v0_1.jsonl"),
    Path("data/manifests/app_marketplace_context_rows_v0_1.jsonl"),
    Path("data/manifests/hiring_capacity_context_rows_v0_1.jsonl"),
    Path("data/manifests/public_contract_award_context_rows_v0_1.jsonl"),
    Path("data/manifests/channel_offer_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_trusted_external_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_openalex_technology_research_context_rows_v0_1.jsonl"),
    Path("data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl"),
    Path("data/manifests/vertical_lane_public_context_rows_v0_1.jsonl"),
)


def main() -> int:
    args = parse_args()
    registry = json.loads(args.registry_path.read_text(encoding="utf-8"))
    source_rows = load_jsonl_rows(args.source_capability_path)
    observed_rows: list[dict[str, Any]] = []
    for path in args.observed_paths:
        observed_rows.extend(load_jsonl_rows(path))
    selected = set(str(item).upper() for item in args.lane_id) if args.lane_id else None
    closeouts: list[dict[str, Any]] = []
    outputs: dict[str, dict[str, str]] = {}
    for lane in registry.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        lane_id = str(lane.get("lane_id") or "").upper()
        if selected and lane_id not in selected:
            continue
        payload = build_lane_source_coverage_closeout(
            lane_coverage=lane,
            source_layer_capability_rows=source_rows,
            observed_rows=observed_rows,
        )
        slug = lane_slug(lane)
        outputs[lane_id] = write_lane_source_coverage_closeout(
            payload,
            output_path=args.manifests_dir / f"{slug}_source_closeout_v0_1.json",
            report_path=args.report_dir / f"{slug}_source_closeout.zh-CN.md",
        )
        closeouts.append(payload)
    summary = _summary(closeouts=closeouts, outputs=outputs, observed_paths=args.observed_paths)
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.summary_report_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_report_path.write_text(_render_summary_report(summary, closeouts), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["validation"]["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source coverage closeouts for vertical lanes.")
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--source-capability-path", type=Path, default=DEFAULT_SOURCE_CAPABILITY_PATH)
    parser.add_argument("--observed-path", dest="observed_paths", action="append", type=Path)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--summary-report-path", type=Path, default=DEFAULT_SUMMARY_REPORT_PATH)
    parser.add_argument("--lane-id", action="append")
    args = parser.parse_args()
    if not args.observed_paths:
        args.observed_paths = list(DEFAULT_OBSERVED_PATHS)
    return args


def _summary(*, closeouts: list[dict[str, Any]], outputs: dict[str, dict[str, str]], observed_paths: list[Path]) -> dict[str, Any]:
    by_status = Counter(str(item.get("status") or "unknown") for item in closeouts)
    rows = []
    for item in closeouts:
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        rows.append(
            {
                "lane_id": item.get("lane_id"),
                "lane_name": item.get("lane_name"),
                "industry_schema": item.get("industry_schema"),
                "status": item.get("status"),
                "requirement_count": summary.get("requirement_count"),
                "pass_requirement_count": summary.get("pass_requirement_count"),
                "source_gap_requirement_count": summary.get("source_gap_requirement_count"),
                "commercial_gap_count": summary.get("commercial_gap_count"),
                "observed_runtime_row_count": summary.get("observed_runtime_row_count"),
                "observed_primary_ticker_count": summary.get("observed_primary_ticker_count"),
                "primary_ticker_count": summary.get("primary_ticker_count"),
                "by_closeout_status": summary.get("by_closeout_status"),
            }
        )
    validation_errors = [
        {"lane_id": item.get("lane_id"), **error}
        for item in closeouts
        for error in ((item.get("validation") or {}).get("errors") or [])
    ]
    return {
        "schema_version": "finsight_vertical_lane_source_closeout_summary_v0_1",
        "status": "fail" if any(item.get("status") == "fail" for item in closeouts) else "gap" if any(item.get("status") == "gap" for item in closeouts) else "pass",
        "lane_count": len(closeouts),
        "by_status": dict(sorted(by_status.items())),
        "lanes": rows,
        "observed_paths": [str(path) for path in observed_paths],
        "outputs": outputs,
        "validation": {
            "status": "fail" if validation_errors else "pass",
            "errors": validation_errors,
        },
    }


def _render_summary_report(summary: dict[str, Any], closeouts: list[dict[str, Any]]) -> str:
    lines = [
        "# Vertical Lane Source Closeouts Summary",
        "",
        f"- status: `{summary.get('status')}`",
        f"- validation: `{(summary.get('validation') or {}).get('status')}`",
        f"- lane_count: `{summary.get('lane_count')}`",
        "",
        "| lane | status | pass req | source gaps | commercial gaps | observed primary | observed rows |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.get("lanes") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.get('lane_id')}` {row.get('lane_name')}",
                    str(row.get("status") or ""),
                    str(row.get("pass_requirement_count") or 0),
                    str(row.get("source_gap_requirement_count") or 0),
                    str(row.get("commercial_gap_count") or 0),
                    f"{row.get('observed_primary_ticker_count')}/{row.get('primary_ticker_count')}",
                    str(row.get("observed_runtime_row_count") or 0),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Source Gap Ledger", ""])
    for payload in closeouts:
        gaps = [gap for gap in payload.get("source_gap_ledger") or [] if isinstance(gap, dict)]
        if not gaps:
            continue
        lines.append(f"### {payload.get('lane_id')} {payload.get('lane_name')}")
        lines.append("")
        for gap in gaps:
            lines.append(
                f"- `{gap.get('requirement_id')}`: `{gap.get('gap_type')}`; "
                f"primary={gap.get('primary_ticker_covered_count')}; "
                f"inclusive={gap.get('inclusive_ticker_covered_count')}; next={gap.get('next_action')}"
            )
        lines.append("")
    lines.extend(["## Boundary", "", "Closeout pass is requirement-level runtime availability. It does not mean every ticker or product in a lane has complete coverage.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
