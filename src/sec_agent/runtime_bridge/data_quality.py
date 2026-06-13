from __future__ import annotations

from typing import Any, Iterable, Mapping


def evaluate_data_processing_quality(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(record) for record in records]
    failures: list[dict[str, Any]] = []
    for index, record in enumerate(rows, start=1):
        record_id = str(record.get("chunk_id") or record.get("evidence_id") or record.get("record_id") or f"row_{index}")
        text = str(record.get("text") or record.get("content") or "")
        if not text.strip():
            failures.append(_failure(record_id, "empty_text", "chunk text should be non-empty", "empty"))
        if record.get("truncated") is True and not str(record.get("truncation_reason") or "").strip():
            failures.append(_failure(record_id, "truncation_reason_missing", "truncated chunks require reason", "missing"))
        if _looks_like_table(record) and not _has_table_refs(record):
            failures.append(_failure(record_id, "table_refs_missing", "table rows need page/table/row/column refs", "missing"))
        for field in ("value", "unit", "period", "entity"):
            if record.get("structured_metric") and not str(record.get(field) or "").strip():
                failures.append(_failure(record_id, f"structured_{field}_missing", f"structured metric requires {field}", "missing"))
        if record.get("product_metric") and not str(record.get("product") or "").strip():
            failures.append(_failure(record_id, "product_binding_missing", "product metric requires product binding", "missing"))

    total = len(rows)
    failure_count = len(failures)
    return {
        "schema_version": "finsight_data_processing_quality_eval_v0_1",
        "status": "pass" if failure_count == 0 else "fail",
        "record_count": total,
        "failure_count": failure_count,
        "pass_rate": 1.0 if total == 0 else max(0.0, (total - failure_count) / total),
        "failure_events": failures,
        "eval_scope": [
            "chunk_boundary",
            "truncation_reason",
            "table_cell_refs",
            "structured_value_unit_period_entity_binding",
            "product_binding",
        ],
    }


def _looks_like_table(record: Mapping[str, Any]) -> bool:
    value = str(record.get("record_type") or record.get("source_type") or record.get("content_type") or "").lower()
    if "table" in value:
        return True
    return bool(record.get("table_id") or record.get("row_index") or record.get("column_index"))


def _has_table_refs(record: Mapping[str, Any]) -> bool:
    return bool(record.get("table_id")) and (
        record.get("row_index") is not None or record.get("cell_refs") or record.get("column_index") is not None
    )


def _failure(record_id: str, failure_type: str, expected: str, actual: str) -> dict[str, str]:
    return {
        "failure_type": failure_type,
        "node": "data_processing_quality",
        "record_id": record_id,
        "expected": expected,
        "actual": actual,
        "status": "observed",
    }
