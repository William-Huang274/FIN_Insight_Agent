from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r17_product_family_evidence_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_r17_product_family_evidence_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_nvidia_product_spec_rows_are_context_not_financial_exact() -> None:
    rows = MODULE.parse_nvidia_h100_product_spec_rows(
        text=(
            "FP8 Tensor Core * 3,958 teraFLOPS 3,341 teraFLOPS "
            "INT8 Tensor Core * 3,958 TOPS 3,341 TOPS "
            "GPU Memory 80GB 94GB GPU Memory Bandwidth 3.35TB/s 3.9TB/s"
        ),
        raw_path=Path("h100.html"),
        generated_at="2026-06-22T00:00:00Z",
    )

    assert len(rows) == 8
    assert {row["runtime_contract"] for row in rows} == {"ProductSpecSlot"}
    assert {row["source_role"] for row in rows} == {"technical_product_spec"}
    assert not any(row["exact_value_authority"] for row in rows)
    assert all(row["signal_authority_type"] == "technical_fact" for row in rows)
    assert all(row["thesis_driver_authority"] is True for row in rows)
    assert all("product_revenue_without_company_disclosure" in row["forbidden_claims"] for row in rows)


def test_nvidia_deployment_proxy_preserves_no_revenue_boundary() -> None:
    rows = MODULE.parse_nvidia_xai_deployment_rows(
        text=(
            "NVIDIA today announced that xAI’s Colossus supercomputer cluster comprising "
            "100,000 NVIDIA Hopper GPUs in Memphis, Tennessee achieved this massive scale by using "
            "the NVIDIA Spectrum-X Ethernet networking. xAI is in the process of doubling the size "
            "of Colossus to a combined total of 200,000 NVIDIA Hopper GPUs."
        ),
        raw_path=Path("xai.html"),
        generated_at="2026-06-22T00:00:00Z",
    )

    deployment_rows = [row for row in rows if row["runtime_contract"] == "CustomerDeploymentProxy"]
    assert {row["value"] for row in deployment_rows} == {100000.0, 200000.0}
    assert all(row["customer_name"] == "xAI" for row in deployment_rows)
    assert all("not revenue" in row["claim_boundary"] for row in deployment_rows)
    assert all(row["signal_authority_type"] == "customer_deployment_signal" for row in deployment_rows)
    assert all(row["thesis_driver_authority"] is True for row in deployment_rows)
    assert any(row["runtime_contract"] == "ProductEcosystemContext" for row in rows)


def test_company_disclosed_operating_metrics_are_not_product_kpi_exact() -> None:
    msft_rows = MODULE.parse_microsoft_cloud_operating_metric_rows(
        text="And Azure surpassed $75 billion in revenue for the first time, up 34 percent.",
        raw_path=Path("msft.html"),
        generated_at="2026-06-22T00:00:00Z",
    )
    asml_rows = MODULE.parse_asml_semicap_operating_metric_rows(
        text=(
            "System sales in units 535 Read more 48 EUV lithography systems "
            "279 DUV lithography systems 208 Metrology and inspection systems"
        ),
        raw_path=Path("asml.html"),
        generated_at="2026-06-22T00:00:00Z",
    )

    assert msft_rows[0]["slot_id"] == "cloud_revenue"
    assert msft_rows[0]["value"] == 75_000_000_000
    assert msft_rows[0]["source_family"] == "company_product_evidence_graph"
    assert msft_rows[0]["signal_authority_type"] == "industry_operating_signal"
    assert msft_rows[0]["thesis_driver_authority"] is True
    assert "product_revenue" in msft_rows[0]["forbidden_claims"]
    assert {row["slot_id"] for row in asml_rows} >= {
        "semicap_system_sales_units",
        "semicap_euv_system_sales_units",
        "semicap_duv_system_sales_units",
    }


def test_summary_requires_all_r17_contract_roles() -> None:
    rows = [
        {"source_role": "technical_product_spec", "runtime_contract": "ProductSpecSlot", "source_family": "public_source_context", "ticker": "NVDA"},
        {"source_role": "product_generation_edge", "runtime_contract": "ProductGenerationEdge", "source_family": "public_source_context", "ticker": "NVDA"},
        {"source_role": "product_benchmark_proxy", "runtime_contract": "ProductBenchmarkProxy", "source_family": "public_source_context", "ticker": "NVDA"},
        {"source_role": "customer_deployment_proxy", "runtime_contract": "CustomerDeploymentProxy", "source_family": "public_source_context", "ticker": "NVDA"},
        {"source_role": "product_ecosystem_deployment_context", "runtime_contract": "ProductEcosystemContext", "source_family": "public_source_context", "ticker": "NVDA"},
        {
            "source_role": "industry_operating_metric",
            "runtime_contract": "IndustryOperatingMetricSlot",
            "source_family": "company_product_evidence_graph",
            "ticker": "MSFT",
        },
        {
            "source_role": "business_mix_operating_metric",
            "runtime_contract": "IndustryOperatingMetricSlot",
            "source_family": "company_product_evidence_graph",
            "ticker": "2317.TW",
        },
    ]

    summary = MODULE.build_summary(
        rows=rows,
        source_status=[{"file": "sample", "exists": True, "row_count": 1}],
        generated_at="2026-06-22T00:00:00Z",
        output_rows=Path("rows.jsonl"),
        output_report=Path("report.md"),
    )

    assert summary["status"] == "pass"
    assert summary["missing_required_roles"] == []
    assert summary["by_signal_authority_type"]
    assert "thesis_driver_authority_row_count" in summary
