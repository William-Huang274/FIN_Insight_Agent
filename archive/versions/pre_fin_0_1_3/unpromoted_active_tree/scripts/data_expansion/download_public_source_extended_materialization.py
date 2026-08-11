from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_extended_materialization_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_source_extended_materialization_summary_v0.1"
DEFAULT_RAW_ROOT = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization")
DEFAULT_PROCESSED_ROOT = Path("Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization")
DEFAULT_MANIFEST_OUTPUT = REPO_ROOT / "data" / "manifests" / "public_source_extended_materialization_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "data" / "manifests" / "public_source_extended_materialization_summary_v0_1.json"
DEFAULT_PRODUCT_METRIC_CANDIDATES = REPO_ROOT / "data" / "manifests" / "company_product_operating_metric_candidates_v0_1.jsonl"
DEFAULT_CHUNK_INPUTS = [
    REPO_ROOT / "data" / "staging" / "sec_tier1_sp500_annual" / "chunks" / "tier1_sp500_us_annual_10k_chunks_fy2023_2025_v0_1.jsonl",
    REPO_ROOT / "data" / "staging" / "sec_tier2_supply_chain_annual" / "chunks" / "tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl",
]
DEFAULT_USER_AGENT = "FinSight-Agent/0.1 public-source-materializer contact@example.com"
PRODUCT_PAGE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 FinSight-Agent/0.1"

SEC_BULK_PROFILES = {
    "sec_financial_statement_data_sets": {
        "provider": "SEC",
        "landing_url": "https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets",
        "preferred_label_pattern": r"2026\s+Q1",
        "artifact_type": "sec_bulk_financial_statement_zip",
    },
    "sec_ownership_and_13f": {
        "provider": "SEC",
        "landing_url": "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets",
        "preferred_label_pattern": r"2026\s+March\s+April\s+May\s+13F",
        "artifact_type": "sec_bulk_13f_zip",
    },
}

PRODUCT_PAGE_PROFILES = [
    {
        "ticker": "AAPL",
        "company": "Apple Inc.",
        "product": "iPhone",
        "url": "https://www.apple.com/iphone/",
    },
    {
        "ticker": "NVDA",
        "company": "NVIDIA Corporation",
        "product": "Blackwell GPU architecture",
        "url": "https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/",
    },
    {
        "ticker": "AMD",
        "company": "Advanced Micro Devices, Inc.",
        "product": "Ryzen desktop processors",
        "url": "https://www.amd.com/en/products/processors/desktops/ryzen.html",
    },
]

PRODUCT_METRIC_PATTERNS = {
    "product_revenue": [
        r"\bproduct revenue\b",
        r"\bnet sales\b",
        r"\brevenue by product\b",
        r"\brevenue by segment\b",
        r"\bfranchise revenue\b",
    ],
    "unit_sales_or_deliveries": [r"\bunit sales\b", r"\bunits sold\b", r"\bdeliveries\b", r"\bdelivered\b"],
    "shipments": [r"\bshipments\b", r"\bshipped\b"],
    "backlog_or_orders": [r"\bbacklog\b", r"\border(s)?\b", r"\bbookings\b", r"\brpo\b", r"\bremaining performance obligations\b"],
    "subscribers_or_arpu": [r"\bsubscribers\b", r"\bpaid subscribers\b", r"\barpu\b", r"\baverage revenue per user\b"],
    "same_store_sales": [r"\bsame-store sales\b", r"\bcomparable sales\b", r"\bcomparable store sales\b"],
    "production_or_throughput": [r"\bproduction\b", r"\bthroughput\b", r"\bproduced\b"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize additional public-source assets outside the core disclosure pipeline.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--processed-root", type=Path, default=DEFAULT_PROCESSED_ROOT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--product-metric-candidates-output", type=Path, default=DEFAULT_PRODUCT_METRIC_CANDIDATES)
    parser.add_argument("--source-id-filter", default="", help="Comma-separated source ids to materialize.")
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--max-product-metric-candidates", type=int, default=300)
    parser.add_argument("--max-product-metric-candidates-per-family", type=int, default=60)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = set(_split_csv(args.source_id_filter))
    generated_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for source_id, profile in SEC_BULK_PROFILES.items():
        if selected and source_id not in selected:
            continue
        try:
            rows.append(materialize_sec_bulk_zip(source_id, profile, args.raw_root, args.processed_root, args.timeout_s, args.skip_existing, generated_at))
        except Exception as exc:  # noqa: BLE001
            failures.append(_failure_row(source_id, str(exc)))

    if not selected or "company_product_pages" in selected:
        try:
            rows.append(materialize_company_product_pages(args.raw_root, args.processed_root, args.timeout_s, generated_at))
        except Exception as exc:  # noqa: BLE001
            failures.append(_failure_row("company_product_pages", str(exc)))

    if not selected or "company_reported_product_operating_metrics" in selected:
        try:
            candidate_rows = extract_product_metric_candidates(
                DEFAULT_CHUNK_INPUTS,
                max_candidates=args.max_product_metric_candidates,
                max_per_family=args.max_product_metric_candidates_per_family,
                generated_at=generated_at,
            )
            _write_jsonl(_resolve(args.product_metric_candidates_output), candidate_rows)
            rows.append(product_metric_materialization_row(candidate_rows, args.product_metric_candidates_output, generated_at))
        except Exception as exc:  # noqa: BLE001
            failures.append(_failure_row("company_reported_product_operating_metrics", str(exc)))

    manifest_output = _resolve(args.manifest_output)
    summary_output = _resolve(args.summary_output)
    _write_jsonl(manifest_output, rows)
    summary = build_summary(rows, failures, manifest_output, summary_output, args.product_metric_candidates_output, generated_at)
    _write_json(summary_output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 2


def materialize_sec_bulk_zip(
    source_id: str,
    profile: dict[str, Any],
    raw_root: Path,
    processed_root: Path,
    timeout_s: float,
    skip_existing: bool,
    generated_at: str,
) -> dict[str, Any]:
    landing_url = str(profile["landing_url"])
    html_text = _http_get_text(landing_url, timeout_s)
    link = find_zip_link(html_text, landing_url, str(profile.get("preferred_label_pattern") or ""))
    raw_dir = raw_root / source_id
    processed_dir = processed_root / source_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    zip_name = Path(link["url"].split("?")[0]).name or f"{source_id}.zip"
    raw_zip = raw_dir / zip_name
    if not skip_existing or not raw_zip.exists():
        _download_binary(link["url"], raw_zip, timeout_s)
    zip_summary = inspect_zip(raw_zip)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "provider": profile["provider"],
        "artifact_type": profile["artifact_type"],
        "generated_at": generated_at,
        "landing_url": landing_url,
        "download_url": link["url"],
        "download_label": link["label"],
        "raw_zip_path": _path_str(raw_zip),
        **zip_summary,
    }
    metadata_path = processed_dir / f"{raw_zip.stem}.metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "status": "materialized",
        "provider": profile["provider"],
        "artifact_type": profile["artifact_type"],
        "materialization_channel": "public_bulk_zip",
        "generated_at": generated_at,
        "landing_url": landing_url,
        "download_url": link["url"],
        "download_label": link["label"],
        "raw_path": _path_str(raw_zip),
        "processed_metadata_path": _path_str(metadata_path),
        "downloaded_bytes": zip_summary["downloaded_bytes"],
        "sha256": zip_summary["sha256"],
        "zip_member_count": zip_summary["zip_member_count"],
        "table_count": len(zip_summary["tables"]),
        "record_count": sum(int(table.get("data_row_count") or 0) for table in zip_summary["tables"]),
        "runtime_promotion_status": "staging_only_parser_or_parity_gate_pending",
    }


def find_zip_link(html_text: str, landing_url: str, preferred_label_pattern: str = "") -> dict[str, str]:
    anchors: list[dict[str, str]] = []
    for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html_text, flags=re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1))
        label = _strip_html(match.group(2))
        if ".zip" not in href.lower():
            continue
        anchors.append({"url": urljoin(landing_url, href), "label": re.sub(r"\s+", " ", label).strip()})
    if not anchors:
        raise RuntimeError(f"No ZIP links found on {landing_url}")
    if preferred_label_pattern:
        pattern = re.compile(preferred_label_pattern, flags=re.IGNORECASE)
        for anchor in anchors:
            if pattern.search(anchor["label"]):
                return anchor
    return anchors[0]


def inspect_zip(path: Path) -> dict[str, Any]:
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
    tables: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        for member in members:
            if not member.filename.lower().endswith((".tsv", ".txt", ".csv")):
                continue
            line_count = 0
            header = ""
            with archive.open(member, "r") as zipped:
                for raw in zipped:
                    line_count += 1
                    if line_count == 1:
                        header = raw[:4000].decode("utf-8", errors="replace").strip()
            tables.append(
                {
                    "member_name": member.filename,
                    "compressed_size": member.compress_size,
                    "uncompressed_size": member.file_size,
                    "line_count": line_count,
                    "data_row_count": max(line_count - 1, 0),
                    "header": header,
                }
            )
    return {
        "downloaded_bytes": path.stat().st_size,
        "sha256": sha256.hexdigest(),
        "zip_member_count": len(members),
        "tables": tables,
    }


def materialize_company_product_pages(raw_root: Path, processed_root: Path, timeout_s: float, generated_at: str) -> dict[str, Any]:
    raw_dir = raw_root / "company_product_pages"
    processed_dir = processed_root / "company_product_pages"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    page_rows: list[dict[str, Any]] = []
    page_failures: list[dict[str, Any]] = []
    for profile in PRODUCT_PAGE_PROFILES:
        ticker = str(profile["ticker"])
        try:
            response = requests.get(str(profile["url"]), headers={"User-Agent": PRODUCT_PAGE_USER_AGENT}, timeout=timeout_s)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            page_failures.append({"ticker": ticker, "product": profile["product"], "source_url": profile["url"], "error": str(exc)})
            continue
        raw_path = raw_dir / f"{ticker.lower()}_{_slug(str(profile['product']))}.html"
        raw_path.write_text(response.text, encoding="utf-8", errors="replace")
        clean_text = _strip_html(response.text)
        clean_path = processed_dir / f"{ticker.lower()}_{_slug(str(profile['product']))}.txt"
        clean_path.write_text(clean_text, encoding="utf-8")
        page_rows.append(
            {
                "ticker": ticker,
                "company": profile["company"],
                "product": profile["product"],
                "source_url": profile["url"],
                "status_code": response.status_code,
                "raw_path": _path_str(raw_path),
                "clean_text_path": _path_str(clean_path),
                "clean_text_char_count": len(clean_text),
                "title": _html_title(response.text),
            }
        )
    if not page_rows:
        raise RuntimeError(f"No company product pages were materialized: {page_failures}")
    rows_path = processed_dir / "company_product_pages.materialized.jsonl"
    _write_jsonl(rows_path, page_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": "company_product_pages",
        "status": "materialized",
        "provider": "Company official web",
        "artifact_type": "official_product_page_html_text",
        "materialization_channel": "official_product_page_clean_text",
        "generated_at": generated_at,
        "processed_rows_path": _path_str(rows_path),
        "record_count": len(page_rows),
        "failure_count": len(page_failures),
        "failures": page_failures,
        "cleaned_text_char_count": sum(int(row["clean_text_char_count"]) for row in page_rows),
        "runtime_promotion_status": "staging_only_official_origin_parser_gate_pending",
    }


def extract_product_metric_candidates(
    chunk_inputs: Iterable[Path],
    *,
    max_candidates: int,
    max_per_family: int,
    generated_at: str,
) -> list[dict[str, Any]]:
    compiled = {family: [re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns] for family, patterns in PRODUCT_METRIC_PATTERNS.items()}
    counts = Counter()
    candidates: list[dict[str, Any]] = []
    for path in chunk_inputs:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(candidates) >= max_candidates:
                    return candidates
                if not line.strip():
                    continue
                row = json.loads(line)
                text = str(row.get("text") or "")
                for family, patterns in compiled.items():
                    if counts[family] >= max_per_family:
                        continue
                    matched = next((pattern.pattern for pattern in patterns if pattern.search(text)), "")
                    if not matched:
                        continue
                    snippet = _snippet_for_pattern(text, matched)
                    candidates.append(
                        {
                            "schema_version": "fin_agent_company_product_operating_metric_candidate_v0.1",
                            "source_id": "company_reported_product_operating_metrics",
                            "generated_at": generated_at,
                            "metric_family": family,
                            "match_pattern": matched,
                            "ticker": row.get("ticker"),
                            "company": row.get("company"),
                            "fiscal_year": row.get("fiscal_year"),
                            "form_type": row.get("form_type") or row.get("source_type"),
                            "section": row.get("section"),
                            "chunk_id": row.get("chunk_id"),
                            "source_url": row.get("source_url"),
                            "input_path": _path_str(path),
                            "candidate_status": "needs_value_unit_period_product_parser",
                            "snippet": snippet,
                        }
                    )
                    counts[family] += 1
                    break
    return candidates


def product_metric_materialization_row(candidate_rows: list[dict[str, Any]], output: Path, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": "company_reported_product_operating_metrics",
        "status": "materialized",
        "provider": "Company filings and earnings materials",
        "artifact_type": "product_operating_metric_ontology_candidate_table",
        "materialization_channel": "metric_ontology_candidate_extraction",
        "generated_at": generated_at,
        "processed_rows_path": _path_str(_resolve(output)),
        "record_count": len(candidate_rows),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in candidate_rows).items())),
        "runtime_promotion_status": "candidate_only_value_unit_period_parser_gate_pending",
    }


def build_summary(
    rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    manifest_output: Path,
    summary_output: Path,
    product_metric_candidates_output: Path,
    generated_at: str,
) -> dict[str, Any]:
    source_stats = {
        str(row["source_id"]): {
            "status": row.get("status"),
            "artifact_type": row.get("artifact_type"),
            "materialization_channel": row.get("materialization_channel"),
            "record_count": int(row.get("record_count") or 0),
            "downloaded_bytes": int(row.get("downloaded_bytes") or 0),
            "cleaned_text_char_count": int(row.get("cleaned_text_char_count") or 0),
            "runtime_promotion_status": row.get("runtime_promotion_status"),
        }
        for row in rows
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass" if not failures else "partial" if rows else "fail",
        "generated_at": generated_at,
        "source_count": len(source_stats),
        "materialized_sources": sorted(source_stats),
        "source_stats": source_stats,
        "failure_count": len(failures),
        "failures": failures,
        "outputs": {
            "manifest": _path_str(manifest_output),
            "summary": _path_str(summary_output),
            "product_metric_candidates": _path_str(_resolve(product_metric_candidates_output)),
        },
    }


def _http_get_text(url: str, timeout_s: float) -> str:
    response = requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=timeout_s)
    response.raise_for_status()
    return response.text


def _download_binary(url: str, path: Path, timeout_s: float) -> None:
    with requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=timeout_s, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _html_title(value: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", value)
    return _strip_html(match.group(1)) if match else ""


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80]


def _snippet_for_pattern(text: str, pattern: str, radius: int = 220) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return text[: radius * 2].strip()
    start = max(match.start() - radius, 0)
    end = min(match.end() + radius, len(text))
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _failure_row(source_id: str, error: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "source_id": source_id, "status": "failed", "error": error}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _path_str(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
