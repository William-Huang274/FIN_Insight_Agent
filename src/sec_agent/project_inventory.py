from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_SECTIONS = (
    "Item 1. Business",
    "Item 1A. Risk Factors",
    "Item 7. Management's Discussion and Analysis",
    "Item 8. Financial Statements and Supplementary Data",
)


def build_project_inventory(
    manifest_rows: list[dict[str, Any]],
    *,
    manifest_path: str,
    bm25_index_dir: str,
    object_bm25_index_dir: str,
    bge_model: str,
    sections: tuple[str, ...] = DEFAULT_SECTIONS,
) -> dict[str, Any]:
    companies: dict[str, dict[str, Any]] = {}
    categories: dict[str, set[str]] = defaultdict(set)
    form_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    year_counts: Counter[int] = Counter()

    for row in manifest_rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        year = _int_or_none(row.get("fiscal_year"))
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
                "filings": [],
            },
        )
        if not company.get("company") and row.get("company"):
            company["company"] = str(row.get("company") or "").strip()
        if not company.get("category") and row.get("category"):
            company["category"] = str(row.get("category") or "").strip()
        company["years"].add(year)
        form_type = str(row.get("form_type") or row.get("source_type") or "").upper().strip()
        source_type = str(row.get("source_type") or form_type).upper().strip()
        if form_type:
            company["form_types"].add(form_type)
            form_counts[form_type] += 1
        if source_type:
            company["source_types"].add(source_type)
            source_counts[source_type] += 1
        year_counts[year] += 1
        category = str(row.get("category") or "uncategorized").strip() or "uncategorized"
        categories[category].add(ticker)
        company["filings"].append(
            {
                "year": year,
                "form_type": form_type,
                "source_type": source_type,
                "filing_date": str(row.get("filing_date") or ""),
                "report_date": str(row.get("report_date") or ""),
                "accession_number": str(row.get("accession_number") or ""),
            }
        )

    normalized_companies = []
    for ticker in sorted(companies):
        item = companies[ticker]
        item["years"] = sorted(item["years"])
        item["form_types"] = sorted(item["form_types"])
        item["source_types"] = sorted(item["source_types"])
        item["filings"] = sorted(item["filings"], key=lambda filing: (filing["year"], filing["form_type"]))
        normalized_companies.append(item)

    inventory = {
        "schema_version": "project_source_inventory_v0.1",
        "source": "manifest_derived",
        "manifest_path": manifest_path,
        "company_count": len(normalized_companies),
        "filing_count": sum(len(item["filings"]) for item in normalized_companies),
        "years": sorted(year_counts),
        "form_types": dict(sorted(form_counts.items())),
        "source_types": dict(sorted(source_counts.items())),
        "sections": list(sections),
        "categories": [
            {"category": category, "tickers": sorted(tickers), "count": len(tickers)}
            for category, tickers in sorted(categories.items())
        ],
        "companies": normalized_companies,
        "indexes": {
            "manifest_path": manifest_path,
            "bm25_index_dir": bm25_index_dir,
            "object_bm25_index_dir": object_bm25_index_dir,
            "bge_model": bge_model,
        },
    }
    inventory["inventory_digest"] = inventory_digest(inventory)
    return inventory


def inventory_digest(inventory: dict[str, Any]) -> str:
    stable = dict(inventory)
    stable.pop("inventory_digest", None)
    data = json.dumps(_jsonable(stable), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:12]


def inventory_brief(inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "inventory_digest": inventory.get("inventory_digest"),
        "company_count": inventory.get("company_count"),
        "filing_count": inventory.get("filing_count"),
        "years": inventory.get("years") or [],
        "form_types": inventory.get("form_types") or {},
        "source_types": inventory.get("source_types") or {},
        "categories": inventory.get("categories") or [],
    }


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
            f"forms={','.join(str(form) for form in item['forms']) or '<none>'}"
        )
    lines.extend(
        [
            "",
            "PLANNER BOUNDARY RULES",
            "- Choose only tickers, years, form types, and source types listed above.",
            "- If the user asks for data outside the inventory, keep it as a caveat or mark it unsupported; do not pretend the source exists.",
            "- Treat SEC filings as the only evidence boundary unless the user explicitly changes the project scope.",
            "- Do not mention 8-K, 10-Q, earnings calls, market prices, macro data, or news unless the inventory lists those source types.",
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
