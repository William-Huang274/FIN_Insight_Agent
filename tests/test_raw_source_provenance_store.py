from __future__ import annotations

import json
from pathlib import Path

from sec_agent.raw_source_provenance_store import build_raw_source_provenance_store, discover_runtime_rowset_paths


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_rd1_builds_raw_source_documents_and_matches_runtime_lineage(tmp_path: Path) -> None:
    repo = tmp_path
    raw_doc = repo / "data/raw_private/sec/2025/ai_gpu_semiconductor/NVDA/10-K.html"
    raw_doc.parent.mkdir(parents=True, exist_ok=True)
    raw_doc.write_text("<html>filing</html>", encoding="utf-8")
    _write_json(
        repo / "data/raw_private/sec/2025/ai_gpu_semiconductor/NVDA/10-K.metadata.json",
        {
            "ticker": "NVDA",
            "company": "NVIDIA CORP",
            "cik": "0001045810",
            "form_type": "10-K",
            "fiscal_year": 2025,
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
            "accession_number": "0001045810-25-000023",
            "local_html_path": str(raw_doc),
            "cache_status": "hit",
            "source_tier": "primary_sec_filing",
        },
    )
    _write_jsonl(
        repo / "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
        [
            {
                "ticker": "NVDA",
                "evidence_id": "sec_financial_statement_metric:nvda-revenue",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
                "source_document_id": "0001045810-25-000023",
                "source_layer": "L1",
                "source_id": "sec_filing",
                "exact_value_authority": True,
                "runtime_ready_context": True,
            }
        ],
    )

    result = build_raw_source_provenance_store(repo)

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["exact_authority_unresolved_count"] == 0
    assert result["source_documents"][0]["ticker"] == "NVDA"
    assert result["source_snapshots"][0]["snapshot_storage_status"] == "local_raw_snapshot_available"
    assert result["runtime_lineage_rows"][0]["lineage_status"] == "matched_raw_document"


def test_rd1_redacts_secret_query_params_and_marks_url_only_context(tmp_path: Path) -> None:
    repo = tmp_path
    _write_jsonl(
        repo / "data/manifests/non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
        [
            {
                "ticker": "000660.KS",
                "evidence_id": "non_us_l1:skhynix-revenue",
                "source_url": "https://opendart.fss.or.kr/api/document.xml?crtfc_key=secret&rcept_no=20260317000635",
                "source_document_id": "data/raw_private/global_public_disclosures/kr_dart/000660_KS/2025/ANNUAL_REPORT/20260317000635.zip",
                "source_layer": "L1",
                "source_id": "company_ir_reports",
                "exact_value_authority": True,
                "runtime_ready_context": True,
            }
        ],
    )

    result = build_raw_source_provenance_store(repo)
    document = result["source_documents"][0]
    snapshot = result["source_snapshots"][0]
    lineage = result["runtime_lineage_rows"][0]

    assert "secret" not in document["source_url"]
    assert "crtfc_key=REDACTED" in document["source_url"]
    assert snapshot["snapshot_storage_status"] == "url_only_no_local_snapshot"
    assert snapshot["replayability"] == "not_replayable_until_cached"
    assert lineage["lineage_status"] == "runtime_declared_source_document"
    assert result["summary"]["exact_authority_unresolved_count"] == 0
    assert result["summary"]["url_only_context_lineage_count"] == 1


def test_runtime_rowset_discovery_excludes_attempt_and_rejection_files(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "data/manifests").mkdir(parents=True)
    for name in [
        "official_product_surface_context_rows_v0_1.jsonl",
        "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
        "source_route_attempt_ledger_v0_1.jsonl",
        "company_disclosed_product_business_mix_rejections_v0_1.jsonl",
        "_tmp_official_product_surface_context_rows_v0_1.jsonl",
    ]:
        (repo / "data/manifests" / name).write_text("", encoding="utf-8")

    names = {path.name for path in discover_runtime_rowset_paths(repo)}

    assert "official_product_surface_context_rows_v0_1.jsonl" in names
    assert "company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl" in names
    assert "source_route_attempt_ledger_v0_1.jsonl" not in names
    assert "company_disclosed_product_business_mix_rejections_v0_1.jsonl" not in names
    assert "_tmp_official_product_surface_context_rows_v0_1.jsonl" not in names


def test_sec_financial_statement_dataset_rows_resolve_to_companyfacts_by_ticker(tmp_path: Path) -> None:
    repo = tmp_path
    companyfacts = repo / "data/raw_private/structured_financial_facts/sec/A/sec_companyfacts.json"
    companyfacts.parent.mkdir(parents=True, exist_ok=True)
    companyfacts.write_text("{}", encoding="utf-8")
    _write_json(
        repo / "data/raw_private/structured_financial_facts/sec/A/sec_companyfacts.metadata.json",
        {
            "schema_version": "fin_agent_sec_structured_fact_raw_metadata_v0.1",
            "ticker": "A",
            "cik": "0001090872",
            "fact_source": "sec_companyfacts",
            "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001090872.json",
            "content_type": "application/json",
            "byte_count": 2,
            "sha256": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
            "cache_status": "downloaded",
        },
    )
    _write_jsonl(
        repo / "data/manifests/capital_funding_ownership_context_rows_v0_1.jsonl",
        [
            {
                "ticker": "A",
                "evidence_ref": "fsd-capital-structure:0001090872-26-000023",
                "source_id": "sec_financial_statement_data_sets",
                "source_layer_id": "L1",
                "exact_value_authority": True,
                "can_support_company_exact_fact": True,
                "runtime_ready_context": True,
            }
        ],
    )

    result = build_raw_source_provenance_store(repo)
    lineage = result["runtime_lineage_rows"][0]
    companyfacts_documents = [
        row
        for row in result["source_documents"]
        if row.get("source_id") == "sec_companyfacts"
    ]

    assert companyfacts_documents
    assert "sec_companyfacts_by_ticker:A" in companyfacts_documents[0]["external_document_keys"]
    assert lineage["lineage_status"] == "matched_derived_structured_source_document"
    assert lineage["snapshot_storage_status"] == "api_response_cached"
    assert result["summary"]["exact_authority_unresolved_count"] == 0
