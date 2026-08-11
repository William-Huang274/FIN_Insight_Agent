from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_non_us_supply_chain_disclosure_coverage_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_non_us_supply_chain_disclosure_coverage_summary_v0.1"
DEFAULT_SOURCE_PLAN = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_v0_1.jsonl"
DEFAULT_PROFILES = REPO_ROOT / "configs" / "data_sources" / "global_public_disclosure_profiles_v0_1.yaml"
DEFAULT_DOWNLOAD_MANIFESTS = [
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_kr_dart_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_eu_ifx_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_tw_mops_portal_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_hkex_cninfo_portal_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_jp_company_ir_fallback_download_clean_v0_1.jsonl",
]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "non_us_supply_chain_primary_disclosure_coverage_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "non_us_supply_chain_primary_disclosure_coverage_summary_v0_1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize non-US supply-chain primary disclosure download and cleaning coverage.")
    parser.add_argument("--source-plan", type=Path, default=DEFAULT_SOURCE_PLAN)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--download-manifest", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_plan = _load_jsonl(_resolve(args.source_plan))
    profiles_config = _load_yaml(_resolve(args.profiles))
    download_paths = [_resolve(path) for path in (args.download_manifest or DEFAULT_DOWNLOAD_MANIFESTS)]
    download_rows = []
    for path in download_paths:
        if path.exists():
            download_rows.extend(_load_jsonl(path))
    coverage_rows = build_coverage_rows(source_plan=source_plan, profiles_config=profiles_config, download_rows=download_rows)
    output = _resolve(args.output)
    summary_output = _resolve(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output, coverage_rows)
    summary = summarize_coverage_rows(coverage_rows=coverage_rows, output=output, summary_output=summary_output, download_paths=download_paths)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in {"pass", "pass_with_gaps"} else 1


def build_coverage_rows(
    *,
    source_plan: Iterable[Mapping[str, Any]],
    profiles_config: Mapping[str, Any],
    download_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    profiles = profiles_config.get("profiles") or {}
    downloads_by_plan_id = {str(row.get("plan_id") or ""): dict(row) for row in download_rows if row.get("plan_id")}
    coverage_rows: list[dict[str, Any]] = []
    for plan in source_plan:
        plan_id = str(plan.get("plan_id") or "")
        profile_name = str(plan.get("disclosure_profile") or "")
        profile = profiles.get(profile_name) or {}
        downloaded = downloads_by_plan_id.get(plan_id)
        base = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "task_id": f"DOWNLOAD::{plan_id}",
            "ticker": plan.get("ticker"),
            "company_name": plan.get("company_name"),
            "country": plan.get("country"),
            "listing_exchange": plan.get("listing_exchange"),
            "exchange_symbol": plan.get("exchange_symbol"),
            "disclosure_profile": profile_name,
            "fiscal_year": plan.get("fiscal_year"),
            "report_type": plan.get("report_type"),
            "source_family": plan.get("source_family"),
            "source_tier": plan.get("source_tier"),
            "source_boundary": plan.get("source_boundary"),
            "download_strategy": profile.get("locator_strategy") or plan.get("locator_strategy"),
            "download_implementation_status": profile.get("download_implementation_status") or "",
            "parser_implementation_status": profile.get("parser_implementation_status") or "",
            "mainline_vector_promotion_allowed": False,
            "relationship_edge_candidate_allowed": bool(plan.get("relationship_edge_candidate_allowed")),
        }
        if downloaded and downloaded.get("document_downloaded"):
            coverage_rows.append(
                {
                    **base,
                    "coverage_status": "downloaded_cleaned" if downloaded.get("cleaned_text_status") == "cleaned_text_written" else "downloaded_raw_parser_pending",
                    "gap_type": "",
                    "gap_detail": "",
                    "document_path": downloaded.get("document_path", ""),
                    "document_url": downloaded.get("document_url", ""),
                    "download_status": downloaded.get("download_status", ""),
                    "downloaded_bytes": downloaded.get("downloaded_bytes", 0),
                    "sha256": downloaded.get("sha256", ""),
                    "cleaned_text_path": downloaded.get("cleaned_text_path", ""),
                    "cleaned_text_char_count": downloaded.get("cleaned_text_char_count", 0),
                    "cleaned_text_status": downloaded.get("cleaned_text_status", ""),
                    "parser_status": downloaded.get("parser_status", ""),
                    "promotion_status": "staging_only_table_parser_and_source_boundary_gate_pending",
                }
            )
            continue
        gap_type, gap_detail = infer_gap(profile_name=profile_name, profile=profile)
        coverage_rows.append(
            {
                **base,
                "coverage_status": "gap",
                "gap_type": gap_type,
                "gap_detail": gap_detail,
                "document_path": "",
                "document_url": "",
                "download_status": "",
                "downloaded_bytes": 0,
                "sha256": "",
                "cleaned_text_path": "",
                "cleaned_text_char_count": 0,
                "cleaned_text_status": "",
                "parser_status": profile.get("parser_implementation_status") or "",
                "promotion_status": "blocked_until_profile_downloader_and_parser_pass",
            }
        )
    return sorted(coverage_rows, key=lambda row: (str(row.get("ticker") or ""), int(row.get("fiscal_year") or 0), str(row.get("report_type") or "")))


def infer_gap(*, profile_name: str, profile: Mapping[str, Any]) -> tuple[str, str]:
    api_key_env = str(profile.get("api_key_env") or "").strip()
    implementation_status = str(profile.get("download_implementation_status") or "").strip()
    blocker = str(profile.get("download_blocker") or "").strip()
    if profile_name == "jp_edinet_annual_securities_report" and api_key_env:
        return "edinet_api_key_invalid_or_key_backed_smoke_failed", blocker or f"{api_key_env} must be configured and validated."
    if implementation_status == "profile_specific_scaffold_pending":
        return "profile_specific_portal_downloader_pending", blocker or "Profile-specific official portal downloader is not implemented."
    if api_key_env and "blocked_requires_official_api_key" in implementation_status:
        return "missing_official_api_key", blocker or f"{api_key_env} must be configured."
    return "download_not_run_or_unmatched", blocker or "No downloaded row matched this source-plan task."


def summarize_coverage_rows(
    *,
    coverage_rows: list[Mapping[str, Any]],
    output: Path,
    summary_output: Path,
    download_paths: list[Path],
) -> dict[str, Any]:
    downloaded_rows = [row for row in coverage_rows if row.get("coverage_status") != "gap"]
    gap_rows = [row for row in coverage_rows if row.get("coverage_status") == "gap"]
    unique_doc_hashes = {str(row.get("sha256") or "") for row in downloaded_rows if row.get("sha256")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass_with_gaps" if gap_rows else "pass",
        "plan_row_count": len(coverage_rows),
        "company_count": len({str(row.get("ticker") or "") for row in coverage_rows}),
        "downloaded_row_count": len(downloaded_rows),
        "downloaded_company_count": len({str(row.get("ticker") or "") for row in downloaded_rows}),
        "downloaded_unique_document_count": len(unique_doc_hashes),
        "downloaded_byte_count": sum(int(row.get("downloaded_bytes") or 0) for row in downloaded_rows),
        "cleaned_text_row_count": sum(1 for row in downloaded_rows if row.get("cleaned_text_status") == "cleaned_text_written"),
        "cleaned_text_char_count": sum(int(row.get("cleaned_text_char_count") or 0) for row in downloaded_rows),
        "gap_row_count": len(gap_rows),
        "gap_company_count": len({str(row.get("ticker") or "") for row in gap_rows}),
        "coverage_status_counts": dict(sorted(Counter(str(row.get("coverage_status") or "unknown") for row in coverage_rows).items())),
        "profile_counts": dict(sorted(Counter(str(row.get("disclosure_profile") or "unknown") for row in coverage_rows).items())),
        "profile_downloaded_counts": dict(sorted(Counter(str(row.get("disclosure_profile") or "unknown") for row in downloaded_rows).items())),
        "profile_gap_counts": dict(sorted(Counter(str(row.get("disclosure_profile") or "unknown") for row in gap_rows).items())),
        "gap_type_counts": dict(sorted(Counter(str(row.get("gap_type") or "none") for row in gap_rows).items())),
        "gap_companies_by_profile": {
            profile: sorted(tickers)
            for profile, tickers in sorted(_group_tickers_by_profile(gap_rows).items())
        },
        "downloaded_companies_by_profile": {
            profile: sorted(tickers)
            for profile, tickers in sorted(_group_tickers_by_profile(downloaded_rows).items())
        },
        "download_manifests": [_path_for_metadata(path) for path in download_paths],
        "outputs": {"coverage_rows": _path_for_metadata(output), "summary": _path_for_metadata(summary_output)},
    }


def _group_tickers_by_profile(rows: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        grouped[str(row.get("disclosure_profile") or "unknown")].add(str(row.get("ticker") or ""))
    return grouped


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


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _path_for_metadata(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
