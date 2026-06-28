from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_official_product_spec_context_rows_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_official_product_spec_context_summary_v0_1"

DEFAULT_INPUT = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/"
    "company_product_pages/company_product_pages.materialized.jsonl"
)
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "official_product_spec_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_product_spec_context_summary_v0_1.json"

SPEC_UNIT_PATTERN = (
    r"CUDA cores?|tensor cores?|RT cores?|vCPUs?|CPUs?|GPUs?|cores?|threads?|transistors?|parameters?|"
    r"TB/s|GB/s|Gbps|Gb/s|GB|TB|MB|TOPS|TFLOPS|teraFLOPS|FLOPS|fps|hours?|hrs?|"
    r"mm|nm|kW|MW|GHz|MHz|MP|megapixels?|miles|km|W|watts?|percent|%"
)

FORBIDDEN_CONTEXT = re.compile(
    r"\b("
    r"bill credits?|trade[- ]?in|monthly|installment|apr|carrier|verizon|t-mobile|at&t|"
    r"miles per dollar|eligible purchases?|credit card|named support contacts?|phone support|chat support|"
    r"support 24 hours|market data 24 hours|365 days|six days a week|"
    r"annual reports?|integrated reports?|product sheets?|ebook|whitepaper download|pdf|"
    r"machine-readable file|download at least|file may be large|"
    r"processing costs?|cut costs?|cost savings?|"
    r"ppa|power purchase agreement|customer agreement|entered into .*agreements?|dispatched|ercot|"
    r"privacy|cookie|copyright|terms of use|legal|domain|akamai|cloudfront|googleapis|"
    r"investor relations?|stock|shareholder|dividend|market share|sales|revenue|asp|"
    r"price|pricing|discount|promotion|coupon|cart|checkout"
    r")\b|\$",
    flags=re.IGNORECASE,
)

WEAK_LABELS = {
    "all rights reserved",
    "apple store",
    "career",
    "contact",
    "cookie",
    "copyright",
    "customer service",
    "download",
    "home",
    "investor relations",
    "learn more",
    "login",
    "news",
    "privacy policy",
    "products",
    "search",
    "shop",
    "support",
    "terms",
}

SPEC_NAME_KEYWORDS = (
    ("memory bandwidth", "memory_bandwidth"),
    ("gpu memory", "memory_capacity"),
    ("hbm", "memory_standard"),
    ("memory", "memory_capacity"),
    ("bandwidth", "bandwidth"),
    ("tensor", "accelerator_throughput"),
    ("flops", "compute_throughput"),
    ("tops", "compute_throughput"),
    ("cuda", "compute_core_count"),
    ("cores", "core_count"),
    ("core", "core_count"),
    ("video playback", "battery_life_video_playback"),
    ("battery life", "battery_life"),
    ("battery", "battery_or_power_spec"),
    ("power", "power_rating"),
    ("watt", "power_rating"),
    ("wafer", "supported_wafer_size"),
    ("technology node", "process_node_support"),
    ("process node", "process_node_support"),
    ("node", "process_node_support"),
    ("camera", "camera_or_video_spec"),
    ("zoom", "optical_zoom"),
    ("resolution", "display_or_image_resolution"),
    ("sensor", "sensor_resolution"),
    ("frequency", "frequency"),
    ("speed", "speed_or_frequency"),
    ("throughput", "throughput"),
    ("capacity", "capacity"),
    ("range", "range"),
    ("ports", "port_count"),
    ("channels", "channel_count"),
    ("pcie", "interface_generation"),
    ("ddr", "memory_standard"),
)

THIRD_PARTY_TECH_NAMES = {
    "akamai": "akamai",
    "amazon": "amazon",
    "cloudflare": "cloudflare",
    "google": "google",
    "microsoft": "microsoft",
}

GENERIC_PRODUCT_FAMILY_PREFIXES = (
    "general ",
    "mixed ",
    "unknown ",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract conservative parser-backed technical product spec rows from official product pages."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--additional-input",
        action="append",
        type=Path,
        default=[],
        help="Additional materialized official spec/detail page JSONL files to parse.",
    )
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--max-specs-per-page", type=int, default=8)
    parser.add_argument("--max-specs-per-ticker", type=int, default=24)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    page_rows = _load_jsonl(args.input)
    for path in args.additional_input:
        page_rows.extend(_load_jsonl(path))
    rows, diagnostics = build_official_product_spec_context_rows(
        page_rows=page_rows,
        generated_at=generated_at,
        max_specs_per_page=args.max_specs_per_page,
        max_specs_per_ticker=args.max_specs_per_ticker,
    )
    summary = build_summary(
        page_rows=page_rows,
        rows=rows,
        diagnostics=diagnostics,
        generated_at=generated_at,
        output_rows=args.output_rows,
    )
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_official_product_spec_context_rows(
    *,
    page_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    max_specs_per_page: int = 8,
    max_specs_per_ticker: int = 24,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_ticker = Counter()
    diagnostics = {
        "page_count": 0,
        "missing_body_count": 0,
        "candidate_count": 0,
        "rejected_candidate_count": 0,
        "rejection_reasons": Counter(),
    }
    for page in page_rows:
        ticker = str(page.get("ticker") or "").upper().strip()
        url = str(page.get("source_url") or page.get("url") or "").strip()
        if not ticker or not url:
            continue
        diagnostics["page_count"] += 1
        if per_ticker[ticker] >= max_specs_per_ticker:
            continue
        body = _page_body(page)
        if not body.strip():
            diagnostics["missing_body_count"] += 1
            continue
        specs, rejects = extract_spec_candidates(
            text=body,
            page=page,
            max_candidates=max_specs_per_page,
        )
        diagnostics["candidate_count"] += len(specs)
        diagnostics["rejected_candidate_count"] += len(rejects)
        diagnostics["rejection_reasons"].update(rejects)
        for spec in specs:
            if per_ticker[ticker] >= max_specs_per_ticker:
                break
            row = _spec_row(page=page, spec=spec, generated_at=generated_at)
            key = str(row["evidence_ref"])
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
            per_ticker[ticker] += 1
    diagnostics["rejection_reasons"] = dict(sorted(diagnostics["rejection_reasons"].items()))
    return sorted(output, key=lambda row: (row["ticker"], row["product_or_segment"], row["spec_name"], row["value"])), diagnostics


def extract_spec_candidates(
    *,
    text: str,
    page: Mapping[str, Any],
    max_candidates: int = 8,
) -> tuple[list[dict[str, Any]], list[str]]:
    plain = _normalize_text(text)
    candidates: list[dict[str, Any]] = []
    rejects: list[str] = []
    for match in _iter_spec_matches(plain):
        window = _window(plain, match.start(), match.end())
        candidate = _candidate_from_match(match=match, window=window, page=page)
        reason = _reject_reason(candidate, window=window)
        if reason:
            rejects.append(reason)
            continue
        candidates.append(candidate)
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = "::".join(
            [
                str(candidate["spec_name"]),
                str(candidate["value"]),
                str(candidate["unit"]),
                str(candidate["product_or_segment"]),
            ]
        ).lower()
        existing = deduped.get(key)
        if not existing or len(str(candidate.get("citation_span") or "")) > len(str(existing.get("citation_span") or "")):
            deduped[key] = candidate
    ranked = sorted(deduped.values(), key=_candidate_rank)
    return ranked[: max(1, int(max_candidates or 1))], rejects


def build_summary(
    *,
    page_rows: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_page_count": len(page_rows),
        "technical_product_spec_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows}),
        "product_or_segment_count": len({str(row.get("ticker") or "") + "::" + str(row.get("product_or_segment") or "") for row in rows}),
        "spec_name_counts": _top_counts(rows, "spec_name", limit=30),
        "rows_by_ticker_top30": _top_counts(rows, "ticker", limit=30),
        "diagnostics": dict(diagnostics),
        "outputs": {"rows": str(output_rows)},
        "authority_boundary": (
            "Rows are official technical product specs only. They support product capability, generation, and "
            "comparison analysis; they do not support product revenue, unit sales, ASP, share, inventory, "
            "sell-through, backlog, order value, or customer demand claims."
        ),
    }


def _iter_spec_matches(text: str) -> Iterable[re.Match[str]]:
    unit = SPEC_UNIT_PATTERN
    patterns = [
        re.compile(
            r"(?P<label>[A-Za-z][A-Za-z0-9 /+().,\-™®]{2,100}?)"
            r"\s+(?:includes?|has|with|of|at|:)?\s*"
            r"(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>billion|million|trillion)\s+"
            r"(?P<unit>transistors?|parameters?)\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<label>[A-Za-z][A-Za-z0-9 /+().,\-™®]{{2,80}}?)"
            rf"\s+(?:up to|supports?|for|with|of|at|:)?\s*"
            rf"(?P<value>\d+(?:,\d{{3}})*(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>{unit})\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<value>\d+(?:,\d{{3}})*(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>{unit})"
            rf"\s+(?P<label>wafer|wafers|memory|bandwidth|battery|video playback|range|camera|sensor|node|process|ports?|channels?)\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"(?P<value>\d+(?:\.\d+)?)\s*x\s+(?P<label>optical(?:-quality)? zoom|zoom)\b",
            flags=re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        yield from pattern.finditer(text)


def _candidate_from_match(
    *,
    match: re.Match[str],
    window: str,
    page: Mapping[str, Any],
) -> dict[str, Any]:
    value = str(match.group("value") or "").replace(",", "").replace(" ", "")
    scale = str(match.groupdict().get("scale") or "").strip().lower()
    if scale:
        value = f"{value} {scale}"
    unit = str(match.groupdict().get("unit") or ("x" if "x" in match.group(0).lower() else "")).strip()
    raw_label = _clean_label(str(match.group("label") or ""))
    spec_name = _spec_name(raw_label=raw_label, window=window, unit=unit)
    return {
        "spec_name": spec_name,
        "raw_label": raw_label,
        "value": value,
        "unit": _normalize_unit(unit),
        "product_or_segment": _product_or_segment(page=page, raw_label=raw_label, window=window),
        "product_family": str(page.get("product") or "").strip() or raw_label,
        "citation_span": _trim_citation(window),
        "company_name": str(page.get("company") or page.get("company_name") or "").strip(),
    }


def _reject_reason(candidate: Mapping[str, Any], *, window: str) -> str:
    label = str(candidate.get("raw_label") or "").lower().strip()
    product_family = str(candidate.get("product_family") or "").lower().strip()
    unit = str(candidate.get("unit") or "").lower().strip()
    value = str(candidate.get("value") or "").strip()
    if not label or label in WEAK_LABELS:
        return "weak_or_empty_label"
    if product_family.startswith(GENERIC_PRODUCT_FAMILY_PREFIXES):
        return "generic_product_family_not_product_spec"
    if len(label) > 90:
        return "label_too_long"
    if FORBIDDEN_CONTEXT.search(window):
        # Keep storage-capacity specs only when the sentence is about a model, not financing.
        if unit not in {"gb", "tb"} or re.search(r"\b(bill|credit|trade|monthly|installment|carrier|price)\b", window, flags=re.I):
            return "forbidden_commercial_or_site_context"
    if not re.search(r"\d", value):
        return "missing_numeric_value"
    if unit in {"%", "percent"} and not re.search(
        r"\b(battery|recycled|efficiency|utilization|uptime|yield|accuracy|coverage)\b",
        window,
        flags=re.I,
    ):
        return "percentage_not_product_spec"
    if unit in {"w", "watts"} and not re.search(r"\b(power|thermal|tdp|watt|charging|adapter|consumption)\b", window, flags=re.I):
        return "watt_without_power_context"
    if unit in {
        "cuda cores",
        "tensor cores",
        "rt cores",
        "cores",
        "core",
        "vcpus",
        "vcpu",
        "cpus",
        "cpu",
        "gpus",
        "gpu",
        "threads",
        "thread",
    } and not re.search(
        r"\b(cpu|gpu|cuda|tensor|rt core|processor|accelerator|instance|server|thread|compute|cluster|chip|socket)\b",
        window,
        flags=re.I,
    ):
        return "core_or_processor_count_without_compute_context"
    if unit in {"parameters", "parameter"} and not re.search(
        r"\b(model|language model|llm|neural|ai|machine learning|foundation model|inference)\b",
        window,
        flags=re.I,
    ):
        return "parameter_count_without_ai_model_context"
    if unit in {"transistors", "transistor"} and not re.search(
        r"\b(chip|silicon|processor|gpu|cpu|soc|die|semiconductor|integrated circuit)\b",
        window,
        flags=re.I,
    ):
        return "transistor_count_without_chip_context"
    if unit in {"mb"} and not re.search(r"\b(memory|cache|on-chip|ram|dram|sram|buffer)\b", window, flags=re.I):
        return "megabyte_file_size_context"
    if unit in {"gb", "tb"} and re.search(
        r"\b(annual report|integrated report|ebook|product sheet|download|machine-readable file|terabyte of data)\b",
        window,
        flags=re.I,
    ):
        return "storage_file_size_context"
    if unit in {"hours", "hour", "hrs", "hr"} and not re.search(
        r"\b(battery|video playback|playback|charge|charging|runtime|run time)\b",
        window,
        flags=re.I,
    ):
        return "hours_without_battery_or_runtime_context"
    if unit in {"miles", "mile", "km"} and not re.search(
        r"\b(range|driving range|ev|vehicle|battery electric|electric vehicle)\b",
        window,
        flags=re.I,
    ):
        return "distance_without_vehicle_range_context"
    if re.search(r"\b(stock|bond|coupon|dividend|shareholder|investor)\b", window, flags=re.I):
        return "capital_market_context_not_product_spec"
    if _third_party_context(candidate, window=window):
        return "third_party_product_context_not_issuer_spec"
    if re.search(r"\b(cookie|domain|privacy|terms|copyright)\b", label, flags=re.I):
        return "site_metadata_context"
    return ""


def _third_party_context(candidate: Mapping[str, Any], *, window: str) -> bool:
    company = str(candidate.get("company_name") or "").lower()
    text = window.lower()
    for name, token in THIRD_PARTY_TECH_NAMES.items():
        if token in text and token not in company:
            return True
    return False


def _spec_name(*, raw_label: str, window: str, unit: str) -> str:
    text = f"{raw_label} {window}".lower()
    normalized_unit = _normalize_unit(unit).lower()
    if normalized_unit in {"cuda cores", "tensor cores", "rt cores", "cores", "core", "threads", "thread"}:
        return "compute_core_count"
    if normalized_unit in {"vcpus", "vcpu", "cpus", "cpu"}:
        return "virtual_or_processor_core_count"
    if normalized_unit in {"gpus", "gpu"}:
        return "accelerator_count"
    if normalized_unit in {"parameters", "parameter"}:
        return "model_parameter_count"
    if normalized_unit in {"transistors", "transistor"}:
        return "transistor_count"
    if normalized_unit in {"nm"}:
        if re.search(r"\b(node|process|lithography|resolution|light source|duv|euv)\b", text, flags=re.I):
            return "process_node_support"
        return "process_or_dimension"
    if normalized_unit in {"mm"}:
        if "wafer" in text:
            return "supported_wafer_size"
        return "size_or_dimension"
    if normalized_unit in {"fps"}:
        return "video_frame_rate"
    if normalized_unit in {"hours", "hour", "hrs", "hr"}:
        if "video playback" in text:
            return "battery_life_video_playback"
        return "battery_life"
    if normalized_unit in {"miles", "mile", "km"}:
        return "range"
    for keyword, name in SPEC_NAME_KEYWORDS:
        if keyword in text:
            return name
    if normalized_unit in {"gb", "tb", "mb"}:
        return "capacity_or_memory"
    if normalized_unit in {"gb/s", "tb/s", "gbps", "gb/s"}:
        return "bandwidth"
    if normalized_unit in {"tops", "tflops", "teraflops", "flops"}:
        return "compute_throughput"
    if normalized_unit in {"mm"}:
        return "size_or_dimension"
    if normalized_unit in {"nm"}:
        return "process_or_dimension"
    if normalized_unit in {"fps"}:
        return "video_frame_rate"
    if normalized_unit in {"hours", "hour", "hrs", "hr"}:
        return "duration_or_battery_life"
    return "technical_attribute"


def _product_or_segment(*, page: Mapping[str, Any], raw_label: str, window: str) -> str:
    product = str(page.get("product") or "").strip()
    title = str(page.get("title") or "").strip()
    if product:
        return product
    for token in (title, raw_label):
        token = re.sub(r"\s*[-|].*$", "", token).strip()
        if token and token.lower() not in WEAK_LABELS:
            return token[:120]
    return _trim_citation(window, limit=80)


def _candidate_rank(candidate: Mapping[str, Any]) -> tuple[int, str, str]:
    spec_name = str(candidate.get("spec_name") or "")
    priority = {
        "memory_capacity": 0,
        "memory_bandwidth": 0,
        "compute_throughput": 0,
        "supported_wafer_size": 1,
        "process_node_support": 1,
        "battery_life_video_playback": 1,
        "camera_or_video_spec": 2,
        "optical_zoom": 2,
        "capacity_or_memory": 3,
    }.get(spec_name, 5)
    return (priority, str(candidate.get("product_or_segment") or ""), str(candidate.get("spec_name") or ""))


def _spec_row(*, page: Mapping[str, Any], spec: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    ticker = str(page.get("ticker") or "").upper().strip()
    company = str(page.get("company") or page.get("company_name") or "").strip()
    url = str(page.get("source_url") or page.get("url") or "").strip()
    raw_path = str(page.get("raw_path") or page.get("clean_text_path") or "").strip()
    evidence_ref = _stable_ref(
        "official_product_spec",
        [
            ticker,
            url,
            str(spec.get("product_or_segment") or ""),
            str(spec.get("spec_name") or ""),
            str(spec.get("value") or ""),
            str(spec.get("unit") or ""),
        ],
    )
    text = (
        f"{ticker} official technical product spec: {spec.get('product_or_segment')} "
        f"{spec.get('spec_name')}={spec.get('value')} {spec.get('unit')}. "
        f"Citation: {spec.get('citation_span')}"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company": company,
        "company_name": company,
        "source_family": "live_public_web_context",
        "runtime_source_family": "public_source_context",
        "source_layer": "L2",
        "source_layer_id": "L2",
        "layer_id": "L2",
        "source_class": "company_official_product_spec",
        "source_id": "official_product_spec_parser",
        "underlying_source_id": "company_product_pages",
        "source_role": "technical_product_spec",
        "runtime_contract": "ProductSpecSlot",
        "structured_context_type": "technical_product_spec",
        "structured_fact_status": "bounded_context_fact_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "parser_status": "source_specific_context_parser_pass",
        "source_specific_parser": "official_product_spec_extractor_v0_1",
        "technical_spec_authority": True,
        "bounded_structured_context": True,
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "evidence_id": evidence_ref,
        "evidence_ref": evidence_ref,
        "source_url": url,
        "url": url,
        "raw_path": raw_path,
        "citation": {"url": url, "source_url": url, "title": str(page.get("title") or "")},
        "citation_span": str(spec.get("citation_span") or ""),
        "product_family": str(spec.get("product_family") or ""),
        "product_or_segment": str(spec.get("product_or_segment") or ""),
        "product_binding_status": "product_mentioned_in_snapshot",
        "issuer_binding_status": "company_domain_bound",
        "spec_name": str(spec.get("spec_name") or ""),
        "spec_label": str(spec.get("raw_label") or ""),
        "spec_value": str(spec.get("value") or ""),
        "spec_unit": str(spec.get("unit") or ""),
        "value": str(spec.get("value") or ""),
        "unit": str(spec.get("unit") or ""),
        "metric_name": str(spec.get("spec_name") or ""),
        "claim_types": ["technical_product_spec", "product_spec_context", "product_comparison_context"],
        "allowed_claims": ["technical_product_spec", "product_spec_context", "product_comparison_context"],
        "forbidden_claims": [
            "product_revenue",
            "unit_sales",
            "ASP",
            "market_share",
            "inventory",
            "sell_through",
            "backlog",
            "customer_order_value",
        ],
        "claim_boundary": (
            "Official technical product specification. Supports bounded product capability/generation/comparison "
            "analysis only; no product revenue, unit sales, ASP, share, inventory, sell-through, backlog, "
            "customer order value, or demand proof."
        ),
        "authority_boundary": (
            "Technical spec row from company official product surface; not a financial, market-share, "
            "order, or sales fact."
        ),
        "text": text,
        "preview": text,
    }


def _page_body(page: Mapping[str, Any]) -> str:
    for key in ("body", "text", "clean_text"):
        if str(page.get(key) or "").strip():
            return str(page.get(key) or "")
    for key in ("clean_text_path", "raw_path"):
        value = str(page.get(key) or "").strip()
        if not value:
            continue
        path = Path(value)
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _window(text: str, start: int, end: int, radius: int = 170) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _trim_citation(text: str, limit: int = 300) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _clean_label(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip(" :;,.|-")
    text = re.sub(r"^(and|or|with|for|up to|supports?)\s+", "", text, flags=re.I).strip()
    return text[:120]


def _normalize_unit(unit: str) -> str:
    text = (unit or "").strip()
    replacements = {
        "teraFLOPS": "TFLOPS",
        "hrs": "hours",
        "hr": "hours",
        "watts": "W",
        "percent": "%",
        "CUDA core": "CUDA cores",
        "CUDA cores": "CUDA cores",
        "cuda core": "CUDA cores",
        "cuda cores": "CUDA cores",
        "tensor core": "tensor cores",
        "tensor cores": "tensor cores",
        "RT core": "RT cores",
        "RT cores": "RT cores",
        "rt core": "RT cores",
        "rt cores": "RT cores",
        "core": "cores",
        "cores": "cores",
        "thread": "threads",
        "threads": "threads",
        "vCPU": "vCPU",
        "vCPUs": "vCPU",
        "vcpu": "vCPU",
        "vcpus": "vCPU",
        "CPU": "CPU",
        "CPUs": "CPU",
        "cpu": "CPU",
        "cpus": "CPU",
        "GPU": "GPU",
        "GPUs": "GPU",
        "gpu": "GPU",
        "gpus": "GPU",
        "transistor": "transistors",
        "transistors": "transistors",
        "parameter": "parameters",
        "parameters": "parameters",
    }
    return replacements.get(text, text)


def _stable_ref(prefix: str, parts: Iterable[str]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _top_counts(rows: Iterable[Mapping[str, Any]], key: str, *, limit: int) -> dict[str, int]:
    counts = Counter(str(row.get(key) or "") for row in rows if str(row.get(key) or ""))
    return dict(counts.most_common(limit))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
