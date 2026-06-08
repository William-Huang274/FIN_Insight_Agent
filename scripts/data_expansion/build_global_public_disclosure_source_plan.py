from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLOBAL_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier2_supply_chain_supplement_manifest.jsonl"
DEFAULT_PROFILES = REPO_ROOT / "configs" / "data_sources" / "global_public_disclosure_profiles_v0_1.yaml"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_global_public_disclosure_source_plan_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a source-discovery plan for Tier2 non-US public disclosure companies.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_GLOBAL_MANIFEST)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--years", default="", help="Comma-separated fiscal years. Defaults to profiles.default_years.")
    parser.add_argument("--include-interim", action="store_true", help="Also include quarterly, semiannual, and interim reports.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_rows = _load_jsonl(_resolve(args.manifest))
    profiles_config = _load_yaml(_resolve(args.profiles))
    years = _parse_years(args.years) or [int(year) for year in profiles_config.get("default_years") or []]
    plan_rows, issues = build_global_public_disclosure_source_plan(
        manifest_rows=manifest_rows,
        profiles_config=profiles_config,
        years=years,
        include_interim=args.include_interim,
    )
    output = _resolve(args.output)
    summary_output = _resolve(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output, plan_rows)
    summary = summarize_source_plan(plan_rows=plan_rows, issues=issues, output_path=output, summary_path=summary_output)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def build_global_public_disclosure_source_plan(
    *,
    manifest_rows: Iterable[Mapping[str, Any]],
    profiles_config: Mapping[str, Any],
    years: Iterable[int],
    include_interim: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    profiles = profiles_config.get("profiles") or {}
    annual_like = {str(value) for value in profiles_config.get("annual_like_report_types") or []}
    interim = {str(value) for value in profiles_config.get("interim_report_types") or []}
    allowed_report_types = set(annual_like)
    if include_interim:
        allowed_report_types.update(interim)
    plan_rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    years_list = [int(year) for year in years]
    seen_ids: set[str] = set()

    for row in manifest_rows:
        if not row.get("global_public_download_eligible"):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        profile_name = str(row.get("disclosure_profile") or "").strip()
        profile = profiles.get(profile_name)
        if not profile:
            issues.append({"type": "missing_profile", "ticker": ticker, "disclosure_profile": profile_name})
            continue
        official_sources = _official_sources(row.get("official_sources"))
        if not official_sources:
            issues.append({"type": "missing_official_sources", "ticker": ticker, "disclosure_profile": profile_name})
            continue
        profile_annual_reports = [report for report in _string_list(profile.get("annual_report_types")) if report in allowed_report_types]
        profile_interim_reports = [report for report in _string_list(profile.get("interim_report_types")) if include_interim and report in allowed_report_types]
        include_overrides = [report for report in _string_list(row.get("report_type_include_overrides")) if report in allowed_report_types]
        exclude_overrides = {report for report in _string_list(row.get("report_type_exclude_overrides")) if report in allowed_report_types}
        if (include_overrides or exclude_overrides) and not str(row.get("report_type_override_reason") or "").strip():
            issues.append({"type": "report_type_override_reason_required", "ticker": ticker, "disclosure_profile": profile_name})
            continue
        deprecated_company_targets = [report for report in _string_list(row.get("target_reports")) if report in allowed_report_types]
        if deprecated_company_targets:
            issues.append({"type": "deprecated_company_level_target_reports", "ticker": ticker, "disclosure_profile": profile_name})
            continue
        selected_reports = [report for report in _unique_strings([*profile_annual_reports, *profile_interim_reports, *include_overrides]) if report not in exclude_overrides]
        if not selected_reports:
            issues.append({"type": "no_selected_report_types", "ticker": ticker, "disclosure_profile": profile_name})
            continue
        for fiscal_year in years_list:
            for report_type in selected_reports:
                plan_id = "GLOBALDISC::{ticker}::{profile}::{year}::{report}".format(
                    ticker=_slug(ticker),
                    profile=_slug(profile_name),
                    year=fiscal_year,
                    report=_slug(report_type),
                )
                if plan_id in seen_ids:
                    issues.append({"type": "duplicate_plan_id", "plan_id": plan_id, "ticker": ticker})
                    continue
                seen_ids.add(plan_id)
                plan_rows.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "plan_id": plan_id,
                        "ticker": ticker,
                        "issuer_id": str(row.get("issuer_id") or ticker).strip(),
                        "exchange_symbol": str(row.get("exchange_symbol") or "").strip(),
                        "company_name": str(row.get("company_name") or "").strip(),
                        "country": str(row.get("country") or "").strip(),
                        "listing_exchange": str(row.get("listing_exchange") or "").strip(),
                        "sector": str(row.get("sector") or "").strip(),
                        "industry_group": str(row.get("category") or "").strip(),
                        "supply_chain_role": str(row.get("supply_chain_role") or "").strip(),
                        "priority": str(row.get("priority") or "").strip(),
                        "source_family": str(row.get("source_family") or profile.get("source_family") or "global_public_annual_report").strip(),
                        "source_tier": str(profile.get("source_tier") or "primary_company_disclosure").strip(),
                        "disclosure_profile": profile_name,
                        "parser_profile": str(profile.get("parser_profile") or "").strip(),
                        "locator_strategy": str(profile.get("locator_strategy") or "").strip(),
                        "regulator_or_exchange": str(profile.get("regulator_or_exchange") or "").strip(),
                        "fiscal_year": fiscal_year,
                        "report_type": report_type,
                        "report_type_rule_source": "disclosure_profile",
                        "report_type_include_overrides": include_overrides,
                        "report_type_exclude_overrides": sorted(exclude_overrides),
                        "report_type_override_reason": str(row.get("report_type_override_reason") or "").strip(),
                        "reporting_currency": str(row.get("reporting_currency") or "").strip(),
                        "official_sources": official_sources,
                        "preferred_source_kinds": _string_list(profile.get("preferred_source_kinds")),
                        "source_locator_urls": _preferred_locator_urls(official_sources, _string_list(profile.get("preferred_source_kinds"))),
                        "cache_dir": _cache_dir(profile=profile, row=row, fiscal_year=fiscal_year, report_type=report_type),
                        "expected_artifact_globs": _expected_artifact_globs(profile=profile, row=row, fiscal_year=fiscal_year, report_type=report_type),
                        "document_status": "planned_locator_only",
                        "discovery_method": "official_source_locator_from_tier2_manifest",
                        "mainline_vector_promotion_allowed": False,
                        "relationship_edge_candidate_allowed": True,
                        "source_boundary": "primary_company_disclosure_not_news_lead",
                    }
                )
    return sorted(plan_rows, key=lambda item: (str(item["ticker"]), int(item["fiscal_year"]), str(item["report_type"]))), issues


def summarize_source_plan(
    *,
    plan_rows: list[Mapping[str, Any]],
    issues: list[Mapping[str, Any]],
    output_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    company_count = len({str(row.get("ticker") or "") for row in plan_rows})
    return {
        "schema_version": "fin_agent_global_public_disclosure_source_plan_summary_v0.1",
        "status": "fail" if issues else "pass",
        "plan_row_count": len(plan_rows),
        "company_count": company_count,
        "profile_counts": dict(sorted(Counter(str(row.get("disclosure_profile") or "unknown") for row in plan_rows).items())),
        "country_counts": dict(sorted(Counter(str(row.get("country") or "unknown") for row in plan_rows).items())),
        "report_type_counts": dict(sorted(Counter(str(row.get("report_type") or "unknown") for row in plan_rows).items())),
        "report_type_rule_source_counts": dict(sorted(Counter(str(row.get("report_type_rule_source") or "unknown") for row in plan_rows).items())),
        "source_family_counts": dict(sorted(Counter(str(row.get("source_family") or "unknown") for row in plan_rows).items())),
        "issue_counts": dict(sorted(Counter(str(issue.get("type") or "unknown") for issue in issues).items())),
        "issues": list(issues),
        "outputs": {"source_plan": str(output_path), "summary": str(summary_path)},
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


def _parse_years(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _official_sources(value: Any) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    if not isinstance(value, list):
        return sources
    for item in value:
        if not isinstance(item, Mapping):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        sources.append({"kind": str(item.get("kind") or "source").strip(), "url": url})
    return sources


def _preferred_locator_urls(sources: list[Mapping[str, str]], preferred_kinds: list[str]) -> list[str]:
    preferred = [str(kind) for kind in preferred_kinds]
    ordered: list[str] = []
    for kind in preferred:
        ordered.extend(str(source.get("url") or "") for source in sources if source.get("kind") == kind and source.get("url"))
    ordered.extend(str(source.get("url") or "") for source in sources if source.get("url"))
    return _unique_strings(ordered)


def _cache_dir(*, profile: Mapping[str, Any], row: Mapping[str, Any], fiscal_year: int, report_type: str) -> str:
    namespace = str(profile.get("cache_namespace") or "global_public").strip()
    ticker = _slug(str(row.get("ticker") or "unknown"))
    return (Path("data/raw_private/global_public_disclosures") / namespace / ticker / str(fiscal_year) / _slug(report_type)).as_posix()


def _expected_artifact_globs(*, profile: Mapping[str, Any], row: Mapping[str, Any], fiscal_year: int, report_type: str) -> list[str]:
    cache_dir = _cache_dir(profile=profile, row=row, fiscal_year=fiscal_year, report_type=report_type)
    return [
        (Path(cache_dir) / "*.pdf").as_posix(),
        (Path(cache_dir) / "*.html").as_posix(),
        (Path(cache_dir) / "*.xhtml").as_posix(),
        (Path(cache_dir) / "metadata.json").as_posix(),
    ]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().upper()).strip("_")
    return text or "UNKNOWN"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
