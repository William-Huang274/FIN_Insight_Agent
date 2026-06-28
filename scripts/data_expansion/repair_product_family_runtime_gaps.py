from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_official_product_surface_context_rows import build_official_product_surface_context_rows  # noqa: E402
from build_product_slot_relationship_graph import DEFAULT_PUBLIC_CONTEXT_ROW_FILES  # noqa: E402
from materialize_family_official_product_surface_pages import (  # noqa: E402
    DEFAULT_CLEAN_DIR,
    DEFAULT_DOMAIN_CACHE,
    DEFAULT_RAW_DIR,
    build_family_product_surface_profiles,
)
from materialize_official_product_surface_pages import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_MATERIALIZED_OUTPUT,
    HttpThenBrowserFetcher,
    PlaywrightBrowserFetcher,
    materialize_official_product_surface_pages,
)
from sec_agent.product_family_gap_repair import build_product_family_gap_repair_ledger  # noqa: E402
from sec_agent.product_family_source_routes import load_jsonl_rows  # noqa: E402
from sec_agent.product_slot_relationship_graph import (  # noqa: E402
    build_company_product_slots,
    build_product_relationship_graph,
    write_product_relationship_artifacts,
)


DEFAULT_CLOSEOUT_ROWS = REPO_ROOT / "data/manifests/product_family_runtime_gap_closeout_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data/manifests/company_product_family_assignments_v0_1.jsonl"
DEFAULT_FAMILY_ROUTE_PLAN = REPO_ROOT / "data/manifests/family_source_route_plan_v0_1.jsonl"
DEFAULT_PRODUCT_RUNTIME_ROWS = REPO_ROOT / "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl"
DEFAULT_PRODUCT_SLOTS = REPO_ROOT / "data/manifests/company_product_slots_v0_1.jsonl"
DEFAULT_CONTEXT_ROWS = REPO_ROOT / "data/manifests/official_product_surface_context_rows_v0_1.jsonl"
DEFAULT_CONTEXT_SUMMARY = REPO_ROOT / "data/manifests/official_product_surface_context_rows_summary_v0_1.json"
DEFAULT_OUTPUT_NODES = REPO_ROOT / "data/manifests/product_relationship_graph_nodes_v0_1.jsonl"
DEFAULT_OUTPUT_EDGES = REPO_ROOT / "data/manifests/product_relationship_graph_edges_v0_1.jsonl"
DEFAULT_OUTPUT_GRAPH_SUMMARY = REPO_ROOT / "data/manifests/product_relationship_graph_summary_v0_1.json"
DEFAULT_OUTPUT_GRAPH_REPORT = REPO_ROOT / "docs/internal/vnext_20260610/vertical_lanes/product_slot_relationship_graph.zh-CN.md"
DEFAULT_REPAIR_LEDGER = REPO_ROOT / "data/manifests/product_family_runtime_gap_repair_ledger_v0_1.jsonl"
DEFAULT_REPAIR_SUMMARY = REPO_ROOT / "data/manifests/product_family_runtime_gap_repair_summary_v0_1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run audited repair ladder for product-family runtime gap closeout rows.")
    parser.add_argument("--closeout-rows", type=Path, default=DEFAULT_CLOSEOUT_ROWS)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--family-route-plan", type=Path, default=DEFAULT_FAMILY_ROUTE_PLAN)
    parser.add_argument("--product-runtime-rows", type=Path, default=DEFAULT_PRODUCT_RUNTIME_ROWS)
    parser.add_argument("--before-product-slots", type=Path, default=DEFAULT_PRODUCT_SLOTS)
    parser.add_argument("--existing-materialized", type=Path, default=DEFAULT_MATERIALIZED_OUTPUT)
    parser.add_argument("--output-materialized", type=Path, default=DEFAULT_MATERIALIZED_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE)
    parser.add_argument("--output-context-rows", type=Path, default=DEFAULT_CONTEXT_ROWS)
    parser.add_argument("--output-context-summary", type=Path, default=DEFAULT_CONTEXT_SUMMARY)
    parser.add_argument("--output-slots", type=Path, default=DEFAULT_PRODUCT_SLOTS)
    parser.add_argument("--output-nodes", type=Path, default=DEFAULT_OUTPUT_NODES)
    parser.add_argument("--output-edges", type=Path, default=DEFAULT_OUTPUT_EDGES)
    parser.add_argument("--output-graph-summary", type=Path, default=DEFAULT_OUTPUT_GRAPH_SUMMARY)
    parser.add_argument("--output-graph-report", type=Path, default=DEFAULT_OUTPUT_GRAPH_REPORT)
    parser.add_argument("--output-repair-ledger", type=Path, default=DEFAULT_REPAIR_LEDGER)
    parser.add_argument("--output-repair-summary", type=Path, default=DEFAULT_REPAIR_SUMMARY)
    parser.add_argument("--public-context-row-file", action="append", type=Path, default=[])
    parser.add_argument("--no-default-public-context", action="store_true")
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--max-urls-per-issuer", type=int, default=8)
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--min-clean-text-chars", type=int, default=250)
    parser.add_argument("--fetch-mode", choices=["http_only", "browser_only", "http_then_browser"], default="http_then_browser")
    parser.add_argument("--browser-executable", type=Path, default=None)
    parser.add_argument("--allow-final-closeout", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build profiles and ledger without writing runtime rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    closeout_rows = _filter_closeout_rows(load_jsonl_rows(args.closeout_rows), args.tickers)
    before_slots = load_jsonl_rows(args.before_product_slots)
    existing_materialized = load_jsonl_rows(args.existing_materialized)
    domain_cache = _load_json(args.domain_cache)
    profiles, resolver_report = build_family_product_surface_profiles(
        slots=_slots_for_closeout(before_slots, closeout_rows),
        existing_rows=existing_materialized,
        domain_cache=domain_cache,
        ticker_filter={_ticker(row) for row in closeout_rows},
        max_targets=0,
        resolver_workers=1,
    )
    args.domain_cache.parent.mkdir(parents=True, exist_ok=True)
    args.domain_cache.write_text(json.dumps(domain_cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    materialized_result = {"rows": existing_materialized, "summary": {"attempts": [], "new_materialized_count": 0, "updated_materialized_count": 0}}
    if profiles and not args.dry_run:
        fetcher = _make_fetcher(args)
        if hasattr(fetcher, "__enter__"):
            with fetcher as active_fetcher:
                materialized_result = _materialize(args=args, profiles=profiles, existing_materialized=existing_materialized, generated_at=generated_at, fetch=active_fetcher)
        else:
            materialized_result = _materialize(args=args, profiles=profiles, existing_materialized=existing_materialized, generated_at=generated_at, fetch=fetcher)
        _write_jsonl(args.output_materialized, materialized_result["rows"])

    context_rows = build_official_product_surface_context_rows(
        materialized_result["rows"],
        generated_at=generated_at,
        max_rows_per_page=12,
    )
    if not args.dry_run:
        _write_jsonl(args.output_context_rows, context_rows)
        _write_json(
            args.output_context_summary,
            {
                "schema_version": "finsight_product_family_gap_repair_context_summary_v0_1",
                "generated_at": generated_at,
                "context_row_count": len(context_rows),
                "ticker_count": len({_ticker(row) for row in context_rows if _ticker(row)}),
                "tickers": sorted({_ticker(row) for row in context_rows if _ticker(row)}),
                "boundary": "Official product pages remain bounded context only; no sales/share/ASP/inventory/sell-through authority.",
            },
        )

    after_slots, graph = _rebuild_product_graph(args=args, context_rows=context_rows, generated_at=generated_at)
    if not args.dry_run:
        write_product_relationship_artifacts(
            product_slots=graph["slots"],
            nodes=graph["nodes"],
            edges=graph["edges"],
            summary=graph["summary"],
            output_slots_path=args.output_slots,
            output_nodes_path=args.output_nodes,
            output_edges_path=args.output_edges,
            output_summary_path=args.output_graph_summary,
            output_report_path=args.output_graph_report,
        )

    ledger = build_product_family_gap_repair_ledger(
        closeout_rows=closeout_rows,
        before_slots=before_slots,
        after_slots=after_slots,
        materialization_attempts=materialized_result.get("summary", {}).get("attempts") or [],
        context_rows=context_rows,
        generated_at=generated_at,
        allow_final_closeout=bool(args.allow_final_closeout),
    )
    ledger["summary"]["resolver_report"] = resolver_report
    ledger["summary"]["materialization_summary"] = _redact_attempt_urls(dict(materialized_result.get("summary") or {}))
    ledger["summary"]["product_graph_summary"] = graph["summary"]
    ledger["summary"]["outputs"] = {
        "repair_ledger": str(args.output_repair_ledger),
        "repair_summary": str(args.output_repair_summary),
        "materialized_rows": str(args.output_materialized),
        "context_rows": str(args.output_context_rows),
        "product_slots": str(args.output_slots),
        "product_graph_summary": str(args.output_graph_summary),
    }
    if not args.dry_run:
        _write_jsonl(args.output_repair_ledger, ledger["rows"])
        _write_json(args.output_repair_summary, ledger["summary"])
    print(json.dumps(ledger["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _materialize(
    *,
    args: argparse.Namespace,
    profiles: Mapping[str, Mapping[str, Any]],
    existing_materialized: list[Mapping[str, Any]],
    generated_at: str,
    fetch: Any,
) -> dict[str, Any]:
    return materialize_official_product_surface_pages(
        profiles=profiles,
        existing_rows=existing_materialized,
        raw_dir=args.raw_dir,
        clean_dir=args.clean_dir,
        generated_at=generated_at,
        max_urls_per_issuer=args.max_urls_per_issuer,
        timeout_s=args.timeout_s,
        min_clean_text_chars=args.min_clean_text_chars,
        skip_existing=False,
        prune_unusable_existing=False,
        fetch=fetch,
    )


def _make_fetcher(args: argparse.Namespace) -> Any:
    if args.fetch_mode == "http_only":
        return None
    browser = PlaywrightBrowserFetcher(executable_path=args.browser_executable)
    if args.fetch_mode == "browser_only":
        return browser
    return HttpThenBrowserFetcher(browser, min_clean_text_chars=args.min_clean_text_chars)


def _rebuild_product_graph(*, args: argparse.Namespace, context_rows: list[Mapping[str, Any]], generated_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    family_assignments = load_jsonl_rows(args.family_assignments)
    route_plan = load_jsonl_rows(args.family_route_plan)
    product_runtime_rows = load_jsonl_rows(args.product_runtime_rows)
    context_paths = [] if args.no_default_public_context else list(DEFAULT_PUBLIC_CONTEXT_ROW_FILES)
    context_paths.extend(args.public_context_row_file)
    public_context_rows: list[dict[str, Any]] = []
    for path in context_paths:
        if Path(path) == args.output_context_rows:
            continue
        public_context_rows.extend(load_jsonl_rows(path))
    public_context_rows.extend(dict(row) for row in context_rows)
    slots = build_company_product_slots(
        family_assignments=family_assignments,
        route_plan_rows=route_plan,
        product_runtime_rows=product_runtime_rows,
        public_context_rows=public_context_rows,
        generated_at=generated_at,
    )
    graph = build_product_relationship_graph(product_slots=slots, route_plan_rows=route_plan, generated_at=generated_at)
    return slots, graph


def _slots_for_closeout(slots: list[Mapping[str, Any]], closeout_rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    keys = {(_ticker(row), str(row.get("family_id") or "")) for row in closeout_rows}
    return [row for row in slots if (_ticker(row), str(row.get("family_id") or "")) in keys]


def _filter_closeout_rows(rows: list[Mapping[str, Any]], tickers: Iterable[str]) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = _ticker(row)
        if ticker_filter and ticker not in ticker_filter:
            continue
        out.append(dict(row))
    return out


def _redact_attempt_urls(summary: dict[str, Any]) -> dict[str, Any]:
    attempts = summary.get("attempts")
    if isinstance(attempts, list) and len(attempts) > 30:
        summary["attempts"] = attempts[:30]
        summary["attempts_truncated"] = len(attempts) - 30
    return summary


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").strip().upper()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
