from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier1_plus_tier2_supply_chain_manifest.jsonl"
DEFAULT_PROFILES = REPO_ROOT / "configs" / "data_sources" / "company_earnings_material_profiles_v0_1.yaml"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "company_earnings_material_source_plan_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "company_earnings_material_source_plan_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_company_earnings_material_source_plan_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a staged source plan for company-authored earnings materials.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--years", default="", help="Comma-separated fiscal years. Defaults to profile defaults.")
    parser.add_argument("--periods", default="", help="Comma-separated periods such as FY,Q1,Q2,Q3,Q4.")
    parser.add_argument("--non-us-only", action="store_true", help="Only emit new non-US company IR material locator rows.")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_rows = _load_jsonl(_resolve(args.manifest))
    profiles = _load_yaml(_resolve(args.profiles))
    years = _parse_int_csv(args.years) or [int(year) for year in profiles.get("default_years") or []]
    periods = _parse_str_csv(args.periods) or [str(period) for period in profiles.get("default_fiscal_periods") or []]
    rows, issues = build_company_earnings_material_source_plan(
        manifest_rows=manifest_rows,
        profiles_config=profiles,
        years=years,
        fiscal_periods=periods,
        include_sec_reuse=not args.non_us_only,
        limit=args.limit,
    )
    output = _resolve(args.output)
    summary_output = _resolve(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output, rows)
    summary = summarize_source_plan(rows=rows, issues=issues, output_path=output, summary_path=summary_output)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def build_company_earnings_material_source_plan(
    *,
    manifest_rows: Iterable[Mapping[str, Any]],
    profiles_config: Mapping[str, Any],
    years: Iterable[int],
    fiscal_periods: Iterable[str],
    include_sec_reuse: bool = True,
    limit: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    sec_reuse = profiles_config.get("us_sec_reuse") or {}
    non_us = profiles_config.get("non_us_company_ir") or {}
    material_types = non_us.get("material_types") or {}
    year_list = [int(year) for year in years]
    period_list = [str(period).upper().strip() for period in fiscal_periods if str(period).strip()]

    for item in manifest_rows:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        if include_sec_reuse and item.get("sec_download_eligible"):
            plan_id = f"EARNMAT::SEC_REUSE::{_slug(ticker)}"
            if plan_id not in seen:
                seen.add(plan_id)
                rows.append(_sec_reuse_row(item, sec_reuse, plan_id))
        if item.get("global_public_download_eligible"):
            company_ir_urls = _official_source_urls(item.get("official_sources"), preferred_kind=str(non_us.get("preferred_source_kind") or "company_ir"))
            if not company_ir_urls:
                issues.append({"type": "missing_company_ir_locator", "ticker": ticker, "company_name": item.get("company_name")})
                continue
            for year in year_list:
                for period in period_list:
                    for material_type, material_config in material_types.items():
                        plan_id = f"EARNMAT::GLOBAL_IR::{_slug(ticker)}::{year}::{_slug(period)}::{_slug(material_type)}"
                        if plan_id in seen:
                            issues.append({"type": "duplicate_plan_id", "plan_id": plan_id, "ticker": ticker})
                            continue
                        seen.add(plan_id)
                        rows.append(_global_ir_row(item, non_us, material_type, material_config, plan_id, year, period, company_ir_urls))
                        if limit and len(rows) >= limit:
                            return _sort_rows(rows), issues
        if limit and len(rows) >= limit:
            break
    return _sort_rows(rows), issues


def _sec_reuse_row(item: Mapping[str, Any], sec_reuse: Mapping[str, Any], plan_id: str) -> dict[str, Any]:
    ticker = str(item.get("ticker") or "").upper().strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "ticker": ticker,
        "issuer_id": str(item.get("issuer_id") or item.get("cik") or "").strip(),
        "cik": str(item.get("cik") or "").strip(),
        "company_name": str(item.get("company_name") or "").strip(),
        "sector": str(item.get("sector") or "").strip(),
        "source_family": str(sec_reuse.get("source_family") or "sec_8k_earnings_release"),
        "source_tier": str(sec_reuse.get("source_tier") or "company_authored_unaudited_sec_filing"),
        "integration_mode": str(sec_reuse.get("integration_mode") or "reuse_existing_sec_8k_earnings_pipeline"),
        "source_type": "earnings_release",
        "material_type": "sec_8k_earnings_release",
        "document_status": "reuse_existing_pipeline_ready",
        "existing_scripts": list(sec_reuse.get("existing_scripts") or []),
        "source_boundary": str(sec_reuse.get("source_boundary") or "company_authored_unaudited_sec_filing_not_audited_ledger_fact"),
        "mainline_vector_promotion_allowed": False,
    }


def _global_ir_row(
    item: Mapping[str, Any],
    non_us: Mapping[str, Any],
    material_type: str,
    material_config: Mapping[str, Any],
    plan_id: str,
    fiscal_year: int,
    fiscal_period: str,
    company_ir_urls: list[str],
) -> dict[str, Any]:
    ticker = str(item.get("ticker") or "").upper().strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "ticker": ticker,
        "issuer_id": str(item.get("issuer_id") or ticker).strip(),
        "exchange_symbol": str(item.get("exchange_symbol") or "").strip(),
        "company_name": str(item.get("company_name") or "").strip(),
        "country": str(item.get("country") or "").strip(),
        "listing_exchange": str(item.get("listing_exchange") or "").strip(),
        "sector": str(item.get("sector") or "").strip(),
        "disclosure_profile": str(item.get("disclosure_profile") or "").strip(),
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "material_type": material_type,
        "source_type": str(material_config.get("source_type") or material_type),
        "source_family": str(material_config.get("source_family") or "company_earnings_release"),
        "source_tier": str(material_config.get("source_tier") or "company_authored_earnings_material"),
        "integration_mode": str(non_us.get("integration_mode") or "new_company_ir_material_locator"),
        "download_strategy": str(non_us.get("download_strategy") or "company_ir_material_locator"),
        "source_locator_urls": company_ir_urls,
        "search_terms": list(material_config.get("search_terms") or []),
        "cache_dir": (Path("data/raw_private/company_earnings_materials") / _slug(ticker) / str(fiscal_year) / _slug(fiscal_period) / _slug(material_type)).as_posix(),
        "document_status": "planned_locator_only",
        "source_boundary": "company_authored_material_not_audited_ledger_fact",
        "mainline_vector_promotion_allowed": False,
    }


def summarize_source_plan(*, rows: list[Mapping[str, Any]], issues: list[Mapping[str, Any]], output_path: Path, summary_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "fin_agent_company_earnings_material_source_plan_summary_v0.1",
        "status": "fail" if issues else "pass",
        "plan_row_count": len(rows),
        "company_count": len({str(row.get("ticker") or "") for row in rows}),
        "integration_mode_counts": dict(sorted(Counter(str(row.get("integration_mode") or "unknown") for row in rows).items())),
        "source_family_counts": dict(sorted(Counter(str(row.get("source_family") or "unknown") for row in rows).items())),
        "source_tier_counts": dict(sorted(Counter(str(row.get("source_tier") or "unknown") for row in rows).items())),
        "material_type_counts": dict(sorted(Counter(str(row.get("material_type") or "unknown") for row in rows).items())),
        "issue_counts": dict(sorted(Counter(str(issue.get("type") or "unknown") for issue in issues).items())),
        "issues": list(issues),
        "outputs": {"source_plan": str(output_path), "summary": str(summary_path)},
    }


def _official_source_urls(value: Any, *, preferred_kind: str) -> list[str]:
    urls: list[str] = []
    if not isinstance(value, list):
        return urls
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("kind") or "").strip() != preferred_kind:
            continue
        url = str(item.get("url") or "").strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (str(row.get("integration_mode") or ""), str(row.get("ticker") or ""), str(row.get("fiscal_year") or ""), str(row.get("fiscal_period") or ""), str(row.get("material_type") or "")))


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


def _parse_int_csv(raw: str | None) -> list[int]:
    return [int(part.strip()) for part in (raw or "").split(",") if part.strip()]


def _parse_str_csv(raw: str | None) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip().upper()).strip("_")
    return text or "UNKNOWN"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
