from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import EvidenceObject
from .structured_objects import ClaimObject, MetricObject, TableObject


TABLE_PATTERN = re.compile(
    r"\[TABLE_START id=(?P<table_id>[^\s]+) rows=(?P<rows>\d+)\]\n"
    r"(?P<body>.*?)\n\[TABLE_END\]",
    re.DOTALL,
)
YEAR_PATTERN = re.compile(r"(?:20\d{2}|19\d{2}|Jan\s+\d{1,2},\s+20\d{2}|Nov\s+\d{1,2},\s+20\d{2})")
NUMBER_PATTERN = re.compile(r"(?P<prefix>[$(]?\s*)(?P<number>-?\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>%|million|billion)?\)?", re.I)
MONTH_PATTERN = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

CLAIM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "revenue_visibility": ("remaining performance obligations", "rpo", "deferred revenue", "visibility", "recognized as revenue"),
    "accounting_policy": ("recognize revenue", "recognized ratably", "performance obligation", "contract", "subscription revenue"),
    "risk": ("risk", "could", "may", "adversely", "uncertain", "volatility", "depend", "depends", "dependent", "dependence", "dependency", "dependencies"),
    "strategy": ("strategy", "invest", "investment", "focus", "plan", "continue to", "partnership", "initiative"),
    "demand": ("demand", "customer", "customers", "consumption", "usage", "growth", "adoption"),
    "cost_pressure": ("cost", "costs", "expense", "expenses", "margin", "margins", "depreciation", "energy", "offset", "pressure"),
    "capex": ("capital expenditure", "property and equipment", "infrastructure", "datacenter", "data center"),
}

POSITIVE_WORDS = ("increased", "grew", "growth", "strong", "improved", "higher", "benefit")
NEGATIVE_WORDS = ("risk", "decrease", "decline", "offset", "pressure", "adversely", "uncertain", "loss")

BANKING_IXBRL_FACTS: dict[str, tuple[str, str]] = {
    "us-gaap:InterestIncomeExpenseNet": ("net_interest_income", "Net interest income"),
    "us-gaap:ProvisionForLoanLeaseAndOtherLosses": ("provision_for_credit_losses", "Provision for credit losses"),
    "us-gaap:FinancingReceivableExcludingAccruedInterestCreditLossExpenseReversal": (
        "provision_for_credit_losses",
        "Provision for credit losses",
    ),
    "us-gaap:FinancingReceivableExcludingAccruedInterestAllowanceForCreditLossWriteoffAfterRecovery": (
        "net_charge_offs",
        "Net charge-offs",
    ),
    "us-gaap:FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest": (
        "allowance_for_credit_losses",
        "Allowance for credit losses",
    ),
    "us-gaap:FinancingReceivableExcludingAccruedInterestNonaccrual": (
        "nonperforming_loans",
        "Nonaccrual loans",
    ),
    "jpm:FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLossesNetOfDeferredIncome": (
        "loans",
        "Loans",
    ),
    "us-gaap:FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss": (
        "loans",
        "Loans",
    ),
    "us-gaap:Deposits": ("deposits", "Deposits"),
    "us-gaap:Assets": ("total_assets", "Total assets"),
    "jpm:CommonEquityTier1CapitaltoRiskWeightedAssets": (
        "capital_ratio",
        "Common Equity Tier 1 capital ratio",
    ),
}


@dataclass(frozen=True)
class StructuredExtractionResult:
    tables: list[TableObject]
    metrics: list[MetricObject]
    claims: list[ClaimObject]


def extract_structured_objects(evidence: EvidenceObject) -> StructuredExtractionResult:
    tables = extract_tables(evidence)
    metrics: list[MetricObject] = []
    for table in tables:
        metrics.extend(extract_table_metrics(evidence, table))
    metrics.extend(extract_sentence_metrics(evidence))
    metrics.extend(extract_banking_ixbrl_metrics(evidence))
    claims = extract_claims(evidence)
    return StructuredExtractionResult(tables=tables, metrics=metrics, claims=claims)


def extract_tables(evidence: EvidenceObject) -> list[TableObject]:
    tables: list[TableObject] = []
    for table_index, match in enumerate(TABLE_PATTERN.finditer(evidence.text), start=1):
        rows = _parse_table_rows(match.group("body"))
        if not rows:
            continue
        table_id = match.group("table_id")
        context_before = _context_before(evidence.text, match.start())
        context_after = _context_after(evidence.text, match.end())
        candidate_periods = _extract_periods(match.group("body")) or _extract_nearest_context_periods(context_before)
        cells = _table_cells(
            rows,
            candidate_periods,
            context_before,
            context_after,
            form_type=evidence.metadata.get("form_type") or evidence.source_type,
            period_type=evidence.period_type or evidence.metadata.get("period_type"),
            duration_months=evidence.duration_months or evidence.metadata.get("duration_months"),
            reporting_currency=evidence.metadata.get("reporting_currency"),
        )
        object_id = _object_id(evidence.evidence_id, "TABLE", table_index)
        tables.append(
            TableObject(
                object_id=object_id,
                source_evidence_id=evidence.evidence_id,
                ticker=evidence.ticker,
                fiscal_year=evidence.fiscal_year,
                **_source_object_fields(evidence),
                **_period_object_fields(evidence),
                section=evidence.section,
                subsection=evidence.subsection,
                source_url=evidence.source_url,
                local_path=evidence.local_path,
                table_id=str(table_id),
                title=_infer_table_title(context_before),
                row_count=len(rows),
                column_count=max(len(row) for row in rows),
                rows=rows,
                cells=cells,
                candidate_periods=candidate_periods,
                text_before=context_before,
                text_after=context_after,
                metadata={
                    "source_table_id": table_id,
                    "source_table_rows": int(match.group("rows")),
                    "table_index": table_index,
                    "block_id": evidence.metadata.get("block_id"),
                    "item_code": evidence.metadata.get("item_code"),
                    "form_type": evidence.metadata.get("form_type") or evidence.source_type,
                    "source_tier": evidence.source_tier,
                    "reporting_currency": evidence.metadata.get("reporting_currency"),
                },
            )
        )
    return tables


def extract_table_metrics(evidence: EvidenceObject, table: TableObject) -> list[MetricObject]:
    metrics: list[MetricObject] = []
    header_index = _table_header_index(table.rows)
    header = table.rows[header_index] if header_index is not None else []
    data_start = _table_data_start_index(table.rows, header_index)
    data_rows = table.rows[data_start:]
    active_group: str | None = None
    row_offset = data_start + 1
    for row_index, row in enumerate(data_rows, start=row_offset):
        if not row:
            continue
        row_label = _clean_metric_name(row[0])
        if _looks_like_group_header(row):
            active_group = row_label
            continue
        if not row_label or _looks_like_header(row_label):
            continue
        numeric_cells = _row_numeric_cells(
            row,
            header,
            table,
            row_index=row_index,
        )
        if not numeric_cells:
            continue
        metric_name = _infer_table_metric_name(row_label, active_group, table.title)
        segment = _infer_table_segment(row_label, metric_name, evidence.subsection)
        context = _table_metric_context(table, active_group)
        for metric_index, cell in enumerate(numeric_cells, start=1):
            value, unit = _parse_number(cell["raw_value"])
            metrics.append(
                MetricObject(
                    object_id=_object_id(
                        evidence.evidence_id,
                        "METRIC_TABLE",
                        table.metadata.get("table_index", 0),
                        row_index,
                        metric_index,
                    ),
                    source_evidence_id=evidence.evidence_id,
                    ticker=evidence.ticker,
                    fiscal_year=evidence.fiscal_year,
                    **_source_object_fields(evidence),
                    **_period_object_fields(evidence),
                    section=evidence.section,
                    subsection=evidence.subsection,
                    source_url=evidence.source_url,
                    local_path=evidence.local_path,
                    metric_name=metric_name,
                    raw_value=cell["raw_value"],
                    value=value,
                    unit=cell.get("unit") or unit,
                    period=cell.get("period"),
                    period_role=cell.get("period_role"),
                    segment=segment,
                    table_object_id=table.object_id,
                    row_label=row_label,
                    column_label=cell.get("column_label"),
                    context=context,
                    extraction_method="table_row_heuristic",
                    confidence=0.82 if cell.get("cell_kind") == "period_value" else 0.64,
                    metadata={
                        "table_object_id": table.object_id,
                        "source_table_id": table.table_id,
                        "table_cell_key": cell.get("cell_key"),
                        "row_index": row_index,
                        "column_index": cell.get("column_index"),
                        "logical_column_index": cell.get("logical_column_index"),
                        "cell_key": cell.get("cell_key"),
                        "cell_kind": cell.get("cell_kind"),
                        "period_role": cell.get("period_role"),
                        "block_id": evidence.metadata.get("block_id"),
                        "form_type": evidence.metadata.get("form_type") or evidence.source_type,
                        "source_tier": evidence.source_tier,
                    },
                )
            )
    return metrics


def extract_sentence_metrics(evidence: EvidenceObject) -> list[MetricObject]:
    metrics: list[MetricObject] = []
    for sent_index, sentence in enumerate(_sentences_without_tables(evidence.text), start=1):
        if not _metric_sentence_candidate(sentence):
            continue
        for match_index, match in enumerate(NUMBER_PATTERN.finditer(sentence), start=1):
            raw = match.group(0).strip()
            if _is_standalone_year(raw):
                continue
            if not _should_keep_sentence_number(sentence, match):
                continue
            value, unit = _parse_number(raw)
            if value is None:
                continue
            metrics.append(
                MetricObject(
                    object_id=_object_id(evidence.evidence_id, "METRIC_SENT", sent_index, match_index),
                    source_evidence_id=evidence.evidence_id,
                    ticker=evidence.ticker,
                    fiscal_year=evidence.fiscal_year,
                    **_source_object_fields(evidence),
                    **_period_object_fields(evidence),
                    section=evidence.section,
                    subsection=evidence.subsection,
                    source_url=evidence.source_url,
                    local_path=evidence.local_path,
                    metric_name=_infer_sentence_metric_name(sentence, raw),
                    raw_value=raw,
                    value=value,
                    unit=unit,
                    period=_extract_period(sentence) or (str(evidence.fiscal_year) if evidence.fiscal_year else None),
                    period_role=_period_role_for_sentence(evidence, sentence),
                    segment=_infer_segment(sentence, None, evidence.subsection),
                    context=_trim(sentence, 500),
                    extraction_method="sentence_heuristic",
                    confidence=0.45,
                    metadata={
                        "sentence_index": sent_index,
                        "match_index": match_index,
                        "period_role": _period_role_for_sentence(evidence, sentence),
                        "block_id": evidence.metadata.get("block_id"),
                        "form_type": evidence.metadata.get("form_type") or evidence.source_type,
                        "source_tier": evidence.source_tier,
                    },
                )
            )
    return metrics


def extract_banking_ixbrl_metrics(evidence: EvidenceObject) -> list[MetricObject]:
    if not _is_banking_ixbrl_anchor(evidence):
        return []
    filing_path = _resolve_local_filing_path(evidence)
    if filing_path is None:
        return []
    raw_html = filing_path.read_text(encoding="utf-8", errors="ignore")
    contexts = _extract_ixbrl_contexts(raw_html)
    if not contexts:
        return []

    metrics: list[MetricObject] = []
    seen: set[tuple[str, str, str, str]] = set()
    fact_pattern = re.compile(r"<ix:nonFraction\b(?P<attrs>[^>]*)>(?P<body>.*?)</ix:nonFraction>", re.I | re.S)
    for match_index, match in enumerate(fact_pattern.finditer(raw_html), start=1):
        attrs = _parse_html_attrs(match.group("attrs"))
        fact_name = attrs.get("name")
        if fact_name not in BANKING_IXBRL_FACTS:
            continue
        context_ref = attrs.get("contextref")
        context = contexts.get(str(context_ref or ""))
        if context is None or context.get("year") is None:
            continue
        family, metric_name = BANKING_IXBRL_FACTS[fact_name]
        members = list(context.get("members") or [])
        if members and family != "capital_ratio":
            continue
        raw_value = _clean_ixbrl_value(match.group("body"))
        if not raw_value or raw_value in {"—", "-", "–", "n/a", "N/A"}:
            continue
        value = _parse_ixbrl_float(raw_value)
        if value is None:
            continue
        if attrs.get("sign") == "-":
            value = -value
        unit = _ixbrl_unit(attrs)
        period = str(context["year"])
        segment = _ixbrl_segment_label(members)
        key = (fact_name, period, raw_value, segment or "")
        if key in seen:
            continue
        seen.add(key)
        object_id = _object_id(evidence.evidence_id, "METRIC_BANK_IXBRL", match_index)
        metrics.append(
            MetricObject(
                object_id=object_id,
                source_evidence_id=evidence.evidence_id,
                ticker=evidence.ticker,
                fiscal_year=evidence.fiscal_year,
                **_source_object_fields(evidence),
                **_period_object_fields(evidence),
                section=evidence.section,
                subsection=evidence.subsection,
                source_url=evidence.source_url,
                local_path=str(filing_path),
                metric_name=metric_name,
                raw_value=raw_value,
                value=value,
                unit=unit,
                period=period,
                period_role=_period_role_for_ixbrl_context(context, evidence),
                segment=segment,
                table_object_id=None,
                row_label=metric_name,
                column_label=period,
                context=_banking_ixbrl_context_text(fact_name, family, context, members),
                extraction_method="banking_ixbrl_fact_heuristic",
                confidence=0.9 if not members else 0.78,
                metadata={
                    "metric_family": family,
                    "ixbrl_fact_name": fact_name,
                    "ixbrl_context_ref": context_ref,
                    "ixbrl_unit_ref": attrs.get("unitref"),
                    "ixbrl_scale": attrs.get("scale"),
                    "ixbrl_decimals": attrs.get("decimals"),
                    "ixbrl_context_period": context.get("period"),
                    "period_role": _period_role_for_ixbrl_context(context, evidence),
                    "ixbrl_context_members": members,
                    "is_banking_metric": True,
                    "block_id": evidence.metadata.get("block_id"),
                    "item_code": evidence.metadata.get("item_code"),
                    "form_type": evidence.metadata.get("form_type") or evidence.source_type,
                    "source_tier": evidence.source_tier,
                },
            )
        )
    return metrics


def extract_claims(evidence: EvidenceObject) -> list[ClaimObject]:
    claims: list[ClaimObject] = []
    for sentence_index, sentence in enumerate(_sentences_without_tables(evidence.text), start=1):
        claim_type = _claim_type(sentence)
        if claim_type is None:
            continue
        claims.append(
            ClaimObject(
                object_id=_object_id(evidence.evidence_id, "CLAIM", sentence_index),
                source_evidence_id=evidence.evidence_id,
                ticker=evidence.ticker,
                fiscal_year=evidence.fiscal_year,
                **_source_object_fields(evidence),
                **_period_object_fields(evidence),
                section=evidence.section,
                subsection=evidence.subsection,
                source_url=evidence.source_url,
                local_path=evidence.local_path,
                claim_text=_trim(sentence, 900),
                claim_type=claim_type,
                polarity=_claim_polarity(sentence),
                entities=_extract_entities(sentence, evidence.ticker),
                metrics_mentioned=_extract_metric_mentions(sentence),
                context=evidence.subsection,
                extraction_method="sentence_heuristic",
                confidence=0.55 if claim_type != "other" else 0.35,
                metadata={
                    "sentence_index": sentence_index,
                    "block_id": evidence.metadata.get("block_id"),
                    "item_code": evidence.metadata.get("item_code"),
                    "form_type": evidence.metadata.get("form_type") or evidence.source_type,
                    "source_tier": evidence.source_tier,
                },
            )
        )
    return claims


def _is_banking_ixbrl_anchor(evidence: EvidenceObject) -> bool:
    if str(evidence.source_type or "").upper() != "10-K":
        return False
    item_code = str(evidence.metadata.get("item_code") or "").upper()
    if item_code != "7":
        return False
    category = str(evidence.metadata.get("category") or "").lower()
    ticker = str(evidence.ticker or "").upper()
    return "bank" in category or ticker in {"JPM"}


def _period_object_fields(evidence: EvidenceObject) -> dict[str, Any]:
    return {
        "period_end": evidence.period_end or evidence.metadata.get("period_end"),
        "period_type": evidence.period_type or evidence.metadata.get("period_type"),
        "duration_months": evidence.duration_months or evidence.metadata.get("duration_months"),
        "fiscal_period": evidence.fiscal_period or evidence.metadata.get("fiscal_period"),
    }


def _period_role_for_sentence(evidence: EvidenceObject, sentence: str) -> str | None:
    return _period_role_for_texts(
        sentence,
        form_type=evidence.metadata.get("form_type") or evidence.source_type,
        period_type=evidence.period_type or evidence.metadata.get("period_type"),
        duration_months=evidence.duration_months or evidence.metadata.get("duration_months"),
    )


def _period_role_for_ixbrl_context(context: dict[str, Any], evidence: EvidenceObject) -> str | None:
    if str(context.get("period") or "").lower() == "instant":
        return "instant"
    start = str(context.get("start") or "")
    end = str(context.get("end") or "")
    duration_months = _duration_months_from_dates(start, end)
    if duration_months is not None:
        if duration_months <= 4:
            return "qtd"
        if duration_months <= 10:
            return "ytd"
        if duration_months <= 13:
            return "annual"
    return _period_role_for_texts(
        evidence.subsection,
        evidence.section,
        form_type=evidence.metadata.get("form_type") or evidence.source_type,
        period_type=evidence.period_type or evidence.metadata.get("period_type"),
        duration_months=evidence.duration_months or evidence.metadata.get("duration_months"),
    )


def _period_role_for_table_cell(table: TableObject, column_label: str | None, row_label: str | None) -> str | None:
    return _period_role_for_table_cell_parts(
        form_type=table.form_type or table.source_type,
        period_type=table.period_type,
        duration_months=table.duration_months,
        column_label=column_label,
        row_label=row_label,
        active_group=None,
        title=table.title,
        context_before=table.text_before,
        context_after=table.text_after,
    )


def _period_role_for_table_cell_parts(
    *,
    form_type: str | None,
    period_type: str | None,
    duration_months: Any,
    column_label: str | None,
    row_label: str | None,
    active_group: str | None,
    title: str | None,
    context_before: str | None,
    context_after: str | None,
) -> str | None:
    # A row can state the economic time role more precisely than a compact
    # period column.  For example, "End-quarter cash" is an instant even when
    # it sits under a "Q2 2026" column, while sales under the same column are
    # quarter-to-date.  Preserve that distinction before consulting the
    # column shorthand.
    row_role = _period_role_from_text(row_label)
    if row_role:
        return row_role
    column_role = _period_role_from_text(column_label)
    if column_role:
        return column_role
    context_role = _period_role_for_texts(
        row_label,
        active_group,
        title,
        context_before,
        context_after,
        form_type=form_type,
        period_type=period_type,
        duration_months=duration_months,
    )
    return context_role


def _period_role_for_texts(
    *texts: Any,
    form_type: Any = None,
    period_type: Any = None,
    duration_months: Any = None,
) -> str | None:
    for text in texts:
        role = _period_role_from_text(text)
        if role:
            return role
    form = str(form_type or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")
    if form == "10-K" or str(period_type or "").lower() == "annual" or _int_or_none(duration_months) == 12:
        return "annual"
    return None


def _period_role_from_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").lower()).strip()
    if not text:
        return None
    role_patterns = {
        "ttm": (
            r"\bttm\b",
            r"trailing\s+twelve\s+months",
            r"twelve\s+months\s+ended",
            r"12\s+months\s+ended",
        ),
        "ytd": (
            r"\bytd\b",
            r"year[-\s]?to[-\s]?date",
            r"six\s+months\s+ended",
            r"nine\s+months\s+ended",
            r"6\s+months\s+ended",
            r"9\s+months\s+ended",
        ),
        "qtd": (
            r"three\s+months\s+ended",
            r"3\s+months\s+ended",
            r"quarter\s+ended",
            r"for\s+the\s+quarter",
            r"\bquarterly\b",
            r"\b(?:q[1-4]\s*(?:fy\s*)?(?:19|20)\d{2}|(?:19|20)\d{2}\s*q[1-4])\b",
            r"\b(?:first|second|third|fourth)\s+(?:fiscal\s+)?quarter(?:\s+of)?\s+(?:19|20)\d{2}\b",
        ),
        "annual": (
            r"year\s+ended",
            r"fiscal\s+year",
            r"for\s+the\s+year",
            r"\bannual\b",
        ),
        "instant": (
            rf"as\s+of\s+{MONTH_PATTERN}",
            rf"^{MONTH_PATTERN}\s+\d{{1,2}},\s+(?:19|20)\d{{2}}$",
            r"\bat\s+(?:the\s+)?(?:period|quarter|year)[-\s]?end\b",
            r"\bend[-\s]?quarter\b",
            r"\bquarter[-\s]?end\b",
            r"\b(?:ending|closing)\s+balance\b",
            r"\b(?:gross|net)\s+carrying\s+amount\b",
            r"\baccumulated\s+(?:amortization|depreciation)\b",
            r"\b(?:weighted[-\s]?average\s+)?remaining\s+useful\s+lives?\b",
        ),
    }
    matches = {
        role
        for role, patterns in role_patterns.items()
        if any(re.search(pattern, text, flags=re.I) for pattern in patterns)
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


def _duration_months_from_dates(start: str, end: str) -> int | None:
    match_start = re.match(r"^(\d{4})-(\d{2})-\d{2}$", start)
    match_end = re.match(r"^(\d{4})-(\d{2})-\d{2}$", end)
    if not match_start or not match_end:
        return None
    start_month = int(match_start.group(1)) * 12 + int(match_start.group(2))
    end_month = int(match_end.group(1)) * 12 + int(match_end.group(2))
    return max(1, end_month - start_month + 1)


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _source_object_fields(evidence: EvidenceObject) -> dict[str, Any]:
    form_type = str(evidence.metadata.get("form_type") or evidence.source_type or "").upper().strip()
    return {
        "source_type": evidence.source_type,
        "form_type": form_type,
        "source_tier": evidence.source_tier or evidence.metadata.get("source_tier"),
    }


def _resolve_local_filing_path(evidence: EvidenceObject) -> Path | None:
    candidates: list[Path] = []
    local_path = str(evidence.local_path or "")
    if local_path:
        candidates.append(Path(local_path))
    repo_root = Path(__file__).resolve().parents[2]
    ticker = str(evidence.ticker or "").upper()
    year = str(evidence.fiscal_year or "")
    form_type = str(evidence.metadata.get("form_type") or evidence.source_type or "10-K")
    category_slug = str(evidence.metadata.get("category_slug") or "")
    primary_document = str(evidence.metadata.get("primary_document") or "")
    file_names = [primary_document, f"{form_type}.html", "10-K.html"]
    file_names = [name for name in dict.fromkeys(file_names) if name]
    folders = [
        repo_root / "data" / "raw_private" / "sec" / ticker / year,
        repo_root / "data" / "raw_private" / "sec" / year / "uncategorized" / ticker,
    ]
    if category_slug:
        folders.append(repo_root / "data" / "raw_private" / "sec" / year / category_slug / ticker)
    for folder in folders:
        for file_name in file_names:
            candidates.append(folder / file_name)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _parse_html_attrs(attr_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in re.finditer(r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*\"([^\"]*)\"", attr_text or ""):
        attrs[match.group(1).lower()] = html.unescape(match.group(2))
    return attrs


def _extract_ixbrl_contexts(raw_html: str) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    pattern = re.compile(r"<xbrli:context\b(?P<attrs>[^>]*)>(?P<body>.*?)</xbrli:context>", re.I | re.S)
    for match in pattern.finditer(raw_html):
        attrs = _parse_html_attrs(match.group("attrs"))
        context_id = attrs.get("id")
        if not context_id:
            continue
        body = match.group("body")
        start = _first_xml_text(body, "xbrli:startDate")
        end = _first_xml_text(body, "xbrli:endDate") or _first_xml_text(body, "xbrli:instant")
        year = _year_from_date(end)
        members = [
            _strip_namespace(html.unescape(member))
            for member in re.findall(r"<xbrldi:explicitMember\b[^>]*>(.*?)</xbrldi:explicitMember>", body, re.I | re.S)
        ]
        contexts[context_id] = {
            "id": context_id,
            "period": "instant" if _first_xml_text(body, "xbrli:instant") else "duration",
            "start": start,
            "end": end,
            "year": year,
            "members": [member for member in members if member],
        }
    return contexts


def _first_xml_text(text: str, tag: str) -> str | None:
    match = re.search(rf"<{re.escape(tag)}\b[^>]*>(.*?)</{re.escape(tag)}>", text or "", re.I | re.S)
    if not match:
        return None
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


def _year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(20\d{2}|19\d{2})\b", value)
    return int(match.group(1)) if match else None


def _strip_namespace(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "").strip()
    return value.split(":", 1)[-1] if ":" in value else value


def _clean_ixbrl_value(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", value or "")
    cleaned = html.unescape(cleaned).replace("\xa0", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _parse_ixbrl_float(value: str) -> float | None:
    cleaned = re.sub(r"[$,%()]", "", value or "").replace(",", "").strip()
    if not cleaned or cleaned in {"—", "-", "–"}:
        return None
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    if "(" in value and ")" in value:
        parsed = -parsed
    return parsed


def _ixbrl_unit(attrs: dict[str, str]) -> str:
    unit_ref = str(attrs.get("unitref") or "").lower()
    scale = str(attrs.get("scale") or "")
    if unit_ref == "usd":
        if scale == "9":
            return "usd_billions"
        return "usd_millions" if scale == "6" else "usd"
    if unit_ref in {"number", "pure"} and scale == "-2":
        return "percent"
    return "percent" if unit_ref in {"number", "pure"} else unit_ref


def _ixbrl_segment_label(members: list[str]) -> str | None:
    if not members:
        return None
    return "; ".join(members[:4])


def _banking_ixbrl_context_text(
    fact_name: str,
    family: str,
    context: dict[str, Any],
    members: list[str],
) -> str:
    parts = [
        "banking ixbrl fact",
        family,
        fact_name,
        str(context.get("period") or ""),
        str(context.get("start") or ""),
        str(context.get("end") or ""),
        " ".join(members),
    ]
    return " ".join(part for part in parts if part)


def _parse_table_rows(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in body.splitlines():
        cells = []
        for raw_cell in line.split("|"):
            cell = _clean_cell(raw_cell)
            if not cell:
                continue
            if cell == ")" and cells:
                cells[-1] = f"{cells[-1]})"
                continue
            cells.append(cell)
        if cells:
            rows.append(cells)
    return rows


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _context_before(text: str, index: int, max_chars: int = 500) -> str:
    return _trim(text[max(0, index - max_chars) : index], max_chars)


def _context_after(text: str, index: int, max_chars: int = 300) -> str:
    return _trim(text[index : index + max_chars], max_chars)


def _infer_table_title(context_before: str | None) -> str | None:
    if not context_before:
        return None
    lines = [line.strip() for line in context_before.splitlines() if line.strip()]
    for line in reversed(lines):
        if "[TABLE_" not in line and "|" not in line and len(line) <= 180:
            return line
    return lines[-1] if lines else None


def _extract_periods(text: str) -> list[str]:
    periods = []
    pattern = re.compile(
        rf"\bQ[1-4]\s+(?:20\d{{2}}|19\d{{2}})\b|{YEAR_PATTERN.pattern}",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        value = match.group(0)
        if value not in periods:
            periods.append(value)
    return periods


def _extract_nearest_context_periods(context_before: str | None) -> list[str]:
    if not context_before:
        return []
    lines = [line.strip() for line in context_before.splitlines() if line.strip()]
    for line in reversed(lines):
        if "|" in line:
            periods = _extract_periods(line)
            if len(periods) >= 2:
                return periods
    return _extract_periods(context_before)


def _table_header(rows: list[list[str]]) -> list[str]:
    header_index = _table_header_index(rows)
    return rows[header_index] if header_index is not None else []


def _table_header_index(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows[:5]):
        if _is_table_unit_row(row):
            continue
        if len(_extract_periods(" ".join(row))) >= 2:
            return index
        if (
            len(row) > 2
            and _is_table_unit_row([row[0]])
            and sum(bool(str(cell or "").strip()) for cell in row[1:]) >= 2
        ):
            # Equity rollforwards often have descriptor-only columns beneath a
            # unit marker and encode the year in balance rows, not the header.
            # This is still a real header; treating the first data row as the
            # coordinate source shifts values onto arbitrary candidate years.
            return index
        if len(row) > 1 and _looks_like_header(row[0]) and any(_numeric_column_hint(cell) for cell in row[1:]):
            return index
    return None


def _row_numeric_cells(
    row: list[str],
    header: list[str],
    table: TableObject,
    *,
    row_index: int | None = None,
) -> list[dict[str, Any]]:
    table_unit = _infer_table_unit(table)
    table_unit_context = _table_unit_context(
        rows=table.rows,
        context_before=" ".join(value for value in [table.title, table.text_before] if value),
        context_after=table.text_after,
    )
    logical_values = _logical_value_cells(row)
    header_index = _table_header_index(table.rows)
    expanded_labels = _logical_column_labels_for_rows(
        table.rows,
        header_index,
        table.candidate_periods,
        len(logical_values),
    )
    rollforward_period = _rollforward_period_for_row(
        table.rows,
        None if row_index is None else row_index - 1,
    )
    numeric_values = []
    for logical_index, cell in enumerate(logical_values):
        raw = str(cell["raw_value"])
        if not _looks_like_numeric_table_cell(raw):
            continue
        value, parsed_unit = _parse_number(raw)
        if value is None or _is_standalone_year(raw):
            continue
        column_label = _logical_column_label(
            header,
            table.candidate_periods,
            logical_index,
            len(logical_values),
            expanded_labels=expanded_labels,
        )
        period = _period_for_column_label(column_label)
        if period is None and not _is_change_column(column_label):
            if rollforward_period:
                period = rollforward_period
            else:
                periods = table.candidate_periods
                period = (
                    _extract_period(periods[logical_index]) or periods[logical_index]
                    if logical_index < len(periods)
                    else None
                )
        numeric_values.append(
            {
                "raw_value": raw,
                "column_index": cell["column_index"],
                "logical_column_index": logical_index,
                "parsed_unit": parsed_unit,
                "period": period,
                "column_label": column_label,
                "period_role": _period_role_for_table_cell(
                    column_label=column_label,
                    row_label=row[0] if row else "",
                    table=table,
                ),
                "unit": _infer_cell_unit(raw, column_label, table_unit, row_label=row[0] if row else "", table_context=table_unit_context),
                "cell_kind": _cell_kind(column_label),
            }
        )
    row_key = _safe_cell_key(row[0] if row else "row")
    for item in numeric_values:
        col_key = _safe_cell_key(item.get("column_label") or f"col_{item['logical_column_index'] + 1}")
        item["cell_key"] = f"{row_key}__{col_key}"
    return numeric_values


def _table_cells(
    rows: list[list[str]],
    candidate_periods: list[str],
    context_before: str | None,
    context_after: str | None,
    *,
    form_type: str | None = None,
    period_type: str | None = None,
    duration_months: int | None = None,
    reporting_currency: str | None = None,
) -> list[dict[str, Any]]:
    header_index = _table_header_index(rows)
    header = rows[header_index] if header_index is not None else []
    data_start = _table_data_start_index(rows, header_index)
    data_rows = rows[data_start:]
    table_unit = _infer_table_unit_from_values(
        rows=rows,
        context_before=context_before,
        context_after=context_after,
        reporting_currency=reporting_currency,
    )
    table_unit_context = _table_unit_context(rows=rows, context_before=context_before, context_after=context_after)
    cells = []
    active_group: str | None = None
    row_offset = data_start + 1
    for row_index, row in enumerate(data_rows, start=row_offset):
        if not row:
            continue
        row_label = _clean_metric_name(row[0])
        if _looks_like_group_header(row):
            active_group = row_label
            continue
        if not row_label or _looks_like_header(row_label) or _is_table_unit_row(row):
            continue
        logical_values = _logical_value_cells(row)
        expanded_labels = _logical_column_labels_for_rows(rows, header_index, candidate_periods, len(logical_values))
        rollforward_period = _rollforward_period_for_row(rows, row_index - 1)
        for logical_index, cell in enumerate(logical_values):
            raw = str(cell["raw_value"])
            if not _looks_like_numeric_table_cell(raw):
                continue
            value, parsed_unit = _parse_number(raw)
            if value is None or _is_standalone_year(raw):
                continue
            column_label = _logical_column_label(
                header,
                candidate_periods,
                logical_index,
                len(logical_values),
                expanded_labels=expanded_labels,
            )
            period = _period_for_column_label(column_label)
            if period is None and not _is_change_column(column_label):
                if rollforward_period:
                    period = rollforward_period
                elif logical_index < len(candidate_periods):
                    period = _extract_period(candidate_periods[logical_index]) or candidate_periods[logical_index]
            unit = _infer_cell_unit(raw, column_label, table_unit, row_label=row_label, table_context=table_unit_context) or parsed_unit
            period_role = _period_role_for_table_cell_parts(
                form_type=form_type,
                period_type=period_type,
                duration_months=duration_months,
                column_label=column_label,
                row_label=row_label,
                active_group=active_group,
                title=_infer_table_title(context_before),
                context_before=context_before,
                context_after=context_after,
            )
            cells.append(
                {
                    "cell_key": f"{_safe_cell_key(row_label)}__{_safe_cell_key(column_label or f'col_{logical_index + 1}')}",
                    "row_index": row_index,
                    "column_index": cell["column_index"],
                    "logical_column_index": logical_index,
                    "row_label": row_label,
                    "column_label": column_label,
                    "period": period,
                    "period_role": period_role,
                    "raw_value": raw,
                    "value": value,
                    "unit": unit,
                    "cell_kind": _cell_kind(column_label),
                    "active_group": active_group.rstrip(":") if active_group else None,
                }
            )
    return cells


def _logical_value_cells(row: list[str]) -> list[dict[str, Any]]:
    values = row[1:]
    cells = []
    index = 0
    while index < len(values):
        raw = values[index]
        source_col = index + 1
        if raw == "$" and index + 1 < len(values):
            cells.append({"raw_value": f"$ {values[index + 1]}", "column_index": source_col})
            index += 2
            continue
        if index + 1 < len(values) and values[index + 1] == "%":
            cells.append({"raw_value": f"{raw} %", "column_index": source_col})
            index += 2
            continue
        if raw not in {"$", "%"}:
            cells.append({"raw_value": raw, "column_index": source_col})
        index += 1
    return cells


def _rollforward_period_for_row(
    rows: list[list[str]],
    physical_row_index: int | None,
) -> str | None:
    if physical_row_index is None or not 0 <= physical_row_index < len(rows):
        return None
    balance_rows: list[tuple[int, str]] = []
    for index, candidate in enumerate(rows):
        label = str(candidate[0] if candidate else "").strip()
        if not re.search(r"\bbalances?\s+(?:as|at)\s+of\b", label, re.IGNORECASE):
            continue
        period = _extract_period(label)
        if period:
            balance_rows.append((index, period))
    if len(balance_rows) < 2:
        return None
    own = next(
        (period for index, period in balance_rows if index == physical_row_index),
        None,
    )
    if own:
        return own
    previous = [index for index, _ in balance_rows if index < physical_row_index]
    following = [
        (index, period)
        for index, period in balance_rows
        if index > physical_row_index
    ]
    if previous and following:
        return min(following, key=lambda item: item[0])[1]
    return None


def _logical_column_label(
    header: list[str],
    candidate_periods: list[str],
    logical_index: int,
    logical_count: int | None = None,
    *,
    expanded_labels: list[str] | None = None,
) -> str | None:
    expanded = expanded_labels or _expanded_logical_column_labels(header, candidate_periods, logical_count)
    if logical_index < len(expanded):
        return expanded[logical_index]
    if logical_index < len(header):
        return header[logical_index]
    if logical_index < len(candidate_periods):
        return candidate_periods[logical_index]
    return None


def _table_data_start_index(rows: list[list[str]], header_index: int | None) -> int:
    if header_index is None:
        return 0
    next_index = header_index + 1
    if (
        next_index < len(rows)
        and _header_has_period_role(rows[header_index])
        and _is_pure_year_header_row(rows[next_index])
    ):
        return next_index + 1
    if next_index < len(rows) and _is_column_descriptor_row(rows[next_index]):
        return next_index + 1
    return next_index


def _logical_column_labels_for_rows(
    rows: list[list[str]],
    header_index: int | None,
    candidate_periods: list[str],
    logical_count: int | None,
) -> list[str]:
    if header_index is None or not logical_count:
        return []
    header = rows[header_index]
    next_index = header_index + 1
    if next_index < len(rows):
        grouped = _expanded_year_group_descriptor_labels(
            header,
            rows[next_index],
            logical_count,
        )
        if grouped:
            return grouped
    if header_index > 0:
        grouped = _expanded_period_group_year_labels(rows[header_index - 1], header, logical_count)
        if grouped:
            return grouped
    expanded = _expanded_logical_column_labels(header, candidate_periods, logical_count)
    if expanded:
        return expanded
    if next_index < len(rows):
        grouped = _expanded_period_group_year_labels(header, rows[next_index], logical_count)
        if grouped:
            return grouped
    if len(candidate_periods) == logical_count:
        # Summary/ratio rows in a wider table often omit the intervening
        # Actual/Constant change columns and carry only one value per period.
        # Bind that compressed row directly to the table's ordered periods
        # instead of falling back to physical header positions such as the
        # table-unit cell.
        return list(candidate_periods)
    return []


def _is_column_descriptor_row(row: list[str]) -> bool:
    labels = [str(cell or "").strip().casefold() for cell in row if str(cell or "").strip()]
    if len(labels) < 2:
        return False
    descriptor_markers = (
        "amount",
        "interest rate",
        "date of issuance",
        "percentage",
        "percent",
        "units",
        "shares",
    )
    return sum(any(marker in label for marker in descriptor_markers) for label in labels) >= 2


def _expanded_year_group_descriptor_labels(
    year_header: list[str],
    descriptor_row: list[str],
    logical_count: int,
) -> list[str]:
    """Combine grouped years with a following row of repeated subcolumns.

    SEC debt tables commonly use ``2026 | 2025`` above
    ``Date of Issuance | Amount | Rate | Amount | Rate``.  Treating the two
    physical header rows independently assigns years from bond maturity text
    to cells.  This helper preserves the actual two-dimensional coordinate.
    """
    years = [_extract_period(cell) for cell in year_header]
    years = [year for year in years if year]
    if len(years) < 2 or not _is_column_descriptor_row(descriptor_row):
        return []
    descriptors = [
        str(cell or "").strip()
        for cell in descriptor_row
        if str(cell or "").strip() and not _is_table_unit_row([str(cell or "").strip()])
    ]
    if len(descriptors) != logical_count:
        return []
    leading = len(descriptors) % len(years)
    repeated_count = len(descriptors) - leading
    if repeated_count <= 0 or repeated_count % len(years) != 0:
        return []
    span = repeated_count // len(years)
    if span < 1:
        return []
    labels = descriptors[:leading]
    offset = leading
    for year_index, year in enumerate(years):
        group = descriptors[offset + year_index * span : offset + (year_index + 1) * span]
        labels.extend(f"{label} {year}" for label in group)
    return labels if len(labels) == logical_count else []


def _expanded_period_group_year_labels(
    group_header: list[str],
    year_header: list[str],
    logical_count: int | None,
) -> list[str]:
    if not logical_count or not _is_year_header_row(year_header):
        return []
    groups = [
        str(cell or "").strip()
        for cell in group_header
        if str(cell or "").strip()
        and not _is_table_unit_row([str(cell or "").strip()])
        and _period_role_from_text(cell)
    ]
    years = [_extract_period(cell) for cell in year_header]
    years = [year for year in years if year]
    if not groups or not years or len(years) != logical_count or len(years) % len(groups) != 0:
        return []
    span = len(years) // len(groups)
    labels: list[str] = []
    for group_index, group in enumerate(groups):
        for year in years[group_index * span : (group_index + 1) * span]:
            labels.append(f"{group} {year}")
    return labels if len(labels) == logical_count else []


def _header_has_period_role(row: list[str]) -> bool:
    return any(_period_role_from_text(cell) for cell in row)


def _is_year_header_row(row: list[str]) -> bool:
    cells = [
        str(cell or "").strip()
        for cell in row
        if str(cell or "").strip()
        and not _is_table_unit_row([str(cell or "").strip()])
    ]
    periods = [_extract_period(cell) for cell in cells]
    return (
        sum(bool(period) for period in periods) >= 2
        and all(period or _is_change_column(cell) for cell, period in zip(cells, periods, strict=True))
    )


def _is_pure_year_header_row(row: list[str]) -> bool:
    cells = [
        str(cell or "").strip()
        for cell in row
        if str(cell or "").strip()
        and not _is_table_unit_row([str(cell or "").strip()])
    ]
    periods = [_extract_period(cell) for cell in cells]
    return len(cells) >= 2 and all(periods)


def _expanded_logical_column_labels(
    header: list[str],
    candidate_periods: list[str],
    logical_count: int | None,
) -> list[str]:
    if not header or not logical_count:
        return []
    labels = [str(item or "").strip() for item in header if str(item or "").strip()]
    if labels and _is_table_unit_row([labels[0]]):
        labels = labels[1:]
    elif len(labels) == logical_count + 1 and not _extract_period(labels[0]):
        labels = labels[1:]
    # A leading descriptor column (for example ``Useful Life``) is a real
    # logical coordinate, even though it is neither a period nor a change
    # column.  Once the optional table-unit cell has been removed, an exact
    # header/value cardinality match is the strongest available coordinate
    # signal.  Rejecting that match used to shift every following amount one
    # column to the left in mixed descriptor + period tables.
    if len(labels) == logical_count:
        return labels
    change_positions = [index for index, label in enumerate(labels) if _is_change_column(label)]
    if not change_positions or len(candidate_periods) < 2:
        return []
    expanded: list[str] = []
    for change_index in change_positions:
        group_label = labels[change_index - 1] if change_index > 0 else ""
        for period in candidate_periods[:2]:
            expanded.append(" ".join(part for part in (group_label, period) if part).strip())
        expanded.append(labels[change_index])
    if len(expanded) >= logical_count:
        return expanded[:logical_count]
    return []


def _period_for_column_label(column_label: str | None) -> str | None:
    if not column_label or _is_change_column(column_label):
        return None
    return _extract_period(column_label)


def _is_change_column(column_label: str | None) -> bool:
    lower = (column_label or "").lower()
    return " vs " in lower or "change" in lower or "%" in lower and len(_extract_periods(lower)) > 1


def _cell_kind(column_label: str | None) -> str:
    return "change_value" if _is_change_column(column_label) else "period_value"


def _looks_like_group_header(row: list[str]) -> bool:
    if not row:
        return False
    if len(row) == 1:
        label = _clean_metric_name(row[0])
        return (bool(label) and label.endswith(":")) or label.lower() in {"gross margin", "gross margin percentage"}
    return all(_parse_number(cell)[0] is None for cell in row[1:])


def _infer_table_metric_name(row_label: str, active_group: str | None, table_title: str | None) -> str:
    normalized_group = _clean_metric_name(active_group or "").rstrip(":")
    lower_label = row_label.lower()
    if normalized_group and _is_segment_label(row_label):
        return normalized_group
    if normalized_group and lower_label.startswith("total ") and normalized_group.lower() not in lower_label:
        return f"Total {normalized_group}"
    if lower_label in {"products", "services"} and table_title and "gross margin" in table_title.lower():
        return "gross margin"
    return row_label


def _infer_table_segment(row_label: str, metric_name: str, subsection: str | None) -> str | None:
    if row_label.lower().startswith("total "):
        return None
    row_segment = _segment_from_label(row_label)
    if row_segment:
        return row_segment
    return _infer_segment(subsection)


def _table_metric_context(table: TableObject, active_group: str | None) -> str | None:
    parts = []
    if table.title:
        parts.append(table.title)
    if active_group:
        parts.append(active_group.rstrip(":"))
    return " | ".join(parts) if parts else None


def _is_segment_label(value: str) -> bool:
    return _segment_from_label(value) is not None


def _segment_from_label(value: str) -> str | None:
    lower = value.lower().strip()
    mapping = {
        "products": "products",
        "product": "products",
        "services": "services",
        "aws": "aws",
        "google cloud": "google cloud",
        "microsoft cloud": "microsoft cloud",
        "digital media": "digital media",
        "digital experience": "digital experience",
        "north america": "north america",
        "international": "international",
        "data center": "data center",
    }
    return mapping.get(lower)


def _periods_in_order(header: list[str]) -> list[str]:
    periods = []
    for cell in header:
        period = _extract_period(cell)
        if period and period not in periods:
            periods.append(period)
    return periods


def _infer_table_unit(table: TableObject) -> str | None:
    return _infer_table_unit_from_values(
        rows=table.rows,
        context_before=" ".join(value for value in [table.title, table.text_before] if value),
        context_after=table.text_after,
        reporting_currency=table.metadata.get("reporting_currency"),
    )


def _infer_table_unit_from_values(
    *,
    rows: list[list[str]],
    context_before: str | None,
    context_after: str | None,
    reporting_currency: str | None = None,
) -> str | None:
    # A scale/currency declaration inside the table header is more authoritative
    # than nearby narrative.  The surrounding paragraph may discuss constant-
    # currency conversion (and therefore mention both USD and EUR) while the
    # table itself is still explicitly reported in dollars.  Treating all nearby
    # text as one flat currency bag previously downgraded those rows to bare USD.
    header_index = _table_header_index(rows)
    header_row_count = header_index + 1 if header_index is not None else min(3, len(rows))
    header_context = " ".join(
        " ".join(row) for row in rows[:header_row_count]
    ).casefold()
    explicit_header_unit = _explicit_scaled_currency_unit(header_context)
    if explicit_header_unit:
        return explicit_header_unit
    context = _table_unit_context(rows=rows, context_before=context_before, context_after=context_after)
    currencies = _currency_codes_from_text(context)
    if len(currencies) > 1:
        return None
    explicit_currency = next(iter(currencies), "")
    currency = explicit_currency or str(reporting_currency or "").strip().lower()
    if currency and not re.fullmatch(r"[a-z]{3}", currency):
        currency = ""
    if "in billions" in context:
        return f"{currency or 'usd'}_billions"
    if "in millions" in context:
        return f"{currency or 'usd'}_millions"
    if "in thousands" in context:
        return f"{currency or 'usd'}_thousands"
    if "percentage" in context or "percent" in context:
        return "percent"
    if explicit_currency:
        return explicit_currency
    return None


def _explicit_scaled_currency_unit(text: str) -> str | None:
    normalized = " ".join(str(text or "").casefold().split())
    if (
        "except" in normalized
        and sum(
            marker in normalized
            for marker in ("in billions", "in millions", "in thousands")
        )
        > 1
    ):
        # Mixed-scale tables (common in bank filings) deliberately declare a
        # default and row-level exceptions.  Their existing row-aware unit
        # resolver must see the full context instead of being short-circuited
        # by the first explicit phrase.
        return None
    currencies = {
        "usd": ("dollar", "dollars", "usd"),
        "eur": ("euro", "euros", "eur"),
        "gbp": ("pound", "pounds", "gbp"),
        "chf": ("swiss franc", "chf"),
        "cny": ("renminbi", "rmb", "cny"),
        "jpy": ("yen", "jpy"),
    }
    scales = {
        "billions": "billions",
        "billion": "billions",
        "millions": "millions",
        "million": "millions",
        "thousands": "thousands",
        "thousand": "thousands",
    }
    matched_units: set[str] = set()
    for currency, markers in currencies.items():
        for marker in markers:
            for scale_marker, scale in scales.items():
                if re.search(
                    rf"(?:{re.escape(marker)}.{{0,28}}(?:in|of)\s+{scale_marker}\b|"
                    rf"\b{scale_marker}\s+(?:of\s+)?{re.escape(marker)})",
                    normalized,
                ):
                    matched_units.add(f"{currency}_{scale}")
    return next(iter(matched_units)) if len(matched_units) == 1 else None


def _table_unit_context(
    *,
    rows: list[list[str]],
    context_before: str | None,
    context_after: str | None,
) -> str:
    row_text = " ".join(" ".join(row) for row in rows[:6])
    return " ".join(value for value in [context_before, row_text, context_after] if value).lower()


def _infer_cell_unit(
    raw_value: str,
    column_label: str | None,
    table_unit: str | None,
    *,
    row_label: str | None = None,
    table_context: str | None = None,
) -> str | None:
    lower_label = (column_label or "").lower()
    lower_row = (row_label or "").lower()
    dimension_text = f"{lower_label} {lower_row}"
    if any(
        marker in dimension_text
        for marker in (
            "useful life",
            "useful lives",
            "remaining life",
            "remaining lives",
            "(in years)",
            " in years",
        )
    ):
        return "years"
    if (
        "%" in raw_value
        or "%" in lower_label
        or "percent" in lower_label
        or "interest rate" in lower_label
    ):
        return "percent"
    if re.search(r"\b(?:units?|systems? sold)\b", lower_row):
        return "count"
    effective_table_unit = _mixed_bank_table_row_unit(row_label, table_unit, table_context)
    if re.search(r"\bper\s+(?:(?:basic|diluted|ordinary)\s+)?share\b", lower_row) or re.search(r"\beps\b", lower_row):
        currency = str(effective_table_unit or "").split("_", 1)[0]
        return f"{currency}_per_share" if re.fullmatch(r"[a-z]{3}", currency) else "per_share"
    if "$" in raw_value:
        return effective_table_unit or _row_currency_unit(lower_row, table_context) or "usd"
    if "amount" in lower_label:
        row_unit = _row_currency_unit(lower_row, table_context)
        if row_unit:
            return row_unit
    if "%" in lower_row or "margin (%)" in lower_row:
        return "percent"
    return effective_table_unit


def _row_currency_unit(row_label: str | None, table_context: str | None) -> str | None:
    currencies = _currency_codes_from_text(str(row_label or ""))
    if len(currencies) != 1:
        return None
    currency = next(iter(currencies))
    context = str(table_context or "").casefold()
    if "in billions" in context:
        return f"{currency}_billions"
    if "in millions" in context or "amounts in millions" in context:
        return f"{currency}_millions"
    if "in thousands" in context:
        return f"{currency}_thousands"
    return currency


def _currency_codes_from_text(text: str) -> set[str]:
    lower = str(text or "").casefold()
    pairs = {
        "usd": ("$", " usd", "u.s. dollar", "us dollar", "dollars in"),
        "eur": ("€", " eur", "euro"),
        "gbp": ("£", " gbp", "pound sterling"),
        "chf": (" chf", "swiss franc"),
        "cny": (" cny", " rmb", "renminbi"),
        "jpy": (" jpy", "yen"),
        "twd": (" twd", "nt$", "new taiwan dollar"),
        "krw": ("₩", " krw", "won"),
    }
    return {
        code for code, markers in pairs.items() if any(marker in lower for marker in markers)
    }


def _mixed_bank_table_row_unit(row_label: str | None, table_unit: str | None, table_context: str | None) -> str | None:
    if table_unit != "usd_billions":
        return table_unit
    context = str(table_context or "").lower()
    if not ("in millions" in context and "in billions" in context and "except" in context):
        return table_unit
    label = str(row_label or "").lower()
    billion_exception_terms = (
        "end-of-period assets",
        "average loans",
        "average deposits",
        "total assets",
        "total loans",
        "total deposits",
        "deposit balances",
    )
    if any(term in label for term in billion_exception_terms):
        return "usd_billions"
    return "usd_millions"


def _nearest_period(header: list[str], col_index: int) -> str | None:
    for idx in range(min(col_index, len(header) - 1), -1, -1):
        period = _extract_period(header[idx])
        if period:
            return period
    return None


def _extract_period(text: str) -> str | None:
    match = YEAR_PATTERN.search(text)
    return match.group(0) if match else None


def _numeric_column_hint(value: str) -> bool:
    return value in {"$", "%", "change"} or bool(_parse_number(value)[0] is not None)


def _parse_number(raw_value: str) -> tuple[float | None, str | None]:
    cleaned = raw_value.strip()
    if not cleaned or cleaned in {"$", "%", "-"}:
        return None, None
    negative = "(" in cleaned and ")" in cleaned
    match = NUMBER_PATTERN.search(cleaned)
    if not match:
        return None, None
    try:
        value = float(match.group("number").replace(",", ""))
    except ValueError:
        return None, None
    if negative:
        value = -value
    suffix = match.group("suffix")
    unit = suffix.lower() if suffix else None
    if "%" in cleaned or suffix == "%":
        unit = "percent"
    elif "$" in cleaned and suffix and suffix.lower() == "million":
        unit = "usd_millions"
    elif "$" in cleaned and suffix and suffix.lower() == "billion":
        unit = "usd_billions"
    elif "$" in cleaned:
        unit = "usd"
    return value, unit


def _is_standalone_year(raw_value: str) -> bool:
    return bool(re.fullmatch(r"[($\s]*20\d{2}[)\s,]*", raw_value.strip()))


def _should_keep_sentence_number(sentence: str, match: re.Match[str]) -> bool:
    raw = match.group(0)
    suffix = match.group("suffix")
    if "$" in raw or "%" in raw or suffix:
        return True
    start, end = match.span()
    window = sentence[max(0, start - 16) : min(len(sentence), end + 16)].lower()
    if any(month in window for month in ("jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec")):
        return False
    try:
        value = float(match.group("number").replace(",", ""))
    except ValueError:
        return False
    lower = sentence.lower()
    if "customers" in lower and value >= 100:
        return True
    if "year" in window:
        return value < 100
    if "," in match.group("number") and value >= 1000:
        return True
    return False


def _clean_metric_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip(" :-"))
    cleaned = cleaned.replace("(loss)", "loss")
    return cleaned


def _looks_like_header(value: str) -> bool:
    lower = value.lower()
    return (
        lower in {"year ended", "gross margin:", "net sales:", "operating income"}
        or lower.startswith("table of contents")
        or any(
            marker in lower
            for marker in (
                "statements of operations",
                "statements of cash flows",
                "statements of stockholders",
                "balance sheets as of",
                "financial statements for",
            )
        )
        or _is_standalone_year(value)
        or _is_table_unit_row([value])
    )


def _is_table_unit_row(row: list[str]) -> bool:
    text = " ".join(row).lower()
    compact = re.sub(r"\s+", " ", text).strip()
    unit_only = re.fullmatch(
        r"\(?\s*(?:(?:figures|amounts)\s+)?(?:dollars\s+)?in\s+(?:billions|millions|thousands)(?:\s+of\s+(?:euros?|dollars?|pounds?|[a-z]{3}))?(?:,?\s*(?:except|unless)[^)]*)?\s*\)?",
        compact,
    )
    return bool(text) and (
        bool(unit_only)
        or compact in {"$", "%", "except percentages"}
    )


def _looks_like_numeric_table_cell(value: str) -> bool:
    compact = re.sub(r"\s+", " ", str(value or "").strip())
    return bool(
        re.fullmatch(
            r"(?:[$€£]\s*)?\(?-?\d[\d,]*(?:\.\d+)?\)?\s*(?:%|million|billion)?",
            compact,
            re.IGNORECASE,
        )
    )


def _safe_cell_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return cleaned[:80] or "cell"


def _infer_segment(*values: str | None) -> str | None:
    joined = " ".join(value for value in values if value).lower()
    known = [
        "services",
        "products",
        "aws",
        "google cloud",
        "microsoft cloud",
        "data center",
        "digital media",
        "digital experience",
        "north america",
        "international",
        "google services",
    ]
    for segment in known:
        if segment in joined:
            return segment
    return None


def _sentences_without_tables(text: str) -> list[str]:
    text_without_tables = TABLE_PATTERN.sub(" ", text)
    rough_sentences = re.split(r"(?<=[.!?])\s+|\n+", text_without_tables)
    sentences = []
    for sentence in rough_sentences:
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if 40 <= len(cleaned) <= 1200:
            sentences.append(cleaned)
    return sentences


def _metric_sentence_candidate(sentence: str) -> bool:
    lower = sentence.lower()
    if not NUMBER_PATTERN.search(sentence):
        return False
    metric_terms = (
        "revenue",
        "sales",
        "margin",
        "income",
        "cash flow",
        "capital expenditure",
        "remaining performance obligations",
        "arr",
        "customer",
        "customers",
        "retention",
        "cost",
        "expense",
    )
    return any(_keyword_in_text(term, lower) for term in metric_terms)


def _infer_sentence_metric_name(sentence: str, raw_value: str) -> str:
    lower = sentence.lower()
    metric_aliases = [
        ("remaining performance obligations", "remaining performance obligations"),
        ("total adobe arr", "Total Adobe ARR"),
        ("arr", "ARR"),
        ("net revenue retention", "net revenue retention"),
        ("operating income", "operating income"),
        ("capital expenditures", "capital expenditures"),
        ("free cash flow", "free cash flow"),
        ("revenue", "revenue"),
        ("net sales", "net sales"),
        ("gross margin", "gross margin"),
        ("customers", "customers"),
    ]
    for needle, label in metric_aliases:
        if _keyword_in_text(needle, lower):
            return label
    before = sentence.split(raw_value, 1)[0].strip()
    tokens = before.split()
    return " ".join(tokens[-6:]) if tokens else "metric"


def _claim_type(sentence: str) -> str | None:
    lower = sentence.lower()
    for claim_type, keywords in CLAIM_KEYWORDS.items():
        if any(_keyword_in_text(keyword, lower) for keyword in keywords):
            return claim_type
    return None


def _claim_polarity(sentence: str) -> str:
    lower = sentence.lower()
    positive = any(word in lower for word in POSITIVE_WORDS)
    negative = any(word in lower for word in NEGATIVE_WORDS)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "neutral"


def _extract_entities(sentence: str, ticker: str) -> list[str]:
    entities = [ticker]
    lower = sentence.lower()
    for entity in (
        "AWS",
        "Google Cloud",
        "Microsoft Cloud",
        "Azure",
        "Data Center",
        "Services",
        "Digital Media",
        "RPO",
        "ARR",
    ):
        if _keyword_in_text(entity, lower) and entity not in entities:
            entities.append(entity)
    return entities


def _extract_metric_mentions(sentence: str) -> list[str]:
    mentions = []
    lower = sentence.lower()
    for term in (
        "revenue",
        "net sales",
        "gross margin",
        "operating income",
        "capital expenditures",
        "remaining performance obligations",
        "ARR",
        "RPO",
        "free cash flow",
        "customers",
    ):
        if _keyword_in_text(term, lower) and term not in mentions:
            mentions.append(term)
    return mentions


def _trim(text: str, max_chars: int) -> str:
    compact = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return compact[:max_chars] + ("...[truncated]" if len(compact) > max_chars else "")


def _keyword_in_text(keyword: str, lower_text: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return bool(re.search(pattern, lower_text))


def _object_id(source_evidence_id: str, prefix: str, *parts: Any) -> str:
    suffix = "_".join(str(part).upper().replace(" ", "") for part in parts if part is not None)
    raw = f"{source_evidence_id}_{prefix}_{suffix}" if suffix else f"{source_evidence_id}_{prefix}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8].upper()
    return f"{source_evidence_id}_{prefix}_{digest}"
