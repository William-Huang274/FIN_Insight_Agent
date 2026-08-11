from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[2]

SPEC_ROWS = REPO_ROOT / "data" / "manifests" / "ai_semis_product_spec_followup_context_rows_v0_1.jsonl"
DEPLOYMENT_ROWS = REPO_ROOT / "data" / "manifests" / "ai_semis_customer_deployment_followup_context_rows_v0_1.jsonl"
PROXY_ROWS = REPO_ROOT / "data" / "manifests" / "ai_semis_product_performance_proxy_followup_context_rows_v0_1.jsonl"
ATTEMPTS = REPO_ROOT / "data" / "manifests" / "ai_semis_product_depth_followup_attempts_v0_1.jsonl"
SUMMARY = REPO_ROOT / "data" / "manifests" / "ai_semis_product_depth_followup_summary_v0_1.json"

CONTEXT_BOUNDARY = (
    "Targeted follow-up product context only. Supports bounded product capability, architecture, adoption, "
    "technology, supply-chain, or demand-direction claims; does not prove product revenue, sales, shipments, "
    "ASP, market share, inventory, sell-through, backlog, order value, or customer spend unless a separate "
    "exact Product-KPI row exists."
)

LAYER_TO_OUTPUT = {
    "product_spec_architecture": SPEC_ROWS,
    "customer_deployment_adoption": DEPLOYMENT_ROWS,
    "product_performance_proxy": PROXY_ROWS,
}


@dataclass(frozen=True)
class FollowupTarget:
    ticker: str
    company_name: str
    evidence_layer: str
    source_id: str
    source_role: str
    source_url: str
    product_family: str
    product_or_segment: str
    metric_name: str
    expected_terms: tuple[str, ...]
    source_layer: str = "L2"
    counterparty: str = ""
    relationship_role: str = ""
    edge_type: str = ""
    claim_boundary: str = CONTEXT_BOUNDARY


TARGETS: tuple[FollowupTarget, ...] = (
    FollowupTarget(
        ticker="005930.KS",
        company_name="Samsung Electronics Co., Ltd.",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_official_product_spec",
        source_role="technical_product_spec",
        source_url="https://semiconductor.samsung.com/dram/hbm/hbm3e/",
        product_family="Memory / Storage Semiconductors",
        product_or_segment="HBM3E",
        metric_name="official_hbm3e_product_spec_context",
        expected_terms=("hbm3e", "bandwidth", "memory"),
    ),
    FollowupTarget(
        ticker="2308.TW",
        company_name="Delta Electronics, Inc.",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_official_product_spec",
        source_role="technical_product_spec",
        source_url="https://www.deltaww.com/en-US/products/data-center/",
        product_family="Datacenter Power / Cooling",
        product_or_segment="Data Center Infrastructure",
        metric_name="official_datacenter_power_cooling_product_context",
        expected_terms=("data center", "power", "cooling"),
    ),
    FollowupTarget(
        ticker="2317.TW",
        company_name="Hon Hai Precision Industry Co., Ltd.",
        evidence_layer="product_performance_proxy",
        source_id="ai_semis_targeted_trusted_customer_deployment_proxy",
        source_role="customer_deployment_proxy",
        source_url="https://nvidianews.nvidia.com/news/foxconn-builds-ai-factory-in-partnership-with-taiwan-and-nvidia",
        product_family="AI Server / Infrastructure OEM",
        product_or_segment="Foxconn AI factory / AI server buildout",
        metric_name="trusted_official_ai_factory_deployment_proxy",
        expected_terms=("foxconn", "ai factory", "nvidia"),
        source_layer="L3",
        counterparty="NVIDIA",
        relationship_role="deployed_by_or_adopted_by",
        edge_type="deployed_by_or_adopted_by",
    ),
    FollowupTarget(
        ticker="ACLS",
        company_name="AXCELIS TECHNOLOGIES INC",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_official_product_spec",
        source_role="technical_product_spec",
        source_url="https://www.axcelis.com/products/purion/",
        product_family="Semiconductor Capital Equipment",
        product_or_segment="Purion ion implant platform",
        metric_name="official_ion_implant_platform_context",
        expected_terms=("purion", "ion", "implant"),
    ),
    FollowupTarget(
        ticker="ETN",
        company_name="Eaton Corporation",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_issuer_disclosure_product_architecture",
        source_role="technical_product_spec",
        source_url="https://www.sec.gov/Archives/edgar/data/1551182/000155118226000007/etn-20251231.htm",
        product_family="Datacenter Power / Cooling",
        product_or_segment="Electrical Americas / Electrical Global",
        metric_name="issuer_disclosed_power_management_product_architecture_context",
        expected_terms=("electrical", "power", "data center"),
    ),
    FollowupTarget(
        ticker="LSCC",
        company_name="LATTICE SEMICONDUCTOR CORP",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_issuer_disclosure_product_architecture",
        source_role="technical_product_spec",
        source_url="https://www.sec.gov/Archives/edgar/data/855658/000143774925003987/lscc20241228_10k.htm",
        product_family="FPGA / Programmable Logic",
        product_or_segment="Low-power FPGA product families",
        metric_name="issuer_disclosed_fpga_product_architecture_context",
        expected_terms=("fpga", "lattice", "low power"),
    ),
    FollowupTarget(
        ticker="LSCC",
        company_name="LATTICE SEMICONDUCTOR CORP",
        evidence_layer="customer_deployment_adoption",
        source_id="ai_semis_targeted_issuer_disclosure_end_market_adoption",
        source_role="customer_deployment_proxy",
        source_url="https://www.sec.gov/Archives/edgar/data/855658/000143774925003987/lscc20241228_10k.htm",
        product_family="FPGA / Programmable Logic",
        product_or_segment="Low-power FPGA end-market adoption",
        metric_name="issuer_disclosed_end_market_adoption_context",
        expected_terms=("communications", "industrial", "automotive"),
        source_layer="L3",
        relationship_role="deployed_by_or_adopted_by",
        edge_type="deployed_by_or_adopted_by",
    ),
    FollowupTarget(
        ticker="MCHP",
        company_name="Microchip Technology",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_official_product_spec",
        source_role="technical_product_spec",
        source_url="https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/ProductBrief/PolarFire-FPGA-Product-Overview-60001657.pdf",
        product_family="MCU / Analog / FPGA",
        product_or_segment="PolarFire FPGA",
        metric_name="official_polarfire_fpga_product_spec_context",
        expected_terms=("polarfire", "fpga", "microchip"),
    ),
    FollowupTarget(
        ticker="TXN",
        company_name="Texas Instruments",
        evidence_layer="product_spec_architecture",
        source_id="ai_semis_targeted_official_product_spec",
        source_role="technical_product_spec",
        source_url="https://www.ti.com/microcontrollers-mcus-processors/overview.html",
        product_family="Analog / Embedded Semiconductors",
        product_or_segment="Microcontrollers and processors",
        metric_name="official_mcu_processor_product_spec_context",
        expected_terms=("microcontrollers", "processors", "ti.com"),
    ),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize targeted parser-backed follow-up rows for AI/Semis ProductEvidencePack strict-depth gaps. "
            "Rows are admitted only when a public source can be fetched and parsed with expected issuer/product terms."
        )
    )
    parser.add_argument("--timeout", type=float, default=18.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows_by_layer, attempts = materialize_followup_rows(timeout=args.timeout, generated_at=generated_at)
    for layer, output_path in LAYER_TO_OUTPUT.items():
        _write_jsonl(output_path, rows_by_layer.get(layer, []))
    _write_jsonl(ATTEMPTS, attempts)
    summary = build_summary(rows_by_layer=rows_by_layer, attempts=attempts, generated_at=generated_at)
    _write_json(SUMMARY, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["failed_target_count"] == 0 else 1


def materialize_followup_rows(
    *,
    timeout: float = 18.0,
    generated_at: str = "2026-06-27T00:00:00Z",
    fetcher: Callable[[FollowupTarget, float], tuple[str, int, str, str | None]] | None = None,
) -> tuple[dict[str, list[dict]], list[dict]]:
    fetch = fetcher or fetch_target_text
    rows_by_layer: dict[str, list[dict]] = defaultdict(list)
    attempts: list[dict] = []
    for target in TARGETS:
        text, status_code, parser_status, error = fetch(target, timeout)
        matched_terms = _matched_terms(text, target.expected_terms)
        ok = bool(text.strip()) and len(matched_terms) >= min(2, len(target.expected_terms))
        attempt = {
            "schema_version": "finsight_ai_semis_product_depth_followup_attempt_v0_1",
            "generated_at": generated_at,
            "ticker": target.ticker,
            "company_name": target.company_name,
            "evidence_layer": target.evidence_layer,
            "source_id": target.source_id,
            "source_role": target.source_role,
            "source_url": target.source_url,
            "http_status": status_code,
            "parser_status": parser_status,
            "matched_terms": matched_terms,
            "admitted_as_evidence": ok,
            "error": error or "",
        }
        attempts.append(attempt)
        if not ok:
            continue
        rows_by_layer[target.evidence_layer].append(build_context_row(target, text, generated_at, matched_terms))
    for layer in rows_by_layer:
        rows_by_layer[layer] = _dedupe_rows(rows_by_layer[layer])
    return dict(rows_by_layer), attempts


def fetch_target_text(target: FollowupTarget, timeout: float) -> tuple[str, int, str, str | None]:
    headers = {
        "User-Agent": "FINInsightAgent/0.1 research-public-source-audit contact=finsight@example.com",
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    }
    try:
        response = requests.get(target.source_url, headers=headers, timeout=(5, timeout), allow_redirects=True)
    except requests.RequestException as exc:
        return "", 0, "fetch_error", f"{type(exc).__name__}: {exc}"
    content_type = response.headers.get("content-type", "").lower()
    if response.status_code >= 400:
        return "", response.status_code, "http_error", ""
    try:
        if "pdf" in content_type or target.source_url.lower().endswith(".pdf"):
            return _extract_pdf_text(response.content), response.status_code, "verified_public_pdf_text", None
        return _extract_html_text(response.text), response.status_code, "verified_public_html_text", None
    except Exception as exc:  # pragma: no cover - parser hardening guard
        return "", response.status_code, "parse_error", f"{type(exc).__name__}: {exc}"


def build_context_row(
    target: FollowupTarget,
    text: str,
    generated_at: str,
    matched_terms: list[str],
) -> dict:
    source_row_id = _stable_id(
        "ai_semis_followup",
        {
            "ticker": target.ticker,
            "evidence_layer": target.evidence_layer,
            "source_url": target.source_url,
            "metric_name": target.metric_name,
        },
    )
    return {
        "schema_version": "finsight_ai_semis_product_depth_followup_context_row_v0_1",
        "generated_at": generated_at,
        "source_row_id": source_row_id,
        "ticker": target.ticker,
        "company_name": target.company_name,
        "source_id": target.source_id,
        "source_role": target.source_role,
        "source_layer": target.source_layer,
        "evidence_layer": target.evidence_layer,
        "product_family": target.product_family,
        "product_or_segment": target.product_or_segment,
        "metric_name": target.metric_name,
        "source_url": target.source_url,
        "citation_url": target.source_url,
        "citation_span": _snippet(text, matched_terms),
        "matched_terms": matched_terms,
        "counterparty": target.counterparty,
        "relationship_role": target.relationship_role,
        "edge_type": target.edge_type,
        "claim_boundary": target.claim_boundary,
        "exact_value_authority": False,
        "evidence_bundle_allowed": True,
        "forbidden_claims": [
            "product_revenue",
            "shipment",
            "sales_volume",
            "asp",
            "market_share",
            "inventory",
            "sell_through",
            "backlog",
            "order_value",
            "customer_spend",
        ],
    }


def build_summary(*, rows_by_layer: dict[str, list[dict]], attempts: list[dict], generated_at: str) -> dict:
    admitted = [row for rows in rows_by_layer.values() for row in rows]
    admitted_tickers = sorted({str(row.get("ticker") or "") for row in admitted})
    failed_attempts = [attempt for attempt in attempts if not attempt.get("admitted_as_evidence")]
    return {
        "schema_version": "finsight_ai_semis_product_depth_followup_summary_v0_1",
        "generated_at": generated_at,
        "target_count": len(TARGETS),
        "admitted_row_count": len(admitted),
        "admitted_ticker_count": len(admitted_tickers),
        "admitted_tickers": admitted_tickers,
        "row_count_by_layer": dict(sorted((layer, len(rows)) for layer, rows in rows_by_layer.items())),
        "attempt_count_by_status": dict(Counter(str(attempt.get("parser_status") or "") for attempt in attempts)),
        "failed_target_count": len(failed_attempts),
        "failed_targets": [
            {
                "ticker": str(attempt.get("ticker") or ""),
                "evidence_layer": str(attempt.get("evidence_layer") or ""),
                "source_url": str(attempt.get("source_url") or ""),
                "http_status": attempt.get("http_status"),
                "parser_status": str(attempt.get("parser_status") or ""),
                "matched_terms": list(attempt.get("matched_terms") or []),
                "error": str(attempt.get("error") or ""),
            }
            for attempt in failed_attempts
        ],
    }


def _extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return _clean_text(soup.get_text(" "))


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    chunks: list[str] = []
    for page in reader.pages[:8]:
        chunks.append(page.extract_text() or "")
    return _clean_text(" ".join(chunks))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = text.lower()
    return [term for term in terms if term.lower() in normalized]


def _snippet(text: str, matched_terms: list[str]) -> str:
    if not text:
        return ""
    lowered = text.lower()
    positions = [lowered.find(term.lower()) for term in matched_terms if lowered.find(term.lower()) >= 0]
    start = max(0, min(positions) - 180) if positions else 0
    end = min(len(text), start + 520)
    return text[start:end]


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        key = "|".join(str(row.get(field) or "") for field in ("ticker", "evidence_layer", "source_url", "metric_name"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _stable_id(prefix: str, payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"{prefix}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
