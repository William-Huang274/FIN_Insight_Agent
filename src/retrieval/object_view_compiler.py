from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .evidence_role_contract import (
    EvidenceRoleContractError,
    build_evidence_object_view,
)
from .query_plan import canonical_digest
from .route_compiler import QueryObjectFactRoutePolicy


COMPILED_OBJECT_SCHEMA_VERSION = "fin_ia_compiled_financial_object_view_v1_1"
OBJECT_STORE_COMPILATION_SCHEMA_VERSION = (
    "fin_ia_financial_object_store_compilation_v1_0"
)

_TABLE_PATTERN = re.compile(
    r"\[TABLE_START id=(?P<table_id>[^\s\]]+) rows=(?P<rows>\d+)\]\r?\n"
    r"(?P<body>.*?)\[TABLE_END\]",
    re.DOTALL,
)
_SENTENCE_PATTERN = re.compile(r"[^.!?\n]+(?:[.!?](?:[\"”’])?|$)")
_MONTH_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b",
    re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
_FISCAL_PERIOD_LABEL_PATTERN = re.compile(
    r"^(?:FY|FQ|Q)\s*\d{1,2}(?:[-/]\d{2,4})?$",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"(?:\$|€|£)?\(?-?\d[\d,]*(?:\.\d+)?\)?%?")
_FINANCIAL_HEADER_TERMS = (
    "revenue",
    "sales",
    "gross margin",
    "operating income",
    "net income",
    "earnings",
    "cash",
    "debt",
    "assets",
    "liabilities",
    "inventory",
    "receivable",
    "payable",
    "capital expenditure",
    "free cash flow",
    "shipments",
    "backlog",
    "capacity",
    "dividend",
    "repurchase",
    "fiscal year ended",
    "quarter ended",
    "in millions",
    "in thousands",
    "percentages",
)
_FINANCIAL_ROW_TERMS = (
    "revenue",
    "sales",
    "gross profit",
    "gross margin",
    "operating income",
    "operating expense",
    "net income",
    "earnings per share",
    "ebitda",
    "cash",
    "debt",
    "assets",
    "liabilities",
    "inventory",
    "receivable",
    "payable",
    "capital expenditure",
    "free cash flow",
    "shipments",
    "backlog",
    "capacity",
    "dividend",
    "repurchase",
)


@dataclass(frozen=True)
class ObjectStoreCompilation:
    objects: tuple[Mapping[str, Any], ...]
    diagnostics: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any]

    def as_dict(self, *, include_objects: bool = True) -> dict[str, Any]:
        value = {
            "schema_version": OBJECT_STORE_COMPILATION_SCHEMA_VERSION,
            "summary": dict(self.summary),
            "diagnostics": [dict(row) for row in self.diagnostics],
        }
        if include_objects:
            value["objects"] = [dict(row) for row in self.objects]
        return value


def _is_navigation_only(text: str) -> bool:
    normalized = " ".join(text.split()).casefold()
    return (
        not normalized
        or normalized == "table of contents"
        or normalized.isdigit()
        or normalized in {"index", "contents"}
    )


def _claim_units(
    raw_text: str,
    table_spans: list[tuple[int, int]],
    *,
    minimum: int,
    maximum: int,
    limit: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    masked = list(raw_text)
    for start, end in table_spans:
        masked[start:end] = "\n" * (end - start)
    narrative = "".join(masked)
    candidates: list[str] = []
    diagnostics: list[dict[str, Any]] = []

    def add(surface: str) -> None:
        value = surface.strip()
        if (
            len(value) < minimum
            or len(value) > maximum
            or _is_navigation_only(value)
            or value in candidates
        ):
            return
        if raw_text.count(value) != 1:
            diagnostics.append(
                {
                    "diagnostic_code": "claim_surface_not_unique",
                    "surface_digest": canonical_digest(value),
                }
            )
            return
        candidates.append(value)

    for line in narrative.splitlines():
        value = line.strip()
        if not value or _is_navigation_only(value):
            continue
        if len(value) <= maximum:
            add(value)
        else:
            for match in _SENTENCE_PATTERN.finditer(value):
                add(match.group(0))
        if len(candidates) >= limit:
            break
    return candidates[:limit], diagnostics


def _table_is_financial_or_operating(
    *,
    header_lines: list[str],
    metric_lines: list[str],
) -> bool:
    """Reject person/security/nav tables even when a role contains words like sales."""

    header = " ".join(header_lines).casefold()
    has_explicit_unit = any(
        term in header
        for term in ("in millions", "in thousands", "except per share", "percentages")
    )
    has_period = (
        bool(_MONTH_PATTERN.search(header))
        or bool(_YEAR_PATTERN.search(header))
        or "quarter" in header
        or "fiscal" in header
        or "period ended" in header
    )
    header_has_metric = any(term in header for term in _FINANCIAL_HEADER_TERMS)
    labelled_rows = sum(
        any(term in line.split("|", 1)[0].casefold() for term in _FINANCIAL_ROW_TERMS)
        for line in metric_lines
    )
    return has_explicit_unit or (has_period and header_has_metric) or labelled_rows >= 2


def _row_is_metric(line: str) -> bool:
    if "|" not in line:
        return False
    cells = [cell.strip() for cell in line.split("|")]
    label = cells[0] if cells else ""
    normalized = label.casefold()
    if not label or not any(char.isalpha() for char in label):
        return False
    if (
        "ended" in normalized
        or _MONTH_PATTERN.search(label)
        or _FISCAL_PERIOD_LABEL_PATTERN.fullmatch(label.strip())
        or normalized in {"name", "date", "period", "fiscal year", "quarter"}
    ):
        return False
    return any(_NUMBER_PATTERN.search(cell) for cell in cells[1:])


def _row_context_candidate(line: str) -> bool:
    """Return whether a non-metric table line can scope following metric rows."""

    value = line.strip()
    normalized = value.casefold()
    if not value or "|" in value or not any(char.isalpha() for char in value):
        return False
    if (
        _MONTH_PATTERN.search(value)
        or _FISCAL_PERIOD_LABEL_PATTERN.fullmatch(value)
        or "ended" in normalized
        or "in millions" in normalized
        or "in thousands" in normalized
        or "except per share" in normalized
        or normalized.startswith("quarterly ")
    ):
        return False
    return len(value) <= 240


def _compile_table_rows(
    *,
    table_match: re.Match[str],
    record: Mapping[str, Any],
    parent: Mapping[str, Any],
    policy: QueryObjectFactRoutePolicy,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    table_id = table_match.group("table_id")
    body = table_match.group("body")
    source_record_id = str(record.get("evidence_id") or "")
    lines = [line.strip() for line in body.strip().splitlines() if line.strip()]
    metric_indices = [index for index, line in enumerate(lines) if _row_is_metric(line)]
    if not metric_indices:
        return [], [
            {
                "diagnostic_code": "financial_table_has_no_compilable_metric_row",
                "source_record_id": source_record_id,
                "table_id": table_id,
            }
        ]
    first_metric = metric_indices[0]
    header_lines = lines[:first_metric]
    metric_lines = [lines[index] for index in metric_indices]
    if not _table_is_financial_or_operating(
        header_lines=header_lines,
        metric_lines=metric_lines,
    ):
        return [], [
            {
                "diagnostic_code": "nonfinancial_table_not_compiled_as_metric_rows",
                "source_record_id": source_record_id,
                "table_id": table_id,
            }
        ]
    try:
        base = build_evidence_object_view(
            object_key=f"{source_record_id}::table::{table_id}",
            object_form="metric_table",
            locator={"mode": "balanced_table", "table_id": table_id},
            record=record,
            parent=parent,
        ).as_dict()
    except EvidenceRoleContractError as exc:
        return [], [
            {
                "diagnostic_code": str(exc),
                "source_record_id": source_record_id,
                "table_id": table_id,
            }
        ]
    period_hints = [
        line
        for line in header_lines
        if _MONTH_PATTERN.search(line)
        or _YEAR_PATTERN.search(line)
        or "quarter" in line.casefold()
        or "fiscal" in line.casefold()
    ]
    unit_hints = [
        line
        for line in header_lines
        if "million" in line.casefold()
        or "thousand" in line.casefold()
        or "percentage" in line.casefold()
        or "except per share" in line.casefold()
    ]
    title = str(record.get("subsection") or record.get("section") or "").strip()
    limit = int(policy.object_compiler["max_metric_rows_per_table"])
    max_text = int(policy.object_compiler["max_model_text_characters"])
    row_context_by_index: dict[int, list[str]] = {}
    active_context: list[str] = []
    for line in header_lines:
        if _row_context_candidate(line):
            active_context = [line]
    for row_index in range(first_metric, len(lines)):
        line = lines[row_index]
        if _row_is_metric(line):
            row_context_by_index[row_index] = list(active_context)
        elif _row_context_candidate(line):
            active_context = [line]
    output: list[dict[str, Any]] = []
    for row_index in metric_indices[:limit]:
        line = lines[row_index]
        cells = [cell.strip() for cell in line.split("|")]
        row_context_lines = row_context_by_index.get(row_index, [])
        projection = {
            "table_id": table_id,
            "declared_row_count": int(table_match.group("rows")),
            "table_title": title,
            "header_lines": header_lines,
            "period_hints": period_hints,
            "unit_hints": unit_hints,
            "row_context_lines": row_context_lines,
            "metric_row_label": cells[0],
            "metric_row_cells": cells[1:],
            "parent_section": str(record.get("section") or ""),
        }
        model_text = "\n".join(
            value
            for value in (
                f"Company: {record.get('company')} ({record.get('ticker')})",
                f"Source: {record.get('source_type')} published {record.get('publication_date')}",
                f"Section: {record.get('section')}",
                f"Table: {title}" if title else "",
                f"Header: {' || '.join(header_lines)}" if header_lines else "",
                (
                    f"Row context: {' || '.join(row_context_lines)}"
                    if row_context_lines
                    else ""
                ),
                f"Row: {line}",
            )
            if value
        )[:max_text]
        identity = {
            "base_object_view_id": base["object_view_id"],
            "row_index": row_index,
            "row": line,
            "projection": projection,
        }
        output.append(
            {
                "schema_version": COMPILED_OBJECT_SCHEMA_VERSION,
                "compiled_object_id": f"COBJ::{canonical_digest(identity)[:24]}",
                "object_kind": "metric_row",
                "base_object_view": base,
                "structured_projection": projection,
                "model_text": model_text,
                "candidate_not_evidence": True,
                "numeric_authority": False,
                "evidence_promoted": False,
            }
        )
    return output, []


def compile_record_object_views(
    *,
    record: Mapping[str, Any],
    parent: Mapping[str, Any],
    policy: QueryObjectFactRoutePolicy,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compile source-bound candidate views without assigning relevance or authority."""

    raw_text = str(record.get("text") or "")
    source_record_id = str(record.get("evidence_id") or "")
    output: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    try:
        context = build_evidence_object_view(
            object_key=f"{source_record_id}::parent_context",
            object_form="parent_context",
            locator={"mode": "parent_context"},
            record=record,
            parent=parent,
        ).as_dict()
        output.append(
            {
                "schema_version": COMPILED_OBJECT_SCHEMA_VERSION,
                "compiled_object_id": f"COBJ::{canonical_digest(context)[:24]}",
                "object_kind": "bounded_parent_context",
                "base_object_view": context,
                "structured_projection": {},
                "model_text": context["surface_text"],
                "candidate_not_evidence": True,
                "numeric_authority": False,
                "evidence_promoted": False,
            }
        )
    except EvidenceRoleContractError as exc:
        diagnostics.append(
            {
                "diagnostic_code": str(exc),
                "source_record_id": source_record_id,
            }
        )

    matches = list(_TABLE_PATTERN.finditer(raw_text))
    claim_surfaces, claim_diagnostics = _claim_units(
        raw_text,
        [(match.start(), match.end()) for match in matches],
        minimum=int(policy.object_compiler["claim_min_characters"]),
        maximum=int(policy.object_compiler["claim_max_characters"]),
        limit=int(policy.object_compiler["max_claims_per_source_record"]),
    )
    diagnostics.extend(
        {"source_record_id": source_record_id, **row}
        for row in claim_diagnostics
    )
    max_text = int(policy.object_compiler["max_model_text_characters"])
    for index, surface in enumerate(claim_surfaces, start=1):
        try:
            base = build_evidence_object_view(
                object_key=f"{source_record_id}::claim::{index:02d}",
                object_form="claim",
                locator={"mode": "exact_text", "text": surface},
                record=record,
                parent=parent,
            ).as_dict()
        except EvidenceRoleContractError as exc:
            diagnostics.append(
                {
                    "diagnostic_code": str(exc),
                    "source_record_id": source_record_id,
                }
            )
            continue
        output.append(
            {
                "schema_version": COMPILED_OBJECT_SCHEMA_VERSION,
                "compiled_object_id": f"COBJ::{canonical_digest(base)[:24]}",
                "object_kind": "claim",
                "base_object_view": base,
                "structured_projection": {},
                "model_text": surface[:max_text],
                "candidate_not_evidence": True,
                "numeric_authority": False,
                "evidence_promoted": False,
            }
        )
    for match in matches:
        rows, row_diagnostics = _compile_table_rows(
            table_match=match,
            record=record,
            parent=parent,
            policy=policy,
        )
        output.extend(rows)
        diagnostics.extend(row_diagnostics)
    return output, diagnostics


def compile_object_store(
    *,
    records: Iterable[Mapping[str, Any]],
    parents_by_id: Mapping[str, Mapping[str, Any]],
    policy: QueryObjectFactRoutePolicy,
) -> ObjectStoreCompilation:
    raw_objects: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    source_record_count = 0
    missing_parent_count = 0
    for record in records:
        source_record_count += 1
        parent_id = str((record.get("metadata") or {}).get("parent_document_id") or "")
        parent = parents_by_id.get(parent_id)
        if parent is None:
            missing_parent_count += 1
            diagnostics.append(
                {
                    "diagnostic_code": "compiled_object_parent_missing",
                    "source_record_id": str(record.get("evidence_id") or ""),
                    "parent_document_id": parent_id,
                }
            )
            continue
        compiled, record_diagnostics = compile_record_object_views(
            record=record,
            parent=parent,
            policy=policy,
        )
        raw_objects.extend(compiled)
        diagnostics.extend(record_diagnostics)
    deduplicated: dict[str, dict[str, Any]] = {}
    duplicate_group_counts: dict[str, int] = {}
    for row in raw_objects:
        base = row["base_object_view"]
        kind = str(row["object_kind"])
        parent_id = str(base["parent_document_id"])
        if kind == "metric_row":
            projection = row["structured_projection"]
            identity = {
                "object_kind": kind,
                "parent_document_id": parent_id,
                "table_id": projection["table_id"],
                "header_lines": projection["header_lines"],
                "row_context_lines": projection.get("row_context_lines", []),
                "metric_row_label": projection["metric_row_label"],
                "metric_row_cells": projection["metric_row_cells"],
            }
        elif kind == "claim":
            identity = {
                "object_kind": kind,
                "parent_document_id": parent_id,
                "normalized_surface": " ".join(row["model_text"].split()).casefold(),
            }
        else:
            identity = {
                "object_kind": kind,
                "parent_document_id": parent_id,
                "section": base["section"],
                "subsection": base["subsection"],
            }
        key = canonical_digest(identity)
        source_id = str(base["source_record_id"])
        existing = deduplicated.get(key)
        if existing is None:
            value = dict(row)
            value["lineage_source_record_ids"] = [source_id]
            value["duplicate_lineage_count"] = 0
            deduplicated[key] = value
            continue
        lineage = set(existing["lineage_source_record_ids"])
        lineage.add(source_id)
        existing["lineage_source_record_ids"] = sorted(lineage)
        existing["duplicate_lineage_count"] = len(lineage) - 1
        duplicate_group_counts[key] = existing["duplicate_lineage_count"]
    objects = list(deduplicated.values())
    kind_counts: dict[str, int] = {}
    for row in objects:
        kind = str(row["object_kind"])
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    diagnostic_counts: dict[str, int] = {}
    for row in diagnostics:
        code = str(row["diagnostic_code"])
        diagnostic_counts[code] = diagnostic_counts.get(code, 0) + 1
    summary = {
        "source_record_count": source_record_count,
        "parent_document_count": len(parents_by_id),
        "raw_compiled_object_count": len(raw_objects),
        "compiled_object_count": len(objects),
        "deduplicated_object_count": len(raw_objects) - len(objects),
        "duplicate_object_group_count": len(duplicate_group_counts),
        "object_kind_counts": dict(sorted(kind_counts.items())),
        "diagnostic_count": len(diagnostics),
        "diagnostic_counts": dict(sorted(diagnostic_counts.items())),
        "missing_parent_count": missing_parent_count,
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "network_calls": 0,
        "model_calls": 0,
    }
    return ObjectStoreCompilation(
        objects=tuple(objects),
        diagnostics=tuple(diagnostics),
        summary=summary,
    )


__all__ = [
    "COMPILED_OBJECT_SCHEMA_VERSION",
    "OBJECT_STORE_COMPILATION_SCHEMA_VERSION",
    "ObjectStoreCompilation",
    "compile_object_store",
    "compile_record_object_views",
]
