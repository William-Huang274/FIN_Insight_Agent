from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build accepted full238 US and foreign canary configs for sector-depth expansion."
    )
    parser.add_argument("--base-full78", default="configs/sec_investment_coverage_full78_fy2023_2027.yaml")
    parser.add_argument("--full128-additions", default="configs/sec_investment_coverage_full128_us_additions_v0_2.yaml")
    parser.add_argument("--sector-depth", default="configs/sector_depth_packs_v0_2.yaml")
    parser.add_argument("--foreign-canary", default="configs/foreign_issuer_source_family_canary_v0_2.yaml")
    parser.add_argument("--output-dir", default="configs")
    parser.add_argument("--batch-id", default="sector_depth_full238_us_v0_2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = load_yaml(args.base_full78)
    additions = load_yaml(args.full128_additions)
    sector = load_yaml(args.sector_depth)
    foreign = load_yaml(args.foreign_canary)
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    companies = build_full238_companies(base, additions, sector)
    annual = build_config(
        batch_id=args.batch_id,
        role="accepted_us_annual_primary",
        form_types=["10-K"],
        years=[2023, 2024, 2025],
        source_policy="SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        companies=companies,
    )
    interim = build_config(
        batch_id=args.batch_id,
        role="accepted_us_latest_interim_candidates",
        form_types=["10-Q"],
        years=[2026, 2027],
        source_policy="SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        companies=companies,
    )
    earnings_8k = build_config(
        batch_id=args.batch_id,
        role="accepted_us_8k_earnings_candidates",
        form_types=["8-K"],
        years=[2026, 2027],
        source_policy="SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        companies=companies,
        extra={
            "source_tier": "company_authored_unaudited_sec_filing",
            "selection": {
                "item_codes": ["2.02", "9.01"],
                "exhibit_types": ["EX-99.1", "EX-99.01", "EX-99"],
                "include_terms": [
                    "earnings",
                    "financial results",
                    "quarterly results",
                    "press release",
                    "reports results",
                    "announces results",
                ],
                "exclude_terms": ["investor presentation", "presentation", "slides", "transcript"],
            },
        },
    )
    foreign_configs = build_foreign_configs(foreign)

    outputs = {
        "annual_10k": output_dir / f"{args.batch_id}_10k_fy2023_2025.yaml",
        "interim_10q": output_dir / f"{args.batch_id}_10q_fy2026_2027.yaml",
        "earnings_8k": output_dir / f"{args.batch_id}_8k_earnings_2026_2027.yaml",
        "foreign_20f": output_dir / "foreign_source_family_canary_20f_2025_2026_v0_2.yaml",
        "foreign_6k": output_dir / "foreign_source_family_canary_6k_2026_v0_2.yaml",
        "foreign_40f": output_dir / "foreign_source_family_canary_40f_2023_2025_v0_2.yaml",
    }
    write_yaml(outputs["annual_10k"], annual)
    write_yaml(outputs["interim_10q"], interim)
    write_yaml(outputs["earnings_8k"], earnings_8k)
    write_yaml(outputs["foreign_20f"], foreign_configs["20f"])
    write_yaml(outputs["foreign_6k"], foreign_configs["6k"])
    write_yaml(outputs["foreign_40f"], foreign_configs["40f"])

    summary = {
        "status": "completed",
        "batch_id": args.batch_id,
        "full238_us_company_count": len(companies),
        "foreign_20f_company_count": len(foreign_configs["20f"]["companies"]),
        "foreign_6k_company_count": len(foreign_configs["6k"]["companies"]),
        "foreign_40f_company_count": len(foreign_configs["40f"]["companies"]),
        "outputs": {key: str(path) for key, path in outputs.items()},
        "accepted_ticker_adjustments": (sector.get("selection_policy", {}) or {}).get("accepted_ticker_adjustments", []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def load_yaml(path: str) -> dict[str, Any]:
    with (REPO_ROOT / path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def build_full238_companies(
    base: dict[str, Any],
    additions: dict[str, Any],
    sector: dict[str, Any],
) -> list[dict[str, Any]]:
    by_ticker: dict[str, dict[str, Any]] = {}
    cik_overrides = {
        str(key).upper(): str(value)
        for key, value in ((sector.get("selection_policy", {}) or {}).get("cik_overrides", {}) or {}).items()
    }

    def add_company(
        ticker: str,
        *,
        category: str,
        category_slug: str,
        source_sets: list[str],
        industry_group: str | None = None,
        pack_id: str | None = None,
        priority: str | None = None,
    ) -> None:
        ticker_upper = str(ticker or "").upper().strip()
        if not ticker_upper:
            return
        row = by_ticker.setdefault(
            ticker_upper,
            {
                "ticker": ticker_upper,
                "category": category,
                "category_slug": category_slug,
                "source_sets": [],
                "sector_depth_packs": [],
                "industry_groups": [],
                "sector_depth_priority": [],
            },
        )
        for source_set in source_sets:
            if source_set not in row["source_sets"]:
                row["source_sets"].append(source_set)
        if industry_group and industry_group not in row["industry_groups"]:
            row["industry_groups"].append(industry_group)
        if pack_id and pack_id not in row["sector_depth_packs"]:
            row["sector_depth_packs"].append(pack_id)
        if priority and priority not in row["sector_depth_priority"]:
            row["sector_depth_priority"].append(priority)
        if ticker_upper in cik_overrides:
            row["cik"] = cik_overrides[ticker_upper]

    for company in base.get("companies", []) or []:
        add_company(
            company.get("ticker"),
            category=str(company.get("category") or "full78_base"),
            category_slug=str(company.get("category_slug") or _slug(company.get("category") or "full78_base")),
            source_sets=["full78_base"],
        )
    for company in additions.get("companies", []) or []:
        add_company(
            company.get("ticker"),
            category=str(company.get("category") or "full128_addition"),
            category_slug=str(company.get("category_slug") or _slug(company.get("category") or "full128_addition")),
            source_sets=["full128_us_addition"],
        )
    for pack in sector.get("packs", []) or []:
        pack_id = str(pack.get("pack_id") or "")
        industry_group = str(pack.get("industry_group") or "")
        candidates = pack.get("candidate_tickers", {}) or {}
        for priority in ("p0", "p1"):
            for ticker in candidates.get(priority, []) or []:
                add_company(
                    ticker,
                    category=industry_group or pack_id or "sector_depth",
                    category_slug=_slug(industry_group or pack_id or "sector_depth"),
                    source_sets=["sector_depth_pack"],
                    industry_group=industry_group,
                    pack_id=pack_id,
                    priority=priority,
                )
    return [normalize_company(row) for row in sorted(by_ticker.values(), key=lambda item: item["ticker"])]


def normalize_company(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "ticker": row["ticker"],
        "category": row["category"],
        "category_slug": row["category_slug"],
        "source_sets": sorted(row.get("source_sets") or []),
    }
    if row.get("sector_depth_packs"):
        normalized["sector_depth_packs"] = sorted(row["sector_depth_packs"])
    if row.get("industry_groups"):
        normalized["industry_groups"] = sorted(row["industry_groups"])
    if row.get("sector_depth_priority"):
        normalized["sector_depth_priority"] = sorted(row["sector_depth_priority"])
    if row.get("cik"):
        normalized["cik"] = str(row["cik"])
    return normalized


def build_config(
    *,
    batch_id: str,
    role: str,
    form_types: list[str],
    years: list[int],
    source_policy: str,
    companies: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "version": "v0.2",
        "batch_id": batch_id,
        "scope": {
            "role": role,
            "target_universe": "full238_us_sector_depth",
            "company_count": len(companies),
            "notes": [
                "Generated by scripts/data_sec/build_sector_depth_expansion_configs.py.",
                "Keep separate from full30/full78 artifacts to avoid scope confusion.",
            ],
        },
        "form_type": form_types[0],
        "form_types": form_types,
        "years": years,
        "source_policy": source_policy,
        "companies": companies,
    }
    if extra:
        payload.update(extra)
    return payload


def build_foreign_configs(foreign: dict[str, Any]) -> dict[str, dict[str, Any]]:
    companies = foreign.get("canary_companies", []) or []

    def rows_for(form: str) -> list[dict[str, Any]]:
        out = []
        for company in companies:
            forms = {str(value).upper() for value in company.get("target_forms", []) or []}
            if form not in forms:
                continue
            out.append(
                {
                    "ticker": str(company.get("ticker") or "").upper(),
                    "category": str(company.get("industry_group") or "foreign_issuer_canary"),
                    "category_slug": _slug(str(company.get("industry_group") or "foreign_issuer_canary")),
                    "source_family": _source_family_for_form(form),
                    "source_gap_policy": company.get("source_gap_policy"),
                    "canary_reason": company.get("canary_reason"),
                }
            )
        return sorted(out, key=lambda item: item["ticker"])

    return {
        "20f": build_foreign_config("20-F", [2025, 2026], rows_for("20-F")),
        "6k": build_foreign_config("6-K", [2026], rows_for("6-K")),
        "40f": build_foreign_config("40-F", [2023, 2024, 2025], rows_for("40-F")),
    }


def build_foreign_config(form_type: str, years: list[int], companies: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "v0.2",
        "batch_id": "foreign_source_family_canary_v0_2",
        "scope": {
            "role": f"{form_type.lower().replace('-', '')}_source_family_canary",
            "target_universe": "foreign_source_family_canary",
            "company_count": len(companies),
            "notes": [
                "Parser canary only; do not treat foreign forms as 10-K/10-Q equivalents.",
                "Generated by scripts/data_sec/build_sector_depth_expansion_configs.py.",
            ],
        },
        "form_type": form_type,
        "form_types": [form_type],
        "years": years,
        "source_policy": "SEC_FOREIGN_SOURCE_FAMILY_CANARY",
        "companies": companies,
    }


def _source_family_for_form(form: str) -> str:
    return {
        "20-F": "foreign_primary_annual",
        "6-K": "foreign_company_authored_interim",
        "40-F": "canadian_primary_annual",
    }.get(form, "foreign_source_family_canary")


def _slug(value: Any) -> str:
    text = str(value or "").lower().strip()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_") or "uncategorized"


if __name__ == "__main__":
    raise SystemExit(main())
