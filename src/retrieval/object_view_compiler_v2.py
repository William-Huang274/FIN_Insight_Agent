from __future__ import annotations

from typing import Any, Iterable, Mapping

from .object_view_compiler import (
    ObjectStoreCompilation,
    _TABLE_PATTERN,
    _is_navigation_only,
    compile_record_object_views as compile_record_object_views_v1,
)
from .query_plan import canonical_digest
from .route_compiler import QueryObjectFactRoutePolicy


COMPILED_OBJECT_SCHEMA_VERSION = "fin_ia_compiled_financial_object_view_v1_3"
OBJECT_STORE_COMPILATION_SCHEMA_VERSION = (
    "fin_ia_financial_object_store_compilation_v1_1"
)


def _table_local_context(raw_text: str, table_start: int) -> list[str]:
    """Return source-bound prose immediately introducing one table."""

    previous_table_end = raw_text.rfind("[TABLE_END]", 0, table_start)
    start = previous_table_end + len("[TABLE_END]") if previous_table_end >= 0 else 0
    segment = raw_text[start:table_start]
    lines: list[str] = []
    for raw_line in segment.splitlines():
        value = " ".join(raw_line.split()).strip()
        normalized = value.casefold()
        if (
            not value
            or _is_navigation_only(value)
            or normalized in {"(unaudited)", "unaudited"}
            or normalized.endswith("(continued)")
            or normalized
            in {
                "nvidia corp",
                "nvidia corporation",
                "dell technologies inc.",
                "micron technology, inc.",
            }
        ):
            continue
        if len(value) > 600:
            value = value[-600:].lstrip()
        lines.append(value)
    return lines[-3:]


def _local_table_title(local_context_lines: list[str]) -> str:
    """Choose only a heading-like local line as a semantic table title."""

    prose_prefixes = (
        "the following ",
        "our ",
        "we ",
        "as of ",
        "during ",
        "for a description ",
    )
    for value in reversed(local_context_lines):
        normalized = value.casefold()
        if (
            len(value) <= 180
            and not value.endswith((".", ":", ";", "?", "!"))
            and not normalized.startswith(prose_prefixes)
            and any(char.isalpha() for char in value)
        ):
            return value
    return ""


def _successor_metric_row(
    row: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
    table_start_by_id: Mapping[str, int],
    policy: QueryObjectFactRoutePolicy,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    value = dict(row)
    value["schema_version"] = COMPILED_OBJECT_SCHEMA_VERSION
    if str(value.get("object_kind") or "") != "metric_row":
        return value, None

    projection = dict(value.get("structured_projection") or {})
    table_id = str(projection.get("table_id") or "")
    raw_text = str(record.get("text") or "")
    table_start = table_start_by_id.get(table_id)
    diagnostic = None
    local_context_lines: list[str] = []
    if table_start is None:
        diagnostic = {
            "diagnostic_code": "successor_table_local_context_missing",
            "source_record_id": str(record.get("evidence_id") or ""),
            "table_id": table_id,
        }
    else:
        local_context_lines = _table_local_context(raw_text, table_start)
    title = _local_table_title(local_context_lines)
    projection.update(
        {
            "table_title": title,
            "table_title_source": (
                "local_pre_table_heading" if title else "none"
            ),
            "local_context_lines": local_context_lines,
        }
    )
    header_lines = [str(item) for item in projection.get("header_lines") or ()]
    row_context_lines = [
        str(item) for item in projection.get("row_context_lines") or ()
    ]
    cells = [
        str(projection.get("metric_row_label") or ""),
        *(str(item) for item in projection.get("metric_row_cells") or ()),
    ]
    line = " | ".join(item for item in cells if item)
    model_text = "\n".join(
        item
        for item in (
            f"Company: {record.get('company')} ({record.get('ticker')})",
            (
                f"Source: {record.get('source_type')} published "
                f"{record.get('publication_date')}"
            ),
            f"Section: {record.get('section')}",
            f"Table: {title}" if title else "",
            (
                f"Local table context: {' || '.join(local_context_lines)}"
                if local_context_lines
                else ""
            ),
            f"Header: {' || '.join(header_lines)}" if header_lines else "",
            (
                f"Row context: {' || '.join(row_context_lines)}"
                if row_context_lines
                else ""
            ),
            f"Row: {line}",
        )
        if item
    )[: int(policy.object_compiler["max_model_text_characters"])]
    identity = {
        "predecessor_compiled_object_id": str(value["compiled_object_id"]),
        "base_object_view_id": str(value["base_object_view"]["object_view_id"]),
        "structured_projection": projection,
        "model_text": model_text,
    }
    value.update(
        {
            "compiled_object_id": f"COBJ::{canonical_digest(identity)[:24]}",
            "structured_projection": projection,
            "model_text": model_text,
        }
    )
    return value, diagnostic


def compile_record_object_views(
    *,
    record: Mapping[str, Any],
    parent: Mapping[str, Any],
    policy: QueryObjectFactRoutePolicy,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compile v1 objects, then remove cross-table context before deduplication."""

    rows, diagnostics = compile_record_object_views_v1(
        record=record,
        parent=parent,
        policy=policy,
    )
    raw_text = str(record.get("text") or "")
    table_start_by_id = {
        str(match.group("table_id")): int(match.start())
        for match in _TABLE_PATTERN.finditer(raw_text)
    }
    output: list[dict[str, Any]] = []
    successor_diagnostics = list(diagnostics)
    for row in rows:
        value, diagnostic = _successor_metric_row(
            row,
            record=record,
            table_start_by_id=table_start_by_id,
            policy=policy,
        )
        output.append(value)
        if diagnostic is not None:
            successor_diagnostics.append(diagnostic)
    return output, successor_diagnostics


def compile_object_store(
    *,
    records: Iterable[Mapping[str, Any]],
    parents_by_id: Mapping[str, Mapping[str, Any]],
    policy: QueryObjectFactRoutePolicy,
) -> ObjectStoreCompilation:
    """Compile and deduplicate successor objects with local table context."""

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
                "local_context_lines": projection.get("local_context_lines", []),
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
        "table_context_mode": "source_bound_local_pre_table_v2",
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
    "compile_object_store",
    "compile_record_object_views",
]
