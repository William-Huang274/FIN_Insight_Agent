from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier1_sp500_plus_current_manifest.jsonl"
DEFAULT_SUPPLEMENT_CONFIG = REPO_ROOT / "configs" / "data_sources" / "tier2_supply_chain_supplements_v0_1.yaml"
DEFAULT_SEC_TICKERS = REPO_ROOT / "data" / "raw_private" / "sec" / "_reference" / "company_tickers.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "manifests"
SCHEMA_VERSION = "fin_agent_universe_manifest_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Tier 2 supply-chain supplement and combined Tier1+Tier2 manifests.")
    parser.add_argument("--base-manifest", type=Path, default=DEFAULT_BASE_MANIFEST)
    parser.add_argument("--supplement-config", type=Path, default=DEFAULT_SUPPLEMENT_CONFIG)
    parser.add_argument("--sec-company-tickers", type=Path, default=DEFAULT_SEC_TICKERS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tier2-output", default="tier2_supply_chain_supplement_manifest.jsonl")
    parser.add_argument("--combined-output", default="tier1_plus_tier2_supply_chain_manifest.jsonl")
    parser.add_argument("--summary-output", default="tier2_supply_chain_supplement_summary_v0_1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_path = _resolve(args.base_manifest)
    config_path = _resolve(args.supplement_config)
    output_dir = _resolve(args.output_dir)
    base_rows = _load_jsonl(base_path)
    config = _load_yaml(config_path)
    sec_reference = _load_sec_company_reference(_resolve(args.sec_company_tickers))

    tier2_rows, skipped = build_supply_chain_supplement_rows(
        base_rows=base_rows,
        supplement_config=config,
        sec_reference=sec_reference,
        source_config_ref=str(config_path),
    )
    combined = [*base_rows, *tier2_rows]

    output_dir.mkdir(parents=True, exist_ok=True)
    tier2_path = output_dir / args.tier2_output
    combined_path = output_dir / args.combined_output
    summary_path = output_dir / args.summary_output
    _write_jsonl(tier2_path, tier2_rows)
    _write_jsonl(combined_path, combined)
    summary = summarize_supply_chain_supplements(
        base_rows=base_rows,
        tier2_rows=tier2_rows,
        skipped=skipped,
        config=config,
        outputs={"tier2_manifest": str(tier2_path), "combined_manifest": str(combined_path), "summary": str(summary_path)},
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_supply_chain_supplement_rows(
    *,
    base_rows: list[Mapping[str, Any]],
    supplement_config: Mapping[str, Any],
    sec_reference: Mapping[str, Mapping[str, Any]],
    source_config_ref: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_tickers = {str(row.get("ticker") or "").upper().strip() for row in base_rows}
    base_ciks = {str(row.get("cik") or "").strip() for row in base_rows if str(row.get("cik") or "").strip()}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_ciks: set[str] = set()
    seen_tickers: set[str] = set()
    for raw in supplement_config.get("companies") or []:
        ticker = str(raw.get("ticker") or "").upper().strip()
        if not ticker:
            skipped.append({"ticker": "", "reason": "missing_ticker"})
            continue
        ref = sec_reference.get(ticker, {})
        cik = _normalize_cik(raw.get("cik") or ref.get("cik"))
        if ticker in base_tickers or cik in base_ciks:
            skipped.append({"ticker": ticker, "cik": cik, "reason": "already_in_base_tier"})
            continue
        if ticker in seen_tickers or (cik and cik in seen_ciks):
            skipped.append({"ticker": ticker, "cik": cik, "reason": "duplicate_in_supplement"})
            continue
        if not cik:
            skipped.append({"ticker": ticker, "cik": "", "reason": "missing_cik_mapping"})
            continue
        company_name = str(raw.get("company_name") or ref.get("company_name") or "").strip()
        if not company_name:
            skipped.append({"ticker": ticker, "cik": cik, "reason": "missing_company_name"})
            continue
        row = {
            "schema_version": SCHEMA_VERSION,
            "ticker": ticker,
            "cik": cik,
            "company_name": company_name,
            "sector": str(raw.get("sector") or raw.get("industry_group") or "").strip(),
            "category": str(raw.get("industry_group") or raw.get("sector") or "").strip(),
            "source_sets": ["tier2_supply_chain_supplement"],
            "source_config_ref": source_config_ref,
            "sec_download_eligible": True,
            "global_public_download_eligible": False,
            "source_family": "sec_primary_filing",
            "disclosure_profile": "sec_edgar_company_filing",
            "source_gap": "",
            "alternate_tickers": [],
            "universe_tier": "tier2_supply_chain_supplement",
            "supply_chain_role": str(raw.get("supply_chain_role") or "").strip(),
            "priority": str(raw.get("priority") or "p2").strip(),
            "target_forms": _string_list(raw.get("target_forms")),
            "target_reports": [],
            "issuer_id": cik,
            "exchange_symbol": ticker,
            "country": str(raw.get("country") or "").strip(),
            "listing_exchange": str(raw.get("listing_exchange") or "").strip(),
            "official_sources": [],
            "rationale": str(raw.get("rationale") or "").strip(),
        }
        rows.append(row)
        seen_tickers.add(ticker)
        seen_ciks.add(cik)
    for raw in supplement_config.get("global_public_disclosure_companies") or []:
        ticker = str(raw.get("ticker") or "").upper().strip()
        issuer_id = str(raw.get("issuer_id") or ticker).upper().strip()
        if not ticker:
            skipped.append({"ticker": "", "issuer_id": issuer_id, "reason": "missing_ticker"})
            continue
        if ticker in base_tickers:
            skipped.append({"ticker": ticker, "issuer_id": issuer_id, "reason": "already_in_base_tier"})
            continue
        if ticker in seen_tickers or issuer_id in seen_ciks:
            skipped.append({"ticker": ticker, "issuer_id": issuer_id, "reason": "duplicate_in_supplement"})
            continue
        company_name = str(raw.get("company_name") or "").strip()
        official_sources = _official_sources(raw.get("official_sources"))
        if not company_name:
            skipped.append({"ticker": ticker, "issuer_id": issuer_id, "reason": "missing_company_name"})
            continue
        if not official_sources:
            skipped.append({"ticker": ticker, "issuer_id": issuer_id, "reason": "missing_official_sources"})
            continue
        row = {
            "schema_version": SCHEMA_VERSION,
            "ticker": ticker,
            "cik": "",
            "company_name": company_name,
            "sector": str(raw.get("sector") or raw.get("industry_group") or "").strip(),
            "category": str(raw.get("industry_group") or raw.get("sector") or "").strip(),
            "source_sets": ["tier2_supply_chain_supplement", "global_public_disclosure"],
            "source_config_ref": source_config_ref,
            "sec_download_eligible": False,
            "global_public_download_eligible": True,
            "source_family": str(raw.get("source_family") or "global_public_annual_report").strip(),
            "disclosure_profile": str(raw.get("disclosure_profile") or "").strip(),
            "source_gap": "",
            "alternate_tickers": _string_list(raw.get("alternate_tickers")),
            "universe_tier": "tier2_supply_chain_supplement",
            "supply_chain_role": str(raw.get("supply_chain_role") or "").strip(),
            "priority": str(raw.get("priority") or "p2").strip(),
            "target_forms": [],
            "target_reports": [],
            "report_type_include_overrides": _string_list(raw.get("report_type_include_overrides")),
            "report_type_exclude_overrides": _string_list(raw.get("report_type_exclude_overrides")),
            "report_type_override_reason": str(raw.get("report_type_override_reason") or "").strip(),
            "issuer_id": issuer_id,
            "exchange_symbol": str(raw.get("exchange_symbol") or ticker).strip(),
            "country": str(raw.get("country") or "").strip(),
            "listing_exchange": str(raw.get("listing_exchange") or "").strip(),
            "reporting_currency": str(raw.get("reporting_currency") or "").strip(),
            "official_sources": official_sources,
            "rationale": str(raw.get("rationale") or "").strip(),
        }
        rows.append(row)
        seen_tickers.add(ticker)
        seen_ciks.add(issuer_id)
    return sorted(rows, key=lambda item: (str(item.get("priority") or ""), str(item.get("ticker") or ""))), skipped


def summarize_supply_chain_supplements(
    *,
    base_rows: list[Mapping[str, Any]],
    tier2_rows: list[Mapping[str, Any]],
    skipped: list[Mapping[str, Any]],
    config: Mapping[str, Any],
    outputs: Mapping[str, str],
) -> dict[str, Any]:
    priority_counts = Counter(str(row.get("priority") or "unknown") for row in tier2_rows)
    sector_counts = Counter(str(row.get("sector") or "unknown") for row in tier2_rows)
    form_counts = Counter(form for row in tier2_rows for form in row.get("target_forms") or [])
    report_counts = Counter(report for row in tier2_rows for report in row.get("target_reports") or [])
    include_override_counts = Counter(report for row in tier2_rows for report in row.get("report_type_include_overrides") or [])
    exclude_override_counts = Counter(report for row in tier2_rows for report in row.get("report_type_exclude_overrides") or [])
    source_family_counts = Counter(str(row.get("source_family") or "unknown") for row in tier2_rows)
    disclosure_profile_counts = Counter(str(row.get("disclosure_profile") or "unknown") for row in tier2_rows)
    skipped_counts = Counter(str(row.get("reason") or "unknown") for row in skipped)
    return {
        "schema_version": "fin_agent_tier2_supply_chain_supplement_summary_v0.1",
        "status": "completed",
        "base_company_count": len(base_rows),
        "tier2_company_count": len(tier2_rows),
        "combined_company_count": len(base_rows) + len(tier2_rows),
        "tier2_sec_company_count": sum(1 for row in tier2_rows if row.get("sec_download_eligible")),
        "tier2_global_public_company_count": sum(1 for row in tier2_rows if row.get("global_public_download_eligible")),
        "priority_counts": dict(sorted(priority_counts.items())),
        "sector_counts": dict(sorted(sector_counts.items())),
        "target_form_counts": dict(sorted(form_counts.items())),
        "target_report_counts": dict(sorted(report_counts.items())),
        "report_type_include_override_counts": dict(sorted(include_override_counts.items())),
        "report_type_exclude_override_counts": dict(sorted(exclude_override_counts.items())),
        "source_family_counts": dict(sorted(source_family_counts.items())),
        "disclosure_profile_counts": dict(sorted(disclosure_profile_counts.items())),
        "skipped_counts": dict(sorted(skipped_counts.items())),
        "skipped": list(skipped),
        "global_public_disclosure_config_count": len(config.get("global_public_disclosure_companies") or []),
        "outputs": dict(outputs),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_sec_company_reference(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.values() if isinstance(payload, Mapping) else payload
    result: dict[str, dict[str, str]] = {}
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        result[ticker] = {
            "ticker": ticker,
            "cik": _normalize_cik(item.get("cik_str") or item.get("cik")),
            "company_name": str(item.get("title") or item.get("name") or "").strip(),
        }
    return result


def _normalize_cik(value: Any) -> str:
    digits = "".join(char for char in str(value or "") if char.isdigit())
    return digits.zfill(10) if digits else ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _official_sources(value: Any) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    if not isinstance(value, list):
        return sources
    for item in value:
        if isinstance(item, str):
            url = item.strip()
            if url:
                sources.append({"kind": "source", "url": url})
            continue
        if not isinstance(item, Mapping):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        sources.append({"kind": str(item.get("kind") or "source").strip(), "url": url})
    return sources


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
