from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


RAW_DISCLOSURE_DATA_INVENTORY_SCHEMA_VERSION = "finsight_raw_disclosure_data_inventory_v0_1"
RAG_INDEX_INVENTORY_SCHEMA_VERSION = "finsight_rag_index_inventory_v0_1"
RUNTIME_DATABASE_INVENTORY_SCHEMA_VERSION = "finsight_runtime_database_inventory_v0_1"
DATA_BASE_INVENTORY_SUMMARY_SCHEMA_VERSION = "finsight_raw_disclosure_rag_database_inventory_summary_v0_1"


RAW_DISCLOSURE_ASSETS: tuple[dict[str, Any], ...] = (
    {
        "artifact_name": "sec_raw_root",
        "relative_path": "data/raw_private/sec",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "sec_raw_disclosure_download",
        "mainline_status": "mainline_source_root",
        "primary_keys": ["ticker", "accession_number", "form_type", "filing_date"],
    },
    {
        "artifact_name": "sec_filings_root",
        "relative_path": "data/raw_private/sec_filings",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "sec_raw_disclosure_download",
        "mainline_status": "mainline_source_root",
        "primary_keys": ["ticker", "accession_number", "form_type"],
    },
    {
        "artifact_name": "sec_8k_earnings_root",
        "relative_path": "data/raw_private/sec_8k_earnings",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "sec_8k_earnings_download",
        "mainline_status": "mainline_source_root",
        "primary_keys": ["ticker", "accession_number", "accepted_date"],
    },
    {
        "artifact_name": "sec_tier1_sp500_annual_root",
        "relative_path": "data/raw_private/sec_tier1_sp500_annual",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "sec_annual_download",
        "mainline_status": "mainline_source_root",
        "primary_keys": ["ticker", "accession_number", "fiscal_year"],
    },
    {
        "artifact_name": "sec_tier2_supply_chain_annual_root",
        "relative_path": "data/raw_private/sec_tier2_supply_chain_annual",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "sec_annual_download",
        "mainline_status": "mainline_source_root",
        "primary_keys": ["ticker", "accession_number", "fiscal_year"],
    },
    {
        "artifact_name": "sec_structured_financial_facts_raw_root",
        "relative_path": "data/raw_private/structured_financial_facts",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "sec_companyfacts_download",
        "mainline_status": "mainline_structured_source_root",
        "primary_keys": ["cik", "taxonomy", "concept", "period", "unit", "form"],
    },
    {
        "artifact_name": "global_public_disclosures_root",
        "relative_path": "data/raw_private/global_public_disclosures",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "non_us_disclosure_download",
        "mainline_status": "non_us_source_root",
        "primary_keys": ["ticker", "market", "document_type", "period"],
    },
    {
        "artifact_name": "company_ir_root",
        "relative_path": "data/raw_private/company_ir",
        "inventory_kind": "raw_source_dataset",
        "data_layer": "bronze_raw",
        "owner_stage": "company_ir_fallback_download",
        "mainline_status": "non_us_and_ir_source_root",
        "primary_keys": ["ticker", "source_url", "document_type", "period"],
    },
    {
        "artifact_name": "structured_financial_facts_staging",
        "relative_path": "data/staging/structured_financial_facts",
        "inventory_kind": "staging_dataset",
        "data_layer": "silver_staging",
        "owner_stage": "sec_companyfacts_normalization",
        "mainline_status": "mainline_staging",
        "primary_keys": ["ticker", "concept", "period", "unit", "form"],
    },
    {
        "artifact_name": "processed_chunks",
        "relative_path": "data/processed_private/chunks",
        "inventory_kind": "processed_disclosure_artifact",
        "data_layer": "silver_parsed",
        "owner_stage": "chunk_builder",
        "mainline_status": "mainline_parsed_artifacts",
        "primary_keys": ["evidence_id", "ticker", "document_id", "chunk_id"],
    },
    {
        "artifact_name": "processed_evidence_objects",
        "relative_path": "data/processed_private/evidence_objects",
        "inventory_kind": "processed_disclosure_artifact",
        "data_layer": "silver_parsed",
        "owner_stage": "evidence_store_builder",
        "mainline_status": "mainline_parsed_artifacts",
        "primary_keys": ["evidence_id", "ticker", "source_family"],
    },
    {
        "artifact_name": "processed_structured_objects",
        "relative_path": "data/processed_private/structured_objects",
        "inventory_kind": "processed_disclosure_artifact",
        "data_layer": "silver_parsed",
        "owner_stage": "structured_object_builder",
        "mainline_status": "mainline_parsed_artifacts",
        "primary_keys": ["object_id", "ticker", "object_type"],
    },
)


RAW_MANIFEST_ASSETS: tuple[dict[str, Any], ...] = (
    {
        "artifact_name": "sec_full_source_download_config_summary",
        "relative_path": "data/manifests/tier1_tier2_sec_full_source_download_config_summary_v0_1.json",
        "inventory_kind": "source_route_summary",
        "data_layer": "bronze_source_plan",
        "owner_stage": "sec_full_source_download_config",
        "mainline_status": "mainline_source_plan",
        "primary_keys": ["config_id", "ticker", "form_type"],
    },
    {
        "artifact_name": "sec_structured_facts_download_summary",
        "relative_path": "data/manifests/sec_structured_facts_download_summary_v0_1.json",
        "inventory_kind": "source_download_summary",
        "data_layer": "bronze_to_silver_summary",
        "owner_stage": "sec_companyfacts_download",
        "mainline_status": "mainline_structured_fact_source",
        "primary_keys": ["ticker", "concept", "period", "unit", "form"],
    },
    {
        "artifact_name": "sec_financial_statement_metric_runtime_rows",
        "relative_path": "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
        "summary_path": "data/manifests/sec_financial_statement_metric_runtime_summary_v0_1.json",
        "inventory_kind": "runtime_fact_row_set",
        "data_layer": "gold_fact_mart_candidate",
        "owner_stage": "sec_financial_statement_metric_runtime",
        "mainline_status": "mainline_gold_fact_rows",
        "primary_keys": ["ticker", "metric_family", "period", "unit", "source_fact_id"],
    },
    {
        "artifact_name": "non_us_l1_financial_statement_metric_runtime_rows",
        "relative_path": "data/manifests/non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
        "summary_path": "data/manifests/non_us_l1_financial_statement_metric_runtime_summary_v0_1.json",
        "inventory_kind": "runtime_fact_row_set",
        "data_layer": "gold_fact_mart_candidate",
        "owner_stage": "non_us_l1_financial_statement_runtime",
        "mainline_status": "non_us_gold_fact_rows",
        "primary_keys": ["ticker", "metric_family", "period", "unit", "source_ref"],
    },
    {
        "artifact_name": "non_us_product_kpi_local_disclosure_runtime_rows",
        "relative_path": "data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
        "summary_path": "data/manifests/non_us_product_kpi_local_disclosure_runtime_summary_v0_1.json",
        "inventory_kind": "runtime_fact_row_set",
        "data_layer": "gold_fact_mart_candidate",
        "owner_stage": "non_us_product_kpi_local_disclosure_runtime",
        "mainline_status": "non_us_product_fact_rows",
        "primary_keys": ["ticker", "product_node", "metric_family", "period", "unit"],
    },
    {
        "artifact_name": "company_product_slots",
        "relative_path": "data/manifests/company_product_slots_v0_1.jsonl",
        "inventory_kind": "product_graph_node_row_set",
        "data_layer": "graph_candidate",
        "owner_stage": "product_family_source_route_plan",
        "mainline_status": "graph_node_rows",
        "primary_keys": ["ticker", "product_slot_id", "product_family_id"],
    },
    {
        "artifact_name": "product_relationship_graph_nodes",
        "relative_path": "data/manifests/product_relationship_graph_nodes_v0_1.jsonl",
        "summary_path": "data/manifests/product_relationship_graph_summary_v0_1.json",
        "inventory_kind": "graph_node_row_set",
        "data_layer": "graph_candidate",
        "owner_stage": "product_relationship_graph",
        "mainline_status": "graph_node_rows",
        "primary_keys": ["node_id", "node_type"],
    },
    {
        "artifact_name": "product_relationship_graph_edges",
        "relative_path": "data/manifests/product_relationship_graph_edges_v0_1.jsonl",
        "summary_path": "data/manifests/product_relationship_graph_summary_v0_1.json",
        "inventory_kind": "graph_edge_row_set",
        "data_layer": "graph_candidate",
        "owner_stage": "product_relationship_graph",
        "mainline_status": "graph_edge_rows",
        "primary_keys": ["edge_id", "source_node_id", "target_node_id", "edge_type"],
    },
    {
        "artifact_name": "company_disclosed_product_profile_context_rows",
        "relative_path": "data/manifests/company_disclosed_product_profile_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/company_disclosed_product_profile_context_summary_v0_1.json",
        "inventory_kind": "runtime_signal_row_set",
        "data_layer": "gold_signal_mart_candidate",
        "owner_stage": "company_disclosed_product_profile",
        "mainline_status": "bounded_product_profile_rows",
        "primary_keys": ["ticker", "product_slot_id", "source_ref"],
    },
    {
        "artifact_name": "official_product_surface_context_rows",
        "relative_path": "data/manifests/official_product_surface_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/official_product_surface_materialization_summary_v0_1.json",
        "inventory_kind": "runtime_signal_row_set",
        "data_layer": "gold_signal_mart_candidate",
        "owner_stage": "official_product_surface_materialization",
        "mainline_status": "bounded_product_surface_rows",
        "primary_keys": ["ticker", "product_or_family", "source_url"],
    },
    {
        "artifact_name": "official_product_spec_context_rows",
        "relative_path": "data/manifests/official_product_spec_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/official_product_spec_context_summary_v0_1.json",
        "inventory_kind": "runtime_signal_row_set",
        "data_layer": "gold_signal_mart_candidate",
        "owner_stage": "official_product_spec_parser",
        "mainline_status": "technical_product_spec_rows",
        "primary_keys": ["ticker", "product_or_family", "spec_metric", "source_url"],
    },
    {
        "artifact_name": "company_disclosed_product_business_mix_runtime_rows",
        "relative_path": "data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
        "summary_path": "data/manifests/company_disclosed_product_business_mix_summary_v0_1.json",
        "inventory_kind": "runtime_fact_row_set",
        "data_layer": "gold_fact_mart_candidate",
        "owner_stage": "company_disclosed_product_business_mix",
        "mainline_status": "product_business_kpi_rows",
        "primary_keys": ["ticker", "product_or_segment", "metric_family", "period"],
    },
    {
        "artifact_name": "industry_operating_metric_slot_rows",
        "relative_path": "data/manifests/industry_operating_metric_slot_rows_v0_1.jsonl",
        "summary_path": "data/manifests/industry_operating_metric_slot_summary_v0_1.json",
        "inventory_kind": "runtime_fact_row_set",
        "data_layer": "gold_fact_mart_candidate",
        "owner_stage": "industry_operating_metric_slot",
        "mainline_status": "industry_operating_metric_rows",
        "primary_keys": ["ticker", "metric_family", "period", "source_ref"],
    },
    {
        "artifact_name": "official_customer_deployment_surface_context_rows",
        "relative_path": "data/manifests/official_customer_deployment_surface_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/official_customer_deployment_surface_summary_v0_1.json",
        "inventory_kind": "runtime_signal_row_set",
        "data_layer": "gold_signal_mart_candidate",
        "owner_stage": "official_customer_deployment_surface",
        "mainline_status": "customer_deployment_signal_rows",
        "primary_keys": ["ticker", "counterparty", "event_date", "source_url"],
    },
    {
        "artifact_name": "capital_funding_ownership_context_rows",
        "relative_path": "data/manifests/capital_funding_ownership_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/capital_funding_ownership_context_summary_v0_1.json",
        "inventory_kind": "runtime_fact_or_context_row_set",
        "data_layer": "gold_fact_mart_candidate",
        "owner_stage": "capital_funding_ownership",
        "mainline_status": "capital_ownership_rows",
        "primary_keys": ["ticker", "source_role", "metric_family", "period"],
    },
    {
        "artifact_name": "sec_capital_market_event_context_rows",
        "relative_path": "data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/sec_capital_market_event_context_summary_v0_1.json",
        "inventory_kind": "runtime_event_row_set",
        "data_layer": "gold_signal_mart_candidate",
        "owner_stage": "sec_capital_market_event_context",
        "mainline_status": "capital_market_event_rows",
        "primary_keys": ["ticker", "source_role", "accession_number", "event_date"],
    },
    {
        "artifact_name": "market_liquidity_driver_context_rows",
        "relative_path": "data/manifests/market_liquidity_driver_context_rows_v0_1.jsonl",
        "summary_path": "data/manifests/market_liquidity_driver_context_summary_v0_1.json",
        "inventory_kind": "runtime_signal_row_set",
        "data_layer": "gold_signal_mart_candidate",
        "owner_stage": "market_liquidity_driver",
        "mainline_status": "market_liquidity_signal_rows",
        "primary_keys": ["ticker", "as_of_date", "metric_family"],
    },
    {
        "artifact_name": "r18_source_authority_data_mart_rows",
        "relative_path": "data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl",
        "summary_path": "data/manifests/r18_source_authority_data_mart_summary_v0_1.json",
        "inventory_kind": "source_authority_mart",
        "data_layer": "authority_mart",
        "owner_stage": "r18_source_authority_data_mart",
        "mainline_status": "authority_mainline",
        "primary_keys": ["ticker", "source_role", "source_id", "ledger_id"],
    },
    {
        "artifact_name": "second_third_layer_depth_parity_matrix",
        "relative_path": "data/manifests/second_third_layer_depth_parity_matrix_v0_1.jsonl",
        "summary_path": "data/manifests/second_third_layer_depth_parity_summary_v0_1.json",
        "inventory_kind": "coverage_gate_matrix",
        "data_layer": "quality_gate",
        "owner_stage": "r26_depth_parity",
        "mainline_status": "quality_gate_mainline",
        "primary_keys": ["ticker"],
    },
)


DATABASE_ASSETS: tuple[dict[str, Any], ...] = (
    {
        "artifact_name": "workbench_sqlite",
        "relative_path": "data/workbench_private/workbench.sqlite",
        "database_kind": "sqlite",
        "data_layer": "runtime_workbench",
        "owner_stage": "workbench_backend",
        "mainline_status": "runtime_local_store",
    },
    {
        "artifact_name": "runtime_bridge_eval_store",
        "relative_path": "data/workbench_private/runtime_bridge/eval_store.sqlite",
        "database_kind": "sqlite",
        "data_layer": "runtime_eval",
        "owner_stage": "runtime_bridge_eval_store",
        "mainline_status": "runtime_local_store",
    },
    {
        "artifact_name": "workbench_private_root",
        "relative_path": "data/workbench_private",
        "database_kind": "runtime_private_root",
        "data_layer": "runtime_workbench",
        "owner_stage": "workbench_runtime",
        "mainline_status": "runtime_root",
    },
    {
        "artifact_name": "object_store_root",
        "relative_path": "data/object_store",
        "database_kind": "object_store_root",
        "data_layer": "object_store",
        "owner_stage": "runtime_object_store",
        "mainline_status": "configured_root_may_be_empty",
    },
)


def build_raw_disclosure_data_inventory(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    rows: list[dict[str, Any]] = []
    for spec in (*RAW_DISCLOSURE_ASSETS, *RAW_MANIFEST_ASSETS):
        row = _asset_inventory_row(
            root,
            spec,
            schema_version=RAW_DISCLOSURE_DATA_INVENTORY_SCHEMA_VERSION,
            generated_at=generated_at,
            inventory_namespace="raw_disclosure_data",
        )
        summary_path = spec.get("summary_path")
        if summary_path:
            row["summary_artifact"] = _summary_artifact(root / str(summary_path))
            row["summary_metrics"] = _summary_metrics(row["summary_artifact"].get("payload") or {})
        elif row["path"].endswith(".json"):
            row["summary_artifact"] = _summary_artifact(Path(row["absolute_path"]))
            row["summary_metrics"] = _summary_metrics(row["summary_artifact"].get("payload") or {})
        rows.append(row)
    return rows


def build_rag_index_inventory(
    repo_root: str | Path,
    *,
    milvus_config_path: str | Path | None = None,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    rows: list[dict[str, Any]] = []
    bm25_root = root / "data" / "indexes" / "bm25"
    if bm25_root.exists():
        for index_dir in sorted(path for path in bm25_root.iterdir() if path.is_dir()):
            metadata = _read_json(index_dir / "metadata.json")
            row = _path_summary(index_dir, recursive=False)
            row.update(
                {
                    "schema_version": RAG_INDEX_INVENTORY_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "inventory_id": _stable_id("rag_index", str(index_dir.relative_to(root))),
                    "index_name": index_dir.name,
                    "index_type": str(metadata.get("index_type") or _infer_index_type(index_dir.name)),
                    "retriever_role": _retriever_role(index_dir.name, metadata),
                    "path": _rel(index_dir, root),
                    "absolute_path": str(index_dir.resolve()),
                    "path_exists": index_dir.exists(),
                    "records": _int(metadata.get("records")),
                    "object_counts": metadata.get("object_counts") if isinstance(metadata.get("object_counts"), Mapping) else {},
                    "record_files": list(metadata.get("record_files") or []),
                    "source_paths": _source_paths_from_metadata(metadata),
                    "metadata": _compact_payload(metadata),
                    "claim_boundary": "retrieval_candidate_only_no_exact_authority",
                    "mainline_status": _rag_mainline_status(index_dir.name),
                    "lineage_status": "metadata_present" if metadata else "metadata_missing",
                }
            )
            rows.append(row)
    dense_root = root / "data" / "indexes" / "dense"
    if dense_root.exists():
        for index_dir in sorted(path for path in dense_root.iterdir() if path.is_dir()):
            row = _path_summary(index_dir, recursive=False)
            row.update(
                {
                    "schema_version": RAG_INDEX_INVENTORY_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "inventory_id": _stable_id("rag_index", str(index_dir.relative_to(root))),
                    "index_name": index_dir.name,
                    "index_type": "dense_embedding_baseline",
                    "retriever_role": "historical_dense_baseline",
                    "path": _rel(index_dir, root),
                    "absolute_path": str(index_dir.resolve()),
                    "path_exists": True,
                    "records": 0,
                    "object_counts": {},
                    "record_files": [],
                    "source_paths": [],
                    "metadata": {},
                    "claim_boundary": "historical_or_experimental_recall_only",
                    "mainline_status": "not_current_default",
                    "lineage_status": "directory_present",
                }
            )
            rows.append(row)
    config_path = Path(milvus_config_path) if milvus_config_path else root / "configs" / "runtime" / "milvus_runtime_603_local_v0_1.json"
    milvus_config = _read_json(config_path)
    if config_path.exists() or milvus_config:
        db_path = _resolve_path(str(milvus_config.get("db_path") or ""), root)
        row = _path_summary(db_path, recursive=False) if db_path else _empty_path_summary()
        row.update(
            {
                "schema_version": RAG_INDEX_INVENTORY_SCHEMA_VERSION,
                "generated_at": generated_at,
                "inventory_id": _stable_id("rag_index", "milvus", str(config_path)),
                "index_name": str(milvus_config.get("collection_name") or "milvus_runtime_collection"),
                "index_type": "milvus_lite_vector_collection",
                "retriever_role": "typed_semantic_recall_supplement",
                "path": _rel(db_path, root) if db_path else "",
                "absolute_path": str(db_path.resolve()) if db_path else "",
                "path_exists": bool(db_path and db_path.exists()),
                "records": _int(milvus_config.get("vector_count")),
                "vector_count": _int(milvus_config.get("vector_count")),
                "indexed_ticker_count": _int(milvus_config.get("ticker_count_indexed")),
                "declared_company_count": _int(milvus_config.get("company_count_declared")),
                "collection_name": str(milvus_config.get("collection_name") or ""),
                "embedding_model": str(milvus_config.get("embedding_model") or ""),
                "embedding_dim": _int(milvus_config.get("embedding_dim")),
                "vector_kinds": list(milvus_config.get("vector_kinds") or []),
                "source_tiers": list(milvus_config.get("source_tiers") or []),
                "source_paths": [str(config_path)],
                "metadata": _compact_payload(milvus_config),
                "claim_boundary": str(milvus_config.get("claim_boundary") or "semantic_recall_supplement_not_exact_value_authority"),
                "mainline_status": str(milvus_config.get("status") or "configured"),
                "lineage_status": "runtime_config_present",
            }
        )
        rows.append(row)
    return rows


def build_runtime_database_inventory(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in DATABASE_ASSETS:
        row = _database_inventory_row(root, spec, generated_at=generated_at)
        rows.append(row)
        seen.add(row["absolute_path"].lower())
    for pattern in ("data/workbench_private/**/*.sqlite", "data/workbench_private/**/*.db", "data/workbench_private/**/*.duckdb", "data/indexes/staging/**/*.duckdb"):
        for path in sorted(root.glob(pattern)):
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            rows.append(
                _database_inventory_row(
                    root,
                    {
                        "artifact_name": path.stem,
                        "relative_path": _rel(path, root),
                        "database_kind": _database_kind_from_suffix(path),
                        "data_layer": "runtime_or_index_database",
                        "owner_stage": "auto_discovered_runtime_database",
                        "mainline_status": "auto_discovered",
                    },
                    generated_at=generated_at,
                )
            )
            seen.add(key)
    return rows


def build_inventory_summary(
    *,
    raw_rows: Sequence[Mapping[str, Any]],
    rag_rows: Sequence[Mapping[str, Any]],
    database_rows: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    all_rows: list[Mapping[str, Any]] = [*raw_rows, *rag_rows, *database_rows]
    missing_rows = [row for row in all_rows if not row.get("path_exists")]
    missing_required_rows = [row for row in missing_rows if not _is_optional_configured_path(row)]
    missing_optional_rows = [row for row in missing_rows if _is_optional_configured_path(row)]
    return {
        "schema_version": DATA_BASE_INVENTORY_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not missing_required_rows else "action_required",
        "raw_disclosure_inventory_rows": len(raw_rows),
        "rag_index_inventory_rows": len(rag_rows),
        "runtime_database_inventory_rows": len(database_rows),
        "missing_path_count": len(missing_rows),
        "missing_required_path_count": len(missing_required_rows),
        "missing_optional_configured_path_count": len(missing_optional_rows),
        "missing_path_samples": [
            {
                "artifact_name": str(row.get("artifact_name") or row.get("index_name") or ""),
                "path": str(row.get("path") or ""),
                "mainline_status": str(row.get("mainline_status") or ""),
            }
            for row in missing_rows[:25]
        ],
        "raw_by_data_layer": dict(Counter(str(row.get("data_layer") or "") for row in raw_rows)),
        "raw_by_inventory_kind": dict(Counter(str(row.get("inventory_kind") or "") for row in raw_rows)),
        "rag_by_index_type": dict(Counter(str(row.get("index_type") or "") for row in rag_rows)),
        "rag_records_total": sum(_int(row.get("records")) for row in rag_rows),
        "database_by_kind": dict(Counter(str(row.get("database_kind") or "") for row in database_rows)),
        "database_path_exists_count": sum(1 for row in database_rows if row.get("path_exists")),
        "database_table_count_total": sum(_int(row.get("sqlite_table_count")) for row in database_rows),
        "policy": (
            "RD0 inventory is a data-base ledger bootstrap. It records physical artifacts, row counts, "
            "schema hints, lineage status, and authority boundaries; it does not promote any row to evidence by itself."
        ),
    }


def render_inventory_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD0 Raw Disclosure / RAG / Database Inventory",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Raw disclosure inventory rows: `{summary.get('raw_disclosure_inventory_rows', 0)}`",
        f"- RAG index inventory rows: `{summary.get('rag_index_inventory_rows', 0)}`",
        f"- Runtime database inventory rows: `{summary.get('runtime_database_inventory_rows', 0)}`",
        f"- Missing path count: `{summary.get('missing_path_count', 0)}`",
        f"- Missing required path count: `{summary.get('missing_required_path_count', 0)}`",
        f"- Missing optional configured path count: `{summary.get('missing_optional_configured_path_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Raw Layers",
            "",
            _markdown_counter_table(summary.get("raw_by_data_layer") or {}, "Layer", "Rows"),
            "",
            "## RAG Index Types",
            "",
            _markdown_counter_table(summary.get("rag_by_index_type") or {}, "Index type", "Rows"),
            "",
            "## Runtime Database Kinds",
            "",
            _markdown_counter_table(summary.get("database_by_kind") or {}, "Database kind", "Rows"),
            "",
            "## Boundary",
            "",
            "- 本 inventory 只说明数据资产存在、规模、schema hint、主键和血缘状态；不把任何 URL、chunk、vector hit 或 closeout row 直接提升为 evidence。",
            "- Milvus 继续保持 semantic recall supplement，不提供 exact-value authority。",
            "- 后续 RD1/RD2 应在此基础上补 raw source provenance 和 parser run ledger。",
            "",
        ]
    )
    return "\n".join(lines)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _asset_inventory_row(
    root: Path,
    spec: Mapping[str, Any],
    *,
    schema_version: str,
    generated_at: str,
    inventory_namespace: str,
) -> dict[str, Any]:
    path = root / str(spec.get("relative_path") or "")
    summary = _path_summary(path, recursive=True)
    row = {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "inventory_id": _stable_id(inventory_namespace, spec.get("artifact_name"), spec.get("relative_path")),
        "artifact_name": str(spec.get("artifact_name") or ""),
        "inventory_kind": str(spec.get("inventory_kind") or ""),
        "data_layer": str(spec.get("data_layer") or ""),
        "owner_stage": str(spec.get("owner_stage") or ""),
        "mainline_status": str(spec.get("mainline_status") or ""),
        "path": _rel(path, root),
        "absolute_path": str(path.resolve()),
        "path_exists": bool(path.exists()),
        "path_type": summary["path_type"],
        "byte_size": summary["byte_size"],
        "file_count": summary["file_count"],
        "dir_count": summary["dir_count"],
        "last_modified": summary["last_modified"],
        "extension_counts": summary["extension_counts"],
        "row_count": _line_count(path) if path.exists() and path.is_file() and path.suffix.lower() == ".jsonl" else 0,
        "primary_keys": list(spec.get("primary_keys") or []),
        "lineage_inputs": list(spec.get("lineage_inputs") or []),
        "downstream_use": list(spec.get("downstream_use") or []),
        "lineage_status": _lineage_status(spec, path),
        "notes": str(spec.get("notes") or ""),
        "summary_metrics": {},
    }
    return row


def _database_inventory_row(root: Path, spec: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    path = root / str(spec.get("relative_path") or "")
    path_summary = _path_summary(path, recursive=True)
    sqlite_summary = _sqlite_summary(path) if path.exists() and path.is_file() and path.suffix.lower() in {".sqlite", ".db"} else {}
    return {
        "schema_version": RUNTIME_DATABASE_INVENTORY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "inventory_id": _stable_id("runtime_database", spec.get("artifact_name"), spec.get("relative_path")),
        "artifact_name": str(spec.get("artifact_name") or ""),
        "database_kind": str(spec.get("database_kind") or _database_kind_from_suffix(path)),
        "data_layer": str(spec.get("data_layer") or ""),
        "owner_stage": str(spec.get("owner_stage") or ""),
        "mainline_status": str(spec.get("mainline_status") or ""),
        "path": _rel(path, root),
        "absolute_path": str(path.resolve()),
        "path_exists": bool(path.exists()),
        "path_type": path_summary["path_type"],
        "byte_size": path_summary["byte_size"],
        "file_count": path_summary["file_count"],
        "dir_count": path_summary["dir_count"],
        "last_modified": path_summary["last_modified"],
        "sqlite_schema_status": sqlite_summary.get("schema_status", ""),
        "sqlite_table_count": len(sqlite_summary.get("tables") or []),
        "sqlite_tables": sqlite_summary.get("tables") or [],
        "sqlite_row_counts": sqlite_summary.get("row_counts") or {},
        "lineage_status": "database_introspected" if sqlite_summary else ("path_present" if path.exists() else "path_missing"),
        "claim_boundary": "runtime_or_governance_store_not_standalone_evidence_authority",
    }


def _summary_artifact(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "schema_version": str(payload.get("schema_version") or ""),
        "status": str(payload.get("status") or ""),
        "payload": payload,
    }


def _summary_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = {
        "status",
        "company_count",
        "covered_company_count",
        "target_ticker_count",
        "runtime_ticker_count",
        "ticker_count",
        "row_count",
        "runtime_row_count",
        "fact_rows",
        "submission_rows",
        "document_downloaded_count",
        "downloaded_byte_count",
        "edge_count",
        "node_count",
        "product_slot_count",
        "source_role_count",
        "evidence_bundle_allowed_count",
        "uncovered_ticker_count",
        "uncovered_target_ticker_count",
        "parity_status",
        "metrics",
        "by_source_role",
        "metric_family_counts",
        "source_specific_parser_counts",
    }
    return {key: _compact_payload(value) for key, value in payload.items() if key in keys}


def _path_summary(path: Path, *, recursive: bool) -> dict[str, Any]:
    if not path.exists():
        return _empty_path_summary()
    if path.is_file():
        stat = path.stat()
        return {
            "path_type": "file",
            "byte_size": stat.st_size,
            "file_count": 1,
            "dir_count": 0,
            "last_modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "extension_counts": {path.suffix.lower() or "<none>": 1},
        }
    files: list[Path]
    dirs: list[Path]
    if recursive:
        entries = list(path.rglob("*"))
        files = [entry for entry in entries if entry.is_file()]
        dirs = [entry for entry in entries if entry.is_dir()]
    else:
        entries = list(path.iterdir())
        files = [entry for entry in entries if entry.is_file()]
        dirs = [entry for entry in entries if entry.is_dir()]
    size = sum(file.stat().st_size for file in files)
    last_modified = max((entry.stat().st_mtime for entry in [path, *files, *dirs]), default=path.stat().st_mtime)
    return {
        "path_type": "directory",
        "byte_size": size,
        "file_count": len(files),
        "dir_count": len(dirs),
        "last_modified": datetime.fromtimestamp(last_modified, timezone.utc).isoformat(),
        "extension_counts": dict(Counter(file.suffix.lower() or "<none>" for file in files)),
    }


def _empty_path_summary() -> dict[str, Any]:
    return {
        "path_type": "missing",
        "byte_size": 0,
        "file_count": 0,
        "dir_count": 0,
        "last_modified": "",
        "extension_counts": {},
    }


def _sqlite_summary(path: Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(str(path)) as conn:
            table_rows = conn.execute(
                "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
            ).fetchall()
            tables = [str(row[0]) for row in table_rows]
            row_counts: dict[str, int] = {}
            for table in tables[:50]:
                try:
                    row_counts[table] = int(conn.execute(f'select count(*) from "{table}"').fetchone()[0])
                except sqlite3.DatabaseError:
                    row_counts[table] = -1
        return {"schema_status": "sqlite_introspection_pass", "tables": tables, "row_counts": row_counts}
    except sqlite3.DatabaseError as exc:
        return {"schema_status": f"sqlite_introspection_failed:{type(exc).__name__}", "tables": [], "row_counts": {}}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _line_count(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return "rd0_inventory:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _resolve_path(value: str, root: Path) -> Path | None:
    if not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _compact_payload(value: Any, *, max_items: int = 30) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _compact_payload(item, max_items=max_items) for key, item in list(value.items())[:max_items]}
    if isinstance(value, list):
        return [_compact_payload(item, max_items=max_items) for item in value[:max_items]]
    return value


def _lineage_status(spec: Mapping[str, Any], path: Path) -> str:
    if not path.exists():
        return "path_missing"
    if spec.get("summary_path"):
        return "summary_linked"
    if path.suffix.lower() == ".json":
        return "summary_json"
    if path.suffix.lower() == ".jsonl":
        return "row_set_without_summary" if not spec.get("summary_path") else "summary_linked"
    if path.is_dir():
        return "directory_inventory_only"
    return "file_inventory_only"


def _source_paths_from_metadata(metadata: Mapping[str, Any]) -> list[str]:
    paths = []
    for key in ("evidence_path", "structured_dir", "source_path", "records_path"):
        value = str(metadata.get(key) or "").strip()
        if value:
            paths.append(value)
    return paths


def _infer_index_type(name: str) -> str:
    if name.endswith("_objects"):
        return "object_bm25"
    return "rank_bm25"


def _retriever_role(index_name: str, metadata: Mapping[str, Any]) -> str:
    index_type = str(metadata.get("index_type") or "")
    if index_name.endswith("_objects") or "object" in index_name or index_type == "sqlite_fts5":
        return "structured_object_and_exact_value_recall"
    return "lexical_recall"


def _rag_mainline_status(index_name: str) -> str:
    if "sector_depth_full238_us_v0_3_mixed_with_8k" in index_name:
        return "latest_sector_depth_mainline_candidate"
    if "sector_depth_full238_us_v0_2_mixed_with_8k" in index_name:
        return "previous_sector_depth_mainline"
    if index_name.startswith(".tmp"):
        return "diagnostic_or_tmp"
    return "available_index"


def _database_kind_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".sqlite", ".db"}:
        return "sqlite"
    if suffix == ".duckdb":
        return "duckdb"
    if path.is_dir():
        return "directory_store"
    return suffix.lstrip(".") or "unknown"


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_optional_configured_path(row: Mapping[str, Any]) -> bool:
    return str(row.get("mainline_status") or "") in {"configured_root_may_be_empty"}
