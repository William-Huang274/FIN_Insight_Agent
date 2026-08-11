from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sec_agent.industry_playbooks import compact_playbook_registry, load_playbook_registry, match_playbook_candidates


DEFAULT_SECTIONS = (
    "Item 1. Business",
    "Item 1A. Risk Factors",
    "Item 7. Management's Discussion and Analysis",
    "Item 8. Financial Statements and Supplementary Data",
)
_SEC_FORM_TYPES = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
_SEC_FORM_ID_RE = re.compile(r"(?:^|[^A-Z0-9])(?P<form>10-?K|10-?Q|8-?K|20-?F|40-?F|6-?K)(?:[^A-Z0-9]|$)")

KNOWN_RUNTIME_SOURCE_FAMILIES = (
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "company_product_evidence_graph",
    "public_source_context",
    "live_public_web_context",
    "milvus_semantic",
    "market_snapshot",
    "industry_snapshot",
    "relationship_graph",
    "run_artifact",
)

SOURCE_FAMILY_AUTHORITY: dict[str, dict[str, Any]] = {
    "primary_sec_filing": {
        "authority_tier": "primary_exact_value",
        "context_only": False,
        "exact_value_authority": True,
        "allowed_claim_scope": "reported_financial_fact_segment_fact_management_commentary",
    },
    "company_authored_unaudited_sec_filing": {
        "authority_tier": "company_disclosed_context",
        "context_only": False,
        "exact_value_authority": "limited_to_company_disclosed_unaudited_rows",
        "allowed_claim_scope": "earnings_release_and_management_commentary",
    },
    "company_product_evidence_graph": {
        "authority_tier": "company_disclosed_context",
        "context_only": False,
        "exact_value_authority": "row_level_runtime_fact_allowed_only",
        "allowed_claim_scope": "product_taxonomy_and_company_disclosed_product_kpi",
    },
    "public_source_context": {
        "authority_tier": "context_or_proxy",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "public_context_resolver_and_lead_only",
    },
    "live_public_web_context": {
        "authority_tier": "lead_only",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "allowlisted_web_snapshot_candidate_only",
    },
    "milvus_semantic": {
        "authority_tier": "context_or_proxy",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "typed_semantic_recall_supplement_not_exact_value_authority",
    },
    "market_snapshot": {
        "authority_tier": "context_or_proxy",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "market_or_valuation_context_only",
    },
    "industry_snapshot": {
        "authority_tier": "context_or_proxy",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "industry_context_only",
    },
    "relationship_graph": {
        "authority_tier": "context_or_proxy",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "relationship_scope_or_hypothesis_only",
    },
    "run_artifact": {
        "authority_tier": "gap_only",
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "run_trace_gap_and_verification_context_only",
    },
}

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
    product_evidence_graph_summary_path: str | None = None,
    product_evidence_graph_path: str | None = None,
    product_evidence_nodes_path: str | None = None,
    product_evidence_gaps_path: str | None = None,
    product_evidence_facts_path: str | None = None,
    public_source_inventory_summary_path: str | None = None,
    public_source_inventory_rows_path: str | None = None,
    public_source_normalized_snapshot_summary_path: str | None = None,
    public_source_normalized_evidence_rows_path: str | None = None,
    milvus_runtime_status: str | None = None,
    milvus_runtime_location: str | None = None,
    milvus_collection_name: str | None = None,
    milvus_vector_kinds: list[str] | tuple[str, ...] | None = None,
    milvus_summary_path: str | None = None,
    live_public_web_policy_ids: list[str] | tuple[str, ...] | None = None,
    playbook_registry_path: str | None = None,
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
                "cik": _normalize_cik(row.get("cik") or row.get("cik_str")),
                "issuer_id": str(row.get("issuer_id") or row.get("issuer") or "").strip(),
                "lei": str(row.get("lei") or "").strip(),
                "figi": str(row.get("figi") or row.get("composite_figi") or "").strip(),
                "isin": str(row.get("isin") or "").strip(),
                "cusip": str(row.get("cusip") or "").strip(),
                "sedol": str(row.get("sedol") or "").strip(),
                "company": str(row.get("company") or "").strip(),
                "legal_name": str(row.get("legal_name") or "").strip(),
                "aliases": set(_string_list(row.get("aliases"))),
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
        if not company.get("cik"):
            company["cik"] = _normalize_cik(row.get("cik") or row.get("cik_str"))
        for key in ("issuer_id", "lei", "figi", "isin", "cusip", "sedol", "legal_name"):
            if not company.get(key) and row.get(key):
                company[key] = str(row.get(key) or "").strip()
        company["aliases"].update(_string_list(row.get("aliases")))
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
        item["aliases"] = sorted(item["aliases"])
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
    product_evidence_graph = _product_evidence_graph_inventory(
        product_evidence_graph_summary_path=product_evidence_graph_summary_path,
        product_evidence_graph_path=product_evidence_graph_path,
        product_evidence_nodes_path=product_evidence_nodes_path,
        product_evidence_gaps_path=product_evidence_gaps_path,
        product_evidence_facts_path=product_evidence_facts_path,
    )
    public_source_context = _public_source_context_inventory(
        public_source_inventory_summary_path=public_source_inventory_summary_path,
        public_source_inventory_rows_path=public_source_inventory_rows_path,
        public_source_normalized_snapshot_summary_path=public_source_normalized_snapshot_summary_path,
        public_source_normalized_evidence_rows_path=public_source_normalized_evidence_rows_path,
    )
    milvus_runtime = _milvus_runtime_inventory(
        milvus_runtime_status=milvus_runtime_status,
        milvus_runtime_location=milvus_runtime_location,
        milvus_collection_name=milvus_collection_name,
        milvus_vector_kinds=milvus_vector_kinds,
        milvus_summary_path=milvus_summary_path,
    )
    live_public_web_context = _live_public_web_context_inventory(live_public_web_policy_ids=live_public_web_policy_ids)
    context_source_families = [
        block["source_family"]
        for block in (market_snapshot, industry_snapshot, product_evidence_graph, public_source_context, milvus_runtime, live_public_web_context)
        if isinstance(block, dict) and block.get("source_family") and block.get("available", True)
    ]
    available_source_families = sorted(set(source_tier_counts) | set(context_source_families))
    source_family_availability = _source_family_availability(
        available_source_families=available_source_families,
        source_tier_counts=dict(source_tier_counts),
        source_coverage_gap_reasons=dict(Counter(str(gap.get("reason_code") or "unknown") for gap in normalized_source_gaps)),
        market_snapshot=market_snapshot,
        industry_snapshot=industry_snapshot,
        product_evidence_graph=product_evidence_graph,
        public_source_context=public_source_context,
        milvus_runtime=milvus_runtime,
        live_public_web_context=live_public_web_context,
    )
    playbook_registry = load_playbook_registry(playbook_registry_path)
    playbook_candidates = match_playbook_candidates(categories, playbook_registry)
    playbook_registry_summary = compact_playbook_registry(playbook_registry)

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
        "source_family_authority": SOURCE_FAMILY_AUTHORITY,
        "source_family_availability": source_family_availability,
        "playbook_registry": playbook_registry_summary,
        "playbook_candidates": playbook_candidates,
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
    if product_evidence_graph:
        inventory["product_evidence_graph"] = product_evidence_graph
    if public_source_context:
        inventory["public_source_context"] = public_source_context
    if milvus_runtime:
        inventory["milvus_runtime"] = milvus_runtime
    if live_public_web_context:
        inventory["live_public_web_context"] = live_public_web_context
    inventory["source_boundaries"] = _source_boundaries(
        market_snapshot=market_snapshot,
        industry_snapshot=industry_snapshot,
        product_evidence_graph=product_evidence_graph,
        public_source_context=public_source_context,
        milvus_runtime=milvus_runtime,
        live_public_web_context=live_public_web_context,
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
        "schema_version": "project_inventory_brief_v0.2",
        "inventory_digest": inventory.get("inventory_digest"),
        "company_count": inventory.get("company_count"),
        "filing_count": inventory.get("filing_count"),
        "years": inventory.get("years") or [],
        "form_types": inventory.get("form_types") or {},
        "source_types": inventory.get("source_types") or {},
        "source_tiers": inventory.get("source_tiers") or {},
        "source_families": inventory.get("source_families") or [],
        "available_source_families": inventory.get("available_source_families") or [],
        "source_family_availability": inventory.get("source_family_availability") or {},
        "source_family_authority": inventory.get("source_family_authority") or SOURCE_FAMILY_AUTHORITY,
        "categories": inventory.get("categories") or [],
        "source_coverage_gap_count": inventory.get("source_coverage_gap_count") or 0,
        "source_coverage_gap_reasons": inventory.get("source_coverage_gap_reasons") or {},
        "known_gap_type_counts": _known_gap_type_counts(inventory),
        "playbook_registry": inventory.get("playbook_registry") or {},
        "playbook_candidates": inventory.get("playbook_candidates") or [],
    }
    if inventory.get("market_snapshot"):
        brief["market_snapshot"] = _context_inventory_brief(inventory.get("market_snapshot") or {})
    if inventory.get("industry_snapshot"):
        brief["industry_snapshot"] = _context_inventory_brief(inventory.get("industry_snapshot") or {})
    if inventory.get("product_evidence_graph"):
        brief["product_evidence_graph"] = _context_inventory_brief(inventory.get("product_evidence_graph") or {})
    if inventory.get("public_source_context"):
        brief["public_source_context"] = _context_inventory_brief(inventory.get("public_source_context") or {})
    if inventory.get("milvus_runtime"):
        brief["milvus_runtime"] = _context_inventory_brief(inventory.get("milvus_runtime") or {})
    if inventory.get("live_public_web_context"):
        brief["live_public_web_context"] = _context_inventory_brief(inventory.get("live_public_web_context") or {})
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
        f"- inventory_brief_schema: project_inventory_brief_v0.2",
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
            "SOURCE FAMILY AUTHORITY / AVAILABILITY",
            *_source_family_availability_prompt_lines(inventory),
            "",
            "PLAYBOOK CANDIDATES",
            *_playbook_candidate_prompt_lines(inventory),
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
            "- company_product_evidence_graph exposes company-disclosed product facts only for rows marked runtime_fact_allowed; taxonomy, context, review, and gap rows are not facts.",
            "- public_source_context is context/resolver/lead evidence only; it cannot prove company-reported product sales, market share, channel inventory, or profitability.",
            "- live_public_web_context is not a free-search permission; only allowlisted, fetched, classified, parsed, and gated snapshots may enter context rows.",
            "- milvus_semantic is a typed semantic recall supplement; it cannot prove exact values and must be unavailable when inventory marks Milvus unavailable.",
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


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits.zfill(10) if digits else ""


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


def _product_evidence_graph_inventory(
    *,
    product_evidence_graph_summary_path: str | None,
    product_evidence_graph_path: str | None,
    product_evidence_nodes_path: str | None,
    product_evidence_gaps_path: str | None,
    product_evidence_facts_path: str | None,
) -> dict[str, Any] | None:
    summary = _load_json_file(product_evidence_graph_summary_path)
    path_values = {
        "summary_path": str(product_evidence_graph_summary_path or "").strip(),
        "graph_path": str(product_evidence_graph_path or "").strip(),
        "nodes_path": str(product_evidence_nodes_path or "").strip(),
        "gaps_path": str(product_evidence_gaps_path or "").strip(),
        "facts_path": str(product_evidence_facts_path or "").strip(),
    }
    if not any(path_values.values()) and not summary:
        return None
    outputs = summary.get("outputs") if isinstance(summary.get("outputs"), dict) else {}
    return {
        "source_family": "company_product_evidence_graph",
        "status": "available" if any(path_values.values()) or outputs else "manifest_only",
        "feature_flag_required": True,
        "default_runtime_enabled": False,
        "context_only": False,
        "allowed_claim_scope": "company_disclosed_product_evidence_with_promotion_status_boundary",
        "company_count": summary.get("company_count"),
        "runtime_fact_company_count": summary.get("companies_with_sec_verified_product_kpi"),
        "evidence_node_count": summary.get("evidence_node_count"),
        "gap_count": summary.get("gap_count"),
        "gap_type_counts": _dict_value(summary.get("gap_type_counts")),
        "node_promotion_counts": _dict_value(summary.get("node_promotion_counts")),
        "monotonic_repair_fact_count": summary.get("monotonic_repair_fact_count"),
        "operating_metric_repair_fact_count": summary.get("operating_metric_repair_fact_count"),
        "sentence_repair_fact_count": summary.get("sentence_repair_fact_count"),
        "summary_path": path_values["summary_path"],
        "graph_path": path_values["graph_path"] or str(outputs.get("graph") or ""),
        "nodes_path": path_values["nodes_path"] or str(outputs.get("nodes") or ""),
        "gaps_path": path_values["gaps_path"] or str(outputs.get("gaps") or ""),
        "facts_path": path_values["facts_path"],
        "claim_boundary": {
            "runtime_fact_allowed": "company-disclosed product KPI facts may support product-financial bridge claims.",
            "runtime_context_taxonomy_only": "taxonomy may support product/segment retrieval planning only.",
            "context_or_lead_available": "public or official context may support directional context or source leads only.",
            "review_queue_not_runtime_fact": "review candidates are not facts.",
            "gap_rows": "commercial/public gaps may be exposed as missing evidence, never filled by proxy fallback.",
        },
        "forbidden_uses": [
            "cannot use review_queue_not_runtime_fact rows as facts",
            "cannot use taxonomy/context rows to state product sales or market share",
            "cannot fill commercial tracker gaps with weak public proxies",
            "cannot overwrite SEC filing facts without a later promotion gate",
        ],
    }


def _public_source_context_inventory(
    *,
    public_source_inventory_summary_path: str | None,
    public_source_inventory_rows_path: str | None,
    public_source_normalized_snapshot_summary_path: str | None,
    public_source_normalized_evidence_rows_path: str | None,
) -> dict[str, Any] | None:
    adapter_summary = _load_json_file(public_source_inventory_summary_path)
    normalized_summary = _load_json_file(public_source_normalized_snapshot_summary_path)
    path_values = {
        "inventory_summary_path": str(public_source_inventory_summary_path or "").strip(),
        "inventory_rows_path": str(public_source_inventory_rows_path or "").strip(),
        "normalized_snapshot_summary_path": str(public_source_normalized_snapshot_summary_path or "").strip(),
        "normalized_evidence_rows_path": str(public_source_normalized_evidence_rows_path or "").strip(),
    }
    if not any(path_values.values()) and not adapter_summary and not normalized_summary:
        return None
    adapter_outputs = adapter_summary.get("outputs") if isinstance(adapter_summary.get("outputs"), dict) else {}
    normalized_outputs = normalized_summary.get("outputs") if isinstance(normalized_summary.get("outputs"), dict) else {}
    return {
        "source_family": "public_source_context",
        "status": "available" if any(path_values.values()) or adapter_outputs or normalized_outputs else "manifest_only",
        "feature_flag_required": True,
        "default_runtime_enabled": False,
        "context_only": True,
        "allowed_claim_scope": "public_context_resolver_and_lead_only",
        "inventory_row_count": adapter_summary.get("promoted_inventory_row_count"),
        "runtime_eligible_row_count": adapter_summary.get("runtime_eligible_row_count"),
        "resolver_eligible_row_count": adapter_summary.get("resolver_eligible_row_count"),
        "bounded_evidence_eligible_row_count": adapter_summary.get("bounded_evidence_eligible_row_count"),
        "exact_value_authority_row_count": adapter_summary.get("exact_value_authority_row_count"),
        "normalized_record_count": normalized_summary.get("normalized_record_count"),
        "normalized_evidence_row_count": normalized_summary.get("evidence_row_count"),
        "successful_source_count": normalized_summary.get("successful_source_count"),
        "successful_sources": _string_list(normalized_summary.get("successful_sources")),
        "promotion_counts_by_source_family": _dict_value(adapter_summary.get("promotion_counts_by_source_family")),
        "normalized_source_family_counts": _dict_value(normalized_summary.get("source_family_counts")),
        "source_record_counts": _dict_value(normalized_summary.get("source_record_counts")),
        "inventory_summary_path": path_values["inventory_summary_path"],
        "inventory_rows_path": path_values["inventory_rows_path"] or str(adapter_outputs.get("public_source_inventory_rows") or ""),
        "normalized_snapshot_summary_path": path_values["normalized_snapshot_summary_path"],
        "normalized_evidence_rows_path": path_values["normalized_evidence_rows_path"] or str(normalized_outputs.get("evidence_rows") or ""),
        "claim_boundary": normalized_summary.get("claim_boundary") or [
            "Public source rows are context/resolver/lead evidence only.",
            "Company-level product sales and financial facts must come from filings or an explicit source-specific promotion gate.",
        ],
        "forbidden_uses": [
            "cannot prove company-reported financial facts",
            "cannot prove company product sales, deliveries, subscribers, backlog, ARPU, market share, or profitability",
            "cannot overwrite SEC filings or exact-value ledger rows",
            "cannot convert public proxies into commercial tracker replacements",
        ],
    }


def _milvus_runtime_inventory(
    *,
    milvus_runtime_status: str | None,
    milvus_runtime_location: str | None,
    milvus_collection_name: str | None,
    milvus_vector_kinds: list[str] | tuple[str, ...] | None,
    milvus_summary_path: str | None,
) -> dict[str, Any]:
    summary = _load_json_file(milvus_summary_path)
    location = str(milvus_runtime_location or summary.get("location") or "").strip().lower()
    status = str(milvus_runtime_status or summary.get("status") or "").strip().lower()
    if not status:
        if location in {"cloud", "local"}:
            status = f"{location}_available"
        else:
            status = "unavailable"
    if status in {"available", "enabled"}:
        status = f"{location or 'cloud'}_available"
    if status not in {"cloud_available", "local_available", "unavailable"}:
        status = "unavailable"
    if status == "cloud_available":
        location = "cloud"
    elif status == "local_available":
        location = "local"
    else:
        location = "none"
    vector_kinds = _string_list(milvus_vector_kinds or summary.get("vector_kinds"))
    if not vector_kinds:
        vector_kinds = ["narrative_chunk", "table_chunk", "paraphrase_context"]
    return {
        "source_family": "milvus_semantic",
        "status": status,
        "available": status in {"cloud_available", "local_available"},
        "location": location,
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "typed_semantic_recall_supplement_not_exact_value_authority",
        "collection": str(milvus_collection_name or summary.get("collection") or summary.get("collection_name") or "").strip(),
        "vector_kinds": vector_kinds,
        "vector_count": summary.get("vector_count") or summary.get("row_count"),
        "as_of_date": str(summary.get("as_of_date") or summary.get("materialized_at") or "").strip(),
        "schema_digest": str(summary.get("schema_digest") or summary.get("digest") or "").strip(),
        "summary_path": str(milvus_summary_path or "").strip(),
        "fallback_routes": ["bm25", "object_bm25", "exact_value_ledger"],
        "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
        "forbidden_uses": [
            "cannot prove exact values",
            "cannot replace SEC Exact-Value Ledger or filing table parser",
            "cannot be activated when status is unavailable",
        ],
    }


def _live_public_web_context_inventory(*, live_public_web_policy_ids: list[str] | tuple[str, ...] | None) -> dict[str, Any]:
    policy_ids = _string_list(live_public_web_policy_ids)
    return {
        "source_family": "live_public_web_context",
        "status": "policy_available" if policy_ids else "policy_not_loaded",
        "available": bool(policy_ids),
        "context_only": True,
        "exact_value_authority": False,
        "allowed_claim_scope": "allowlisted_web_snapshot_candidate_only",
        "web_scope_policy_ids": policy_ids,
        "claim_boundary": [
            "Search snippets are lead-only and cannot enter claim cards.",
            "Fetched snapshots must be allowlisted, classified, parsed, and gated before any promotion.",
            "Commerce pages can support SKU, price, and availability context only.",
        ],
        "forbidden_uses": [
            "cannot use unallowlisted domains",
            "cannot use search snippets as evidence",
            "cannot infer sales, market share, sell-through, inventory, or profitability from weak public proxies",
        ],
    }


def _source_boundaries(
    *,
    market_snapshot: dict[str, Any] | None,
    industry_snapshot: dict[str, Any] | None,
    product_evidence_graph: dict[str, Any] | None = None,
    public_source_context: dict[str, Any] | None = None,
    milvus_runtime: dict[str, Any] | None = None,
    live_public_web_context: dict[str, Any] | None = None,
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
    if product_evidence_graph:
        boundaries["company_product_evidence_graph"] = {
            "context_only": False,
            "feature_flag_required": True,
            "allowed_claim_scope": product_evidence_graph.get("allowed_claim_scope"),
            "claim_boundary": product_evidence_graph.get("claim_boundary") or {},
            "forbidden_uses": product_evidence_graph.get("forbidden_uses") or [],
        }
    if public_source_context:
        boundaries["public_source_context"] = {
            "context_only": True,
            "feature_flag_required": True,
            "allowed_claim_scope": public_source_context.get("allowed_claim_scope"),
            "claim_boundary": public_source_context.get("claim_boundary") or [],
            "forbidden_uses": public_source_context.get("forbidden_uses") or [],
        }
    if milvus_runtime:
        boundaries["milvus_semantic"] = {
            "context_only": True,
            "available": bool(milvus_runtime.get("available")),
            "location": milvus_runtime.get("location") or "none",
            "allowed_claim_scope": milvus_runtime.get("allowed_claim_scope"),
            "claim_boundary": milvus_runtime.get("claim_boundary"),
            "forbidden_uses": milvus_runtime.get("forbidden_uses") or [],
        }
    if live_public_web_context:
        boundaries["live_public_web_context"] = {
            "context_only": True,
            "available": bool(live_public_web_context.get("available")),
            "allowed_claim_scope": live_public_web_context.get("allowed_claim_scope"),
            "web_scope_policy_ids": live_public_web_context.get("web_scope_policy_ids") or [],
            "claim_boundary": live_public_web_context.get("claim_boundary") or [],
            "forbidden_uses": live_public_web_context.get("forbidden_uses") or [],
        }
    return boundaries


def _source_family_availability(
    *,
    available_source_families: list[str],
    source_tier_counts: dict[str, Any],
    source_coverage_gap_reasons: dict[str, Any],
    market_snapshot: dict[str, Any] | None,
    industry_snapshot: dict[str, Any] | None,
    product_evidence_graph: dict[str, Any] | None,
    public_source_context: dict[str, Any] | None,
    milvus_runtime: dict[str, Any],
    live_public_web_context: dict[str, Any],
) -> dict[str, Any]:
    available = set(available_source_families)
    blocks = {
        "market_snapshot": market_snapshot or {},
        "industry_snapshot": industry_snapshot or {},
        "company_product_evidence_graph": product_evidence_graph or {},
        "public_source_context": public_source_context or {},
        "milvus_semantic": milvus_runtime or {},
        "live_public_web_context": live_public_web_context or {},
    }
    result: dict[str, Any] = {}
    for family in KNOWN_RUNTIME_SOURCE_FAMILIES:
        authority = dict(SOURCE_FAMILY_AUTHORITY.get(family) or {})
        block = dict(blocks.get(family) or {})
        row_count = _source_family_row_count(family, source_tier_counts, block)
        status = str(block.get("status") or ("available" if family in available else "unavailable")).strip()
        is_available = bool(block.get("available")) if "available" in block else family in available
        if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
            is_available = row_count > 0 or family in available
            status = "available" if is_available else "unavailable"
        item = {
            "status": status,
            "available": is_available,
            "row_count": row_count,
            "authority_tier": authority.get("authority_tier"),
            "context_only": authority.get("context_only"),
            "exact_value_authority": authority.get("exact_value_authority"),
            "allowed_claim_scope": authority.get("allowed_claim_scope"),
        }
        gap_count = _source_family_gap_count(family, block, source_coverage_gap_reasons)
        if gap_count:
            item["known_gap_count"] = gap_count
        if family == "milvus_semantic":
            item["location"] = block.get("location") or "none"
            item["vector_kinds"] = block.get("vector_kinds") or []
        if family == "live_public_web_context":
            item["web_scope_policy_ids"] = block.get("web_scope_policy_ids") or []
        result[family] = {key: value for key, value in item.items() if value not in (None, "", [], {})}
    return result


def _source_family_row_count(family: str, source_tier_counts: dict[str, Any], block: dict[str, Any]) -> int:
    if family in source_tier_counts:
        return _positive_int(source_tier_counts.get(family))
    for key in (
        "runtime_fact_company_count",
        "evidence_node_count",
        "bounded_evidence_eligible_row_count",
        "normalized_evidence_row_count",
        "market_row_count",
        "mapped_company_count",
        "vector_count",
    ):
        value = _positive_int(block.get(key))
        if value:
            return value
    return 0


def _source_family_gap_count(family: str, block: dict[str, Any], source_coverage_gap_reasons: dict[str, Any]) -> int:
    if family == "company_product_evidence_graph":
        return _positive_int(block.get("gap_count"))
    if family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return sum(_positive_int(value) for value in source_coverage_gap_reasons.values())
    return 0


def _known_gap_type_counts(inventory: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    counts.update({str(key): _positive_int(value) for key, value in dict(inventory.get("source_coverage_gap_reasons") or {}).items()})
    product = inventory.get("product_evidence_graph") if isinstance(inventory.get("product_evidence_graph"), dict) else {}
    counts.update({str(key): _positive_int(value) for key, value in dict(product.get("gap_type_counts") or {}).items()})
    return {key: value for key, value in sorted(counts.items()) if value}


def _context_inventory_brief(block: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
        "source_family",
        "status",
        "available",
        "location",
        "context_only",
        "exact_value_authority",
        "allowed_claim_scope",
        "snapshot_id",
        "as_of_date",
        "collection",
        "vector_kinds",
        "vector_count",
        "schema_digest",
        "fallback_routes",
        "claim_boundary",
        "web_scope_policy_ids",
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
        "feature_flag_required",
        "default_runtime_enabled",
        "runtime_fact_company_count",
        "evidence_node_count",
        "gap_count",
        "gap_type_counts",
        "node_promotion_counts",
        "inventory_row_count",
        "runtime_eligible_row_count",
        "resolver_eligible_row_count",
        "bounded_evidence_eligible_row_count",
        "exact_value_authority_row_count",
        "normalized_record_count",
        "normalized_evidence_row_count",
        "successful_source_count",
        "successful_sources",
        "promotion_counts_by_source_family",
        "normalized_source_family_counts",
        "source_record_counts",
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
    product = inventory.get("product_evidence_graph") if isinstance(inventory.get("product_evidence_graph"), dict) else None
    if product:
        lines.append(
            "- company_product_evidence_graph | "
            f"status={product.get('status') or '<unknown>'} | "
            f"runtime_fact_companies={product.get('runtime_fact_company_count') or 0} | "
            f"nodes={product.get('evidence_node_count') or 0} | "
            f"gaps={product.get('gap_count') or 0} | "
            "feature_flag_required=true"
        )
    public_context = inventory.get("public_source_context") if isinstance(inventory.get("public_source_context"), dict) else None
    if public_context:
        lines.append(
            "- public_source_context | "
            f"status={public_context.get('status') or '<unknown>'} | "
            f"inventory_rows={public_context.get('inventory_row_count') or 0} | "
            f"bounded_rows={public_context.get('bounded_evidence_eligible_row_count') or 0} | "
            f"normalized_records={public_context.get('normalized_record_count') or 0} | "
            "context_only=true"
        )
    milvus = inventory.get("milvus_runtime") if isinstance(inventory.get("milvus_runtime"), dict) else None
    if milvus:
        lines.append(
            "- milvus_semantic | "
            f"status={milvus.get('status') or '<unknown>'} | "
            f"location={milvus.get('location') or 'none'} | "
            f"collection={milvus.get('collection') or '<unset>'} | "
            "context_only=true | exact_value_authority=false"
        )
    live_web = inventory.get("live_public_web_context") if isinstance(inventory.get("live_public_web_context"), dict) else None
    if live_web:
        policy_ids = ",".join(_string_list(live_web.get("web_scope_policy_ids"))[:8]) or "<none>"
        lines.append(
            "- live_public_web_context | "
            f"status={live_web.get('status') or '<unknown>'} | "
            f"web_scope_policy_ids={policy_ids} | "
            "context_only=true | exact_value_authority=false"
        )
    return lines or ["- <none>"]


def _source_family_availability_prompt_lines(inventory: dict[str, Any]) -> list[str]:
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), dict) else {}
    lines: list[str] = []
    for family in KNOWN_RUNTIME_SOURCE_FAMILIES:
        item = availability.get(family) if isinstance(availability.get(family), dict) else {}
        if not item:
            continue
        lines.append(
            "- "
            f"{family} | status={item.get('status') or '<unknown>'} | "
            f"available={str(bool(item.get('available'))).lower()} | "
            f"authority={item.get('authority_tier') or '<unknown>'} | "
            f"exact_value_authority={item.get('exact_value_authority')}"
        )
    return lines or ["- <none>"]


def _playbook_candidate_prompt_lines(inventory: dict[str, Any]) -> list[str]:
    candidates = [dict(item) for item in inventory.get("playbook_candidates") or [] if isinstance(item, dict)]
    if not candidates:
        return ["- generic_public_research | industry_schema=generic | status=fallback_candidate"]
    return [
        "- "
        f"{item.get('playbook_id') or '<unknown>'} | "
        f"industry_schema={item.get('industry_schema') or '<unknown>'} | "
        f"ticker_count={item.get('ticker_count') or 0} | "
        f"status={item.get('status') or 'candidate'} | "
        f"default_sources={','.join(_string_list(item.get('default_source_families'))[:6]) or '<none>'} | "
        f"specialists={_compact_mapping_for_prompt(item.get('specialist_routing'))} | "
        f"forbidden={','.join(_string_list(item.get('forbidden_claims'))[:6]) or '<none>'}"
        for item in candidates[:12]
    ]


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


def _compact_mapping_for_prompt(value: Any, *, max_items: int = 5) -> str:
    if not isinstance(value, dict):
        return "<none>"
    parts = [
        f"{str(key)}:{str(item)}"
        for key, item in list(value.items())[:max_items]
        if str(key or "").strip() and str(item or "").strip()
    ]
    return ",".join(parts) or "<none>"


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
