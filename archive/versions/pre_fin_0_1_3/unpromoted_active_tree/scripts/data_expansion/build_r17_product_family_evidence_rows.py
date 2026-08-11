from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.non_financial_signal_authority import attach_non_financial_signal_authority


SCHEMA_VERSION = "finsight_r17_product_family_evidence_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_r17_product_family_evidence_summary_v0_1"

DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw_private" / "r17_product_family_evidence"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "r17_product_family_evidence_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "r17_product_family_evidence_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = (
    REPO_ROOT
    / "docs"
    / "internal"
    / "vnext_20260610"
    / "vertical_lanes"
    / "r17_product_family_evidence.zh-CN.md"
)

SOURCE_URLS = {
    "nvidia_h100.html": "https://www.nvidia.com/en-us/data-center/h100/",
    "nvidia_gb200_nvl72.html": "https://www.nvidia.com/en-us/data-center/gb200-nvl72/",
    "nvidia_xai_colossus.html": "https://nvidianews.nvidia.com/news/spectrum-x-ethernet-networking-xai-colossus",
    "microsoft_ar25.html": "https://www.microsoft.com/investor/reports/ar25/index.html",
    "asml_2025_annual_report.html": "https://www.asml.com/investors/annual-report/2025",
    "tel_fy25q4_transcript.pdf": "https://www.tel.com/ir/library/report/l8gqgo00000000gl-att/fy25q4transcript-e.pdf",
    "tel_fy25q4_presentation.pdf": "https://www.tel.com/ir/library/report/l8gqgo00000000gl-att/fy25q4presentations-e.pdf",
    "honhai_fy2025_4q25.html": "https://www.honhai.com/en-us/press-center/press-releases/latest-news/1978",
}

FORBIDDEN_FINANCIAL_INFERENCE = [
    "product_revenue_without_company_disclosure",
    "ASP_without_company_or_tracker_data",
    "market_share",
    "sell_through",
    "channel_inventory",
    "customer_order_value",
]

FORBIDDEN_PRODUCT_KPI_INFERENCE = [
    "sku_revenue",
    "product_revenue",
    "ASP",
    "market_share",
    "sell_through",
    "channel_inventory",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build R17 ProductSpec/ProductGeneration/Deployment/OperatingMetric runtime rows."
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    rows, source_status = build_r17_product_family_evidence_rows(raw_dir=args.raw_dir, generated_at=generated_at)
    summary = build_summary(
        rows=rows,
        source_status=source_status,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_report=args.output_report,
    )
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["status"] != "pass":
        return 1
    return 0


def build_r17_product_family_evidence_rows(
    *, raw_dir: Path, generated_at: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []

    def add_html(file_name: str, parser: Any) -> None:
        path = raw_dir / file_name
        if not path.exists():
            source_status.append({"file": file_name, "exists": False, "row_count": 0})
            return
        text = _html_to_text(path.read_text(encoding="utf-8", errors="ignore"))
        parsed = parser(text=text, raw_path=path, generated_at=generated_at)
        rows.extend(parsed)
        source_status.append({"file": file_name, "exists": True, "row_count": len(parsed)})

    def add_pdf(file_name: str, parser: Any) -> None:
        path = raw_dir / file_name
        if not path.exists():
            source_status.append({"file": file_name, "exists": False, "row_count": 0})
            return
        text = _pdf_to_text(path)
        parsed = parser(text=text, raw_path=path, generated_at=generated_at)
        rows.extend(parsed)
        source_status.append({"file": file_name, "exists": True, "row_count": len(parsed)})

    add_html("nvidia_h100.html", parse_nvidia_h100_product_spec_rows)
    add_html("nvidia_gb200_nvl72.html", parse_nvidia_gb200_rows)
    add_html("nvidia_xai_colossus.html", parse_nvidia_xai_deployment_rows)
    add_html("microsoft_ar25.html", parse_microsoft_cloud_operating_metric_rows)
    add_html("asml_2025_annual_report.html", parse_asml_semicap_operating_metric_rows)
    add_pdf("tel_fy25q4_transcript.pdf", parse_tel_semicap_operating_metric_rows)
    add_html("honhai_fy2025_4q25.html", parse_honhai_business_mix_rows)

    return _dedupe_rows(rows), source_status


def parse_nvidia_h100_product_spec_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    memory_match = re.search(
        r"GPU Memory\s+(?P<sxm_memory>\d+)\s*GB\s+(?P<nvl_memory>\d+)\s*GB\s+"
        r"GPU Memory Bandwidth\s+(?P<sxm_bandwidth>[0-9.]+)\s*TB/s\s+(?P<nvl_bandwidth>[0-9.]+)\s*TB/s",
        text,
        flags=re.IGNORECASE,
    )
    fp8_match = re.search(
        r"FP8 Tensor Core\s*\*?\s+(?P<sxm_fp8>[0-9,]+)\s+teraFLOPS\s+(?P<nvl_fp8>[0-9,]+)\s+teraFLOPS",
        text,
        flags=re.IGNORECASE,
    )
    int8_match = re.search(
        r"INT8 Tensor Core\s*\*?\s+(?P<sxm_int8>[0-9,]+)\s+TOPS\s+(?P<nvl_int8>[0-9,]+)\s+TOPS",
        text,
        flags=re.IGNORECASE,
    )
    citation = _citation_around(
        text,
        "GPU Memory",
        fallback="NVIDIA H100 product page lists H100 SXM and H100 NVL specifications, including memory and bandwidth.",
    )
    if memory_match:
        rows.extend(
            [
                _public_context_row(
                    generated_at=generated_at,
                    raw_path=raw_path,
                    ticker="NVDA",
                    company_name="NVIDIA Corporation",
                    source_id="official_nvidia_product_page",
                    source_role="technical_product_spec",
                    runtime_contract="ProductSpecSlot",
                    structured_context_type="technical_product_spec",
                    product_or_segment="H100 SXM",
                    product_family="Hopper data center GPU",
                    metric_name="GPU memory",
                    value=float(memory_match.group("sxm_memory")),
                    unit="GB",
                    source_url=SOURCE_URLS["nvidia_h100.html"],
                    citation_span=citation,
                    claim_types=["technical_product_spec"],
                    allowed_claims=["technical_product_spec", "product_comparison_context"],
                    claim_boundary="Official NVIDIA product-page technical spec; supports product comparison only, not revenue, ASP, unit sales, or market share.",
                ),
                _public_context_row(
                    generated_at=generated_at,
                    raw_path=raw_path,
                    ticker="NVDA",
                    company_name="NVIDIA Corporation",
                    source_id="official_nvidia_product_page",
                    source_role="technical_product_spec",
                    runtime_contract="ProductSpecSlot",
                    structured_context_type="technical_product_spec",
                    product_or_segment="H100 NVL",
                    product_family="Hopper data center GPU",
                    metric_name="GPU memory",
                    value=float(memory_match.group("nvl_memory")),
                    unit="GB",
                    source_url=SOURCE_URLS["nvidia_h100.html"],
                    citation_span=citation,
                    claim_types=["technical_product_spec"],
                    allowed_claims=["technical_product_spec", "product_comparison_context"],
                    claim_boundary="Official NVIDIA product-page technical spec; supports product comparison only, not revenue, ASP, unit sales, or market share.",
                ),
                _public_context_row(
                    generated_at=generated_at,
                    raw_path=raw_path,
                    ticker="NVDA",
                    company_name="NVIDIA Corporation",
                    source_id="official_nvidia_product_page",
                    source_role="technical_product_spec",
                    runtime_contract="ProductSpecSlot",
                    structured_context_type="technical_product_spec",
                    product_or_segment="H100 SXM",
                    product_family="Hopper data center GPU",
                    metric_name="GPU memory bandwidth",
                    value=float(memory_match.group("sxm_bandwidth")),
                    unit="TB/s",
                    source_url=SOURCE_URLS["nvidia_h100.html"],
                    citation_span=citation,
                    claim_types=["technical_product_spec"],
                    allowed_claims=["technical_product_spec", "product_comparison_context"],
                    claim_boundary="Official NVIDIA product-page technical spec; supports product comparison only, not revenue, ASP, unit sales, or market share.",
                ),
                _public_context_row(
                    generated_at=generated_at,
                    raw_path=raw_path,
                    ticker="NVDA",
                    company_name="NVIDIA Corporation",
                    source_id="official_nvidia_product_page",
                    source_role="technical_product_spec",
                    runtime_contract="ProductSpecSlot",
                    structured_context_type="technical_product_spec",
                    product_or_segment="H100 NVL",
                    product_family="Hopper data center GPU",
                    metric_name="GPU memory bandwidth",
                    value=float(memory_match.group("nvl_bandwidth")),
                    unit="TB/s",
                    source_url=SOURCE_URLS["nvidia_h100.html"],
                    citation_span=citation,
                    claim_types=["technical_product_spec"],
                    allowed_claims=["technical_product_spec", "product_comparison_context"],
                    claim_boundary="Official NVIDIA product-page technical spec; supports product comparison only, not revenue, ASP, unit sales, or market share.",
                ),
            ]
        )
    if fp8_match:
        rows.extend(
            _h100_accelerator_rows(
                generated_at=generated_at,
                raw_path=raw_path,
                metric_name="FP8 Tensor Core performance",
                sxm_value=_parse_number(fp8_match.group("sxm_fp8")),
                nvl_value=_parse_number(fp8_match.group("nvl_fp8")),
                unit="teraFLOPS",
                citation_span=_citation_around(text, "FP8 Tensor Core", fallback=citation),
            )
        )
    if int8_match:
        rows.extend(
            _h100_accelerator_rows(
                generated_at=generated_at,
                raw_path=raw_path,
                metric_name="INT8 Tensor Core performance",
                sxm_value=_parse_number(int8_match.group("sxm_int8")),
                nvl_value=_parse_number(int8_match.group("nvl_int8")),
                unit="TOPS",
                citation_span=_citation_around(text, "INT8 Tensor Core", fallback=citation),
            )
        )
    return rows


def parse_nvidia_gb200_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    citation = _citation_around(text, "The NVIDIA GB200 NVL72 connects", fallback="")
    match = re.search(
        r"GB200 NVL72 connects (?P<cpu>\d+) Grace CPUs and (?P<gpu>\d+) Blackwell GPUs.*?"
        r"(?P<nvlink>\d+)-GPU NVIDIA NVLink.*?delivers (?P<inference>[0-9]+)x faster.*?"
        r"(?P<moe>[0-9]+)x greater performance",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return rows
    rows.extend(
        [
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_product_page",
                source_role="technical_product_spec",
                runtime_contract="ProductSpecSlot",
                structured_context_type="technical_product_spec",
                product_or_segment="GB200 NVL72",
                product_family="Blackwell rack-scale AI system",
                metric_name="Blackwell GPU count",
                value=float(match.group("gpu")),
                unit="GPUs",
                source_url=SOURCE_URLS["nvidia_gb200_nvl72.html"],
                citation_span=citation,
                claim_types=["technical_product_spec"],
                allowed_claims=["technical_product_spec", "rack_scale_architecture_context"],
                claim_boundary="Official NVIDIA product-page rack-scale configuration; supports architecture comparison only, not revenue or order value.",
            ),
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_product_page",
                source_role="technical_product_spec",
                runtime_contract="ProductSpecSlot",
                structured_context_type="technical_product_spec",
                product_or_segment="GB200 NVL72",
                product_family="Blackwell rack-scale AI system",
                metric_name="Grace CPU count",
                value=float(match.group("cpu")),
                unit="CPUs",
                source_url=SOURCE_URLS["nvidia_gb200_nvl72.html"],
                citation_span=citation,
                claim_types=["technical_product_spec"],
                allowed_claims=["technical_product_spec", "rack_scale_architecture_context"],
                claim_boundary="Official NVIDIA product-page rack-scale configuration; supports architecture comparison only, not revenue or order value.",
            ),
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_product_page",
                source_role="product_benchmark_proxy",
                runtime_contract="ProductBenchmarkProxy",
                structured_context_type="product_benchmark_proxy",
                product_or_segment="GB200 NVL72",
                product_family="Blackwell rack-scale AI system",
                metric_name="real-time trillion-parameter LLM inference speedup",
                value=float(match.group("inference")),
                unit="x",
                source_url=SOURCE_URLS["nvidia_gb200_nvl72.html"],
                citation_span=citation,
                claim_types=["product_benchmark_proxy"],
                allowed_claims=["vendor_disclosed_performance_context", "product_comparison_context"],
                claim_boundary="Vendor-disclosed benchmark context; use as product capability signal, not independent market performance or customer demand proof.",
            ),
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_product_page",
                source_role="product_benchmark_proxy",
                runtime_contract="ProductBenchmarkProxy",
                structured_context_type="product_benchmark_proxy",
                product_or_segment="GB200 NVL72",
                product_family="Blackwell rack-scale AI system",
                metric_name="mixture-of-experts performance uplift",
                value=float(match.group("moe")),
                unit="x",
                source_url=SOURCE_URLS["nvidia_gb200_nvl72.html"],
                citation_span=citation,
                claim_types=["product_benchmark_proxy"],
                allowed_claims=["vendor_disclosed_performance_context", "product_comparison_context"],
                claim_boundary="Vendor-disclosed benchmark context; use as product capability signal, not independent market performance or customer demand proof.",
            ),
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_product_page",
                source_role="product_generation_edge",
                runtime_contract="ProductGenerationEdge",
                structured_context_type="product_generation_edge",
                product_or_segment="Hopper to Blackwell",
                product_family="NVIDIA data center accelerator generations",
                metric_name="generation transition",
                value="GB200 NVL72 Blackwell rack-scale system after Hopper/H100 generation",
                unit="categorical",
                source_url=SOURCE_URLS["nvidia_gb200_nvl72.html"],
                citation_span=citation,
                claim_types=["product_generation_edge"],
                allowed_claims=["product_generation_context", "architecture_transition_context"],
                claim_boundary="Official product-page generation context; supports product roadmap/comparison framing, not revenue timing or customer adoption.",
            ),
        ]
    )
    return rows


def parse_nvidia_xai_deployment_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first = re.search(r"Colossus supercomputer cluster comprising (?P<count>[0-9,]+) NVIDIA Hopper GPUs", text, re.I)
    expansion = re.search(r"doubling the size of Colossus to a combined total of (?P<count>[0-9,]+) NVIDIA Hopper GPUs", text, re.I)
    if first:
        rows.append(
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_customer_deployment_news",
                source_role="customer_deployment_proxy",
                runtime_contract="CustomerDeploymentProxy",
                structured_context_type="customer_deployment_proxy",
                product_or_segment="NVIDIA Hopper GPUs",
                product_family="Hopper data center GPU deployment",
                metric_name="xAI Colossus initial Hopper GPU deployment",
                value=_parse_number(first.group("count")),
                unit="GPUs",
                customer_name="xAI",
                location="Memphis, Tennessee",
                source_url=SOURCE_URLS["nvidia_xai_colossus.html"],
                citation_span=_citation_around(text, "Colossus supercomputer cluster comprising", fallback=first.group(0)),
                claim_types=["customer_deployment_proxy"],
                allowed_claims=["named_customer_deployment_proxy", "demand_direction_context"],
                claim_boundary="Official NVIDIA customer-deployment news; supports named deployment/proxy context only, not revenue, ASP, shipment, or order value.",
            )
        )
    if expansion:
        rows.append(
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_customer_deployment_news",
                source_role="customer_deployment_proxy",
                runtime_contract="CustomerDeploymentProxy",
                structured_context_type="customer_deployment_proxy",
                product_or_segment="NVIDIA Hopper GPUs",
                product_family="Hopper data center GPU deployment",
                metric_name="xAI Colossus planned combined Hopper GPU deployment",
                value=_parse_number(expansion.group("count")),
                unit="GPUs",
                customer_name="xAI",
                location="Memphis, Tennessee",
                source_url=SOURCE_URLS["nvidia_xai_colossus.html"],
                citation_span=_citation_around(text, "doubling the size of Colossus", fallback=expansion.group(0)),
                claim_types=["customer_deployment_proxy"],
                allowed_claims=["named_customer_deployment_proxy", "demand_direction_context"],
                claim_boundary="Official NVIDIA customer-deployment news; supports named deployment/proxy context only, not revenue, ASP, shipment, or order value.",
            )
        )
    if "Spectrum-X" in text and first:
        rows.append(
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_customer_deployment_news",
                source_role="product_ecosystem_deployment_context",
                runtime_contract="ProductEcosystemContext",
                structured_context_type="product_ecosystem_deployment_context",
                product_or_segment="NVIDIA Spectrum-X Ethernet networking",
                product_family="AI infrastructure networking ecosystem",
                metric_name="Spectrum-X used in xAI Colossus deployment",
                value="Spectrum-X Ethernet networking used in xAI Colossus",
                unit="categorical",
                customer_name="xAI",
                source_url=SOURCE_URLS["nvidia_xai_colossus.html"],
                citation_span=_citation_around(text, "Spectrum-X", fallback="NVIDIA Spectrum-X Ethernet networking was cited for xAI Colossus."),
                claim_types=["product_ecosystem_context", "customer_deployment_proxy"],
                allowed_claims=["ecosystem_attachment_context", "supply_chain_product_context"],
                claim_boundary="Official deployment ecosystem context; supports product adjacency and architecture discussion, not revenue attribution.",
            )
        )
    return rows


def parse_microsoft_cloud_operating_metric_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    match = re.search(r"Azure surpassed \$(?P<value>[0-9.]+) billion in revenue.*?up (?P<growth>[0-9.]+) percent", text, re.I)
    if not match:
        return []
    citation = _citation_around(text, "Azure surpassed", fallback=match.group(0))
    value = float(match.group("value")) * 1_000_000_000
    return [
        _industry_metric_row(
            generated_at=generated_at,
            raw_path=raw_path,
            ticker="MSFT",
            company_name="Microsoft Corporation",
            source_id="microsoft_annual_report",
            source_role="industry_operating_metric",
            structured_context_type="industry_operating_metric_exact_slot",
            slot_id="cloud_revenue",
            product_or_segment="Azure",
            metric_name="Azure revenue",
            metric_family="cloud_revenue",
            value=value,
            unit="USD",
            period="FY2025",
            fiscal_year=2025,
            source_url=SOURCE_URLS["microsoft_ar25.html"],
            citation_span=citation,
            claim_types=["company_disclosed_industry_operating_metric", "cloud_operating_metric"],
            allowed_claims=["company_disclosed_cloud_revenue", "cloud_scale_operating_metric"],
            claim_boundary="Microsoft annual-report cloud operating metric; supports Azure revenue and growth only, not SKU revenue, cloud customer count, or market share.",
            extra={"growth_pct": float(match.group("growth"))},
        )
    ]


def parse_asml_semicap_operating_metric_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    match = re.search(
        r"System sales in units\s+(?P<total>\d+).*?(?P<euv>\d+)\s+EUV lithography systems\s+"
        r"(?P<duv>\d+)\s+DUV lithography systems\s+(?P<metrology>\d+)\s+Metrology and inspection systems",
        text,
        re.I | re.S,
    )
    if not match:
        return []
    citation = _citation_around(text, "System sales in units", fallback=match.group(0))
    specs = [
        ("total system sales", "semicap_system_sales_units", float(match.group("total")), "All ASML systems"),
        ("EUV lithography system sales", "semicap_euv_system_sales_units", float(match.group("euv")), "EUV lithography systems"),
        ("DUV lithography system sales", "semicap_duv_system_sales_units", float(match.group("duv")), "DUV lithography systems"),
        (
            "Metrology and inspection system sales",
            "semicap_metrology_inspection_system_sales_units",
            float(match.group("metrology")),
            "Metrology and inspection systems",
        ),
    ]
    return [
        _industry_metric_row(
            generated_at=generated_at,
            raw_path=raw_path,
            ticker="ASML",
            company_name="ASML Holding N.V.",
            source_id="asml_annual_report",
            source_role="industry_operating_metric",
            structured_context_type="industry_operating_metric_exact_slot",
            slot_id=slot_id,
            product_or_segment=segment,
            metric_name=metric_name,
            metric_family="semicap_system_sales_units",
            value=value,
            unit="systems",
            period="FY2025",
            fiscal_year=2025,
            source_url=SOURCE_URLS["asml_2025_annual_report.html"],
            citation_span=citation,
            claim_types=["company_disclosed_industry_operating_metric", "semicap_operating_metric"],
            allowed_claims=["company_disclosed_system_sales_units", "semicap_operating_metric"],
            claim_boundary="ASML annual-report system unit metric; supports cited system/unit mix only, not product revenue, ASP, backlog, or market share.",
        )
        for metric_name, slot_id, value, segment in specs
    ]


def parse_tel_semicap_operating_metric_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    field = re.search(
        r"FY2025,?\s+field solution[s]? sales (?:were|was)\s+(?P<value>[0-9.]+)\s*billion yen,?\s+"
        r"(?:growing by|up)\s+(?P<growth>[0-9.]+)%\s+(?:year over year|YoY)",
        text,
        re.I,
    )
    if field:
        rows.append(
            _industry_metric_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="8035.T",
                company_name="Tokyo Electron Limited",
                source_id="tel_ir_transcript",
                source_role="industry_operating_metric",
                structured_context_type="industry_operating_metric_exact_slot",
                slot_id="semicap_field_solutions_sales",
                product_or_segment="Field Solutions",
                metric_name="Field Solutions sales",
                metric_family="semicap_field_solutions_sales",
                value=float(field.group("value")) * 1_000_000_000,
                unit="JPY",
                period="FY2025",
                fiscal_year=2025,
                source_url=SOURCE_URLS["tel_fy25q4_transcript.pdf"],
                citation_span=_citation_around(text, "field solution sales", fallback=field.group(0)),
                claim_types=["company_disclosed_industry_operating_metric", "semicap_operating_metric"],
                allowed_claims=["company_disclosed_field_solutions_sales", "semicap_installed_base_service_signal"],
                claim_boundary="Tokyo Electron IR transcript operating metric; supports Field Solutions sales and YoY growth only, not equipment SKU revenue or market share.",
                extra={"growth_pct": float(field.group("growth"))},
            )
        )
    application = re.search(
        r"SPE New Equipment Sales by Application.*?(?P<non_memory>\d+)%\s+(?P<nand>\d+)%\s+(?P<dram>\d+)%.*?FY2025",
        text,
        re.I | re.S,
    )
    if application:
        rows.append(
            _industry_metric_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="8035.T",
                company_name="Tokyo Electron Limited",
                source_id="tel_ir_transcript",
                source_role="industry_operating_metric",
                structured_context_type="industry_operating_metric_exact_slot",
                slot_id="semicap_new_equipment_sales_application_mix",
                product_or_segment="SPE new equipment application mix",
                metric_name="SPE new equipment sales application mix",
                metric_family="semicap_application_mix",
                value={
                    "non_memory_pct": float(application.group("non_memory")),
                    "nand_pct": float(application.group("nand")),
                    "dram_pct": float(application.group("dram")),
                },
                unit="percent_mix",
                period="FY2025",
                fiscal_year=2025,
                source_url=SOURCE_URLS["tel_fy25q4_transcript.pdf"],
                citation_span=_citation_around(text, "SPE New Equipment Sales by Application", fallback=application.group(0)),
                claim_types=["company_disclosed_industry_operating_metric", "semicap_operating_metric"],
                allowed_claims=["company_disclosed_application_mix", "semicap_demand_mix_context"],
                claim_boundary="Tokyo Electron IR application-mix operating metric; supports application mix context only, not customer-specific orders or market share.",
            )
        )
    return rows


def parse_honhai_business_mix_rows(*, text: str, raw_path: Path | str, generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    revenue = re.search(r"2025 full-year revenue reached NT\$(?P<value>[0-9.]+) trillion.*?year-on-year increase of (?P<growth>[0-9.]+)%", text, re.I)
    mix_phrase = re.search(
        r"revenue from cloud and networking products surpassed that of smart consumer electronics products.*?becoming the largest product category in the quarter",
        text,
        re.I | re.S,
    )
    if revenue:
        rows.append(
            _industry_metric_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="2317.TW",
                company_name="Hon Hai Precision Industry Co., Ltd.",
                source_id="honhai_ir_press_release",
                source_role="industry_operating_metric",
                structured_context_type="industry_operating_metric_exact_slot",
                slot_id="total_revenue",
                product_or_segment="Hon Hai total company",
                metric_name="full-year revenue",
                metric_family="total_revenue",
                value=float(revenue.group("value")) * 1_000_000_000_000,
                unit="TWD",
                period="FY2025",
                fiscal_year=2025,
                source_url=SOURCE_URLS["honhai_fy2025_4q25.html"],
                citation_span=_citation_around(text, "2025 full-year revenue", fallback=revenue.group(0)),
                claim_types=["company_disclosed_industry_operating_metric"],
                allowed_claims=["company_disclosed_total_revenue"],
                claim_boundary="Hon Hai official total-company revenue metric; supports total revenue only, not product/SKU revenue or AI server sales.",
                extra={"growth_pct": float(revenue.group("growth"))},
            )
        )
    if mix_phrase:
        rows.append(
            _industry_metric_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="2317.TW",
                company_name="Hon Hai Precision Industry Co., Ltd.",
                source_id="honhai_ir_press_release",
                source_role="business_mix_operating_metric",
                structured_context_type="business_mix_operating_metric",
                slot_id="cloud_networking_largest_product_category_q4",
                product_or_segment="Cloud and Networking Products",
                metric_name="cloud and networking became largest product category in Q4",
                metric_family="business_mix_rank",
                value="largest_product_category_in_q4",
                unit="categorical_rank",
                period="FY2025 Q4",
                fiscal_year=2025,
                source_url=SOURCE_URLS["honhai_fy2025_4q25.html"],
                citation_span=_citation_around(text, "cloud and networking products surpassed", fallback=mix_phrase.group(0)),
                claim_types=["company_disclosed_industry_operating_metric", "business_mix_operating_metric"],
                allowed_claims=["company_disclosed_business_mix_rank", "ai_server_exposure_context"],
                claim_boundary="Hon Hai official category-mix statement; supports business mix/exposure direction only, not exact AI server revenue, product revenue, ASP, or unit shipments.",
            )
        )
    return rows


def build_summary(
    *,
    rows: list[Mapping[str, Any]],
    source_status: list[Mapping[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_report: Path,
) -> dict[str, Any]:
    required_roles = {
        "technical_product_spec",
        "product_generation_edge",
        "product_benchmark_proxy",
        "customer_deployment_proxy",
        "product_ecosystem_deployment_context",
        "industry_operating_metric",
        "business_mix_operating_metric",
    }
    role_counts = Counter(str(row.get("source_role") or "") for row in rows)
    missing_roles = sorted(role for role in required_roles if role_counts.get(role, 0) == 0)
    ticker_counts = Counter(str(row.get("ticker") or "") for row in rows)
    signal_counts = Counter(str(row.get("signal_authority_type") or "") for row in rows)
    signal_promotion_counts = Counter(str(row.get("signal_promotion_level") or "") for row in rows)
    source_failures = [status for status in source_status if not status.get("exists") or int(status.get("row_count") or 0) == 0]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not missing_roles and not source_failures else "gap",
        "runtime_row_count": len(rows),
        "ticker_count": len([ticker for ticker in ticker_counts if ticker]),
        "by_ticker": dict(sorted(ticker_counts.items())),
        "by_source_role": dict(sorted(role_counts.items())),
        "by_runtime_contract": _count(rows, "runtime_contract"),
        "by_source_family": _count(rows, "source_family"),
        "by_signal_authority_type": dict(sorted(signal_counts.items())),
        "by_signal_promotion_level": dict(sorted(signal_promotion_counts.items())),
        "thesis_driver_authority_row_count": sum(1 for row in rows if bool(row.get("thesis_driver_authority"))),
        "missing_required_roles": missing_roles,
        "source_status": [dict(item) for item in source_status],
        "source_failures": [dict(item) for item in source_failures],
        "outputs": {"rows": str(output_rows), "report": str(output_report)},
        "policy": (
            "R17 product-family evidence rows add non-financial product/spec/proxy contracts and industry operating "
            "metric slots. Product/spec/proxy rows cannot support company financial exact facts; operating metric rows "
            "support only their cited company-disclosed metric/period, not Product-KPI exact revenue unless explicitly "
            "labeled as such."
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# R17 Product Family Evidence Runtime Rows",
            "",
            f"- schema_version: `{summary.get('schema_version')}`",
            f"- generated_at: `{summary.get('generated_at')}`",
            f"- status: `{summary.get('status')}`",
            f"- runtime_row_count: `{summary.get('runtime_row_count')}`",
            f"- ticker_count: `{summary.get('ticker_count')}`",
            "",
            "## By Source Role",
            "",
            "```json",
            json.dumps(summary.get("by_source_role") or {}, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## By Signal Authority",
            "",
            "```json",
            json.dumps(summary.get("by_signal_authority_type") or {}, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            f"- thesis_driver_authority_row_count: `{summary.get('thesis_driver_authority_row_count')}`",
            "",
            "## Source Status",
            "",
            "```json",
            json.dumps(summary.get("source_status") or [], ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Policy",
            "",
            str(summary.get("policy") or ""),
            "",
        ]
    )


def _h100_accelerator_rows(
    *,
    generated_at: str,
    raw_path: Path | str,
    metric_name: str,
    sxm_value: float,
    nvl_value: float,
    unit: str,
    citation_span: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product, value in (("H100 SXM", sxm_value), ("H100 NVL", nvl_value)):
        rows.append(
            _public_context_row(
                generated_at=generated_at,
                raw_path=raw_path,
                ticker="NVDA",
                company_name="NVIDIA Corporation",
                source_id="official_nvidia_product_page",
                source_role="technical_product_spec",
                runtime_contract="ProductSpecSlot",
                structured_context_type="technical_product_spec",
                product_or_segment=product,
                product_family="Hopper data center GPU",
                metric_name=metric_name,
                value=value,
                unit=unit,
                source_url=SOURCE_URLS["nvidia_h100.html"],
                citation_span=citation_span,
                claim_types=["technical_product_spec"],
                allowed_claims=["technical_product_spec", "product_comparison_context"],
                claim_boundary="Official NVIDIA product-page technical spec; supports product comparison only, not revenue, ASP, unit sales, or market share.",
            )
        )
    return rows


def _public_context_row(
    *,
    generated_at: str,
    raw_path: Path | str,
    ticker: str,
    company_name: str,
    source_id: str,
    source_role: str,
    runtime_contract: str,
    structured_context_type: str,
    product_or_segment: str,
    product_family: str,
    metric_name: str,
    value: Any,
    unit: str,
    source_url: str,
    citation_span: str,
    claim_types: list[str],
    allowed_claims: list[str],
    claim_boundary: str,
    customer_name: str = "",
    location: str = "",
) -> dict[str, Any]:
    evidence_ref = f"r17_product_family_evidence:{_short_hash(ticker, source_role, product_or_segment, metric_name, value, unit)}"
    row = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "company_name": company_name,
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L2",
        "source_id": source_id,
        "source_role": source_role,
        "runtime_contract": runtime_contract,
        "structured_context_type": structured_context_type,
        "parser_status": "parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot" if customer_name else "",
        "source_url": source_url,
        "raw_path": str(raw_path),
        "product_or_segment": product_or_segment,
        "product_family": product_family,
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "customer_name": customer_name,
        "location": location,
        "promotion_status": "runtime_context_allowed",
        "runtime_action": "use_as_context_not_financial_exact",
        "technical_spec_authority": source_role in {"technical_product_spec"},
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "claim_types": claim_types,
        "allowed_claims": allowed_claims,
        "forbidden_claims": FORBIDDEN_FINANCIAL_INFERENCE,
        "citation_span": _clean_sentence(citation_span),
        "claim_boundary": claim_boundary,
    }
    return attach_non_financial_signal_authority(row)


def _industry_metric_row(
    *,
    generated_at: str,
    raw_path: Path | str,
    ticker: str,
    company_name: str,
    source_id: str,
    source_role: str,
    structured_context_type: str,
    slot_id: str,
    product_or_segment: str,
    metric_name: str,
    metric_family: str,
    value: Any,
    unit: str,
    period: str,
    fiscal_year: int,
    source_url: str,
    citation_span: str,
    claim_types: list[str],
    allowed_claims: list[str],
    claim_boundary: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_ref = f"r17_product_family_evidence:{_short_hash(ticker, slot_id, product_or_segment, metric_name, value, period)}"
    row = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "company_name": company_name,
        "source_family": "company_product_evidence_graph",
        "runtime_source_family": "company_product_evidence_graph",
        "source_layer_id": "L1",
        "source_id": source_id,
        "source_role": source_role,
        "runtime_contract": "IndustryOperatingMetricSlot",
        "structured_context_type": structured_context_type,
        "slot_id": slot_id,
        "source_url": source_url,
        "raw_path": str(raw_path),
        "product_or_segment": product_or_segment,
        "metric_name": metric_name,
        "metric_family": metric_family,
        "value": value,
        "unit": unit,
        "period": period,
        "fiscal_year": fiscal_year,
        "product_node_type": "business_or_industry_operating_metric",
        "promotion_status": "runtime_fact_allowed",
        "runtime_action": "promote_industry_operating_metric_exact",
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "claim_types": claim_types,
        "allowed_claims": allowed_claims,
        "forbidden_claims": FORBIDDEN_PRODUCT_KPI_INFERENCE,
        "citation_span": _clean_sentence(citation_span),
        "claim_boundary": claim_boundary,
    }
    if extra:
        row.update(dict(extra))
    return attach_non_financial_signal_authority(row)


def _html_to_text(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _pdf_to_text(path: Path) -> str:
    try:
        import pypdf
    except Exception as exc:  # pragma: no cover - dependency guard for non-prod shells.
        raise RuntimeError("pypdf is required to extract R17 TEL PDF snapshots") from exc
    reader = pypdf.PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", text).strip()


def _citation_around(text: str, needle: str, *, fallback: str, window: int = 260) -> str:
    index = text.lower().find(needle.lower())
    if index < 0:
        return fallback
    start = max(0, index - window // 2)
    end = min(len(text), index + window)
    return text[start:end]


def _parse_number(value: str) -> float:
    return float(str(value).replace(",", ""))


def _clean_sentence(value: str) -> str:
    text = re.sub(r"\s+", " ", html.unescape(str(value))).strip()
    return text.rstrip(".") + "." if text else ""


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("evidence_ref") or json.dumps(dict(row), ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return output


def _count(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter(str(row.get(key) or "unknown") for row in rows)
    return dict(sorted(counter.items()))


def _short_hash(*values: object) -> str:
    digest = hashlib.sha256("|".join(str(value) for value in values).encode("utf-8")).hexdigest()
    return digest[:16]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
