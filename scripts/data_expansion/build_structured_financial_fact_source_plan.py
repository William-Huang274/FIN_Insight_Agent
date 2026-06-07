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
DEFAULT_CONFIG = REPO_ROOT / "configs" / "data_sources" / "structured_financial_fact_sources_v0_1.yaml"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "structured_financial_fact_source_plan_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "structured_financial_fact_source_plan_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_structured_financial_fact_source_plan_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a staged source plan for structured financial facts.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--years", default="", help="Comma-separated fiscal years for global-public derived facts.")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_rows = _load_jsonl(_resolve(args.manifest))
    config = _load_yaml(_resolve(args.config))
    years = _parse_int_csv(args.years) or [int(year) for year in config.get("default_years") or []]
    rows, issues = build_structured_financial_fact_source_plan(
        manifest_rows=manifest_rows,
        config=config,
        years=years,
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


def build_structured_financial_fact_source_plan(
    *,
    manifest_rows: Iterable[Mapping[str, Any]],
    config: Mapping[str, Any],
    years: Iterable[int],
    limit: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = config.get("sources") or {}
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in manifest_rows:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        if item.get("sec_download_eligible"):
            cik = _cik10(item.get("cik") or item.get("issuer_id"))
            if not cik:
                issues.append({"type": "missing_cik_for_sec_structured_fact", "ticker": ticker, "company_name": item.get("company_name")})
            else:
                for source_name in ("sec_companyfacts", "sec_submissions"):
                    plan_id = f"FINFACT::SEC::{_slug(ticker)}::{_slug(source_name)}"
                    if plan_id in seen:
                        continue
                    seen.add(plan_id)
                    rows.append(_sec_fact_row(item, sources.get(source_name) or {}, source_name, plan_id, cik))
        if item.get("global_public_download_eligible"):
            source = sources.get("global_public_financial_statement_tables") or {}
            for fiscal_year in [int(year) for year in years]:
                plan_id = f"FINFACT::GLOBAL_REPORT::{_slug(ticker)}::{fiscal_year}"
                if plan_id in seen:
                    issues.append({"type": "duplicate_plan_id", "plan_id": plan_id, "ticker": ticker})
                    continue
                seen.add(plan_id)
                rows.append(_global_report_fact_row(item, source, plan_id, fiscal_year))
                if limit and len(rows) >= limit:
                    return _sort_rows(rows), issues
        if limit and len(rows) >= limit:
            break
    return _sort_rows(rows), issues


def _sec_fact_row(item: Mapping[str, Any], source: Mapping[str, Any], source_name: str, plan_id: str, cik10: str) -> dict[str, Any]:
    endpoint = str(source.get("endpoint_template") or "").format(cik10=cik10)
    ticker = str(item.get("ticker") or "").upper().strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "ticker": ticker,
        "issuer_id": str(item.get("issuer_id") or item.get("cik") or "").strip(),
        "cik": str(item.get("cik") or "").strip(),
        "cik10": cik10,
        "company_name": str(item.get("company_name") or "").strip(),
        "sector": str(item.get("sector") or "").strip(),
        "fact_source": source_name,
        "source_family": str(source.get("source_family") or source_name),
        "source_tier": str(source.get("source_tier") or "company_reported_structured_fact"),
        "integration_mode": str(source.get("integration_mode") or "new_sec_api_download"),
        "source_url": endpoint,
        "cache_dir": (Path("data/raw_private/structured_financial_facts/sec") / _slug(ticker)).as_posix(),
        "document_status": "planned_api_download",
        "required_fields": list(source.get("required_fields") or []),
        "mainline_vector_promotion_allowed": False,
        "exact_value_ledger_candidate": source_name == "sec_companyfacts",
    }


def _global_report_fact_row(item: Mapping[str, Any], source: Mapping[str, Any], plan_id: str, fiscal_year: int) -> dict[str, Any]:
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
        "fact_source": "global_public_financial_statement_tables",
        "source_family": str(source.get("source_family") or "global_public_structured_financial_fact"),
        "source_tier": str(source.get("source_tier") or "company_reported_structured_fact"),
        "integration_mode": str(source.get("integration_mode") or "derive_from_downloaded_official_disclosure"),
        "dependency": str(source.get("dependency") or "global_public_official_report_document"),
        "promotion_blocker_until": list(source.get("promotion_blocker_until") or []),
        "cache_dir": (Path("data/staging/global_public_structured_facts") / _slug(ticker) / str(fiscal_year)).as_posix(),
        "document_status": "blocked_until_official_report_parser_pass",
        "required_fields": list(source.get("required_fields") or []),
        "mainline_vector_promotion_allowed": False,
        "exact_value_ledger_candidate": True,
    }


def summarize_source_plan(*, rows: list[Mapping[str, Any]], issues: list[Mapping[str, Any]], output_path: Path, summary_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "fin_agent_structured_financial_fact_source_plan_summary_v0.1",
        "status": "fail" if issues else "pass",
        "plan_row_count": len(rows),
        "company_count": len({str(row.get("ticker") or "") for row in rows}),
        "integration_mode_counts": dict(sorted(Counter(str(row.get("integration_mode") or "unknown") for row in rows).items())),
        "fact_source_counts": dict(sorted(Counter(str(row.get("fact_source") or "unknown") for row in rows).items())),
        "source_family_counts": dict(sorted(Counter(str(row.get("source_family") or "unknown") for row in rows).items())),
        "source_tier_counts": dict(sorted(Counter(str(row.get("source_tier") or "unknown") for row in rows).items())),
        "exact_value_ledger_candidate_count": sum(1 for row in rows if row.get("exact_value_ledger_candidate")),
        "issue_counts": dict(sorted(Counter(str(issue.get("type") or "unknown") for issue in issues).items())),
        "issues": list(issues),
        "outputs": {"source_plan": str(output_path), "summary": str(summary_path)},
    }


def _cik10(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    return digits.zfill(10)


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (str(row.get("integration_mode") or ""), str(row.get("ticker") or ""), str(row.get("fact_source") or ""), str(row.get("fiscal_year") or "")))


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


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip().upper()).strip("_")
    return text or "UNKNOWN"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
