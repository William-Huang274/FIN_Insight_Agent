from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_SECTIONS = (
    "Item 1. Business",
    "Item 1A. Risk Factors",
    "Item 7. Management's Discussion and Analysis",
    "Item 8. Financial Statements and Supplementary Data",
)
_SEC_FORM_TYPES = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
_SEC_FORM_ID_RE = re.compile(r"(?:^|[^A-Z0-9])(?P<form>10-?K|10-?Q|8-?K|20-?F|40-?F|6-?K)(?:[^A-Z0-9]|$)")


def build_project_inventory(
    manifest_rows: list[dict[str, Any]],
    *,
    manifest_path: str,
    bm25_index_dir: str,
    object_bm25_index_dir: str,
    bge_model: str,
    sections: tuple[str, ...] = DEFAULT_SECTIONS,
    source_gap_rows: list[dict[str, Any]] | None = None,
    market_evidence_path: str | None = None,
    market_catalog_path: str | None = None,
    market_snapshot_id: str | None = None,
    market_as_of_date: str | None = None,
    industry_evidence_path: str | None = None,
    industry_snapshot_db_path: str | None = None,
    industry_snapshot_id: str | None = None,
    industry_as_of_date: str | None = None,
    market_industry_manifest_summary_path: str | None = None,
) -> dict[str, Any]:
    companies: dict[str, dict[str, Any]] = {}
    categories: dict[str, set[str]] = defaultdict(set)
    form_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    source_tier_counts: Counter[str] = Counter()
    year_counts: Counter[int] = Counter()

    for row in manifest_rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        year = _int_or_none(row.get("fiscal_year") or row.get("year"))
        if not ticker or year is None:
            continue
        company = companies.setdefault(
            ticker,
            {
                "ticker": ticker,
                "company": str(row.get("company") or "").strip(),
                "category": str(row.get("category") or "").strip(),
                "category_slug": str(row.get("category_slug") or "").strip(),
                "years": set(),
                "form_types": set(),
                "source_types": set(),
                "source_tiers": set(),
                "filings": [],
            },
        )
        if not company.get("company") and row.get("company"):
            company["company"] = str(row.get("company") or "").strip()
        if not company.get("category") and row.get("category"):
            company["category"] = str(row.get("category") or "").strip()
        company["years"].add(year)
        form_type = _manifest_row_form_type(row)
        source_type = _normalize_source_type(row.get("source_type")) or form_type
        source_tier = str(row.get("source_tier") or _default_source_tier_for_form(form_type)).strip()
        if form_type:
            company["form_types"].add(form_type)
            form_counts[form_type] += 1
        if source_type:
            company["source_types"].add(source_type)
            source_counts[source_type] += 1
        if source_tier:
            company["source_tiers"].add(source_tier)
            source_tier_counts[source_tier] += 1
        year_counts[year] += 1
        category = str(row.get("category") or "uncategorized").strip() or "uncategorized"
        categories[category].add(ticker)
        company["filings"].append(
            {
                "year": year,
                "form_type": form_type,
                "source_type": source_type,
                "source_tier": source_tier,
                "filing_date": str(row.get("filing_date") or ""),
                "report_date": str(row.get("report_date") or ""),
                "period_end": str(row.get("period_end") or row.get("report_date") or ""),
                "period_type": str(row.get("period_type") or ""),
                "duration_months": row.get("duration_months"),
                "fiscal_period": str(row.get("fiscal_period") or ""),
                "accession_number": str(row.get("accession_number") or ""),
            }
        )

    normalized_companies = []
    for ticker in sorted(companies):
        item = companies[ticker]
        item["years"] = sorted(item["years"])
        item["form_types"] = sorted(item["form_types"])
        item["source_types"] = sorted(item["source_types"])
        item["source_tiers"] = sorted(item["source_tiers"])
        item["filings"] = sorted(item["filings"], key=lambda filing: (filing["year"], filing["form_type"], filing["period_end"]))
        normalized_companies.append(item)

    normalized_source_gaps = _normalize_source_gap_rows(source_gap_rows or [])
    market_industry_summary = _load_json_file(market_industry_manifest_summary_path)
    market_snapshot = _market_snapshot_inventory(
        market_evidence_path=market_evidence_path,
        market_catalog_path=market_catalog_path,
        market_snapshot_id=market_snapshot_id,
        market_as_of_date=market_as_of_date,
        market_industry_summary=market_industry_summary,
    )
    industry_snapshot = _industry_snapshot_inventory(
        industry_evidence_path=industry_evidence_path,
        industry_snapshot_db_path=industry_snapshot_db_path,
        industry_snapshot_id=industry_snapshot_id,
        industry_as_of_date=industry_as_of_date,
        market_industry_summary=market_industry_summary,
    )
    context_source_families = [
        block["source_family"]
        for block in (market_snapshot, industry_snapshot)
        if isinstance(block, dict) and block.get("source_family")
    ]
    available_source_families = sorted(set(source_tier_counts) | set(context_source_families))

    inventory = {
        "schema_version": "project_source_inventory_v0.1",
        "source": "manifest_derived",
        "manifest_path": manifest_path,
        "company_count": len(normalized_companies),
        "filing_count": sum(len(item["filings"]) for item in normalized_companies),
        "years": sorted(year_counts),
        "form_types": dict(sorted(form_counts.items())),
        "source_types": dict(sorted(source_counts.items())),
        "source_tiers": dict(sorted(source_tier_counts.items())),
        "source_families": available_source_families,
        "available_source_families": available_source_families,
        "sections": list(sections),
        "categories": [
            {"category": category, "tickers": sorted(tickers), "count": len(tickers)}
            for category, tickers in sorted(categories.items())
        ],
        "companies": normalized_companies,
        "source_coverage_gaps": normalized_source_gaps,
        "source_coverage_gap_count": len(normalized_source_gaps),
        "source_coverage_gap_reasons": dict(
            sorted(Counter(str(gap.get("reason_code") or "unknown") for gap in normalized_source_gaps).items())
        ),
        "indexes": {
            "manifest_path": manifest_path,
            "bm25_index_dir": bm25_index_dir,
            "object_bm25_index_dir": object_bm25_index_dir,
            "bge_model": bge_model,
        },
    }
    if market_industry_manifest_summary_path:
        inventory["market_industry_manifest_summary_path"] = market_industry_manifest_summary_path
    if market_snapshot:
        inventory["market_snapshot"] = market_snapshot
    if industry_snapshot:
        inventory["industry_snapshot"] = industry_snapshot
    if market_snapshot or industry_snapshot:
        inventory["source_boundaries"] = _source_boundaries(
            market_snapshot=market_snapshot,
            industry_snapshot=industry_snapshot,
        )
    inventory["inventory_digest"] = inventory_digest(inventory)
    return inventory


def inventory_digest(inventory: dict[str, Any]) -> str:
    stable = dict(inventory)
    stable.pop("inventory_digest", None)
    data = json.dumps(_jsonable(stable), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:12]


def inventory_brief(inventory: dict[str, Any]) -> dict[str, Any]:
    brief = {
        "inventory_digest": inventory.get("inventory_digest"),
        "company_count": inventory.get("company_count"),
        "filing_count": inventory.get("filing_count"),
        "years": inventory.get("years") or [],
        "form_types": inventory.get("form_types") or {},
        "source_types": inventory.get("source_types") or {},
        "source_tiers": inventory.get("source_tiers") or {},
        "source_families": inventory.get("source_families") or [],
        "available_source_families": inventory.get("available_source_families") or [],
        "categories": inventory.get("categories") or [],
        "source_coverage_gap_count": inventory.get("source_coverage_gap_count") or 0,
        "source_coverage_gap_reasons": inventory.get("source_coverage_gap_reasons") or {},
    }
    if inventory.get("market_snapshot"):
        brief["market_snapshot"] = _context_inventory_brief(inventory.get("market_snapshot") or {})
    if inventory.get("industry_snapshot"):
        brief["industry_snapshot"] = _context_inventory_brief(inventory.get("industry_snapshot") or {})
    if inventory.get("source_boundaries"):
        brief["source_boundaries"] = inventory.get("source_boundaries")
    return brief


def inventory_prompt(
    inventory: dict[str, Any],
    *,
    selected_tickers: list[str],
    selected_years: list[int],
    max_companies: int = 80,
) -> str:
    selected = {ticker.upper() for ticker in selected_tickers}
    years = {int(year) for year in selected_years}
    companies = []
    for item in inventory.get("companies") or []:
        ticker = str(item.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        available_years = [year for year in item.get("years") or [] if not years or int(year) in years]
        if not available_years:
            continue
        companies.append(
            {
                "ticker": ticker,
                "company": item.get("company") or "",
                "category": item.get("category") or "",
                "years": available_years,
                "forms": item.get("form_types") or [],
                "sources": item.get("source_types") or [],
                "source_tiers": item.get("source_tiers") or [],
            }
        )
    companies = companies[:max_companies]
    lines = [
        "PROJECT SOURCE INVENTORY",
        f"- inventory_digest: {inventory.get('inventory_digest')}",
        f"- company_count_total: {inventory.get('company_count')}",
        f"- filing_count_total: {inventory.get('filing_count')}",
        f"- available_years_total: {', '.join(str(item) for item in inventory.get('years') or [])}",
        f"- available_form_types: {', '.join(_counter_keys(inventory.get('form_types') or {})) or '<none>'}",
        f"- available_source_types: {', '.join(_counter_keys(inventory.get('source_types') or {})) or '<none>'}",
        f"- available_source_tiers: {', '.join(_counter_keys(inventory.get('source_tiers') or {})) or '<none>'}",
        f"- available_source_families: {', '.join(str(item) for item in inventory.get('available_source_families') or []) or '<none>'}",
        f"- indexed_sections: {', '.join(str(item) for item in inventory.get('sections') or [])}",
        "",
        "INDUSTRY / CATEGORY COVERAGE",
    ]
    for category in inventory.get("categories") or []:
        tickers = [str(item) for item in category.get("tickers") or []]
        overlap = [ticker for ticker in tickers if not selected or ticker in selected]
        if not overlap:
            continue
        lines.append(f"- {category.get('category')}: {', '.join(overlap)}")
    lines.extend(["", "SELECTED COMPANY FILINGS"])
    for item in companies:
        lines.append(
            "- "
            f"{item['ticker']} | {item['company']} | {item['category']} | "
            f"years={','.join(str(year) for year in item['years'])} | "
            f"forms={','.join(str(form) for form in item['forms']) or '<none>'} | "
            f"source_tiers={','.join(str(tier) for tier in item['source_tiers']) or '<none>'}"
        )
    selected_gaps = _selected_source_gap_rows(
        inventory.get("source_coverage_gaps") or [],
        selected_tickers=selected_tickers,
        selected_years=selected_years,
    )
    if selected_gaps:
        lines.extend(["", "SELECTED SOURCE GAPS"])
        for gap in selected_gaps[:20]:
            lines.append(
                "- "
                f"{gap.get('ticker')} {gap.get('year')} {gap.get('form_type')} | "
                f"tier={gap.get('source_tier') or '<unknown>'} | "
                f"reason={gap.get('reason_code') or gap.get('reason') or '<unknown>'}"
            )
    lines.extend(
        [
            "",
            "CONTEXT-ONLY SOURCE FAMILIES",
            *_context_source_prompt_lines(inventory),
            "",
            "PLANNER BOUNDARY RULES",
            "- Choose only tickers, years, form types, and source types listed above.",
            "- If the user asks for data outside the inventory, keep it as a caveat or mark it unsupported; do not pretend the source exists.",
            "- Treat SEC filings as the only evidence boundary unless the active source policy explicitly changes the project scope.",
            "- Do not mention 8-K, earnings calls, market prices, macro data, or news unless the inventory lists those source types, source tiers, or context source families.",
            "- market_snapshot is context-only market or valuation evidence; it cannot prove company-reported fundamentals and cannot overwrite SEC Exact-Value Ledger values.",
            "- industry_snapshot is context-only industry, macro, regulatory, or demand evidence; it cannot prove company-level revenue, margin, customer, or supplier facts.",
            "- If 10-Q is available, label it as unaudited quarterly SEC evidence and do not mix it with annual 10-K values without period caveats.",
            "- Build the task around available materials first, then record missing materials as evidence gaps.",
        ]
    )
    return "\n".join(lines)


def _counter_keys(counter_like: dict[str, Any]) -> list[str]:
    return [str(key) for key in sorted(counter_like)]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None


def _normalize_form_type(value: Any) -> str:
    text = str(value or "").upper().strip()
    return (
        text.replace("10K", "10-K")
        .replace("10Q", "10-Q")
        .replace("8K", "8-K")
        .replace("20F", "20-F")
        .replace("40F", "40-F")
        .replace("6K", "6-K")
    )


def _normalize_source_type(value: Any) -> str:
    text = str(value or "").upper().strip()
    return _normalize_form_type(text) if text in {"10K", "10Q", "8K", "20F", "40F", "6K"} else text


def _manifest_row_form_type(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    for value in (
        row.get("form_type"),
        row.get("source_type"),
        metadata.get("form_type"),
        metadata.get("source_type"),
    ):
        form = _normalize_form_type(value)
        if form in _SEC_FORM_TYPES:
            return form
    for key in ("evidence_id", "source_evidence_id", "source_id", "chunk_id", "block_id", "object_id", "id"):
        form = _form_type_from_source_id(row.get(key))
        if form:
            return form
    return ""


def _form_type_from_source_id(value: Any) -> str:
    match = _SEC_FORM_ID_RE.search(str(value or "").upper())
    if not match:
        return ""
    form = _normalize_form_type(match.group("form"))
    return form if form in _SEC_FORM_TYPES else ""


def _default_source_tier_for_form(form: str) -> str:
    if form in {"8-K", "6-K"}:
        return "company_authored_unaudited_sec_filing"
    return "primary_sec_filing"


def _normalize_source_gap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        year = _int_or_none(row.get("year") or row.get("filing_year") or row.get("fiscal_year"))
        form_type = _manifest_row_form_type(row)
        reason_code = str(row.get("reason_code") or row.get("reason") or "").strip()
        if not ticker or year is None or not form_type or not reason_code:
            continue
        normalized.append(
            {
                "ticker": ticker,
                "year": int(year),
                "form_type": form_type,
                "source_tier": str(row.get("source_tier") or "").strip(),
                "category": str(row.get("category") or "").strip(),
                "category_slug": str(row.get("category_slug") or "").strip(),
                "reason_code": reason_code,
                "reason": str(row.get("reason") or reason_code).strip(),
                "source": str(row.get("source") or "").strip(),
                "status": str(row.get("status") or "missing").strip(),
                "metadata_path": str(row.get("metadata_path") or "").strip(),
                "accession_number": str(row.get("accession_number") or "").strip(),
            }
        )
    return sorted(
        normalized,
        key=lambda gap: (
            str(gap.get("ticker") or ""),
            int(gap.get("year") or 0),
            str(gap.get("form_type") or ""),
            str(gap.get("reason_code") or ""),
        ),
    )


def _load_json_file(path: str | None) -> dict[str, Any]:
    path_text = str(path or "").strip()
    if not path_text:
        return {}
    try:
        with Path(path_text).expanduser().open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _market_snapshot_inventory(
    *,
    market_evidence_path: str | None,
    market_catalog_path: str | None,
    market_snapshot_id: str | None,
    market_as_of_date: str | None,
    market_industry_summary: dict[str, Any],
) -> dict[str, Any] | None:
    market_summary = market_industry_summary.get("market") if isinstance(market_industry_summary.get("market"), dict) else {}
    outputs = market_industry_summary.get("outputs") if isinstance(market_industry_summary.get("outputs"), dict) else {}
    has_manifest_market = bool(market_summary or _artifact_outputs(outputs, "market"))
    if not any(str(value or "").strip() for value in (market_evidence_path, market_catalog_path, market_snapshot_id, market_as_of_date)) and not has_manifest_market:
        return None
    evidence_path = str(market_evidence_path or "").strip()
    catalog_path = str(market_catalog_path or "").strip()
    return {
        "source_family": "market_snapshot",
        "status": "available" if evidence_path or catalog_path else "manifest_only",
        "context_only": True,
        "allowed_claim_scope": "market_or_valuation_context_only",
        "snapshot_id": str(market_snapshot_id or "").strip(),
        "as_of_date": str(market_as_of_date or "").strip(),
        "evidence_path": evidence_path,
        "catalog_path": catalog_path,
        "manifest_outputs": _artifact_outputs(outputs, "market"),
        "company_count": market_summary.get("company_count"),
        "market_row_count": market_summary.get("market_row_count"),
        "provider_symbol_count": market_summary.get("provider_symbol_count"),
        "non_us_provider_symbol_count": market_summary.get("non_us_provider_symbol_count"),
        "currency_counts": _dict_value(market_summary.get("currency_counts")),
        "region_counts": _dict_value(market_summary.get("region_counts")),
        "known_limitations": _string_list(market_summary.get("known_limitations")),
        "forbidden_uses": [
            "cannot prove company-reported financial facts",
            "cannot overwrite SEC Exact-Value Ledger values",
            "cannot be treated as real-time market data without an as_of_date",
        ],
    }


def _industry_snapshot_inventory(
    *,
    industry_evidence_path: str | None,
    industry_snapshot_db_path: str | None,
    industry_snapshot_id: str | None,
    industry_as_of_date: str | None,
    market_industry_summary: dict[str, Any],
) -> dict[str, Any] | None:
    industry_summary = market_industry_summary.get("industry") if isinstance(market_industry_summary.get("industry"), dict) else {}
    outputs = market_industry_summary.get("outputs") if isinstance(market_industry_summary.get("outputs"), dict) else {}
    has_manifest_industry = bool(industry_summary or _artifact_outputs(outputs, "industry"))
    if (
        not any(
            str(value or "").strip()
            for value in (industry_evidence_path, industry_snapshot_db_path, industry_snapshot_id, industry_as_of_date)
        )
        and not has_manifest_industry
    ):
        return None
    evidence_path = str(industry_evidence_path or "").strip()
    snapshot_db_path = str(industry_snapshot_db_path or "").strip()
    return {
        "source_family": "industry_snapshot",
        "status": "available" if evidence_path or snapshot_db_path else "manifest_only",
        "context_only": True,
        "allowed_claim_scope": "industry_context_only",
        "snapshot_id": str(industry_snapshot_id or "").strip(),
        "as_of_date": str(industry_as_of_date or "").strip(),
        "evidence_path": evidence_path,
        "snapshot_db_path": snapshot_db_path,
        "manifest_outputs": _artifact_outputs(outputs, "industry"),
        "company_count": industry_summary.get("company_count"),
        "mapped_company_count": industry_summary.get("mapped_company_count"),
        "unmapped_company_count": industry_summary.get("unmapped_company_count"),
        "source_family_company_counts": _dict_value(industry_summary.get("source_family_company_counts")),
        "known_limitations": _string_list(industry_summary.get("known_limitations")),
        "forbidden_uses": [
            "cannot prove company-reported financial facts",
            "cannot prove company-level revenue, margin, customer, or supplier facts",
            "cannot replace retrieved company filings or ledger rows",
        ],
    }


def _source_boundaries(
    *,
    market_snapshot: dict[str, Any] | None,
    industry_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    boundaries: dict[str, Any] = {}
    if market_snapshot:
        boundaries["market_snapshot"] = {
            "context_only": True,
            "allowed_claim_scope": market_snapshot.get("allowed_claim_scope"),
            "forbidden_uses": market_snapshot.get("forbidden_uses") or [],
        }
    if industry_snapshot:
        boundaries["industry_snapshot"] = {
            "context_only": True,
            "allowed_claim_scope": industry_snapshot.get("allowed_claim_scope"),
            "forbidden_uses": industry_snapshot.get("forbidden_uses") or [],
        }
    return boundaries


def _context_inventory_brief(block: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "source_family",
        "status",
        "context_only",
        "allowed_claim_scope",
        "snapshot_id",
        "as_of_date",
        "evidence_path",
        "catalog_path",
        "snapshot_db_path",
        "manifest_outputs",
        "company_count",
        "market_row_count",
        "provider_symbol_count",
        "non_us_provider_symbol_count",
        "mapped_company_count",
        "unmapped_company_count",
        "source_family_company_counts",
        "currency_counts",
        "region_counts",
        "known_limitations",
    )
    return {key: block.get(key) for key in keep_keys if block.get(key) not in (None, "", [], {})}


def _context_source_prompt_lines(inventory: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    market = inventory.get("market_snapshot") if isinstance(inventory.get("market_snapshot"), dict) else None
    if market:
        lines.append(
            "- market_snapshot | "
            f"status={market.get('status') or '<unknown>'} | "
            f"snapshot_id={market.get('snapshot_id') or '<unset>'} | "
            f"as_of_date={market.get('as_of_date') or '<unset>'} | "
            "context_only=market_or_valuation_context_only"
        )
    industry = inventory.get("industry_snapshot") if isinstance(inventory.get("industry_snapshot"), dict) else None
    if industry:
        families = _dict_value(industry.get("source_family_company_counts"))
        family_text = ",".join(sorted(families)[:8]) if families else "<unset>"
        lines.append(
            "- industry_snapshot | "
            f"status={industry.get('status') or '<unknown>'} | "
            f"snapshot_id={industry.get('snapshot_id') or '<unset>'} | "
            f"as_of_date={industry.get('as_of_date') or '<unset>'} | "
            f"source_families={family_text} | "
            "context_only=industry_context_only"
        )
    return lines or ["- <none>"]


def _artifact_outputs(outputs: dict[str, Any], prefix: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in outputs.items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if key_text.startswith(prefix) and value_text:
            result[key_text] = value_text
    return dict(sorted(result.items()))


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _selected_source_gap_rows(
    rows: list[dict[str, Any]],
    *,
    selected_tickers: list[str],
    selected_years: list[int],
) -> list[dict[str, Any]]:
    tickers = {str(ticker).upper() for ticker in selected_tickers}
    years = {int(year) for year in selected_years}
    selected = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        year = _int_or_none(row.get("year"))
        if tickers and ticker not in tickers:
            continue
        if years and year not in years:
            continue
        selected.append(row)
    return selected


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    return value
