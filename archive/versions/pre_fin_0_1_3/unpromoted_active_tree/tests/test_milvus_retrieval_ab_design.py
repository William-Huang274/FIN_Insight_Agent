from __future__ import annotations

import importlib.util
import json
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "eval_retrieval" / "eval_milvus_retrieval_ab.py"
_SPEC = importlib.util.spec_from_file_location("eval_milvus_retrieval_ab", _MODULE_PATH)
assert _SPEC and _SPEC.loader
ab = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ab)


def test_expanded_queries_add_bounded_credit_terms() -> None:
    case = {
        "category": "paraphrase",
        "query": "evidence that lenders are preparing for borrowers to weaken or loans to sour under higher rates",
        "tickers": ["JPM", "BAC"],
        "terms_any": ["credit losses"],
        "metric_terms_any": ["provision for credit losses"],
    }

    queries = ab._expanded_queries(case, enabled=True)
    joined = " ".join(queries).lower()

    assert queries[0] == case["query"]
    assert "jpm" in joined
    assert "provision for credit losses" in joined
    assert "allowance for credit losses" in joined
    assert "net charge-offs" in joined
    assert len(queries) <= 6


def test_build_vector_records_splits_narrative_table_and_metric_views() -> None:
    evidence_rows = [
        {
            "evidence_id": "MSFT_2026_10Q_ITEM1_BLOCK_0001",
            "ticker": "MSFT",
            "company": "Microsoft Corporation",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "period_type": "quarterly",
            "section": "Item 1. Financial Statements",
            "subsection": "Cash flows",
            "evidence_type": "financial_statement_or_note",
            "text": "Cash flows [TABLE_START] Additions to property and equipment | 2026 | 30876 [TABLE_END]",
            "metadata": {
                "form_type": "10-Q",
                "item_code": "1",
                "category_slug": "software_cloud",
                "contains_table": True,
            },
        }
    ]
    object_rows = [
        {
            "object_id": "MSFT_CAPEX_METRIC",
            "object_type": "metric",
            "source_evidence_id": "MSFT_2026_10Q_ITEM1_BLOCK_0001",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "section": "Item 1. Financial Statements",
            "metric_name": "Additions to property and equipment",
            "period": "2026",
            "unit": "usd_millions",
            "preview": "Additions to property and equipment | 2026 | 30,876 | usd_millions",
        }
    ]

    records = ab._build_vector_records(evidence_rows=evidence_rows, object_rows=object_rows, max_chars=500)
    kinds = {row["vector_kind"] for row in records}
    by_kind = {row["vector_kind"]: row for row in records}

    assert kinds == {"narrative_chunk", "table_chunk", "metric_row"}
    assert by_kind["narrative_chunk"]["vector_id"] == "MSFT_2026_10Q_ITEM1_BLOCK_0001"
    assert by_kind["table_chunk"]["vector_id"].endswith("::table_chunk")
    assert by_kind["metric_row"]["vector_id"] == "object::MSFT_CAPEX_METRIC"
    assert by_kind["metric_row"]["evidence_id"] == "MSFT_2026_10Q_ITEM1_BLOCK_0001"
    assert "structured metric row" in by_kind["metric_row"]["vector_text"]


def test_build_vector_records_adds_relationship_and_paraphrase_contexts() -> None:
    evidence_rows = [
        {
            "evidence_id": "NVDA_2026_10Q_ITEM7_BLOCK_0001",
            "ticker": "NVDA",
            "company": "NVIDIA Corporation",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "period_type": "quarterly",
            "section": "Item 7. Management Discussion",
            "subsection": "Demand",
            "evidence_type": "business_narrative",
            "text": (
                "Demand for accelerated computing and AI infrastructure increased with data center "
                "buildouts, networking demand, customer supply chain constraints, and capital "
                "expenditures by cloud service providers."
            ),
            "metadata": {
                "form_type": "10-Q",
                "item_code": "7",
                "category_slug": "semiconductors_ai_infra",
                "contains_table": False,
            },
        }
    ]

    records = ab._build_vector_records(evidence_rows=evidence_rows, object_rows=[], max_chars=700)
    by_kind = {row["vector_kind"]: row for row in records}

    assert {"narrative_chunk", "relationship_context", "paraphrase_context"} <= set(by_kind)
    assert by_kind["relationship_context"]["semantic_scope"] == "relationship"
    assert by_kind["relationship_context"]["vector_role"] == "economic_linkage_context"
    assert "economic linkage" in by_kind["relationship_context"]["vector_text"]
    assert "demand transmission" in by_kind["relationship_context"]["vector_text"]
    assert by_kind["paraphrase_context"]["semantic_scope"] == "paraphrase"
    assert "plain language retrieval bridge" in by_kind["paraphrase_context"]["vector_text"]
    assert "ai_infrastructure" in by_kind["paraphrase_context"]["intent_tags"]


def test_relationship_queries_use_dedicated_economic_linkage_rewrites() -> None:
    case = {
        "category": "relationship",
        "query": "cloud hyperscaler capex demand transmission to AI chip server networking suppliers",
        "tickers": ["MSFT", "NVDA", "DELL", "ANET"],
        "terms_any": ["capital expenditures", "infrastructure", "cloud", "AI", "servers", "networking"],
        "metric_terms_any": ["capital expenditures", "revenue", "remaining performance obligations"],
    }

    queries = ab._expanded_queries(case, enabled=True)
    joined = " ".join(queries).lower()

    assert "economic linkage" in joined
    assert "upstream downstream" in joined
    assert "customer supplier" in joined
    assert "hyperscaler capital expenditures" in joined
    assert len(queries) <= 6


def test_case_gates_require_typed_semantic_vector_kind() -> None:
    case = {
        "category": "relationship",
        "required_semantic_vector_kinds": ["relationship_context"],
        "min_usable_evidence_rows": 1,
        "min_ticker_coverage": 1,
        "tickers": ["MSFT"],
    }
    base_variant = {
        "row_count": 1,
        "usable_evidence_rows": 1,
        "ticker_coverage_count": 1,
        "metric_evidence_rows": 0,
        "vector_kind_counts": {},
    }
    variants = {
        "bm25": base_variant,
        "object_bm25": base_variant,
        "milvus_semantic": {**base_variant, "vector_kind_counts": {"narrative_chunk": 1}},
        "hybrid_rrf": {**base_variant, "vector_kind_counts": {"relationship_context": 1}},
    }

    gates = ab._case_gates(case, variants)

    assert gates["required_semantic_vector_kind_hit"] is True


def test_summary_exposes_object_bm25_baseline_metrics() -> None:
    results = [
        {
            "case_id": "retrieval_exact_msft_capex_2026",
            "category": "exact_lookup",
            "gate_status": "pass",
            "gates": {"exact_object_metric_hit": True},
            "variants": {
                "bm25": {"usable_evidence_rows": 2},
                "object_bm25": {
                    "usable_evidence_rows": 3,
                    "metric_evidence_rows": 2,
                    "skipped": False,
                },
                "milvus_semantic": {"usable_evidence_rows": 1},
                "hybrid_rrf": {"usable_evidence_rows": 4},
            },
        },
        {
            "case_id": "retrieval_sector_ai_infra_demand_chain",
            "category": "sector_depth",
            "gate_status": "pass",
            "gates": {},
            "variants": {
                "bm25": {"usable_evidence_rows": 4},
                "object_bm25": {
                    "usable_evidence_rows": 1,
                    "metric_evidence_rows": 0,
                    "skipped": False,
                },
                "milvus_semantic": {"usable_evidence_rows": 5},
                "hybrid_rrf": {"usable_evidence_rows": 6},
            },
        },
    ]

    summary = ab._summarize(results)

    assert summary["case_count"] == 2
    assert summary["mean_object_bm25_usable_evidence_rows"] == 2.0
    assert summary["mean_object_bm25_metric_evidence_rows"] == 1.0
    assert summary["object_bm25_enabled_case_count"] == 2
    assert summary["exact_object_metric_hit_pass_count"] == 1


def test_load_object_vector_seed_rows_balances_and_caps(tmp_path: Path) -> None:
    seed_path = tmp_path / "object_seed.jsonl"
    rows = [
        {
            "object_id": f"NVDA_METRIC_{idx}",
            "object_type": "metric",
            "source_evidence_id": f"NVDA_EVIDENCE_{idx}",
            "ticker": "NVDA",
        }
        for idx in range(3)
    ] + [
        {
            "object_id": "DELL_TABLE_0",
            "object_type": "table",
            "source_evidence_id": "DELL_EVIDENCE_0",
            "ticker": "DELL",
        }
    ]
    seed_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    loaded = ab._load_object_vector_seed_rows(seed_path, max_rows=2)

    assert len(loaded) == 2
    assert {row["ticker"] for row in loaded} == {"NVDA", "DELL"}


def test_balanced_rrf_rank_preserves_ticker_item_and_vector_kind() -> None:
    scores = {
        "NVDA_ITEM7": 1.0,
        "NVDA_ITEM8": 0.9,
        "DELL_ITEM7": 0.5,
        "ANET_METRIC": 0.4,
    }
    support = {
        "NVDA_ITEM7": {
            "record": {"ticker": "NVDA", "metadata": {"item_code": "7", "source_tier": "primary_sec_filing"}},
            "vector_kinds": ["narrative_chunk"],
        },
        "NVDA_ITEM8": {
            "record": {"ticker": "NVDA", "metadata": {"item_code": "8", "source_tier": "primary_sec_filing"}},
            "vector_kinds": ["table_row"],
        },
        "DELL_ITEM7": {
            "record": {"ticker": "DELL", "metadata": {"item_code": "7", "source_tier": "primary_sec_filing"}},
            "vector_kinds": ["narrative_chunk"],
        },
        "ANET_METRIC": {
            "record": {"ticker": "ANET", "metadata": {"item_code": "8", "source_tier": "primary_sec_filing"}},
            "vector_kinds": ["metric_row"],
        },
    }

    ranked = ab._balanced_rrf_rank(
        scores,
        support,
        target_tickers=["NVDA", "DELL", "ANET"],
        top_k=4,
        case={"category": "sector_depth"},
    )
    selected_ids = [evidence_id for evidence_id, _score in ranked]

    assert "NVDA_ITEM7" in selected_ids
    assert "DELL_ITEM7" in selected_ids
    assert "ANET_METRIC" in selected_ids
    assert "NVDA_ITEM8" in selected_ids


def test_full_evidence_build_mode_contract(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    rows = [
        {
            "evidence_id": "MSFT_2026_10Q_ITEM1_BLOCK_0001",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metadata": {"form_type": "10-Q"},
        },
        {
            "evidence_id": "NVDA_2026_8K_ITEM202_BLOCK_0001",
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "source_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "metadata": {"form_type": "8-K"},
        },
    ]
    evidence_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    args = ab.parse_args(["--use-all-evidence", "--collection-max-rows", "0"])
    loaded = ab._load_evidence_subset(
        evidence_path,
        tickers=[],
        years=[],
        source_tiers=[],
        form_types=[],
        max_rows=args.collection_max_rows,
    )

    assert args.use_all_evidence is True
    assert len(loaded) == 2
    assert {row["evidence_id"] for row in loaded} == {
        "MSFT_2026_10Q_ITEM1_BLOCK_0001",
        "NVDA_2026_8K_ITEM202_BLOCK_0001",
    }
