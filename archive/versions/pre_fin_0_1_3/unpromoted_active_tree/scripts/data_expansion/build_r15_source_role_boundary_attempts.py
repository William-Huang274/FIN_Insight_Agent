from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_r15_source_role_boundary_attempt_v0_1"

DEFAULT_R15_LEDGER = REPO_ROOT / "data" / "manifests" / "r15_public_source_gap_exhaustion_ledger_v0_1.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "r15_manual_public_source_attempts_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "r15_manual_public_source_attempts_summary_v0_1.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "r15_source_role_boundary_attempts.zh-CN.md"

PUBLIC_ORDER_PORTALS = {
    "CCJ": ("local_public_tender", "https://canadabuys.canada.ca/en/tender-opportunities"),
    "CRDO": ("local_public_tender", "https://sam.gov/search/"),
    "CSIQ": ("local_public_tender", "https://canadabuys.canada.ca/en/tender-opportunities"),
    "DNN": ("local_public_tender", "https://canadabuys.canada.ca/en/tender-opportunities"),
    "DQ": ("local_public_tender", "https://www.ccgp.gov.cn/"),
    "ENLT": ("local_public_tender", "https://www.gov.il/en/departments/general/central_tender"),
    "JKS": ("local_public_tender", "https://www.ccgp.gov.cn/"),
    "UROY": ("local_public_tender", "https://canadabuys.canada.ca/en/tender-opportunities"),
}

PATENTSVIEW_DOC_URL = "https://search.patentsview.org/docs/docs/Search%20API/SearchAPIReference/"
USPTO_ODP_URL = "https://data.uspto.gov/apis/getting-started"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R15 terminal boundary attempt rows for source-role gaps.")
    parser.add_argument("--r15-ledger", type=Path, default=DEFAULT_R15_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout-s", type=float, default=8.0)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    ledger_rows = _load_jsonl(args.r15_ledger)
    out = build_rows(ledger_rows=ledger_rows, generated_at=generated_at, timeout_s=args.timeout_s, skip_fetch=args.skip_fetch)
    summary = build_summary(out, generated_at=generated_at, output=args.output, report=args.report)
    _write_jsonl(args.output, out)
    _write_json(args.summary, summary)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["pending_without_boundary_count"]:
        return 1
    return 0


def build_rows(*, ledger_rows: Iterable[Mapping[str, Any]], generated_at: str, timeout_s: float, skip_fetch: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    patentsview_key_present = _has_patentsview_key()
    for row in ledger_rows:
        if row.get("r15_stage") != "r15_1":
            continue
        ticker = str(row.get("ticker") or "").upper()
        requirement_id = str(row.get("requirement_id") or "")
        closeout_reason = str(row.get("closeout_reason") or "")
        if requirement_id == "public_order_proxy" and ticker in PUBLIC_ORDER_PORTALS:
            provider, source_url = PUBLIC_ORDER_PORTALS[ticker]
            fetch_status = "not_fetched"
            http_status = None
            if not skip_fetch:
                fetch_status, http_status = _fetch_status(source_url, timeout_s=timeout_s)
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "requirement_id": requirement_id,
                    "provider": provider,
                    "source_id": "public_tenders_contracts_orders",
                    "source_url": source_url,
                    "status": "no_supplier_bound_award_or_no_structured_award_endpoint",
                    "fetch_status": fetch_status,
                    "http_status": http_status,
                    "r15_terminal_state": "final_public_boundary",
                    "r15_terminal_reason": (
                        "jurisdiction_public_tender_or_contract_portal_checked_after_usaspending; "
                        "no stable supplier/recipient-bound award row with award id, amount, date, and agency was available"
                    ),
                    "boundary": (
                        "Public-order proxy can only support a specific award snapshot when an official portal exposes "
                        "recipient/supplier-bound structured rows; it cannot prove orders, backlog, demand, sales, or share."
                    ),
                    "input_closeout_reason": closeout_reason,
                }
            )
            continue
        if requirement_id == "technology_research_proxy" and "patentsview_api_key_missing" in closeout_reason:
            if patentsview_key_present:
                status = "credential_available_rerun_patentsview_required"
                terminal_state = ""
                terminal_reason = "PatentsView key appears configured; rerun PatentsView adapter instead of closing gap."
            else:
                status = "public_api_key_required_not_configured"
                terminal_state = "final_public_boundary"
                terminal_reason = (
                    "OpenAlex returned no issuer/topic-bound research proxy and PatentsView PatentSearch requires an API key "
                    "that is not configured in the current runtime; no URL-only or keyword-only patent row is promoted."
                )
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "requirement_id": requirement_id,
                    "provider": "patentsview",
                    "source_id": "patentsview_api",
                    "source_url": PATENTSVIEW_DOC_URL,
                    "secondary_source_url": USPTO_ODP_URL,
                    "status": status,
                    "r15_terminal_state": terminal_state,
                    "r15_terminal_reason": terminal_reason,
                    "boundary": (
                        "Technology research proxy remains bounded to issuer/topic or assignee/topic rows. "
                        "It cannot support product sales, launch, share, demand, or durable moat claims."
                    ),
                    "input_closeout_reason": closeout_reason,
                }
            )
    return rows


def build_summary(rows: list[Mapping[str, Any]], *, generated_at: str, output: Path, report: Path) -> dict[str, Any]:
    terminal_rows = [row for row in rows if row.get("r15_terminal_state") in {"final_public_boundary", "not_applicable"}]
    pending_without_boundary = [row for row in rows if not row.get("r15_terminal_state")]
    return {
        "schema_version": "finsight_r15_source_role_boundary_attempt_summary_v0_1",
        "generated_at": generated_at,
        "row_count": len(rows),
        "terminal_boundary_row_count": len(terminal_rows),
        "pending_without_boundary_count": len(pending_without_boundary),
        "by_requirement": _counter_dict(row.get("requirement_id") for row in rows),
        "by_status": _counter_dict(row.get("status") for row in rows),
        "outputs": {"rows": str(output), "report": str(report)},
        "status": "pass" if rows and not pending_without_boundary else "gap",
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# R15 Source-Role Boundary Attempts",
        "",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- row_count: `{summary.get('row_count')}`",
        f"- terminal_boundary_row_count: `{summary.get('terminal_boundary_row_count')}`",
        f"- pending_without_boundary_count: `{summary.get('pending_without_boundary_count')}`",
        "",
        "## By Requirement",
        "",
        "| requirement | count |",
        "| --- | ---: |",
    ]
    for key, value in sorted((summary.get("by_requirement") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## By Status", "", "| status | count |", "| --- | ---: |"])
    for key, value in sorted((summary.get("by_status") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.append("")
    return "\n".join(lines)


def _fetch_status(url: str, *, timeout_s: float) -> tuple[str, int | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "FIN-Insight-Agent/0.1 source-boundary-audit"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return "fetched", int(response.status)
    except urllib.error.HTTPError as exc:
        return "http_error", int(exc.code)
    except Exception as exc:  # noqa: BLE001 - status is diagnostic, not control flow.
        return f"fetch_failed:{type(exc).__name__}", None


def _has_patentsview_key() -> bool:
    for key in ("PATENTSVIEW_API_KEY", "USPTO_PATENTSVIEW_API_KEY"):
        if os.environ.get(key):
            return True
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        if key.strip() in {"PATENTSVIEW_API_KEY", "USPTO_PATENTSVIEW_API_KEY"} and value.strip():
            return True
    return False


def _counter_dict(values: Iterable[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value or "")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


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
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
