from __future__ import annotations

from typing import Any


def structured_object_search_text(record: dict[str, Any]) -> str:
    if record.get("search_text"):
        return str(record.get("search_text") or "")
    object_type = record.get("object_type")
    common = [
        record.get("ticker"),
        str(record.get("fiscal_year") or ""),
        record.get("section"),
        record.get("subsection"),
        object_type,
        record.get("source_evidence_id"),
    ]
    if object_type == "table":
        rows = record.get("rows") or []
        table_text = " ".join(" ".join(str(cell) for cell in row) for row in rows)
        cell_text = " ".join(_cell_search_text(cell) for cell in record.get("cells") or [])
        parts = [
            *common,
            record.get("table_id"),
            record.get("title"),
            " ".join(record.get("candidate_periods") or []),
            table_text,
            cell_text,
            record.get("text_before"),
            record.get("text_after"),
            _alias_text(table_text),
        ]
    elif object_type == "metric":
        alias_source = " ".join(
            str(part)
            for part in [
                record.get("metric_name"),
                record.get("row_label"),
                record.get("column_label"),
                record.get("context"),
            ]
            if part
        )
        parts = [
            *common,
            record.get("metric_name"),
            record.get("raw_value"),
            str(record.get("value") if record.get("value") is not None else ""),
            record.get("unit"),
            record.get("period"),
            record.get("period_role"),
            record.get("segment"),
            record.get("row_label"),
            record.get("column_label"),
            record.get("context"),
            record.get("extraction_method"),
            _alias_text(alias_source),
        ]
    elif object_type == "claim":
        parts = [
            *common,
            record.get("claim_text"),
            record.get("claim_type"),
            record.get("polarity"),
            " ".join(record.get("entities") or []),
            " ".join(record.get("metrics_mentioned") or []),
            record.get("context"),
            record.get("extraction_method"),
        ]
    else:
        parts = common
    return "\n".join(str(part) for part in parts if part)


def structured_object_preview(record: dict[str, Any], max_chars: int = 280) -> str:
    if record.get("preview"):
        text = " ".join(str(record.get("preview") or "").split())
        return text[:max_chars] + ("..." if len(text) > max_chars else "")
    object_type = record.get("object_type")
    if object_type == "metric":
        parts = [
            record.get("metric_name"),
            record.get("segment"),
            record.get("period"),
            record.get("raw_value"),
            record.get("unit"),
        ]
        text = " | ".join(str(part) for part in parts if part is not None)
    elif object_type == "claim":
        text = str(record.get("claim_text") or "")
    elif object_type == "table":
        text = str(record.get("title") or "")
        if not text:
            rows = record.get("rows") or []
            text = " ".join(" | ".join(str(cell) for cell in row) for row in rows[:3])
    else:
        text = str(record.get("object_id") or "")
    text = " ".join(text.split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _cell_search_text(cell: dict[str, Any]) -> str:
    parts = [
        cell.get("row_label"),
        cell.get("column_label"),
        cell.get("period"),
        cell.get("period_role"),
        cell.get("raw_value"),
        str(cell.get("value") if cell.get("value") is not None else ""),
        cell.get("unit"),
        cell.get("cell_kind"),
        cell.get("active_group"),
    ]
    return " ".join(str(part) for part in parts if part)


def _alias_text(text: str) -> str:
    lower = text.lower()
    aliases = []
    alias_groups = {
        "operating income": (
            "income from operations",
            "total income from operations",
            "operating profit",
        ),
        "income from operations": ("operating income", "operating profit"),
        "net sales": ("revenue", "revenues"),
        "revenue": ("net sales", "sales"),
        "cost of revenue": ("cost of revenues", "costs and expenses", "cost of sales"),
        "headcount": ("employees", "employee headcount", "number of employees"),
        "capital expenditures": ("capex", "purchases of property and equipment", "property and equipment"),
        "operating cash flow": ("net cash provided by operating activities", "cash provided by operating activities"),
        "free cash flow": ("operating cash flow minus capital expenditures",),
        "advertising revenues": ("advertising revenue", "google advertising", "family of apps advertising"),
        "net interest income": ("nii", "taxable-equivalent net interest income", "interest income less interest expense"),
        "net interest margin": ("nim", "net yield on interest-earning assets"),
        "provision for credit losses": (
            "credit loss provision",
            "provision for loan losses",
            "provision for loan lease and other losses",
        ),
        "allowance for credit losses": ("allowance for loan losses", "allowance for expected credit losses"),
        "asset quality": ("credit quality", "nonperforming assets", "nonperforming loans", "net charge-offs"),
        "credit risk": ("credit losses", "allowance for credit losses", "net charge-offs", "delinquencies"),
        "net charge-offs": ("net charge offs", "charge-offs", "charge offs"),
        "nonperforming assets": ("non-performing assets", "nonaccrual assets"),
        "nonperforming loans": ("non-performing loans", "nonaccrual loans"),
        "deposits": ("average deposits", "total deposits", "deposit balances"),
        "loans": ("average loans", "total loans", "loan portfolio"),
        "cet1": ("common equity tier 1", "tier 1 capital", "capital ratio"),
    }
    for canonical, terms in alias_groups.items():
        if canonical in lower or any(term in lower for term in terms):
            aliases.append(canonical)
            aliases.extend(terms)
    return " ".join(dict.fromkeys(aliases))
