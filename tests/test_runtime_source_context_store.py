from __future__ import annotations

import json
from pathlib import Path

from sec_agent.runtime_source_context_store import (
    attach_runtime_source_context_rows,
    load_runtime_source_context_bundle,
)


def test_runtime_source_context_store_filters_scope_and_keeps_latest_unbound(tmp_path: Path) -> None:
    product_path = tmp_path / "product_rows.jsonl"
    official_path = tmp_path / "official_rows.jsonl"
    public_path = tmp_path / "public_rows.jsonl"
    _write_jsonl(
        product_path,
        [
            _product_row("AAPL", "Services", 2023),
            _product_row("AAPL", "Services", 2024),
            _product_row("MSFT", "Cloud", 2024),
        ],
    )
    _write_jsonl(
        official_path,
        [
            {
                "evidence_ref": "official_aapl_iphone",
                "source_family": "live_public_web_context",
                "runtime_source_family": "public_source_context",
                "source_id": "company_product_pages",
                "source_layer_id": "L2",
                "ticker": "AAPL",
                "product_or_segment": "iPhone",
                "structured_context_type": "product_spec_context",
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
            }
        ],
    )
    _write_jsonl(
        public_path,
        [
            _public_unbound_row("fred_old", "FEDFUNDS", "2023-01-01"),
            _public_unbound_row("fred_new", "FEDFUNDS", "2024-01-01"),
        ],
    )

    bundle = load_runtime_source_context_bundle(
        paths={
            "product": product_path,
            "official": official_path,
            "public": public_path,
        },
        focus_tickers=["AAPL"],
        search_scope_tickers=["AAPL"],
        max_product_rows_per_ticker=1,
        max_public_rows_per_ticker=4,
        max_unbound_public_rows=1,
    )

    product_refs = {row["evidence_ref"] for row in bundle["product_evidence_rows"]}
    public_refs = {row["evidence_ref"] for row in bundle["public_source_context_rows"]}
    assert product_refs == {"product_AAPL_Services_2024"}
    assert "official_aapl_iphone" in public_refs
    assert "fred_new" in public_refs
    assert "fred_old" not in public_refs
    assert bundle["summary"]["product_evidence_row_count"] == 1
    assert bundle["summary"]["public_source_context_row_count"] == 2
    assert bundle["summary"]["public_exact_authority_violation_count"] == 0
    assert "by_signal_authority_type" in bundle["summary"]


def test_attach_runtime_source_context_rows_uses_state_config(tmp_path: Path) -> None:
    product_path = tmp_path / "product_rows.jsonl"
    public_path = tmp_path / "public_rows.jsonl"
    _write_jsonl(product_path, [_product_row("NVDA", "Data Center", 2025)])
    _write_jsonl(public_path, [_public_unbound_row("eia_power", "EIA_POWER", "2025-01-01")])

    attached = attach_runtime_source_context_rows(
        {
            "query_contract": {"focus_tickers": ["NVDA"], "search_scope_tickers": ["NVDA"]},
            "multi_agent_context": {
                "runtime_source_context": {
                    "enabled": True,
                    "paths": {"product": product_path, "public": public_path},
                    "max_product_rows_per_ticker": 2,
                    "max_unbound_public_rows": 1,
                }
            },
        }
    )

    assert attached["product_evidence_rows"][0]["ticker"] == "NVDA"
    assert attached["public_source_context_rows"][0]["source_id"] == "fred_api"
    summary = attached["runtime_source_context_store"]["summary"]
    assert summary["selected_row_count"] == 2
    assert attached["multi_agent_context"]["runtime_source_context_store"]["selected_row_count"] == 2


def test_runtime_source_context_store_preserves_public_source_diversity_under_ticker_budget(tmp_path: Path) -> None:
    public_path = tmp_path / "public_rows.jsonl"
    rows = [
        {
            "evidence_ref": f"official_msft_{index}",
            "source_family": "live_public_web_context",
            "runtime_source_family": "public_source_context",
            "source_id": "company_product_pages",
            "source_layer_id": "L2",
            "ticker": "MSFT",
            "structured_context_type": "product_spec_context",
            "product_or_segment": f"Azure {index}",
            "exact_value_authority": False,
            "can_support_company_exact_fact": False,
        }
        for index in range(8)
    ]
    rows.append(
        {
            "evidence_ref": "developer_msft_vscode",
            "source_family": "live_public_web_context",
            "runtime_source_family": "public_source_context",
            "source_id": "developer_ecosystem_github_npm_pypi_huggingface",
            "source_layer_id": "L3",
            "ticker": "MSFT",
            "structured_context_type": "developer_ecosystem_context",
            "product_or_segment": "microsoft/vscode",
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "exact_value_authority": False,
            "can_support_company_exact_fact": False,
        }
    )
    _write_jsonl(public_path, rows)

    bundle = load_runtime_source_context_bundle(
        paths={"public": public_path},
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
        max_public_rows_per_ticker=4,
        max_unbound_public_rows=0,
    )

    refs = {row["evidence_ref"] for row in bundle["public_source_context_rows"]}
    assert "developer_msft_vscode" in refs
    assert len(refs) == 4


def test_runtime_source_context_store_prioritizes_role_specific_product_context_under_budget(tmp_path: Path) -> None:
    public_path = tmp_path / "public_rows.jsonl"
    rows = [
        {
            "evidence_ref": f"generic_nvda_{index}",
            "source_family": "live_public_web_context",
            "runtime_source_family": "public_source_context",
            "source_id": "company_product_pages",
            "source_layer_id": "L2",
            "ticker": "NVDA",
            "structured_context_type": "product_spec_context",
            "product_or_segment": f"Generic Product {index}",
            "exact_value_authority": False,
            "can_support_company_exact_fact": False,
        }
        for index in range(8)
    ]
    rows.extend(
        [
            {
                "evidence_ref": "r17_nvda_h100_memory",
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_id": "official_nvidia_product_page",
                "source_layer_id": "L2",
                "ticker": "NVDA",
                "source_role": "technical_product_spec",
                "runtime_contract": "ProductSpecSlot",
                "structured_context_type": "technical_product_spec",
                "product_or_segment": "H100 SXM",
                "metric_name": "GPU memory",
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
            },
            {
                "evidence_ref": "r17_nvda_xai_deployment",
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_id": "official_nvidia_customer_deployment_news",
                "source_layer_id": "L2",
                "ticker": "NVDA",
                "source_role": "customer_deployment_proxy",
                "runtime_contract": "CustomerDeploymentProxy",
                "structured_context_type": "customer_deployment_proxy",
                "product_or_segment": "NVIDIA Hopper GPUs",
                "metric_name": "xAI Colossus deployment",
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
            },
        ]
    )
    _write_jsonl(public_path, rows)

    bundle = load_runtime_source_context_bundle(
        paths={"public": public_path},
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
        max_public_rows_per_ticker=4,
        max_unbound_public_rows=0,
    )

    refs = {row["evidence_ref"] for row in bundle["public_source_context_rows"]}
    assert {"r17_nvda_h100_memory", "r17_nvda_xai_deployment"} <= refs
    assert len(refs) == 4
    signal_rows = {
        row["evidence_ref"]: row
        for row in bundle["public_source_context_rows"]
        if row["evidence_ref"] in {"r17_nvda_h100_memory", "r17_nvda_xai_deployment"}
    }
    assert signal_rows["r17_nvda_h100_memory"]["signal_authority_type"] == "technical_fact"
    assert signal_rows["r17_nvda_h100_memory"]["thesis_driver_authority"] is True
    assert signal_rows["r17_nvda_xai_deployment"]["signal_authority_type"] == "customer_deployment_signal"
    assert signal_rows["r17_nvda_xai_deployment"]["exact_financial_fact_authority"] is False
    assert bundle["summary"]["thesis_driver_authority_row_count"] >= 2


def _product_row(ticker: str, product: str, year: int) -> dict:
    return {
        "evidence_ref": f"product_{ticker}_{product}_{year}",
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_id": "company_reported_product_operating_metrics",
        "source_layer_id": "L1",
        "ticker": ticker,
        "fiscal_year": year,
        "product_or_segment": product,
        "metric_family": "product_revenue",
        "promotion_status": "runtime_fact_allowed",
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
    }


def _public_unbound_row(evidence_ref: str, metric: str, date: str) -> dict:
    return {
        "evidence_ref": evidence_ref,
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_id": "fred_api",
        "source_layer_id": "L2",
        "metric_name": metric,
        "product_or_segment": metric,
        "structured_context_type": "macro_official_context",
        "observation_date": date,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
