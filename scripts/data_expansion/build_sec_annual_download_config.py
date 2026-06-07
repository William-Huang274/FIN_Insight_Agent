from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier1_sp500_plus_current_manifest.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "configs" / "data_sources" / "tier1_sp500_us_annual_10k_fy2023_2025.yaml"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "tier1_sp500_us_annual_download_config_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_sec_annual_download_config_v0.1"
ANNUAL_SEC_FORM_TYPES = {"10-K", "20-F", "40-F"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SEC annual 10-K download config from a universe manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--form-types", default="10-K")
    parser.add_argument("--dataset-id", default="tier1_sp500_us_annual_v0_1")
    parser.add_argument("--universe-tier", default="tier1_sp500_plus_current")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--respect-target-forms",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use per-company target_forms when present, keeping only annual SEC forms.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = _load_jsonl(_resolve(args.manifest))
    config, skipped = build_sec_annual_download_config(
        rows,
        years=_csv_ints(args.years),
        form_types=_csv_strings(args.form_types, upper=True),
        dataset_id=args.dataset_id,
        universe_tier=args.universe_tier,
        limit=args.limit,
        respect_target_forms=args.respect_target_forms,
    )
    output_path = _resolve(args.output)
    summary_path = _resolve(args.summary_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    summary = summarize_config(config=config, skipped=skipped, output_path=output_path, summary_path=summary_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_sec_annual_download_config(
    manifest_rows: Iterable[Mapping[str, Any]],
    *,
    years: list[int],
    form_types: list[str],
    dataset_id: str,
    universe_tier: str,
    limit: int = 0,
    respect_target_forms: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    companies: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in manifest_rows:
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
        company_form_types = _company_annual_form_types(
            raw,
            fallback_form_types=form_types,
            respect_target_forms=respect_target_forms,
        )
        if not company_form_types:
            skipped.append({"ticker": ticker, "reason": "no_annual_sec_form_type"})
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
                "form_types": company_form_types,
                "target_forms": _string_list(raw.get("target_forms")),
            }
        )
        if limit and len(companies) >= limit:
            break
    config = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "source_family": "sec_primary_filing",
        "source_tier": "primary_sec_filing",
        "universe_tier": universe_tier,
        "form_type": form_types[0] if form_types else "10-K",
        "form_types": form_types or ["10-K"],
        "years": years,
        "companies": companies,
    }
    return config, skipped


def summarize_config(
    *,
    config: Mapping[str, Any],
    skipped: list[Mapping[str, Any]],
    output_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    companies = list(config.get("companies") or [])
    years = list(config.get("years") or [])
    global_form_types = list(config.get("form_types") or [])
    expected_tasks = 0
    company_form_counts: dict[str, int] = {}
    for company in companies:
        company_forms = _string_list(company.get("form_types")) or global_form_types
        company_form_counts[str(company.get("ticker") or "")] = len(company_forms)
        expected_tasks += len(years) * len(company_forms)
    return {
        "schema_version": "fin_agent_sec_annual_download_config_summary_v0.1",
        "status": "pass" if companies else "fail",
        "dataset_id": config.get("dataset_id"),
        "source_family": config.get("source_family"),
        "source_tier": config.get("source_tier"),
        "universe_tier": config.get("universe_tier"),
        "company_count": len(companies),
        "years": years,
        "form_types": global_form_types,
        "company_form_type_counts": company_form_counts,
        "expected_filing_tasks": expected_tasks,
        "skipped_count": len(skipped),
        "skipped": skipped[:100],
        "outputs": {"config": _path_for_metadata(output_path), "summary": _path_for_metadata(summary_path)},
    }


def _csv_ints(raw: str) -> list[int]:
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def _csv_strings(raw: str, *, upper: bool = False) -> list[str]:
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return [value.upper() for value in values] if upper else values


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "uncategorized"


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits.zfill(10) if digits else ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _company_annual_form_types(
    row: Mapping[str, Any],
    *,
    fallback_form_types: list[str],
    respect_target_forms: bool,
) -> list[str]:
    target_forms = [form.upper() for form in _string_list(row.get("target_forms"))]
    if respect_target_forms and target_forms:
        allowed = {form.upper() for form in fallback_form_types}
        return sorted({form for form in target_forms if form in ANNUAL_SEC_FORM_TYPES and (not allowed or form in allowed)})
    return [form.upper() for form in fallback_form_types if form.upper() in ANNUAL_SEC_FORM_TYPES]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _path_for_metadata(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
