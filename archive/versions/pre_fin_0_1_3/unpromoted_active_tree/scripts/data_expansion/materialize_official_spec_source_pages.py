from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_SURFACE_SCRIPT = REPO_ROOT / "scripts" / "data_expansion" / "materialize_official_product_surface_pages.py"
SURFACE_SPEC = importlib.util.spec_from_file_location("official_product_surface_materializer", PRODUCT_SURFACE_SCRIPT)
SURFACE = importlib.util.module_from_spec(SURFACE_SPEC)
assert SURFACE_SPEC and SURFACE_SPEC.loader
SURFACE_SPEC.loader.exec_module(SURFACE)

SCHEMA_VERSION = "finsight_official_spec_source_pages_materialized_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_official_spec_source_pages_materialization_summary_v0_1"

DEFAULT_CANDIDATES = REPO_ROOT / "data" / "manifests" / "official_spec_source_locator_candidates_v0_1.jsonl"
DEFAULT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/"
    "official_spec_pages/official_spec_pages.materialized.jsonl"
)
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/official_spec_pages")
DEFAULT_CLEAN_DIR = Path("Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/official_spec_pages")
DEFAULT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "official_spec_source_materialization_attempts_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_spec_source_materialization_summary_v0_1.json"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 FIN-Insight-Agent/0.1"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize official spec/profile candidate pages found by locator.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    parser.add_argument("--attempts-output", type=Path, default=DEFAULT_ATTEMPTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-per-ticker-route", type=int, default=3)
    parser.add_argument("--max-candidates", type=int, default=900)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--min-clean-text-chars", type=int, default=220)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    candidates = _select_candidates(
        _load_jsonl(args.candidates),
        max_per_ticker_route=args.max_per_ticker_route,
        max_candidates=args.max_candidates,
    )
    existing_rows = _load_jsonl(args.output)
    result = materialize_official_spec_source_pages(
        candidates=candidates,
        existing_rows=existing_rows,
        raw_dir=args.raw_dir,
        clean_dir=args.clean_dir,
        generated_at=generated_at,
        timeout_s=args.timeout_s,
        min_clean_text_chars=args.min_clean_text_chars,
        workers=args.workers,
        skip_existing=bool(args.skip_existing),
    )
    _write_jsonl(args.output, result["rows"])
    _write_jsonl(args.attempts_output, result["attempts"])
    _write_json(args.summary, result["summary"])
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and result["summary"].get("materialized_count", 0) <= 0:
        return 1
    return 0


def materialize_official_spec_source_pages(
    *,
    candidates: Iterable[Mapping[str, Any]],
    existing_rows: Iterable[Mapping[str, Any]],
    raw_dir: Path,
    clean_dir: Path,
    generated_at: str,
    timeout_s: float = 12.0,
    min_clean_text_chars: int = 220,
    workers: int = 16,
    skip_existing: bool = False,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    rows_by_key: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        key = _row_key(row)
        if key:
            rows_by_key[key] = dict(row)

    candidate_list = [dict(row) for row in candidates if isinstance(row, Mapping)]
    if skip_existing:
        candidate_list = [row for row in candidate_list if _candidate_key(row) not in rows_by_key]

    attempts: list[dict[str, Any]] = []
    new_or_updated = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as executor:
        futures = [
            executor.submit(
                _fetch_one,
                candidate=row,
                raw_dir=raw_dir,
                clean_dir=clean_dir,
                generated_at=generated_at,
                timeout_s=timeout_s,
                min_clean_text_chars=min_clean_text_chars,
            )
            for row in candidate_list
        ]
        for future in concurrent.futures.as_completed(futures):
            attempt, materialized = future.result()
            attempts.append(attempt)
            if materialized:
                rows_by_key[_row_key(materialized)] = materialized
                new_or_updated += 1

    rows = sorted(rows_by_key.values(), key=lambda row: (str(row.get("ticker") or ""), str(row.get("source_url") or "")))
    by_status = Counter(str(row.get("status") or "") for row in attempts)
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "selected_candidate_count": len(candidate_list),
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(by_status.items())),
        "materialized_count": new_or_updated,
        "output_row_count": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "route_counts": _counts(rows, "route_id"),
        "source_role_counts": _counts(rows, "source_role"),
        "boundary": (
            "Materialized official spec/profile pages are fetch artifacts only. They become runtime evidence only "
            "after source-specific parsers emit value/unit/period/product/citation rows."
        ),
    }
    return {"rows": rows, "attempts": sorted(attempts, key=lambda row: (str(row.get("ticker") or ""), str(row.get("candidate_url") or ""))), "summary": summary}


def _fetch_one(
    *,
    candidate: Mapping[str, Any],
    raw_dir: Path,
    clean_dir: Path,
    generated_at: str,
    timeout_s: float,
    min_clean_text_chars: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    ticker = str(candidate.get("ticker") or "").upper().strip()
    url = str(candidate.get("candidate_url") or candidate.get("source_url") or "").strip()
    route_id = str(candidate.get("route_id") or "")
    attempt_base = {
        "generated_at": generated_at,
        "ticker": ticker,
        "company_name": candidate.get("company_name") or "",
        "route_id": route_id,
        "source_role": candidate.get("source_role") or "",
        "candidate_url": url,
        "locator_score": candidate.get("locator_score") or 0,
    }
    if not ticker or not url:
        return {**attempt_base, "status": "invalid_candidate", "reason": "missing_ticker_or_url"}, None
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=float(timeout_s or 12.0),
        )
    except Exception as exc:  # noqa: BLE001
        return {**attempt_base, "status": "fetch_failed", "reason": f"{type(exc).__name__}: {str(exc)[:220]}"}, None
    status_code = int(response.status_code or 0)
    content_type = str(response.headers.get("Content-Type") or "")
    if status_code >= 400 or not response.content:
        return {**attempt_base, "status": "unusable_response", "reason": f"http_{status_code}" if status_code else "empty_body"}, None

    is_pdf = "pdf" in content_type.lower() or urlparse(url).path.lower().endswith(".pdf")
    suffix = "pdf" if is_pdf else "html"
    stem = _artifact_stem(ticker=ticker, route_id=route_id, url=url)
    raw_path = raw_dir / f"{stem}.{suffix}"
    clean_path = clean_dir / f"{stem}.txt"
    raw_path.write_bytes(response.content)
    if is_pdf:
        clean_text, title, parse_error = _pdf_to_text(raw_path)
        if parse_error:
            return {**attempt_base, "status": "parse_failed", "reason": parse_error, "status_code": status_code, "content_type": content_type}, None
    else:
        body = response.text
        title = SURFACE.extract_title(body) or str(candidate.get("link_text") or candidate.get("family_name") or "")
        clean_text = SURFACE.html_to_text(body)
    usability_error = SURFACE.response_usability_error(
        title=title,
        clean_text=clean_text,
        min_clean_text_chars=min_clean_text_chars,
    )
    if usability_error:
        return {
            **attempt_base,
            "status": "unusable_response",
            "reason": usability_error,
            "status_code": status_code,
            "content_type": content_type,
            "clean_text_char_count": len(clean_text),
            "title": title,
        }, None
    clean_path.write_text(clean_text, encoding="utf-8", errors="replace")
    row = {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "company": candidate.get("company") or candidate.get("company_name") or "",
        "company_name": candidate.get("company_name") or candidate.get("company") or "",
        "product": candidate.get("product") or candidate.get("family_name") or "",
        "family_id": candidate.get("family_id") or "",
        "family_name": candidate.get("family_name") or "",
        "route_id": route_id,
        "source_role": candidate.get("source_role") or "",
        "source_id": candidate.get("source_id") or "",
        "source_url": url,
        "url": url,
        "referring_source_url": candidate.get("referring_source_url") or "",
        "title": title,
        "status_code": status_code,
        "content_type": content_type,
        "raw_path": str(raw_path),
        "clean_text_path": str(clean_path),
        "clean_text_char_count": len(clean_text),
        "fetched_at": generated_at,
        "materialization_status": "live_fetch_materialized",
        "source_policy": "issuer_domain_official_spec_or_asset_profile_context_only",
        "claim_boundary": candidate.get("claim_boundary") or "",
    }
    return {
        **attempt_base,
        "status": "materialized",
        "status_code": status_code,
        "content_type": content_type,
        "clean_text_char_count": len(clean_text),
        "title": title,
    }, row


def _pdf_to_text(path: Path) -> tuple[str, str, str]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # noqa: BLE001
        return "", "", f"pdf_parser_unavailable:{type(exc).__name__}"
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:12]:
            parts.append(page.extract_text() or "")
        title = ""
        try:
            title = str((reader.metadata or {}).get("/Title") or "")
        except Exception:
            title = ""
        return re.sub(r"\s+", " ", " ".join(parts)).strip(), title, ""
    except Exception as exc:  # noqa: BLE001
        return "", "", f"pdf_parse_failed:{type(exc).__name__}:{str(exc)[:180]}"


def _select_candidates(
    candidates: list[Mapping[str, Any]],
    *,
    max_per_ticker_route: int,
    max_candidates: int,
) -> list[dict[str, Any]]:
    per_key = Counter()
    out: list[dict[str, Any]] = []
    ranked = sorted(
        [dict(row) for row in candidates],
        key=lambda row: (
            str(row.get("ticker") or ""),
            str(row.get("route_id") or ""),
            -int(row.get("locator_score") or 0),
            str(row.get("candidate_url") or ""),
        ),
    )
    for row in ranked:
        key = (str(row.get("ticker") or "").upper(), str(row.get("route_id") or ""))
        if per_key[key] >= max(1, int(max_per_ticker_route or 1)):
            continue
        out.append(row)
        per_key[key] += 1
        if len(out) >= max(1, int(max_candidates or 1)):
            break
    return out


def _artifact_stem(*, ticker: str, route_id: str, url: str) -> str:
    host = re.sub(r"[^a-z0-9]+", "_", urlparse(url).netloc.lower()).strip("_")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"{ticker.lower()}_{_slug(route_id)}_{host}_{digest}"[:180]


def _candidate_key(row: Mapping[str, Any]) -> str:
    return "::".join([str(row.get("ticker") or "").upper(), str(row.get("candidate_url") or row.get("source_url") or "")])


def _row_key(row: Mapping[str, Any]) -> str:
    return "::".join([str(row.get("ticker") or "").upper(), str(row.get("source_url") or row.get("url") or "")])


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "page"


def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
