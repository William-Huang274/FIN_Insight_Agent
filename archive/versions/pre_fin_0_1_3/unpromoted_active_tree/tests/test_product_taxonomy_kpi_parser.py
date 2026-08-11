from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_product_taxonomy_kpi_parser.py"
SPEC = importlib.util.spec_from_file_location("build_product_taxonomy_kpi_parser", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _rules() -> dict:
    return {
        "label_quality_gate": {
            "min_chars": 3,
            "max_chars": 120,
            "max_words": 12,
            "reject_exact_lower": ["business", "products", "net sales"],
            "reject_contains_lower": ["consolidated financial statements", "table_start"],
            "reject_regex": ["^item\\s+\\d", "^[0-9.,%$()\\- ]+$"],
        },
        "canonical_replacements": {"&": "and"},
        "industry_schemas": {
            "consumer_electronics_semiconductor_hardware": {
                "priority": 10,
                "category_keywords": ["hardware", "semiconductor"],
                "label_keywords": ["gpu", "mac", "iphone"],
                "node_types": {
                    "reportable_segment": "segment",
                    "product_or_service_family": "product_family",
                    "customer_market_or_application": "end_market",
                },
            },
            "app_software_consumer_internet": {
                "priority": 20,
                "category_keywords": ["software"],
                "label_keywords": ["cloud", "software"],
                "node_types": {"product_or_service_family": "product_family"},
            },
        },
    }


def _ontology() -> dict:
    return {
        "metric_families": {
            "product_revenue": {"allowed_units": ["currency", "percent_of_revenue"]},
            "unit_sales_or_deliveries": {"allowed_units": ["units", "vehicles", "devices", "systems"]},
            "shipments": {"allowed_units": ["units", "metric tons", "barrels"]},
            "backlog_or_orders": {"allowed_units": ["currency", "units", "months"]},
            "same_store_sales": {"allowed_units": ["percent"]},
            "subscribers_or_arpu": {"allowed_units": ["subscribers", "accounts", "currency_per_user"]},
            "production_or_throughput": {"allowed_units": ["units", "barrels_per_day", "megawatt_hours", "tons"]},
        }
    }


def test_taxonomy_normalizer_creates_nodes_aliases_and_review_queue() -> None:
    rows = [
        {
            "candidate_id": "tax-1",
            "ticker": "TEST",
            "company": "Test Hardware",
            "fiscal_year": 2025,
            "taxonomy_label": "data center GPU platforms",
            "taxonomy_type": "product_or_service_family",
            "confidence_score": 0.7,
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_2025_ITEM1",
        },
        {
            "candidate_id": "tax-2",
            "ticker": "TEST",
            "company": "Test Hardware",
            "fiscal_year": 2025,
            "taxonomy_label": "Item 1. Business",
            "taxonomy_type": "business_line",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_2025_ITEM1",
        },
        {
            "candidate_id": "tax-3",
            "ticker": "NOIND",
            "company": "No Industry",
            "fiscal_year": 2025,
            "taxonomy_label": "specialized products",
            "taxonomy_type": "product_or_service_family",
            "source_url": "https://example.test/noind",
            "chunk_id": "NOIND_2025_ITEM1",
        },
    ]
    universe = {
        "TEST": {"ticker": "TEST", "sector_depth_category": "hardware/ecosystem"},
        "NOIND": {"ticker": "NOIND", "sector": "Unknown"},
    }

    normalized, aliases, review = MODULE.normalize_taxonomy_candidates(
        rows,
        rules=_rules(),
        universe_index=universe,
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(normalized) == 1
    assert normalized[0]["canonical_name"] == "Data Center GPU Platforms"
    assert normalized[0]["industry_schema"] == "consumer_electronics_semiconductor_hardware"
    assert aliases[0]["product_node_id"] == normalized[0]["product_node_id"]
    assert {row["review_reason"] for row in review} == {"boilerplate_or_numeric_label", "no_industry_template"}


def test_kpi_parser_promotes_only_complete_value_unit_period_product_fact() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::hardware::data_center_gpu::abc",
            "ticker": "TEST",
            "canonical_name": "Data Center GPU",
            "aliases": ["Data Center GPU", "H100"],
            "node_type": "product_family",
            "industry_schema": "consumer_electronics_semiconductor_hardware",
            "evidence_count": 2,
        }
    ]
    metrics = [
        {
            "candidate_id": "kpi-1",
            "signal_role": "company_disclosed",
            "ticker": "TEST",
            "company": "Test Hardware",
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "metric_family": "product_revenue",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_2025_ITEM1",
            "snippet": "Data Center GPU revenue was $12.5 billion in fiscal 2025, led by H100 demand.",
        }
    ]

    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        metrics,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not rejections
    assert len(facts) == 1
    assert facts[0]["fact_status"] == "parser_verified_fact"
    assert facts[0]["product_node_id"] == taxonomy[0]["product_node_id"]
    assert facts[0]["value"] == 12_500_000_000
    assert facts[0]["unit"] == "USD"
    assert facts[0]["period"] == "FY2025"


def test_direct_chunk_scan_generates_parser_eligible_candidates(tmp_path: Path) -> None:
    chunk_path = tmp_path / "chunks.jsonl"
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::hardware::systems::abc",
            "ticker": "TEST",
            "canonical_name": "Products and Systems Integration",
            "aliases": ["Products and Systems Integration Segment"],
            "node_type": "segment",
            "industry_schema": "consumer_electronics_semiconductor_hardware",
            "evidence_count": 1,
        }
    ]
    chunk_path.write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "company": "Test Hardware",
                "fiscal_year": 2025,
                "period_end": "2025-12-31",
                "form_type": "10-K",
                "section": "Item 1. Business",
                "chunk_id": "TEST_DIRECT",
                "source_url": "https://example.test/filing",
                "text": "Products and Systems Integration Segment net sales were $6.2 billion in fiscal 2025.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    candidates = MODULE.build_direct_metric_candidates_from_chunks(
        [chunk_path],
        taxonomy,
        generated_at="2026-06-11T00:00:00+00:00",
        max_windows_per_chunk=2,
        max_citation_chars=240,
    )
    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        candidates,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=240,
    )

    assert candidates
    assert not rejections
    assert facts[0]["source_candidate_id"].startswith("DIRECTPRODUCTKPI::")
    assert facts[0]["value"] == 6_200_000_000


def test_kpi_parser_rejects_growth_rate_without_level_value() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::software::cloud::abc",
            "ticker": "TEST",
            "canonical_name": "Cloud Platform",
            "aliases": ["Cloud Platform"],
            "node_type": "product_family",
            "industry_schema": "app_software_consumer_internet",
            "evidence_count": 1,
        }
    ]
    metrics = [
        {
            "candidate_id": "kpi-2",
            "signal_role": "company_disclosed",
            "ticker": "TEST",
            "company": "Test Software",
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "metric_family": "product_revenue",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_2025_ITEM7",
            "snippet": "Cloud Platform revenue increased 12% in fiscal 2025.",
        }
    ]

    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        metrics,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "change_rate_without_level_value"


def test_kpi_parser_rejects_table_multivalue_until_table_parser_exists() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::hardware::interconnect::abc",
            "ticker": "TEST",
            "canonical_name": "Interconnect and Sensor Systems",
            "aliases": ["Interconnect and Sensor Systems"],
            "node_type": "product_family",
            "industry_schema": "consumer_electronics_semiconductor_hardware",
            "evidence_count": 1,
        }
    ]
    metrics = [
        {
            "candidate_id": "kpi-table",
            "signal_role": "company_disclosed",
            "ticker": "TEST",
            "company": "Test Hardware",
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "metric_family": "product_revenue",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_TABLE",
            "snippet": "[TABLE_START id=1] Segment | A | B | Interconnect and Sensor Systems % of 2025 Net Sales: | 28% | 39% | 33%",
        }
    ]

    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        metrics,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "table_layout_requires_table_parser"


def test_kpi_parser_rejects_order_false_positive_context() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::services::segments::abc",
            "ticker": "TEST",
            "canonical_name": "Risk Capital",
            "aliases": ["Risk Capital"],
            "node_type": "segment",
            "industry_schema": "banking_financial_services",
            "evidence_count": 1,
        }
    ]
    metrics = [
        {
            "candidate_id": "kpi-order",
            "signal_role": "company_disclosed",
            "ticker": "TEST",
            "company": "Test Services",
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "metric_family": "backlog_or_orders",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_ORDER",
            "snippet": "Risk Capital made capital allocation decisions in order to maximize value. Total revenue was $17,181 million.",
        }
    ]

    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        metrics,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "no_valid_metric_context"


def test_kpi_parser_rejects_ambiguous_currency_scale() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::industrial::equipment::abc",
            "ticker": "TEST",
            "canonical_name": "Equipment Operations",
            "aliases": ["Equipment Operations"],
            "node_type": "asset_or_product_family",
            "industry_schema": "energy_industrials_materials",
            "evidence_count": 1,
        }
    ]
    metrics = [
        {
            "candidate_id": "kpi-scale",
            "signal_role": "company_disclosed",
            "ticker": "TEST",
            "company": "Test Industrial",
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "metric_family": "product_revenue",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_SCALE",
            "snippet": "Equipment Operations generated $26,790 net sales and revenues in fiscal 2025.",
        }
    ]

    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        metrics,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "ambiguous_currency_scale"


def test_kpi_parser_rejects_ambiguous_percent_allocation() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::retail::home_care::abc",
            "ticker": "TEST",
            "canonical_name": "Home Care",
            "aliases": ["Home Care"],
            "node_type": "category_or_brand_family",
            "industry_schema": "retail_cpg",
            "evidence_count": 1,
        }
    ]
    metrics = [
        {
            "candidate_id": "kpi-percent",
            "signal_role": "company_disclosed",
            "ticker": "TEST",
            "company": "Test CPG",
            "fiscal_year": 2025,
            "period_end": "2025-12-31",
            "metric_family": "product_revenue",
            "source_url": "https://example.test/filing",
            "chunk_id": "TEST_PERCENT",
            "snippet": "Sales of Oral, Personal and Home Care products accounted for 44%, 17% and 16%, respectively, of net sales.",
        }
    ]

    facts, rejections = MODULE.parse_metric_candidates_to_facts(
        metrics,
        taxonomy,
        ontology=_ontology(),
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "ambiguous_percent_allocation_requires_table_or_list_parser"


def test_structured_metric_parser_promotes_table_row_with_source_context() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::software::productivity::abc",
            "ticker": "TEST",
            "canonical_name": "Productivity and Business Processes",
            "aliases": ["Productivity and Business Processes"],
            "node_type": "segment",
            "industry_schema": "app_software_consumer_internet",
            "evidence_count": 2,
        }
    ]
    record = {
        "object_id": "TEST_2025_10K_ITEM7_BLOCK_0001_METRIC_TABLE_A",
        "object_type": "metric",
        "source_evidence_id": "TEST_2025_10K_ITEM7_BLOCK_0001",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "section": "Item 7. Management's Discussion and Analysis",
        "subsection": "Revenue by reportable segment",
        "period_end": "2025-06-30",
        "period_type": "annual",
        "metric_name": "Productivity and Business Processes",
        "raw_value": "$ 69,274",
        "value": 69274.0,
        "unit": "usd_millions",
        "period": "2025",
        "period_role": "annual",
        "row_label": "Productivity and Business Processes",
        "column_label": "2025",
        "extraction_method": "table_row_heuristic",
        "metadata": {"table_object_id": "table-1", "cell_kind": "period_value"},
    }
    contexts = {
        "TEST_2025_10K_ITEM7_BLOCK_0001": {
            "chunk_id": "TEST_2025_10K_ITEM7_BLOCK_0001",
            "source_url": "https://example.test/filing",
            "text": "Revenue by reportable segment (in millions) | Productivity and Business Processes | $ 69,274 | 2025",
        }
    }

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=400,
    )

    assert not rejections
    assert len(facts) == 1
    assert facts[0]["fact_status"] == "parser_verified_fact"
    assert facts[0]["source_table_object_id"] == "table-1"
    assert facts[0]["value"] == 69_274_000_000
    assert facts[0]["period"] == "FY2025"
    assert facts[0]["source_url"] == "https://example.test/filing"


def test_structured_metric_parser_promotes_sentence_metric_with_explicit_segment() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::hardware::data_center::abc",
            "ticker": "TEST",
            "canonical_name": "Data Center",
            "aliases": ["Data Center", "data center"],
            "node_type": "segment",
            "industry_schema": "consumer_electronics_semiconductor_hardware",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "TEST_2025_10K_ITEM7_BLOCK_0001_METRIC_SENT_A",
        "object_type": "metric",
        "source_evidence_id": "chunk-sentence",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "section": "Item 7. Management's Discussion and Analysis",
        "subsection": "Results of Operations",
        "period_end": "2025-01-31",
        "period_type": "annual",
        "metric_name": "revenue",
        "segment": "data center",
        "raw_value": "$47.5 billion",
        "value": 47.5,
        "unit": "usd_billions",
        "period": "2025",
        "period_role": "annual",
        "preview": "revenue | data center | 2025 | $47.5 billion | usd_billions",
    }
    contexts = {
        "chunk-sentence": {
            "chunk_id": "chunk-sentence",
            "source_url": "https://example.test/filing",
            "text": "Data Center revenue was $47.5 billion in fiscal 2025.",
        }
    }

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=400,
    )

    assert not rejections
    assert len(facts) == 1
    assert facts[0]["source_id"] == "company_product_kpi_facts_structured_sentence_metric_parser"
    assert facts[0]["product_or_segment"] == "Data Center"
    assert facts[0]["metric_family"] == "product_revenue"
    assert facts[0]["value"] == 47_500_000_000


def test_structured_metric_taxonomy_repair_adds_segment_before_kpi_parse(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "records.sqlite"
    chunk_path = tmp_path / "chunks.jsonl"
    chunk_path.write_text(
        json.dumps(
            {
                "chunk_id": "chunk-repair",
                "ticker": "TEST",
                "company": "Test Hardware",
                "fiscal_year": 2025,
                "source_url": "https://example.test/filing",
                "period_end": "2025-01-31",
                "form_type": "10-K",
                "section": "Item 7. Management's Discussion and Analysis",
                "text": "Data Center revenue was $47.5 billion in fiscal 2025.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    con = sqlite3.connect(sqlite_path)
    con.execute(
        """
        CREATE TABLE object_records (
            idx INTEGER PRIMARY KEY,
            object_id TEXT,
            object_type TEXT,
            source_evidence_id TEXT,
            ticker TEXT,
            fiscal_year INTEGER,
            form_type TEXT,
            source_type TEXT,
            source_tier TEXT,
            section TEXT,
            subsection TEXT,
            period TEXT,
            period_end TEXT,
            period_type TEXT,
            duration_months INTEGER,
            fiscal_period TEXT,
            preview TEXT,
            periods_json TEXT,
            metric_family TEXT,
            record_json TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX idx_object_records_ticker_year_form_object ON object_records(ticker, fiscal_year, form_type, object_type)")
    record = {
        "object_id": "TEST_2025_10K_ITEM7_BLOCK_0001_METRIC_SENT_A",
        "object_type": "metric",
        "source_evidence_id": "chunk-repair",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "section": "Item 7. Management's Discussion and Analysis",
        "subsection": "Results of Operations",
        "form_type": "10-K",
        "source_tier": "primary_sec_filing",
        "period_end": "2025-01-31",
        "period_type": "annual",
        "duration_months": 12,
        "metric_name": "revenue",
        "segment": "data center",
        "raw_value": "$47.5 billion",
        "value": 47.5,
        "unit": "usd_billions",
        "period": "2025",
        "period_role": "annual",
        "preview": "revenue | data center | 2025 | $47.5 billion | usd_billions",
    }
    con.execute(
        "INSERT INTO object_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            1,
            record["object_id"],
            "metric",
            "chunk-repair",
            "TEST",
            2025,
            "10-K",
            "10-K",
            "primary_sec_filing",
            "Item 7. Management's Discussion and Analysis",
            "Results of Operations",
            "2025",
            "2025-01-31",
            "annual",
            12,
            "FY",
            record["preview"],
            "[]",
            None,
            json.dumps(record),
        ],
    )
    con.commit()
    con.close()

    repaired_rows, alias_rows, repair_summary = MODULE.augment_taxonomy_with_structured_metric_nodes(
        [sqlite_path],
        [],
        rules=_rules(),
        universe_index={"TEST": {"ticker": "TEST", "company_name": "Test Hardware", "sector": "Information Technology", "category": "hardware"}},
        chunk_inputs=[chunk_path],
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=400,
    )
    facts, rejections = MODULE.parse_structured_sqlite_metrics_to_facts(
        [sqlite_path],
        repaired_rows,
        ontology=_ontology(),
        chunk_inputs=[chunk_path],
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=400,
    )[:2]

    assert repair_summary["repaired_node_count"] == 1
    assert alias_rows
    assert repaired_rows[0]["canonical_name"] == "Data Center"
    assert not rejections
    assert facts[0]["product_or_segment"] == "Data Center"


def test_structured_metric_parser_rejects_change_column() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::auto::automotive::abc",
            "ticker": "TEST",
            "canonical_name": "Automotive",
            "aliases": ["Automotive"],
            "node_type": "segment",
            "industry_schema": "automotive",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "metric-change",
        "source_evidence_id": "chunk-change",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "metric_name": "Automotive revenue",
        "raw_value": "77,553",
        "value": 77553.0,
        "unit": "usd_millions",
        "period_role": "annual",
        "row_label": "Automotive revenue",
        "column_label": "2025 vs. 2024 Change",
        "extraction_method": "table_row_heuristic",
    }
    contexts = {"chunk-change": {"chunk_id": "chunk-change", "source_url": "https://example.test/filing", "text": "Automotive revenue by segment"}}

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "change_cell_not_level_value"


def test_structured_metric_parser_rejects_currency_row_without_metric_context() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::software::cloud::abc",
            "ticker": "TEST",
            "canonical_name": "Cloud Platform",
            "aliases": ["Cloud Platform"],
            "node_type": "product_family",
            "industry_schema": "app_software_consumer_internet",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "metric-no-context",
        "source_evidence_id": "chunk-no-context",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "metric_name": "Cloud Platform",
        "raw_value": "$ 500",
        "value": 500.0,
        "unit": "usd_millions",
        "period": "2025",
        "period_role": "annual",
        "row_label": "Cloud Platform",
        "column_label": "2025",
        "extraction_method": "table_row_heuristic",
    }
    contexts = {"chunk-no-context": {"chunk_id": "chunk-no-context", "source_url": "https://example.test/filing", "text": "Cloud Platform contract assets by product line."}}

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "no_valid_metric_context"


def test_structured_metric_parser_rejects_currency_percent_unit_conflict() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::healthcare::us::abc",
            "ticker": "TEST",
            "canonical_name": "U.S.",
            "aliases": ["U.S."],
            "node_type": "segment",
            "industry_schema": "healthcare_pharma_medtech",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "metric-unit-conflict",
        "source_evidence_id": "chunk-unit-conflict",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "metric_name": "U.S.",
        "raw_value": "$ 21,791.0",
        "value": 21791.0,
        "unit": "percent",
        "period": "2025",
        "period_role": "annual",
        "row_label": "U.S.",
        "column_label": "2025",
        "extraction_method": "table_row_heuristic",
    }
    contexts = {"chunk-unit-conflict": {"chunk_id": "chunk-unit-conflict", "source_url": "https://example.test/filing", "text": "Revenue by region | U.S. | $ 21,791.0 | 2025"}}

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "unit_value_conflict"


def test_structured_metric_parser_rejects_decomposition_column() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::industrial::construction::abc",
            "ticker": "TEST",
            "canonical_name": "Construction Industries",
            "aliases": ["Construction Industries"],
            "node_type": "segment",
            "industry_schema": "energy_industrials_materials",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "metric-sales-volume",
        "source_evidence_id": "chunk-sales-volume",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "metric_name": "Construction Industries",
        "raw_value": "$ 2,678",
        "value": 2678.0,
        "unit": "usd",
        "period": "2025",
        "period_role": "annual",
        "row_label": "Construction Industries",
        "column_label": "Sales Volume",
        "extraction_method": "table_row_heuristic",
    }
    contexts = {"chunk-sales-volume": {"chunk_id": "chunk-sales-volume", "source_url": "https://example.test/filing", "text": "Sales and Revenues by Segment (Millions of dollars) | Construction Industries | Sales Volume | $ 2,678"}}

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "non_period_or_decomposition_column"


def test_structured_metric_parser_rejects_currency_as_unit_delivery() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::utility::consumers::abc",
            "ticker": "TEST",
            "canonical_name": "Consumers",
            "aliases": ["Consumers"],
            "node_type": "segment",
            "industry_schema": "energy_industrials_materials",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "metric-currency-delivered",
        "source_evidence_id": "chunk-currency-delivered",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "metric_name": "Total Consumers",
        "raw_value": "$ 105",
        "value": 105.0,
        "unit": "usd_millions",
        "period": "2025",
        "period_role": "annual",
        "row_label": "Total Consumers",
        "column_label": "2025",
        "extraction_method": "table_row_heuristic",
    }
    contexts = {"chunk-currency-delivered": {"chunk_id": "chunk-currency-delivered", "source_url": "https://example.test/filing", "text": "Power delivered under sales agreements included $105 million for Total Consumers."}}

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "no_valid_metric_context"


def test_structured_metric_parser_rejects_non_atomic_raw_text_cell() -> None:
    taxonomy = [
        {
            "product_node_id": "PRODUCTNODE::TEST::transport::industrial::abc",
            "ticker": "TEST",
            "canonical_name": "Industrial",
            "aliases": ["Industrial"],
            "node_type": "segment",
            "industry_schema": "energy_industrials_materials",
            "evidence_count": 1,
        }
    ]
    record = {
        "object_id": "metric-raw-text",
        "source_evidence_id": "chunk-raw-text",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "metric_name": "Industrial shipments",
        "raw_value": "2025 Industrial Carloads",
        "value": 2025.0,
        "period": "2025",
        "period_role": "annual",
        "row_label": "Industrial shipments",
        "column_label": "2025",
        "extraction_method": "table_row_heuristic",
    }
    contexts = {"chunk-raw-text": {"chunk_id": "chunk-raw-text", "source_url": "https://example.test/filing", "text": "Industrial shipments increased in 2025."}}

    facts, rejections = MODULE.parse_structured_metric_records_to_facts(
        [record],
        taxonomy,
        ontology=_ontology(),
        source_context_by_id=contexts,
        generated_at="2026-06-11T00:00:00+00:00",
        max_citation_chars=300,
    )

    assert not facts
    assert rejections[0]["rejection_reason"] == "raw_value_not_atomic_numeric_cell"


def test_cli_writes_outputs(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    taxonomy_path = tmp_path / "taxonomy.jsonl"
    metric_path = tmp_path / "metrics.jsonl"
    universe_path = tmp_path / "universe.csv"
    sector_path = tmp_path / "sector.yaml"
    ontology_path = tmp_path / "ontology.yaml"
    normalized_output = tmp_path / "normalized.jsonl"
    aliases_output = tmp_path / "aliases.jsonl"
    review_output = tmp_path / "review.jsonl"
    facts_output = tmp_path / "facts.jsonl"
    rejections_output = tmp_path / "rejections.jsonl"
    summary_output = tmp_path / "summary.json"
    report_output = tmp_path / "report.md"

    rules_path.write_text(
        """
schema_version: test
label_quality_gate:
  min_chars: 3
  max_chars: 120
  max_words: 12
  reject_exact_lower: [business]
  reject_contains_lower: [table_start]
  reject_regex: ['^item\\s+\\d']
canonical_replacements: {'&': and}
industry_schemas:
  consumer_electronics_semiconductor_hardware:
    priority: 10
    category_keywords: [hardware]
    label_keywords: [gpu]
    node_types:
      product_or_service_family: product_family
""".strip()
        + "\n",
        encoding="utf-8",
    )
    universe_path.write_text(
        "ticker,company_name,sector,category,universe_tier,country\nTEST,Test Hardware,Information Technology,hardware,tier1,US\n",
        encoding="utf-8",
    )
    sector_path.write_text("companies: []\n", encoding="utf-8")
    ontology_path.write_text(
        """
metric_families:
  product_revenue:
    allowed_units: [currency, percent_of_revenue]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    taxonomy_path.write_text(
        json.dumps(
            {
                "candidate_id": "tax-1",
                "ticker": "TEST",
                "company": "Test Hardware",
                "fiscal_year": 2025,
                "taxonomy_label": "data center GPU",
                "taxonomy_type": "product_or_service_family",
                "source_url": "https://example.test/filing",
                "chunk_id": "TEST_1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metric_path.write_text(
        json.dumps(
            {
                "candidate_id": "kpi-1",
                "signal_role": "company_disclosed",
                "ticker": "TEST",
                "company": "Test Hardware",
                "fiscal_year": 2025,
                "period_end": "2025-12-31",
                "metric_family": "product_revenue",
                "source_url": "https://example.test/filing",
                "chunk_id": "TEST_1",
                "snippet": "Data center GPU revenue was $3.2 billion in fiscal 2025.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = MODULE.main(
        [
            "--rules-config",
            str(rules_path),
            "--taxonomy-candidates",
            str(taxonomy_path),
            "--metric-candidates",
            str(metric_path),
            "--universe-manifest",
            str(universe_path),
            "--sector-depth-config",
            str(sector_path),
            "--metric-ontology",
            str(ontology_path),
            "--normalized-taxonomy-output",
            str(normalized_output),
            "--taxonomy-aliases-output",
            str(aliases_output),
            "--taxonomy-review-output",
            str(review_output),
            "--kpi-facts-output",
            str(facts_output),
            "--kpi-rejections-output",
            str(rejections_output),
            "--summary-output",
            str(summary_output),
            "--report-output",
            str(report_output),
        ]
    )

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert result == 0
    assert summary["taxonomy"]["normalized_node_count"] == 1
    assert summary["kpi_parser"]["parser_verified_fact_count"] == 1
    assert normalized_output.exists()
    assert facts_output.exists()


def test_cli_structured_sqlite_scan_hydrates_chunk_source_context(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yaml"
    taxonomy_path = tmp_path / "taxonomy.jsonl"
    metric_path = tmp_path / "metrics.jsonl"
    universe_path = tmp_path / "universe.csv"
    sector_path = tmp_path / "sector.yaml"
    ontology_path = tmp_path / "ontology.yaml"
    chunk_path = tmp_path / "chunks.jsonl"
    sqlite_path = tmp_path / "records.sqlite"
    facts_output = tmp_path / "facts.jsonl"
    summary_output = tmp_path / "summary.json"

    rules_path.write_text(
        """
schema_version: test
label_quality_gate:
  min_chars: 3
  max_chars: 120
  max_words: 12
  reject_exact_lower: [business]
  reject_contains_lower: [table_start]
  reject_regex: ['^item\\s+\\d']
canonical_replacements: {}
industry_schemas:
  app_software_consumer_internet:
    priority: 10
    category_keywords: [software]
    label_keywords: [productivity]
    node_types:
      reportable_segment: segment
""".strip()
        + "\n",
        encoding="utf-8",
    )
    taxonomy_path.write_text(
        json.dumps(
            {
                "candidate_id": "tax-structured",
                "ticker": "TEST",
                "company": "Test Software",
                "fiscal_year": 2025,
                "taxonomy_label": "Productivity and Business Processes",
                "taxonomy_type": "reportable_segment",
                "source_url": "https://example.test/filing",
                "chunk_id": "chunk-structured",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metric_path.write_text("", encoding="utf-8")
    universe_path.write_text(
        "ticker,company_name,sector,category,universe_tier,country\nTEST,Test Software,Information Technology,software,tier1,US\n",
        encoding="utf-8",
    )
    sector_path.write_text("companies: []\n", encoding="utf-8")
    ontology_path.write_text(
        """
metric_families:
  product_revenue:
    allowed_units: [currency, percent_of_revenue]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    chunk_path.write_text(
        json.dumps(
            {
                "chunk_id": "chunk-structured",
                "ticker": "TEST",
                "company": "Test Software",
                "fiscal_year": 2025,
                "source_url": "https://example.test/filing",
                "period_end": "2025-06-30",
                "form_type": "10-K",
                "section": "Item 7. Management's Discussion and Analysis",
                "text": "Revenue by reportable segment (in millions) | Productivity and Business Processes | $ 69,274 | 2025",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    con = sqlite3.connect(sqlite_path)
    con.execute(
        """
        CREATE TABLE object_records (
            idx INTEGER PRIMARY KEY,
            object_id TEXT,
            object_type TEXT,
            source_evidence_id TEXT,
            ticker TEXT,
            fiscal_year INTEGER,
            form_type TEXT,
            source_type TEXT,
            source_tier TEXT,
            section TEXT,
            subsection TEXT,
            period TEXT,
            period_end TEXT,
            period_type TEXT,
            duration_months INTEGER,
            fiscal_period TEXT,
            preview TEXT,
            periods_json TEXT,
            metric_family TEXT,
            record_json TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX idx_object_records_ticker_year_form_object ON object_records(ticker, fiscal_year, form_type, object_type)")
    record = {
        "object_id": "metric-structured",
        "object_type": "metric",
        "source_evidence_id": "chunk-structured",
        "ticker": "TEST",
        "fiscal_year": 2025,
        "section": "Item 7. Management's Discussion and Analysis",
        "subsection": "Revenue by reportable segment",
        "form_type": "10-K",
        "source_tier": "primary_sec_filing",
        "period_end": "2025-06-30",
        "period_type": "annual",
        "duration_months": 12,
        "metric_name": "Productivity and Business Processes",
        "raw_value": "$ 69,274",
        "value": 69274.0,
        "unit": "usd_millions",
        "period": "2025",
        "period_role": "annual",
        "row_label": "Productivity and Business Processes",
        "column_label": "2025",
        "extraction_method": "table_row_heuristic",
    }
    con.execute(
        "INSERT INTO object_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            1,
            "metric-structured",
            "metric",
            "chunk-structured",
            "TEST",
            2025,
            "10-K",
            "10-K",
            "primary_sec_filing",
            "Item 7. Management's Discussion and Analysis",
            "Revenue by reportable segment",
            "2025",
            "2025-06-30",
            "annual",
            12,
            "FY",
            "Productivity and Business Processes | 2025 | $ 69,274 | usd_millions",
            "[]",
            None,
            json.dumps(record),
        ],
    )
    con.commit()
    con.close()

    result = MODULE.main(
        [
            "--rules-config",
            str(rules_path),
            "--taxonomy-candidates",
            str(taxonomy_path),
            "--metric-candidates",
            str(metric_path),
            "--universe-manifest",
            str(universe_path),
            "--sector-depth-config",
            str(sector_path),
            "--metric-ontology",
            str(ontology_path),
            "--chunk-input",
            str(chunk_path),
            "--structured-object-sqlite",
            str(sqlite_path),
            "--enable-structured-metric-kpi-scan",
            "--kpi-facts-output",
            str(facts_output),
            "--summary-output",
            str(summary_output),
            "--normalized-taxonomy-output",
            str(tmp_path / "normalized.jsonl"),
            "--taxonomy-aliases-output",
            str(tmp_path / "aliases.jsonl"),
            "--taxonomy-review-output",
            str(tmp_path / "review.jsonl"),
            "--kpi-rejections-output",
            str(tmp_path / "rejections.jsonl"),
            "--report-output",
            str(tmp_path / "report.md"),
        ]
    )

    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    facts = [json.loads(line) for line in facts_output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert result == 0
    assert summary["structured_metric_kpi_parser"]["parser_verified_fact_count"] == 1
    assert facts[0]["source_id"] == "company_product_kpi_facts_structured_metric_parser"
    assert facts[0]["source_url"] == "https://example.test/filing"
