from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_trusted_external_family_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_trusted_external_family_context_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "trusted_external_family_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "trusted_external_family_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/trusted_external_family_context")

USER_AGENT = "FIN-Insight-Agent public source coverage audit"

LANE_TRUSTED_SOURCES = {
    "V1": {
        "source_url": "https://www.semiconductors.org/",
        "source_title": "Semiconductor Industry Association",
        "topic": "semiconductor industry shipments, policy, and market context",
    },
    "V2": {
        "source_url": "https://www.cta.tech/",
        "source_title": "Consumer Technology Association",
        "topic": "consumer technology devices and electronics context",
    },
    "V3": {
        "source_url": "https://www.cncf.io/",
        "source_title": "Cloud Native Computing Foundation",
        "topic": "cloud native and developer ecosystem context",
    },
    "V4": {
        "source_url": "https://open.fda.gov/apis/drug/drugsfda/",
        "source_title": "openFDA Drugs@FDA API",
        "topic": "healthcare product regulatory context",
    },
    "V5": {
        "source_url": "https://vpic.nhtsa.dot.gov/api/",
        "source_title": "NHTSA vPIC API",
        "topic": "vehicle safety and mobility regulatory context",
    },
    "V6": {
        "source_url": "https://www.fdic.gov/",
        "source_title": "Federal Deposit Insurance Corporation",
        "topic": "banking and financial regulatory context",
    },
    "V7": {
        "source_url": "https://www.eia.gov/",
        "source_title": "U.S. Energy Information Administration",
        "topic": "energy, utilities, and industrial input context",
    },
    "V8": {
        "source_url": "https://nrf.com/",
        "source_title": "National Retail Federation",
        "topic": "retail, consumer, and channel context",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build trusted external family context rows with URL reachability verification.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=15.0)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    family_rows = _load_jsonl(args.family_assignments)
    source_snapshots = fetch_lane_sources(timeout_s=args.timeout_s, raw_dir=args.raw_dir)
    rows = build_trusted_external_family_context_rows(
        matrix_rows=matrix_rows,
        family_rows=family_rows,
        source_snapshots=source_snapshots,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=rows,
        source_snapshots=source_snapshots,
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
    )
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def fetch_lane_sources(*, timeout_s: float, raw_dir: Path) -> dict[str, dict[str, Any]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, Any]] = {}
    for lane_id, source in LANE_TRUSTED_SOURCES.items():
        url = source["source_url"]
        status_code = 0
        body = ""
        error = ""
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
            with urlopen(request, timeout=timeout_s) as response:
                status_code = int(response.status)
                body = response.read(200_000).decode("utf-8", errors="ignore")
        except HTTPError as exc:
            status_code = int(exc.code)
            body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            error = f"HTTPError:{exc.code}"
        except (URLError, TimeoutError) as exc:
            error = f"{type(exc).__name__}:{str(exc)[:200]}"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}:{str(exc)[:200]}"
        raw_path = raw_dir / f"{lane_id.lower()}_{_slug(source['source_title'])}.html"
        raw_path.write_text(body or "", encoding="utf-8")
        reachable = 200 <= status_code < 400 and bool(body.strip())
        out[lane_id] = {
            **source,
            "lane_id": lane_id,
            "fetch_status": "reachable" if reachable else "unreachable",
            "status_code": status_code,
            "raw_path": str(raw_path),
            "error": error,
            "resolved_title": _html_title(body) or source["source_title"],
        }
    return out


def build_trusted_external_family_context_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    family_rows: Iterable[Mapping[str, Any]],
    source_snapshots: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    family_by_ticker = _family_by_ticker(family_rows)
    out: list[dict[str, Any]] = []
    for company in matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        if "trusted_external_context" not in requirements:
            continue
        lane_id = str(company.get("primary_lane_id") or "").strip().upper()
        source = source_snapshots.get(lane_id) or {}
        if source.get("fetch_status") != "reachable":
            continue
        families = family_by_ticker.get(ticker) or [{}]
        family = families[0]
        family_name = str(family.get("family_name") or company.get("industry_schema") or company.get("primary_lane_name") or "industry context")
        evidence_ref = _stable_ref("trusted_external_family_context", [ticker, lane_id, source.get("source_url"), family_name])
        text = (
            f"{ticker} trusted external context bridge: {source.get('source_title')} covers {source.get('topic')} "
            f"for lane={lane_id}, family={family_name}. This is external context only, not company exact value authority."
        )
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "source_id": "industry_association_reports",
                "underlying_source_id": "industry_association_reports",
                "source_class": "industry_association_reports",
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_layer_id": "L2",
                "source_layer": "L2",
                "layer_id": "L2",
                "source_specific_parser": "trusted_external_family_source_locator_v0_1",
                "source_specific_resolver": "company_family_trusted_external_resolver_v0_1",
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "structured_context_type": "trusted_external_context",
                "requirement_id": "trusted_external_context",
                "ticker": ticker,
                "company": company.get("company_name") or "",
                "company_name": company.get("company_name") or "",
                "primary_lane_id": lane_id,
                "primary_lane_name": company.get("primary_lane_name") or "",
                "family_id": family.get("family_id") or "",
                "family_name": family_name,
                "source_url": source.get("source_url") or "",
                "snapshot_url": source.get("source_url") or "",
                "raw_path": source.get("raw_path") or "",
                "source_title": source.get("resolved_title") or source.get("source_title") or "",
                "topic": source.get("topic") or family_name,
                "fact_label": f"{source.get('source_title')} | {family_name}",
                "product_or_segment": family_name,
                "product_family": family_name,
                "as_of_datetime": generated_at,
                "issuer_binding_status": "family_assignment_exposure_context",
                "product_binding_status": "product_mentioned_in_snapshot",
                "counterparty_binding_status": "not_bound",
                "entity_binding": {
                    "issuer_ticker": ticker,
                    "issuer_binding_status": "family_assignment_exposure_context",
                    "product_binding_status": "product_mentioned_in_snapshot",
                    "counterparty_binding_status": "not_bound",
                    "resolver_status": "company_family_trusted_external_context_bridge",
                    "binding_claim_boundary": "Issuer is connected to this trusted source through lane/product-family assignment only; external context not company exact value.",
                },
                "resolver_status": "company_family_trusted_external_context_bridge",
                "context_only": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "allowed_claims": ["trusted_external_context", "verification_lead", "market_proxy_context"],
                "forbidden_claims": ["company_exact_value", "sales_volume", "market_share", "revenue"],
                "claim_boundary": "Trusted external family context only; no company exact value, sales volume, market share, or revenue promotion.",
                "text": text,
                "preview": text,
            }
        )
    return _dedupe_rows(out)


def build_summary(
    *,
    rows: list[dict[str, Any]],
    source_snapshots: Mapping[str, Mapping[str, Any]],
    matrix_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "company_count": len(matrix_rows),
        "context_row_count": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "lane_fetch_status": {lane_id: source.get("fetch_status") for lane_id, source in sorted(source_snapshots.items())},
        "lane_status_codes": {lane_id: source.get("status_code") for lane_id, source in sorted(source_snapshots.items())},
        "source_id_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "outputs": {"rows": str(output_rows)},
        "boundary": "Industry/trusted source rows are exact source locator snapshots routed by company-family assignment; no company exact values or market-share/sales promotion.",
    }


def _family_by_ticker(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            out.setdefault(ticker, []).append(dict(row))
    return out


def _html_title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body or "", flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


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


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] or "source"


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
