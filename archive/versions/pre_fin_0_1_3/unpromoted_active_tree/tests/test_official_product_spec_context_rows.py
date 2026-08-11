from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_official_product_spec_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_official_product_spec_context_rows", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_extracts_official_gpu_specs_without_financial_authority() -> None:
    rows, diagnostics = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "NVDA",
                "company": "NVIDIA Corporation",
                "product": "H100 SXM",
                "source_url": "https://www.nvidia.com/en-us/data-center/h100/",
                "title": "NVIDIA H100 Tensor Core GPU",
                "body": (
                    "NVIDIA H100 SXM GPU Memory 80 GB and GPU Memory Bandwidth 3.35 TB/s. "
                    "FP8 Tensor Core performance reaches 1,979 teraFLOPS."
                ),
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert diagnostics["candidate_count"] >= 2
    assert rows
    assert {row["source_role"] for row in rows} == {"technical_product_spec"}
    assert {row["runtime_contract"] for row in rows} == {"ProductSpecSlot"}
    assert all(row["technical_spec_authority"] is True for row in rows)
    assert all(row["exact_value_authority"] is False for row in rows)
    assert "product_revenue" in rows[0]["forbidden_claims"]


def test_rejects_trade_in_and_site_metadata_numbers() -> None:
    rows, diagnostics = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "AAPL",
                "company": "Apple Inc.",
                "product": "iPhone",
                "source_url": "https://www.apple.com/iphone/",
                "title": "iPhone",
                "body": (
                    "Get iPhone 17e 256 GB with up to $1100 in credit after trade-in. "
                    "Carrier bill credits are applied over 36 months. "
                    "Cookie domain ajax.googleapis.com appears in the page."
                ),
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert rows == []
    assert diagnostics["rejected_candidate_count"] >= 1


def test_extracts_semicap_wafer_size_from_official_product_text() -> None:
    rows, _ = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "8035.T",
                "company": "Tokyo Electron Ltd.",
                "product": "Deposition systems",
                "source_url": "https://www.tel.com/product/",
                "title": "Products and Services",
                "body": "TELINDY PLUS is a batch thermal processing system for 300mm wafers.",
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert rows
    assert rows[0]["spec_name"] == "supported_wafer_size"
    assert rows[0]["unit"] == "mm"


def test_extracts_compute_core_and_model_parameter_specs() -> None:
    rows, diagnostics = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "NVDA",
                "company": "NVIDIA Corporation",
                "product": "Blackwell GPU",
                "source_url": "https://www.nvidia.com/en-us/data-center/blackwell/",
                "title": "NVIDIA Blackwell",
                "body": (
                    "The Blackwell GPU chip includes 208 billion transistors. "
                    "The accelerator platform supports 18,432 CUDA cores for compute workloads."
                ),
            },
            {
                "ticker": "META",
                "company": "Meta Platforms",
                "product": "Llama",
                "source_url": "https://ai.meta.com/llama/",
                "title": "Llama model",
                "body": "The Llama AI language model family includes a 405 billion parameters model.",
            },
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert diagnostics["candidate_count"] >= 3
    assert {"compute_core_count", "transistor_count", "model_parameter_count"}.issubset(
        {row["spec_name"] for row in rows}
    )


def test_rejects_support_hours_and_airline_loyalty_miles() -> None:
    rows, diagnostics = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "TENB",
                "company": "Tenable Holdings",
                "product": "Nessus",
                "source_url": "https://www.tenable.com/products/nessus",
                "title": "Nessus",
                "body": "Advanced Support includes phone support 24 hours a day, 365 days a year.",
            },
            {
                "ticker": "DAL",
                "company": "Delta Air Lines",
                "product": "SkyMiles",
                "source_url": "https://www.delta.com/skymiles",
                "title": "SkyMiles",
                "body": "Earn up to 8 miles per dollar on eligible Delta purchases.",
            },
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert rows == []
    assert diagnostics["rejected_candidate_count"] >= 2


def test_rejects_third_party_product_capacity_as_issuer_spec() -> None:
    rows, diagnostics = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "TOST",
                "company": "Toast, Inc.",
                "product": "Products and Platform",
                "source_url": "https://example.toast.com/platform",
                "title": "Toast platform",
                "body": "Cloudflare has a 192 Tb network capacity and protects the web application firewall layer.",
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert rows == []
    assert diagnostics["rejected_candidate_count"] >= 1


def test_rejects_generic_company_home_capacity_as_product_spec() -> None:
    rows, diagnostics = MODULE.build_official_product_spec_context_rows(
        page_rows=[
            {
                "ticker": "VST",
                "company": "Vistra Corp.",
                "product": "General Energy / Industrials",
                "source_url": "https://vistracorp.com/",
                "title": "Home - Vistra Corp.",
                "body": (
                    "The agreements include 2,176 MW of operating generation and an additional "
                    "433 MW of combined power output increases."
                ),
            }
        ],
        generated_at="2026-06-25T00:00:00Z",
    )
    assert rows == []
    assert "generic_product_family_not_product_spec" in diagnostics["rejection_reasons"]
