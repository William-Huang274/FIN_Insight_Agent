from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build market and industry staging manifests for the expanded Tier1/Tier2 universe."
    )
    parser.add_argument(
        "--universe-manifest",
        default="data/manifests/tier1_plus_tier2_supply_chain_manifest.jsonl",
    )
    parser.add_argument(
        "--industry-source-families",
        default="configs/industry_data_source_families_v0_2.yaml",
    )
    parser.add_argument("--output-dir", default="data/manifests")
    parser.add_argument("--version", default="v0_1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe_path = _resolve(args.universe_manifest)
    families_path = _resolve(args.industry_source_families)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    companies = _read_jsonl(universe_path)
    families = _load_yaml(families_path).get("source_families") or []
    market_rows = _build_market_rows(companies)
    industry_rows, industry_summary = _build_industry_rows(companies, families)

    market_csv = output_dir / f"tier1_tier2_market_universe_{args.version}.csv"
    market_ticker_yaml = output_dir / f"tier1_tier2_market_yahoo_tickers_{args.version}.yaml"
    industry_jsonl = output_dir / f"tier1_tier2_industry_source_family_map_{args.version}.jsonl"
    summary_path = output_dir / f"tier1_tier2_market_industry_manifest_summary_{args.version}.json"

    _write_csv(market_csv, market_rows)
    _write_ticker_yaml(market_ticker_yaml, market_rows)
    _write_jsonl(industry_jsonl, industry_rows)

    summary = {
        "schema_version": "fin_agent_market_industry_expansion_manifest_v0.1",
        "status": "pass",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "universe_manifest": str(universe_path),
            "industry_source_families": str(families_path),
        },
        "outputs": {
            "market_universe_csv": str(market_csv),
            "market_yahoo_tickers_yaml": str(market_ticker_yaml),
            "industry_source_family_map": str(industry_jsonl),
        },
        "market": {
            "company_count": len(companies),
            "market_row_count": len(market_rows),
            "provider_symbol_count": len({row["provider_symbol"] for row in market_rows if row["provider_symbol"]}),
            "non_us_provider_symbol_count": sum(1 for row in market_rows if row["market_region"] != "us_listed_or_adr"),
            "currency_counts": dict(Counter(row["reporting_currency"] or "UNKNOWN" for row in market_rows)),
            "region_counts": dict(Counter(row["market_region"] for row in market_rows)),
            "known_limitations": [
                "Yahoo chart is an unofficial market data source and remains market_snapshot context only.",
                "Non-US local tickers are kept as provider_symbol candidates; provider availability must be validated by download results.",
                "ADR/local share-class and FX conversion are not inferred here; later market snapshot normalization must keep currency fields explicit.",
            ],
        },
        "industry": industry_summary,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _build_market_rows(companies: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for company in companies:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        market_region = _market_region(company, ticker)
        provider_symbol = _provider_symbol(company, ticker)
        rows.append(
            {
                "ticker": ticker,
                "provider_symbol": provider_symbol,
                "company_name": str(company.get("company_name") or ""),
                "sector": str(company.get("sector") or ""),
                "category": str(company.get("category") or ""),
                "universe_tier": str(company.get("universe_tier") or ""),
                "country": str(company.get("country") or ""),
                "listing_exchange": str(company.get("listing_exchange") or ""),
                "exchange_symbol": str(company.get("exchange_symbol") or ""),
                "reporting_currency": str(company.get("reporting_currency") or _default_currency(company, ticker)),
                "market_region": market_region,
                "sec_download_eligible": str(bool(company.get("sec_download_eligible"))).lower(),
                "global_public_download_eligible": str(bool(company.get("global_public_download_eligible"))).lower(),
                "source_sets": "|".join(str(item) for item in company.get("source_sets") or []),
                "source_policy": (
                    "market_snapshot_context_only; provider_symbol_candidate; "
                    "do_not_replace_company_filed_financial_facts"
                ),
            }
        )
    return sorted(rows, key=lambda row: (row["market_region"], row["ticker"]))


def _provider_symbol(company: dict[str, Any], ticker: str) -> str:
    # Current Tier2 non-US supplements already carry Yahoo-compatible suffixes
    # such as .KS, .TW, .SZ, and .T. Keep them explicit instead of rewriting by
    # exchange so later profile-specific providers can override cleanly.
    return ticker or str(company.get("exchange_symbol") or "").strip().upper()


def _market_region(company: dict[str, Any], ticker: str) -> str:
    if company.get("sec_download_eligible"):
        return "us_listed_or_adr"
    if "." in ticker:
        return "non_us_local_listing"
    if company.get("global_public_download_eligible"):
        return "non_us_listing_unmapped_provider_symbol"
    return "unknown"


def _default_currency(company: dict[str, Any], ticker: str) -> str:
    country = str(company.get("country") or "").lower()
    if ticker.endswith(".KS"):
        return "KRW"
    if ticker.endswith(".TW"):
        return "TWD"
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        return "CNY"
    if ticker.endswith(".T"):
        return "JPY"
    if ticker.endswith(".HK"):
        return "HKD"
    if "south korea" in country:
        return "KRW"
    if "taiwan" in country:
        return "TWD"
    if "china" in country:
        return "CNY"
    if "japan" in country:
        return "JPY"
    return "USD"


def _build_industry_rows(
    companies: Iterable[dict[str, Any]],
    families: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    family_targets = {
        str(family.get("source_family") or ""): {
            _normalize_industry_name(item) for item in family.get("target_industries") or []
        }
        for family in families
    }
    rows: list[dict[str, Any]] = []
    coverage_counter: Counter[str] = Counter()
    uncovered: list[str] = []
    for company in companies:
        ticker = str(company.get("ticker") or "").upper()
        sector = str(company.get("sector") or "")
        category = str(company.get("category") or "")
        normalized_tags = {_normalize_industry_name(sector), _normalize_industry_name(category)}
        matched = [
            family
            for family, targets in family_targets.items()
            if family and targets and normalized_tags.intersection(targets)
        ]
        matched.extend(_heuristic_industry_families(sector=sector, category=category))
        matched = sorted(set(matched))
        if not matched:
            uncovered.append(ticker)
        for family in matched:
            coverage_counter[family] += 1
        rows.append(
            {
                "schema_version": "fin_agent_industry_source_family_map_v0.1",
                "ticker": ticker,
                "company_name": company.get("company_name") or "",
                "sector": sector,
                "category": category,
                "universe_tier": company.get("universe_tier") or "",
                "source_families": matched,
                "claim_boundary": "industry_snapshot_context_only; cannot overwrite company-reported facts",
            }
        )
    summary = {
        "company_count": len(rows),
        "mapped_company_count": sum(1 for row in rows if row["source_families"]),
        "unmapped_company_count": len(uncovered),
        "source_family_company_counts": dict(sorted(coverage_counter.items())),
        "unmapped_ticker_sample": uncovered[:40],
        "known_limitations": [
            "Sector/category matching is a staging heuristic; Specialist routing must still use query intent.",
            "Healthcare regulatory and energy/utilities power families require provider-specific evidence checks before strong claims.",
            "Industry rows are background context and cannot prove company-level revenue, margin, customer, or supplier facts.",
        ],
    }
    return rows, summary


def _normalize_industry_name(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("&", "and")
        .replace("/", " ")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _heuristic_industry_families(*, sector: str, category: str) -> list[str]:
    text = f"{sector} {category}".lower()
    families: list[str] = []
    if any(term in text for term in ("bank", "financial", "credit", "real estate", "mortgage")):
        families.append("industry_macro_rates_credit")
    if any(term in text for term in ("consumer", "retail", "restaurant", "auto", "commerce")):
        families.append("industry_consumer_macro")
    if any(term in text for term in ("energy", "oil", "gas", "lng", "uranium")):
        families.append("industry_energy_commodities")
    if any(term in text for term in ("material", "metal", "mining", "chemical", "steel", "copper")):
        families.append("industry_materials_commodities")
    if any(term in text for term in ("health", "pharma", "medical", "drug", "biotech")):
        families.append("industry_healthcare_regulatory")
    if any(term in text for term in ("utility", "power", "electric", "housing", "homebuilder")):
        families.append("industry_housing_real_estate_power")
        families.append("industry_utilities_power_demand")
    if any(term in text for term in ("industrial", "semiconductor", "technology", "software", "hardware", "server")):
        families.append("industry_industrial_macro")
    return families


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "ticker",
        "provider_symbol",
        "company_name",
        "sector",
        "category",
        "universe_tier",
        "country",
        "listing_exchange",
        "exchange_symbol",
        "reporting_currency",
        "market_region",
        "sec_download_eligible",
        "global_public_download_eligible",
        "source_sets",
        "source_policy",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_ticker_yaml(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Generated by build_market_industry_expansion_manifests.py", "tickers:"]
    for row in rows:
        symbol = row["provider_symbol"]
        if symbol:
            lines.append(f"  - ticker: {symbol}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
