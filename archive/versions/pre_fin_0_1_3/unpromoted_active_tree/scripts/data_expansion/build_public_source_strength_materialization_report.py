from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_SCHEMA_VERSION = "fin_agent_public_source_strength_materialization_matrix_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_source_strength_materialization_summary_v0.1"
DEFAULT_STRENGTH_CONFIG = REPO_ROOT / "configs" / "data_sources" / "public_source_information_strength_v0_1.yaml"
DEFAULT_NON_US_SOURCE_PLAN = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_v0_1.jsonl"
DEFAULT_DOWNLOAD_MANIFESTS = [
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_kr_dart_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_eu_ifx_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_tw_mops_portal_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_hkex_cninfo_portal_download_clean_v0_1.jsonl",
    REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_jp_company_ir_fallback_download_clean_v0_1.jsonl",
]
DEFAULT_INVENTORY_ADAPTER_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_source_inventory_adapter_summary_v0_1.json"
DEFAULT_SEC_STRUCTURED_FACTS_SUMMARY = REPO_ROOT / "data" / "manifests" / "sec_structured_facts_download_summary_v0_1.json"
DEFAULT_SEC_ANNUAL_STAGING_SUMMARY = REPO_ROOT / "data" / "manifests" / "tier2_supply_chain_sec_annual_staging_assets_summary_v0_2.json"
DEFAULT_NORMALIZED_SNAPSHOT_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_source_normalized_snapshot_summary_v0_1.json"
DEFAULT_EXTENDED_MATERIALIZATION_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_source_extended_materialization_summary_v0_1.json"
DEFAULT_INDUSTRY_SNAPSHOT_METADATA = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "industry_data"
    / "20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales"
    / "industry_snapshot_metadata.json"
)
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "public_source_strength_materialization_matrix_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_source_strength_materialization_summary_v0_1.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "public_source_strength_materialization.zh-CN.md"

PROFILE_OFFICIAL_SOURCE_ID = {
    "kr_dart_business_report": "kr_dart_openapi",
    "tw_mops_annual_report": "tw_mops_portal",
    "jp_edinet_annual_securities_report": "jp_edinet_api",
    "hkex_annual_report": "hkexnews_portal",
    "szse_cninfo_annual_report": "cninfo_portal",
    "eu_regulated_annual_report": "company_ir_reports",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build S5-S0 materialization matrix for public source strength tiers.")
    parser.add_argument("--strength-config", type=Path, default=DEFAULT_STRENGTH_CONFIG)
    parser.add_argument("--non-us-source-plan", type=Path, default=DEFAULT_NON_US_SOURCE_PLAN)
    parser.add_argument("--download-manifest", type=Path, action="append", default=[])
    parser.add_argument("--inventory-adapter-summary", type=Path, default=DEFAULT_INVENTORY_ADAPTER_SUMMARY)
    parser.add_argument("--sec-structured-facts-summary", type=Path, default=DEFAULT_SEC_STRUCTURED_FACTS_SUMMARY)
    parser.add_argument("--sec-annual-staging-summary", type=Path, default=DEFAULT_SEC_ANNUAL_STAGING_SUMMARY)
    parser.add_argument("--normalized-snapshot-summary", type=Path, default=DEFAULT_NORMALIZED_SNAPSHOT_SUMMARY)
    parser.add_argument("--extended-materialization-summary", type=Path, default=DEFAULT_EXTENDED_MATERIALIZATION_SUMMARY)
    parser.add_argument("--industry-snapshot-metadata", type=Path, default=DEFAULT_INDUSTRY_SNAPSHOT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    strength_config = _load_yaml(_resolve(args.strength_config))
    source_plan_rows = _read_jsonl(_resolve(args.non_us_source_plan)) if _resolve(args.non_us_source_plan).exists() else []
    download_paths = [_resolve(path) for path in (args.download_manifest or DEFAULT_DOWNLOAD_MANIFESTS)]
    download_rows: list[dict[str, Any]] = []
    for path in download_paths:
        if path.exists():
            download_rows.extend(_read_jsonl(path))
    inventory_summary = _read_json(_resolve(args.inventory_adapter_summary))
    sec_structured_summary = _read_json(_resolve(args.sec_structured_facts_summary))
    sec_annual_summary = _read_json(_resolve(args.sec_annual_staging_summary))
    normalized_snapshot_summary = _read_json(_resolve(args.normalized_snapshot_summary))
    extended_materialization_summary = _read_json(_resolve(args.extended_materialization_summary))
    industry_snapshot_metadata = _read_json(_resolve(args.industry_snapshot_metadata))
    generated_at = datetime.now(timezone.utc).isoformat()

    rows = build_materialization_rows(
        strength_config=strength_config,
        non_us_source_plan_rows=source_plan_rows,
        download_rows=download_rows,
        inventory_summary=inventory_summary,
        sec_structured_summary=sec_structured_summary,
        sec_annual_summary=sec_annual_summary,
        normalized_snapshot_summary=normalized_snapshot_summary,
        extended_materialization_summary=extended_materialization_summary,
        industry_snapshot_metadata=industry_snapshot_metadata,
        generated_at=generated_at,
    )
    output = _resolve(args.output)
    summary_output = _resolve(args.summary_output)
    report_output = _resolve(args.report_output)
    summary = summarize_materialization_rows(
        rows=rows,
        download_paths=download_paths,
        output=output,
        summary_output=summary_output,
        report_output=report_output,
        generated_at=generated_at,
    )
    _write_jsonl(output, rows)
    _write_json(summary_output, summary)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary, rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_materialization_rows(
    *,
    strength_config: Mapping[str, Any],
    non_us_source_plan_rows: Iterable[Mapping[str, Any]],
    download_rows: Iterable[Mapping[str, Any]],
    inventory_summary: Mapping[str, Any],
    sec_structured_summary: Mapping[str, Any],
    sec_annual_summary: Mapping[str, Any],
    generated_at: str,
    normalized_snapshot_summary: Mapping[str, Any] | None = None,
    extended_materialization_summary: Mapping[str, Any] | None = None,
    industry_snapshot_metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    assessments = {str(item.get("source_id") or ""): dict(item) for item in strength_config.get("source_assessments") or []}
    official_plan_counts = Counter()
    for plan in non_us_source_plan_rows:
        source_id = PROFILE_OFFICIAL_SOURCE_ID.get(str(plan.get("disclosure_profile") or ""))
        if source_id:
            official_plan_counts[source_id] += 1

    disclosure_stats = _build_disclosure_materialization_stats(download_rows)
    inventory_counts = dict(inventory_summary.get("runtime_counts_by_source") or {})
    sec_structured = _sec_structured_materialization(sec_structured_summary)
    sec_annual = _sec_annual_materialization(sec_annual_summary)
    normalized_stats = _normalized_snapshot_materialization(normalized_snapshot_summary or {})
    extended_stats = _extended_materialization(extended_materialization_summary or {})
    industry_stats = _industry_snapshot_materialization(industry_snapshot_metadata or {})

    rows: list[dict[str, Any]] = []
    for source_id, assessment in assessments.items():
        tier = str(assessment.get("information_strength_tier") or "")
        channels: list[str] = []
        stats = disclosure_stats.get(source_id, _empty_disclosure_stats())
        official_plan_rows = official_plan_counts.get(source_id, 0)
        if stats["downloaded_row_count"]:
            channels.append("non_us_disclosure_clean_text")
        inventory_row_count = int(inventory_counts.get(source_id) or 0)
        if inventory_row_count:
            channels.append("public_source_inventory_adapter")
        normalized_record_count = int(normalized_stats.get(source_id, {}).get("record_count") or 0)
        normalized_evidence_row_count = int(normalized_stats.get(source_id, {}).get("evidence_row_count") or 0)
        if normalized_record_count or normalized_evidence_row_count:
            channels.append("public_source_normalized_snapshot")
        industry_observation_count = int(industry_stats.get(source_id, {}).get("observation_count") or 0)
        industry_evidence_row_count = int(industry_stats.get(source_id, {}).get("evidence_row_count") or 0)
        if industry_observation_count or industry_evidence_row_count:
            channels.append("industry_snapshot_context")
        extended_record_count = int(extended_stats.get(source_id, {}).get("record_count") or 0)
        extended_downloaded_bytes = int(extended_stats.get(source_id, {}).get("downloaded_bytes") or 0)
        extended_cleaned_text_chars = int(extended_stats.get(source_id, {}).get("cleaned_text_char_count") or 0)
        if extended_stats.get(source_id):
            channels.append("public_source_extended_artifact")
        structured_fact_rows = 0
        sec_annual_chunks = 0
        sec_annual_ledger_facts = 0
        if source_id == "sec_edgar_apis":
            channels.append("existing_sec_core_pipeline")
            structured_fact_rows = int(sec_structured.get("fact_rows") or 0)
            sec_annual_chunks = int(sec_annual.get("chunks") or 0)
            sec_annual_ledger_facts = int(sec_annual.get("ledger_facts") or 0)
        official_download_gap_rows = max(official_plan_rows - int(stats["official_downloaded_row_count"]), 0)
        materialization_status = _materialization_status(
            source_id=source_id,
            assessment=assessment,
            tier=tier,
            channels=channels,
            official_plan_rows=official_plan_rows,
            official_download_gap_rows=official_download_gap_rows,
            structured_fact_rows=structured_fact_rows,
        )
        rows.append(
            {
                "schema_version": MATRIX_SCHEMA_VERSION,
                "generated_at": generated_at,
                "source_id": source_id,
                "information_strength_tier": tier,
                "integration_mode": assessment.get("integration_mode", ""),
                "readiness": assessment.get("readiness", ""),
                "evidence_admissibility": assessment.get("evidence_admissibility", ""),
                "current_quality_contribution": assessment.get("current_quality_contribution", ""),
                "potential_quality_contribution": assessment.get("potential_quality_contribution", ""),
                "next_gate": assessment.get("next_gate", ""),
                "materialization_status": materialization_status,
                "materialization_channels": channels,
                "official_non_us_plan_row_count": official_plan_rows,
                "official_non_us_downloaded_row_count": int(stats["official_downloaded_row_count"]),
                "official_non_us_gap_row_count": official_download_gap_rows,
                "fallback_downloaded_for_this_source_count": int(stats["fallback_downloaded_for_this_source_count"]),
                "fallback_to_company_ir_row_count": int(stats["fallback_to_company_ir_row_count"]),
                "downloaded_document_row_count": int(stats["downloaded_row_count"]),
                "downloaded_unique_document_count": len(stats["sha256s"]),
                "downloaded_company_count": len(stats["tickers"]),
                "downloaded_byte_count": int(stats["downloaded_bytes"]),
                "cleaned_text_row_count": int(stats["cleaned_text_row_count"]),
                "cleaned_text_char_count": int(stats["cleaned_text_char_count"]),
                "inventory_runtime_row_count": inventory_row_count,
                "normalized_snapshot_record_count": normalized_record_count,
                "normalized_snapshot_evidence_row_count": normalized_evidence_row_count,
                "industry_snapshot_observation_count": industry_observation_count,
                "industry_snapshot_evidence_row_count": industry_evidence_row_count,
                "extended_materialization_record_count": extended_record_count,
                "extended_materialization_downloaded_bytes": extended_downloaded_bytes,
                "extended_materialization_cleaned_text_char_count": extended_cleaned_text_chars,
                "sec_structured_fact_row_count": structured_fact_rows,
                "sec_companyfacts_payload_count": int(sec_structured.get("companyfacts_payloads") or 0) if source_id == "sec_edgar_apis" else 0,
                "sec_submission_row_count": int(sec_structured.get("submission_rows") or 0) if source_id == "sec_edgar_apis" else 0,
                "sec_annual_chunk_count": sec_annual_chunks,
                "sec_annual_ledger_fact_count": sec_annual_ledger_facts,
                "runtime_promotion_status": _runtime_promotion_status(assessment, materialization_status),
            }
        )
    return sorted(rows, key=lambda row: (-_tier_score(str(row.get("information_strength_tier") or "")), str(row.get("source_id") or "")))


def _build_disclosure_materialization_stats(download_rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_empty_disclosure_stats)
    for row in download_rows:
        if not row.get("document_downloaded"):
            continue
        profile = str(row.get("disclosure_profile") or "")
        official_source_id = PROFILE_OFFICIAL_SOURCE_ID.get(profile, "")
        source_policy = str(row.get("source_policy") or "")
        target_source_id = official_source_id
        fallback_for = ""
        if profile == "jp_edinet_annual_securities_report" and "company_ir_fallback" in source_policy:
            target_source_id = "company_ir_reports"
            fallback_for = "jp_edinet_api"
        if not target_source_id:
            continue
        _add_download_stat(stats[target_source_id], row)
        if target_source_id == official_source_id:
            stats[target_source_id]["official_downloaded_row_count"] += 1
        if fallback_for:
            stats[fallback_for]["fallback_downloaded_for_this_source_count"] += 1
            stats[target_source_id]["fallback_to_company_ir_row_count"] += 1
    return dict(stats)


def _add_download_stat(stats: dict[str, Any], row: Mapping[str, Any]) -> None:
    stats["downloaded_row_count"] += 1
    stats["downloaded_bytes"] += int(row.get("downloaded_bytes") or 0)
    if row.get("cleaned_text_status") == "cleaned_text_written":
        stats["cleaned_text_row_count"] += 1
    stats["cleaned_text_char_count"] += int(row.get("cleaned_text_char_count") or 0)
    if row.get("sha256"):
        stats["sha256s"].add(str(row["sha256"]))
    if row.get("ticker"):
        stats["tickers"].add(str(row["ticker"]))


def _empty_disclosure_stats() -> dict[str, Any]:
    return {
        "downloaded_row_count": 0,
        "official_downloaded_row_count": 0,
        "fallback_downloaded_for_this_source_count": 0,
        "fallback_to_company_ir_row_count": 0,
        "downloaded_bytes": 0,
        "cleaned_text_row_count": 0,
        "cleaned_text_char_count": 0,
        "sha256s": set(),
        "tickers": set(),
    }


def _sec_structured_materialization(summary: Mapping[str, Any]) -> dict[str, int]:
    if summary.get("status") != "pass":
        return {}
    return {
        "fact_rows": int(summary.get("fact_rows") or 0),
        "companyfacts_payloads": int(summary.get("companyfacts_payloads") or 0),
        "submission_rows": int(summary.get("submission_rows") or 0),
    }


def _sec_annual_materialization(summary: Mapping[str, Any]) -> dict[str, int]:
    if not str(summary.get("status") or "").startswith("staging"):
        return {}
    return {
        "chunks": int((summary.get("chunks") or {}).get("count") or 0),
        "ledger_facts": int((summary.get("ledger") or {}).get("facts") or 0),
    }


def _normalized_snapshot_materialization(summary: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    if summary.get("status") not in {"pass", "partial"}:
        return {}
    record_counts = summary.get("source_record_counts") if isinstance(summary.get("source_record_counts"), dict) else {}
    successful = set(str(item) for item in (summary.get("successful_sources") or []))
    return {
        str(source_id): {
            "record_count": int(count or 0),
            "evidence_row_count": 1 if str(source_id) in successful else 0,
        }
        for source_id, count in record_counts.items()
        if int(count or 0) > 0
    }


def _extended_materialization(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if summary.get("status") not in {"pass", "partial"}:
        return {}
    stats = summary.get("source_stats") if isinstance(summary.get("source_stats"), dict) else {}
    return {str(source_id): dict(value) for source_id, value in stats.items() if isinstance(value, Mapping)}


def _industry_snapshot_materialization(metadata: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    if not metadata or int(metadata.get("failure_count") or 0) > 0:
        return {}
    outputs = metadata.get("outputs") if isinstance(metadata.get("outputs"), dict) else {}
    evidence_path = Path(str(outputs.get("evidence_rows") or ""))
    observations_path = Path(str(outputs.get("observations") or ""))
    evidence_rows = _read_jsonl(evidence_path) if evidence_path.exists() else []
    observation_rows = _read_jsonl(observations_path) if observations_path.exists() else []
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"observation_count": 0, "evidence_row_count": 0})
    for row in evidence_rows:
        source_id = _industry_provider_source_id(row)
        if source_id:
            stats[source_id]["evidence_row_count"] += 1
    for row in observation_rows:
        source_id = _industry_provider_source_id(row)
        if source_id:
            stats[source_id]["observation_count"] += 1
    return dict(stats)


def _industry_provider_source_id(row: Mapping[str, Any]) -> str:
    provider = str(row.get("provider") or "").lower()
    route_type = str(row.get("route_type") or "").lower()
    if provider == "fred" and route_type == "fred_csv":
        return "fred_graph_csv"
    if provider == "eia":
        return "eia_open_data"
    if provider == "cms":
        return "cms_public_data"
    if provider == "fda":
        return "openfda_api"
    return ""


def _materialization_status(
    *,
    source_id: str,
    assessment: Mapping[str, Any],
    tier: str,
    channels: list[str],
    official_plan_rows: int,
    official_download_gap_rows: int,
    structured_fact_rows: int,
) -> str:
    readiness = str(assessment.get("readiness") or "")
    if readiness == "deferred_no_commercial_api":
        return "deferred_by_policy"
    if official_plan_rows and official_download_gap_rows == official_plan_rows:
        return "official_source_not_materialized"
    if official_plan_rows and official_download_gap_rows:
        return "partially_materialized_with_official_gaps"
    if "existing_sec_core_pipeline" in channels and structured_fact_rows:
        return "materialized_existing_core"
    if "public_source_extended_artifact" in channels:
        if source_id == "company_reported_product_operating_metrics":
            return "materialized_candidate_metric_parser_gate_pending"
        if source_id in {"sec_financial_statement_data_sets", "sec_ownership_and_13f"}:
            return "materialized_structured_bulk_parser_gate_pending"
        if source_id == "company_product_pages":
            return "materialized_clean_text_parser_gate_pending"
        return "materialized_extended_artifact_gate_pending"
    if "non_us_disclosure_clean_text" in channels:
        return "materialized_clean_text_parser_gate_pending"
    if "industry_snapshot_context" in channels:
        return "materialized_context_snapshot_gate_pending"
    if "public_source_normalized_snapshot" in channels:
        return "materialized_normalized_snapshot_gate_pending"
    if "public_source_inventory_adapter" in channels:
        return "materialized_inventory_or_resolver_only"
    if readiness in {"downloaded_but_held", "identifier_ready_parser_blocked"}:
        return "downloaded_but_held_for_next_gate"
    if tier in {"S0_deferred_or_unofficial", "S1_resolver_or_lead"}:
        return "not_claim_evidence_materialized"
    return "not_materialized"


def _runtime_promotion_status(assessment: Mapping[str, Any], materialization_status: str) -> str:
    admissibility = str(assessment.get("evidence_admissibility") or "")
    if materialization_status == "materialized_existing_core":
        return "runtime_available_through_existing_core_gates"
    if materialization_status == "materialized_clean_text_parser_gate_pending":
        return "staging_only_parser_citation_boundary_gate_pending"
    if materialization_status == "materialized_structured_bulk_parser_gate_pending":
        return "staging_only_structured_parser_or_parity_gate_pending"
    if materialization_status == "materialized_candidate_metric_parser_gate_pending":
        return "candidate_only_value_unit_period_parser_gate_pending"
    if materialization_status in {"materialized_context_snapshot_gate_pending", "materialized_normalized_snapshot_gate_pending"}:
        return "feature_flagged_context_only_boundary_gate_pending"
    if materialization_status == "materialized_inventory_or_resolver_only":
        return "feature_flagged_inventory_or_context_only"
    if "no_runtime_use" in admissibility or "until" in admissibility:
        return "blocked_until_next_gate"
    return "not_promoted"


def summarize_materialization_rows(
    *,
    rows: list[Mapping[str, Any]],
    download_paths: list[Path],
    output: Path,
    summary_output: Path,
    report_output: Path,
    generated_at: str,
) -> dict[str, Any]:
    status_counts = Counter(str(row.get("materialization_status") or "") for row in rows)
    tier_counts = Counter(str(row.get("information_strength_tier") or "") for row in rows)
    materialized_rows = [row for row in rows if str(row.get("materialization_status") or "").startswith("materialized")]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "source_count": len(rows),
        "tier_counts": dict(sorted(tier_counts.items())),
        "materialization_status_counts": dict(sorted(status_counts.items())),
        "materialized_source_count": len(materialized_rows),
        "materialized_sources": sorted(str(row.get("source_id") or "") for row in materialized_rows),
        "non_us_downloaded_document_row_count": sum(int(row.get("downloaded_document_row_count") or 0) for row in rows),
        "non_us_downloaded_unique_document_count": sum(int(row.get("downloaded_unique_document_count") or 0) for row in rows),
        "non_us_cleaned_text_char_count": sum(int(row.get("cleaned_text_char_count") or 0) for row in rows),
        "inventory_runtime_row_count": sum(int(row.get("inventory_runtime_row_count") or 0) for row in rows),
        "normalized_snapshot_record_count": sum(int(row.get("normalized_snapshot_record_count") or 0) for row in rows),
        "industry_snapshot_observation_count": sum(int(row.get("industry_snapshot_observation_count") or 0) for row in rows),
        "extended_materialization_record_count": sum(int(row.get("extended_materialization_record_count") or 0) for row in rows),
        "extended_materialization_downloaded_bytes": sum(int(row.get("extended_materialization_downloaded_bytes") or 0) for row in rows),
        "sec_structured_fact_row_count": sum(int(row.get("sec_structured_fact_row_count") or 0) for row in rows),
        "sec_annual_chunk_count": sum(int(row.get("sec_annual_chunk_count") or 0) for row in rows),
        "sec_annual_ledger_fact_count": sum(int(row.get("sec_annual_ledger_fact_count") or 0) for row in rows),
        "official_non_us_gap_row_count": sum(int(row.get("official_non_us_gap_row_count") or 0) for row in rows),
        "edinet_official_gap_rows": next((int(row.get("official_non_us_gap_row_count") or 0) for row in rows if row.get("source_id") == "jp_edinet_api"), 0),
        "download_manifests": [_repo_path(path) for path in download_paths],
        "outputs": {"matrix": _repo_path(output), "summary": _repo_path(summary_output), "report": _repo_path(report_output)},
    }


def render_report(summary: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    lines = [
        "# S5-S0 公开源数据落地矩阵",
        "",
        f"- 生成时间：`{summary.get('generated_at')}`",
        f"- 已落地 source：`{summary.get('materialized_source_count')}/{summary.get('source_count')}`",
        f"- 非美披露 downloaded rows：`{summary.get('non_us_downloaded_document_row_count')}`",
        f"- 非美披露 cleaned chars：`{summary.get('non_us_cleaned_text_char_count')}`",
        f"- SEC structured fact rows：`{summary.get('sec_structured_fact_row_count')}`",
        f"- SEC annual staging chunks：`{summary.get('sec_annual_chunk_count')}`",
        f"- Public normalized snapshot records：`{summary.get('normalized_snapshot_record_count')}`",
        f"- Industry snapshot observations：`{summary.get('industry_snapshot_observation_count')}`",
        f"- Extended materialization records：`{summary.get('extended_materialization_record_count')}`",
        f"- EDINET official gap rows：`{summary.get('edinet_official_gap_rows')}`",
        "",
        "| Tier | Source | Materialization | Downloaded rows | Inventory rows | Normalized rows | Industry obs | Extended records | SEC fact rows | Official gaps | Runtime status |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("information_strength_tier") or ""),
                    str(row.get("source_id") or ""),
                    str(row.get("materialization_status") or ""),
                    str(row.get("downloaded_document_row_count") or 0),
                    str(row.get("inventory_runtime_row_count") or 0),
                    str(row.get("normalized_snapshot_record_count") or 0),
                    str(row.get("industry_snapshot_observation_count") or 0),
                    str(row.get("extended_materialization_record_count") or 0),
                    str(row.get("sec_structured_fact_row_count") or 0),
                    str(row.get("official_non_us_gap_row_count") or 0),
                    str(row.get("runtime_promotion_status") or ""),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- `materialized_clean_text_parser_gate_pending` 只表示 raw/cleaned text 已落地，不表示可进入主线 evidence/vector/ledger。",
            "- `materialized_inventory_or_resolver_only` 只允许 resolver/source inventory/context，用于 claim 前必须回到更高强度来源核验。",
            "- `official_source_not_materialized` 不能用 fallback 当作监管/交易所原始披露；JP company IR fallback 单独计入 `company_ir_reports`。",
            "",
        ]
    )
    return "\n".join(lines)


def _tier_score(tier: str) -> int:
    for value in range(5, -1, -1):
        if tier.startswith(f"S{value}_"):
            return value
    return -1


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
