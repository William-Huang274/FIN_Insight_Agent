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


def evaluate_index_asset_quality(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(record) for record in records]
    failures: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(rows, start=1):
        record_id = str(record.get("chunk_id") or record.get("vector_id") or record.get("record_id") or f"index_row_{index}")
        if record_id in seen_ids:
            failures.append(_failure(record_id, "duplicate_index_record_id", "index ids should be unique", "duplicate"))
        seen_ids.add(record_id)
        if not str(record.get("company_id") or record.get("ticker") or "").strip():
            failures.append(_failure(record_id, "index_entity_missing", "index row should carry company/ticker binding", "missing"))
        if not str(record.get("source_family") or record.get("source_type") or "").strip():
            failures.append(_failure(record_id, "index_source_family_missing", "index row should carry source family", "missing"))
        if record.get("vector_expected") and not record.get("vector_present"):
            failures.append(_failure(record_id, "vector_missing", "vector expected rows must have vector_present=true", "missing"))
        if record.get("milvus_record") and str(record.get("authority") or "").lower() in {"exact", "exact_value", "financial_fact"}:
            failures.append(_failure(record_id, "milvus_exact_authority_forbidden", "Milvus rows are semantic recall only", "exact_authority"))
    return _quality_result(
        schema_version="finsight_index_asset_quality_eval_v0_1",
        rows=rows,
        failures=failures,
        eval_scope=[
            "id_uniqueness",
            "entity_binding",
            "source_family_binding",
            "vector_presence",
            "milvus_semantic_only_boundary",
        ],
    )


def evaluate_retrieval_quality(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(record) for record in records]
    failures: list[dict[str, Any]] = []
    for index, record in enumerate(rows, start=1):
        record_id = str(record.get("task_id") or record.get("route") or f"retrieval_task_{index}")
        target_in_candidates = record.get("target_in_candidates")
        if target_in_candidates is False:
            failures.append(_failure(record_id, "target_not_in_candidates", "target should enter candidate set before rerank", "false"))
        if _int(record.get("pre_rerank_count")) > 0 and _int(record.get("post_rerank_count")) == 0:
            failures.append(_failure(record_id, "rerank_dropped_all_candidates", "post-rerank should keep usable candidates", "zero"))
        if _int(record.get("post_rerank_count")) > 0 and _int(record.get("role_visible_count")) == 0:
            failures.append(_failure(record_id, "role_visible_rows_missing", "role selector should expose relevant rows", "zero"))
        if record.get("cap_hit") and not str(record.get("cap_reason") or "").strip():
            failures.append(_failure(record_id, "retrieval_cap_reason_missing", "budget caps require cap_reason", "missing"))
    return _quality_result(
        schema_version="finsight_retrieval_quality_eval_v0_1",
        rows=rows,
        failures=failures,
        eval_scope=[
            "target_in_candidates",
            "post_rerank_retention",
            "role_visible_recall",
            "cap_reason",
        ],
    )


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


def _quality_result(*, schema_version: str, rows: list[dict[str, Any]], failures: list[dict[str, Any]], eval_scope: list[str]) -> dict[str, Any]:
    total = len(rows)
    failure_count = len(failures)
    return {
        "schema_version": schema_version,
        "status": "pass" if failure_count == 0 else "fail",
        "record_count": total,
        "failure_count": failure_count,
        "pass_rate": 1.0 if total == 0 else max(0.0, (total - failure_count) / total),
        "failure_events": failures,
        "eval_scope": eval_scope,
    }


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
