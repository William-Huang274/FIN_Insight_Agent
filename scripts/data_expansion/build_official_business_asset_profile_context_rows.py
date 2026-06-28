from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_SPEC_SCRIPT = REPO_ROOT / "scripts" / "data_expansion" / "build_official_product_spec_context_rows.py"
SPEC = importlib.util.spec_from_file_location("official_product_spec_builder", PRODUCT_SPEC_SCRIPT)
PRODUCT_SPEC = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(PRODUCT_SPEC)

SCHEMA_VERSION = "finsight_official_business_asset_profile_context_rows_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_official_business_asset_profile_context_summary_v0_1"

DEFAULT_INPUT = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/"
    "company_product_pages/company_product_pages.materialized.jsonl"
)
DEFAULT_LANE_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "official_business_asset_profile_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_business_asset_profile_context_summary_v0_1.json"

ASSET_PROFILE_LANES = {"V7", "V8"}
ASSET_PROFILE_UNITS = {
    "mw",
    "gw",
    "kw",
    "w",
    "watts",
    "sq ft",
    "square feet",
    "rooms",
    "room",
    "properties",
    "property",
    "stores",
    "store",
    "locations",
    "location",
    "sites",
    "site",
    "facilities",
    "facility",
    "plants",
    "plant",
    "data centers",
    "data center",
    "centers",
    "center",
    "miles",
    "mile",
    "km",
    "acres",
    "acre",
    "beds",
    "bed",
    "branches",
    "branch",
}
ASSET_PROFILE_EXTRA_UNIT_PATTERN = (
    r"GW|MW|kW|watts?|square feet|sq\.?\s*ft\.?|sqft|rooms?|properties|stores?|locations?|"
    r"sites?|facilit(?:y|ies)|plants?|data centers?|centers?|miles?|km|acres?|beds?|branches?"
)
ASSET_PROFILE_CONTEXT = re.compile(
    r"\b(capacity|generation|generating|operating generation|power output|nameplate|plant|facility|"
    r"fleet|project|megawatts?|kilowatts?|thermal|cooling|reactor|renewable|solar|wind|nuclear|"
    r"turbine|compressor|oilfield|industrial equipment|property|properties|rentable|square feet|"
    r"store|stores|location|locations|room|rooms|hotel|branch|branches|data center|pipeline|miles|"
    r"bed|beds|acres|site|sites)\b",
    flags=re.IGNORECASE,
)
ASSET_PROFILE_NOISE = re.compile(
    r"\b(price|pricing|discount|coupon|cart|checkout|bill credit|trade[- ]?in|phone support|"
    r"investor relations?|stock|dividend|cookie|privacy|terms|download|pdf|file size|"
    r"skymiles|miles per dollar|eligible purchases?|loyalty|reward|rewards|points?)\b|\$",
    flags=re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract bounded official business/asset profile capacity rows from company official pages."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--additional-input",
        action="append",
        type=Path,
        default=[],
        help="Additional materialized official spec/detail page JSONL files to parse.",
    )
    parser.add_argument("--lane-assignments", type=Path, default=DEFAULT_LANE_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--max-rows-per-ticker", type=int, default=8)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _utc_now()
    page_rows = _load_jsonl(args.input)
    for path in args.additional_input:
        page_rows.extend(_load_jsonl(path))
    lane_rows = _load_jsonl(args.lane_assignments)
    rows, diagnostics = build_official_business_asset_profile_context_rows(
        page_rows=page_rows,
        lane_rows=lane_rows,
        generated_at=generated_at,
        max_rows_per_ticker=args.max_rows_per_ticker,
    )
    summary = build_summary(page_rows=page_rows, rows=rows, diagnostics=diagnostics, generated_at=generated_at)
    _write_jsonl(args.output_rows, rows)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_official_business_asset_profile_context_rows(
    *,
    page_rows: Iterable[Mapping[str, Any]],
    lane_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    max_rows_per_ticker: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lane_by_ticker = {str(row.get("ticker") or "").upper(): str(row.get("primary_lane_id") or "") for row in lane_rows}
    rows: list[dict[str, Any]] = []
    per_ticker = Counter()
    seen: set[str] = set()
    diagnostics = {
        "page_count": 0,
        "candidate_count": 0,
        "rejected_candidate_count": 0,
        "rejection_reasons": Counter(),
    }
    for page in page_rows:
        ticker = str(page.get("ticker") or "").upper().strip()
        if not ticker or lane_by_ticker.get(ticker) not in ASSET_PROFILE_LANES:
            continue
        if per_ticker[ticker] >= max_rows_per_ticker:
            continue
        body = PRODUCT_SPEC._page_body(page)
        if not body.strip():
            continue
        plain = PRODUCT_SPEC._normalize_text(body)
        diagnostics["page_count"] += 1
        for candidate in _extract_profile_candidates(plain, page=page):
            if per_ticker[ticker] >= max_rows_per_ticker:
                break
            window = str(candidate.get("citation_span") or "")
            reason = _reject_reason(candidate, window=window)
            if reason:
                diagnostics["rejected_candidate_count"] += 1
                diagnostics["rejection_reasons"][reason] += 1
                continue
            diagnostics["candidate_count"] += 1
            row = _profile_row(page=page, candidate=candidate, generated_at=generated_at)
            key = _dedupe_key(row)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            per_ticker[ticker] += 1
    diagnostics["rejection_reasons"] = dict(sorted(diagnostics["rejection_reasons"].items()))
    return sorted(rows, key=lambda row: (row["ticker"], row["metric_name"], row["value"], row["source_url"])), diagnostics


def build_summary(
    *,
    page_rows: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    diagnostics: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_page_count": len(page_rows),
        "business_asset_profile_row_count": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "metric_counts": _counts(rows, "metric_name"),
        "rows_by_ticker_top30": _counts(rows, "ticker", limit=30),
        "diagnostics": dict(diagnostics),
        "authority_boundary": (
            "Rows support bounded business/asset capacity or profile context for asset-heavy companies. "
            "They do not prove revenue, backlog, order value, shipments, ASP, utilization, or market share."
        ),
    }


def _reject_reason(candidate: Mapping[str, Any], *, window: str) -> str:
    unit = _normalize_asset_unit(str(candidate.get("unit") or ""))
    if unit not in ASSET_PROFILE_UNITS:
        return "unit_not_asset_profile_unit"
    if _is_zero_value(candidate.get("value")) and unit in {
        "stores",
        "store",
        "locations",
        "location",
        "properties",
        "property",
        "facilities",
        "facility",
        "sites",
        "site",
        "branches",
        "branch",
    }:
        return "zero_asset_count"
    if _is_year_like_value(candidate.get("value")) and unit in {
        "stores",
        "store",
        "locations",
        "location",
        "properties",
        "property",
        "facilities",
        "facility",
        "sites",
        "site",
        "plants",
        "plant",
        "centers",
        "center",
        "branches",
        "branch",
    }:
        return "year_like_asset_count"
    if ASSET_PROFILE_NOISE.search(window):
        return "commercial_or_site_noise"
    if not ASSET_PROFILE_CONTEXT.search(window):
        return "missing_asset_profile_context"
    if unit in {"beds", "bed"}:
        return "bed_count_requires_healthcare_facility_adapter"
    if unit in {"miles", "mile", "km"} and not re.search(
        r"\b(pipeline|transmission|rail|route|network|line|lines|fiber|utility|electric|gas|water|distribution)\b",
        window,
        flags=re.I,
    ):
        return "distance_without_asset_network_context"
    return ""


def _extract_profile_candidates(text: str, *, page: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for match in PRODUCT_SPEC._iter_spec_matches(text):
        window = PRODUCT_SPEC._window(text, match.start(), match.end())
        candidate = PRODUCT_SPEC._candidate_from_match(match=match, window=window, page=page)
        candidate["unit"] = _normalize_asset_unit(str(candidate.get("unit") or ""))
        candidates.append(candidate)
    for match in _iter_extra_asset_matches(text):
        window = PRODUCT_SPEC._window(text, match.start(), match.end(), radius=190)
        value = str(match.group("value") or "").replace(",", "").strip()
        unit = _normalize_asset_unit(str(match.group("unit") or ""))
        raw_label = PRODUCT_SPEC._clean_label(str(match.group("label") or ""))
        candidates.append(
            {
                "spec_name": _metric_name(raw_label, window, unit=unit),
                "raw_label": raw_label,
                "value": value,
                "unit": unit,
                "product_or_segment": page.get("product") or raw_label or "Business / asset profile",
                "product_family": page.get("product") or "Business / asset profile",
                "citation_span": PRODUCT_SPEC._trim_citation(window),
                "company_name": str(page.get("company") or page.get("company_name") or "").strip(),
            }
        )
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = "::".join(
            [
                str(candidate.get("value") or ""),
                str(candidate.get("unit") or "").lower(),
                str(candidate.get("product_or_segment") or "").lower(),
            ]
        )
        deduped.setdefault(key, candidate)
    return sorted(deduped.values(), key=lambda row: (str(row.get("product_or_segment") or ""), str(row.get("raw_label") or "")))


def _iter_extra_asset_matches(text: str) -> Iterable[re.Match[str]]:
    unit = ASSET_PROFILE_EXTRA_UNIT_PATTERN
    patterns = [
        re.compile(
            rf"(?P<label>[A-Za-z][A-Za-z0-9 /+().,\-]{{2,90}}?)"
            rf"\s+(?:includes?|has|with|of|approximately|approx\.?|over|more than|about|:)?\s*"
            rf"(?P<value>\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<unit>{unit})\b",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<value>\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(?P<unit>{unit})"
            rf"\s+(?:of\s+)?(?P<label>capacity|generation|stores?|locations?|properties|rooms?|"
            rf"facilities|plants?|sites?|branches?|beds?|pipeline|rentable area|data centers?)\b",
            flags=re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        yield from pattern.finditer(text)


def _profile_row(*, page: Mapping[str, Any], candidate: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    ticker = str(page.get("ticker") or "").upper().strip()
    url = str(page.get("source_url") or page.get("url") or "").strip()
    value = str(candidate.get("value") or "")
    unit = _normalize_asset_unit(str(candidate.get("unit") or ""))
    metric_name = _metric_name(str(candidate.get("raw_label") or ""), str(candidate.get("citation_span") or ""), unit=unit)
    evidence_ref = "official_business_asset_profile:" + hashlib.sha1(
        f"{ticker}|{url}|{metric_name}|{value}|{unit}|{candidate.get('citation_span')}".encode("utf-8")
    ).hexdigest()[:16]
    text = (
        f"{ticker} official business/asset profile: {metric_name}={value} {unit}. "
        f"Citation: {candidate.get('citation_span')}"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "ticker": ticker,
        "company": page.get("company") or page.get("company_name") or "",
        "company_name": page.get("company") or page.get("company_name") or "",
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_role": "business_asset_profile_spec",
        "runtime_contract": "BusinessProfileSlot",
        "structured_context_type": "business_asset_profile_spec",
        "structured_fact_status": "bounded_context_fact_materialized",
        "parser_status": "source_specific_context_parser_pass",
        "source_id": "official_business_asset_profile_parser",
        "underlying_source_id": "company_product_pages",
        "source_family": "live_public_web_context",
        "runtime_source_family": "public_source_context",
        "source_layer": "L2",
        "source_layer_id": "L2",
        "layer_id": "L2",
        "source_class": "company_official_business_asset_profile",
        "source_specific_parser": "official_business_asset_profile_extractor_v0_1",
        "source_url": url,
        "url": url,
        "raw_path": page.get("raw_path") or "",
        "citation": {"title": page.get("title") or "", "url": url, "source_url": url},
        "citation_span": candidate.get("citation_span") or "",
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "product_or_segment": page.get("product") or candidate.get("product_or_segment") or "Business / asset profile",
        "product_family": page.get("product") or candidate.get("product_family") or "Business / asset profile",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "business_asset_profile_context",
        "bounded_structured_context": True,
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["business_asset_profile_context", "asset_capacity_context", "product_spec_context"],
        "claim_types": ["business_asset_profile_context", "asset_capacity_context"],
        "forbidden_claims": [
            "revenue",
            "order_value",
            "backlog",
            "shipments",
            "unit_sales",
            "ASP",
            "utilization",
            "market_share",
        ],
        "claim_boundary": (
            "Official business/asset capacity profile context only; no revenue, backlog, order value, shipment, "
            "ASP, utilization, or market-share authority."
        ),
        "authority_boundary": (
            "Official business/asset capacity profile context only; no revenue, backlog, order value, shipment, "
            "ASP, utilization, or market-share authority."
        ),
        "evidence_graph_status": "runtime_ready_context",
        "preview": text,
        "text": text,
    }


def _dedupe_key(row: Mapping[str, Any]) -> str:
    return "::".join(
        [
            str(row.get("ticker") or ""),
            str(row.get("metric_name") or ""),
            str(row.get("value") or ""),
            str(row.get("unit") or ""),
            str(row.get("product_or_segment") or ""),
        ]
    ).lower()


def _metric_name(label: str, window: str, *, unit: str = "") -> str:
    text = f"{label} {window}".lower()
    normalized_unit = _normalize_asset_unit(unit)
    if normalized_unit in {"mw", "gw", "kw", "w", "watts"}:
        if "cool" in text or "thermal" in text:
            return "cooling_or_thermal_capacity"
        if "generation" in text or "generating" in text or "plant" in text:
            return "generation_capacity"
        if "power output" in text or "output" in text:
            return "power_output_capacity"
        return "asset_capacity_or_power_rating"
    if normalized_unit in {"sq ft", "square feet"}:
        return "rentable_or_facility_area"
    if normalized_unit in {"room", "rooms"}:
        return "room_count"
    if normalized_unit in {"store", "stores", "location", "locations", "branch", "branches"}:
        return "store_or_location_count"
    if normalized_unit in {
        "property",
        "properties",
        "facility",
        "facilities",
        "site",
        "sites",
        "plant",
        "plants",
        "data center",
        "data centers",
        "center",
        "centers",
    }:
        return "site_or_property_count"
    if normalized_unit in {"miles", "mile", "km"}:
        return "network_or_pipeline_length"
    if normalized_unit in {"acres", "acre"}:
        return "land_area"
    if normalized_unit in {"bed", "beds"}:
        return "bed_capacity"
    if re.search(r"\b(square feet|sq ft|sqft|rentable|area)\b", text):
        return "rentable_or_facility_area"
    if re.search(r"\b(room|rooms|hotel)\b", text):
        return "room_count"
    if re.search(r"\b(store|stores|location|locations|branch|branches)\b", text):
        return "store_or_location_count"
    if re.search(r"\b(properties|property|facilities|facility|sites|site|plants|plant|data center|data centers)\b", text):
        return "site_or_property_count"
    if re.search(r"\b(miles|mile|km|pipeline)\b", text):
        return "network_or_pipeline_length"
    if re.search(r"\b(acres|acre)\b", text):
        return "land_area"
    if re.search(r"\b(bed|beds)\b", text):
        return "bed_capacity"
    if "cool" in text or "thermal" in text:
        return "cooling_or_thermal_capacity"
    if "generation" in text or "generating" in text or "plant" in text:
        return "generation_capacity"
    if "power output" in text or "output" in text:
        return "power_output_capacity"
    return "asset_capacity_or_power_rating"


def _is_zero_value(value: object) -> bool:
    text = str(value or "").replace(",", "").strip()
    try:
        return float(text) == 0.0
    except ValueError:
        return False


def _is_year_like_value(value: object) -> bool:
    text = str(value or "").replace(",", "").strip()
    try:
        number = float(text)
    except ValueError:
        return False
    return number.is_integer() and 1900 <= int(number) <= 2100


def _normalize_asset_unit(unit: str) -> str:
    text = re.sub(r"\s+", " ", str(unit or "").strip().lower())
    replacements = {
        "gw": "gw",
        "mw": "mw",
        "kw": "kw",
        "w": "w",
        "watt": "watts",
        "watts": "watts",
        "sqft": "sq ft",
        "sq. ft.": "sq ft",
        "sq. ft": "sq ft",
        "sq ft.": "sq ft",
        "square foot": "square feet",
    }
    return replacements.get(text, text)


def _counts(rows: list[Mapping[str, Any]], key: str, *, limit: int = 30) -> dict[str, int]:
    counts = Counter(str(row.get(key) or "") for row in rows)
    return dict(counts.most_common(limit))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
