from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIER1_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier1_sp500_plus_current_manifest.jsonl"
DEFAULT_TIER2_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier2_supply_chain_supplement_manifest.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "configs" / "data_sources"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "tier1_tier2_sec_full_source_download_config_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_sec_full_source_download_config_v0.1"
DEFAULT_US_TARGET_FORMS = ["10-K", "10-Q", "8-K"]
EARNINGS_8K_SELECTION = {
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
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Tier1/Tier2 SEC full-source expansion configs.")
    parser.add_argument("--tier1-manifest", type=Path, default=DEFAULT_TIER1_MANIFEST)
    parser.add_argument("--tier2-manifest", type=Path, default=DEFAULT_TIER2_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--annual-years", default="2023,2024,2025")
    parser.add_argument("--interim-years", default="2026,2027")
    parser.add_argument("--event-years", default="2026,2027")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tier1_rows = _load_jsonl(_resolve(args.tier1_manifest))
    tier2_rows = _load_jsonl(_resolve(args.tier2_manifest))
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = _resolve(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    configs = build_sec_full_source_configs(
        tier1_rows=tier1_rows,
        tier2_rows=tier2_rows,
        interim_years=_csv_ints(args.interim_years),
        event_years=_csv_ints(args.event_years),
        limit=args.limit,
    )
    outputs = write_configs(configs, output_dir=output_dir)
    summary = summarize_configs(configs, outputs=outputs, summary_path=summary_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def build_sec_full_source_configs(
    *,
    tier1_rows: Iterable[Mapping[str, Any]],
    tier2_rows: Iterable[Mapping[str, Any]],
    interim_years: list[int],
    event_years: list[int],
    limit: int = 0,
) -> dict[str, dict[str, Any]]:
    tier1_companies, tier1_skipped = _build_companies(
        tier1_rows,
        universe_tier="tier1_sp500_plus_current",
        allowed_forms={"10-Q", "8-K"},
        default_target_forms=DEFAULT_US_TARGET_FORMS,
        limit=limit,
    )
    tier2_companies, tier2_skipped = _build_companies(
        tier2_rows,
        universe_tier="tier2_supply_chain_supplement",
        allowed_forms={"10-Q", "8-K", "6-K"},
        default_target_forms=[],
        limit=limit,
    )

    return {
        "tier1_sp500_us_interim_10q_fy2026_2027": _config(
            dataset_id="tier1_sp500_us_interim_10q_fy2026_2027_v0_1",
            universe_tier="tier1_sp500_plus_current",
            source_tier="primary_sec_filing",
            source_family="sec_primary_filing",
            form_types=["10-Q"],
            years=interim_years,
            companies=_filter_companies_by_form(tier1_companies, "10-Q"),
            skipped=tier1_skipped,
        ),
        "tier1_sp500_us_8k_earnings_2026_2027": _config(
            dataset_id="tier1_sp500_us_8k_earnings_2026_2027_v0_1",
            universe_tier="tier1_sp500_plus_current",
            source_tier="company_authored_unaudited_sec_filing",
            source_family="sec_8k_earnings_release",
            form_types=["8-K"],
            years=event_years,
            companies=_filter_companies_by_form(tier1_companies, "8-K"),
            skipped=tier1_skipped,
            extra={"selection": EARNINGS_8K_SELECTION},
        ),
        "tier2_supply_chain_sec_interim_10q_fy2026_2027": _config(
            dataset_id="tier2_supply_chain_sec_interim_10q_fy2026_2027_v0_1",
            universe_tier="tier2_supply_chain_supplement",
            source_tier="primary_sec_filing",
            source_family="sec_primary_filing",
            form_types=["10-Q"],
            years=interim_years,
            companies=_filter_companies_by_form(tier2_companies, "10-Q"),
            skipped=tier2_skipped,
        ),
        "tier2_supply_chain_sec_8k_earnings_2026_2027": _config(
            dataset_id="tier2_supply_chain_sec_8k_earnings_2026_2027_v0_1",
            universe_tier="tier2_supply_chain_supplement",
            source_tier="company_authored_unaudited_sec_filing",
            source_family="sec_8k_earnings_release",
            form_types=["8-K"],
            years=event_years,
            companies=_filter_companies_by_form(tier2_companies, "8-K"),
            skipped=tier2_skipped,
            extra={"selection": EARNINGS_8K_SELECTION},
        ),
        "tier2_supply_chain_sec_6k_2026_2027": _config(
            dataset_id="tier2_supply_chain_sec_6k_2026_2027_v0_1",
            universe_tier="tier2_supply_chain_supplement",
            source_tier="primary_sec_filing",
            source_family="sec_primary_filing",
            form_types=["6-K"],
            years=event_years,
            companies=_filter_companies_by_form(tier2_companies, "6-K"),
            skipped=tier2_skipped,
            status="reserved_parser_gap",
            extra={
                "known_gap": "6-K needs a profile-aware event/interim selector and parser before promotion; do not parse it with 10-K item rules.",
            },
        ),
    }


def write_configs(configs: Mapping[str, Mapping[str, Any]], *, output_dir: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for name, config in configs.items():
        path = output_dir / f"{name}.yaml"
        path.write_text(yaml.safe_dump(dict(config), sort_keys=False, allow_unicode=True), encoding="utf-8")
        outputs[name] = _path_for_metadata(path)
    return outputs


def summarize_configs(
    configs: Mapping[str, Mapping[str, Any]],
    *,
    outputs: Mapping[str, str],
    summary_path: Path,
) -> dict[str, Any]:
    config_summaries: dict[str, Any] = {}
    total_companies = set()
    for name, config in configs.items():
        companies = list(config.get("companies") or [])
        for company in companies:
            total_companies.add(str(company.get("ticker") or ""))
        years = list(config.get("years") or [])
        form_types = list(config.get("form_types") or [])
        config_summaries[name] = {
            "dataset_id": config.get("dataset_id"),
            "status": config.get("status") or "active",
            "company_count": len(companies),
            "years": years,
            "form_types": form_types,
            "expected_tasks": len(companies) * len(years) * max(1, len(form_types)),
            "form_target_counts": dict(Counter(form for company in companies for form in _string_list(company.get("target_forms")))),
            "output": outputs.get(name),
        }
    active_company_configs = [
        summary for summary in config_summaries.values() if summary["status"] != "reserved_parser_gap" and summary["company_count"] > 0
    ]
    return {
        "schema_version": "fin_agent_sec_full_source_download_config_summary_v0.1",
        "status": "pass" if active_company_configs else "fail",
        "config_count": len(configs),
        "covered_company_count": len(total_companies),
        "configs": config_summaries,
        "outputs": {**dict(outputs), "summary": _path_for_metadata(summary_path)},
    }


def _build_companies(
    rows: Iterable[Mapping[str, Any]],
    *,
    universe_tier: str,
    allowed_forms: set[str],
    default_target_forms: list[str],
    limit: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    companies: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        ticker = str(raw.get("ticker") or "").upper().strip()
        if not ticker:
            skipped.append({"ticker": "", "reason": "missing_ticker"})
            continue
        if ticker in seen:
            skipped.append({"ticker": ticker, "reason": "duplicate_ticker"})
            continue
        seen.add(ticker)
        if str(raw.get("universe_tier") or "") != universe_tier:
            skipped.append({"ticker": ticker, "reason": "outside_universe_tier"})
            continue
        if not raw.get("sec_download_eligible"):
            skipped.append({"ticker": ticker, "reason": "not_sec_download_eligible"})
            continue
        cik = _normalize_cik(raw.get("cik"))
        if not cik:
            skipped.append({"ticker": ticker, "reason": "missing_cik"})
            continue
        target_forms = _string_list(raw.get("target_forms")) or default_target_forms
        target_forms = [form.upper() for form in target_forms if form.upper() in allowed_forms]
        if not target_forms:
            skipped.append({"ticker": ticker, "reason": "no_allowed_full_source_form"})
            continue
        category = str(raw.get("category") or raw.get("sector") or "uncategorized").strip() or "uncategorized"
        companies.append(
            {
                "ticker": ticker,
                "cik": cik,
                "company_name": str(raw.get("company_name") or "").strip(),
                "category": category,
                "category_slug": _slugify(category),
                "sector": str(raw.get("sector") or "").strip(),
                "source_sets": _string_list(raw.get("source_sets")),
                "universe_tier": universe_tier,
                "form_types": target_forms,
                "target_forms": target_forms,
            }
        )
        if limit and len(companies) >= limit:
            break
    return companies, skipped


def _filter_companies_by_form(companies: Iterable[Mapping[str, Any]], form_type: str) -> list[dict[str, Any]]:
    form = form_type.upper()
    out: list[dict[str, Any]] = []
    for company in companies:
        if form not in {item.upper() for item in _string_list(company.get("target_forms"))}:
            continue
        row = dict(company)
        row["form_types"] = [form]
        out.append(row)
    return out


def _config(
    *,
    dataset_id: str,
    universe_tier: str,
    source_tier: str,
    source_family: str,
    form_types: list[str],
    years: list[int],
    companies: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    status: str = "active",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "status": status,
        "source_family": source_family,
        "source_tier": source_tier,
        "universe_tier": universe_tier,
        "form_type": form_types[0] if form_types else "",
        "form_types": form_types,
        "years": years,
        "companies": companies,
        "skipped_count": len(skipped),
        "skipped_sample": skipped[:100],
    }
    if extra:
        payload.update(dict(extra))
    return payload


def _csv_ints(raw: str) -> list[int]:
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "uncategorized"


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits.zfill(10) if digits else ""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _path_for_metadata(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
