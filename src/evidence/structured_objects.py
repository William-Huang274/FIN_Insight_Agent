from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field


StructuredObjectType = Literal["table", "metric", "claim"]
MetricExtractionMethod = Literal["table_row_heuristic", "sentence_heuristic", "banking_ixbrl_fact_heuristic"]
ClaimExtractionMethod = Literal["sentence_heuristic"]
ClaimType = Literal[
    "risk",
    "strategy",
    "demand",
    "cost_pressure",
    "capex",
    "revenue_visibility",
    "accounting_policy",
    "business_context",
    "other",
]
ClaimPolarity = Literal["positive", "negative", "mixed", "neutral"]


class StructuredObject(BaseModel):
    object_id: str
    object_type: StructuredObjectType
    source_evidence_id: str
    ticker: str
    fiscal_year: int | None = None
    section: str | None = None
    subsection: str | None = None
    source_url: str | None = None
    local_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)


class TableObject(StructuredObject):
    object_type: Literal["table"] = "table"
    table_id: str
    title: str | None = None
    row_count: int
    column_count: int
    rows: list[list[str]]
    cells: list[dict[str, Any]] = Field(default_factory=list)
    candidate_periods: list[str] = Field(default_factory=list)
    text_before: str | None = None
    text_after: str | None = None


class MetricObject(StructuredObject):
    object_type: Literal["metric"] = "metric"
    metric_name: str
    raw_value: str
    value: float | None = None
    unit: str | None = None
    period: str | None = None
    segment: str | None = None
    table_object_id: str | None = None
    row_label: str | None = None
    column_label: str | None = None
    context: str | None = None
    extraction_method: MetricExtractionMethod
    confidence: float = 0.5


class ClaimObject(StructuredObject):
    object_type: Literal["claim"] = "claim"
    claim_text: str
    claim_type: ClaimType = "other"
    polarity: ClaimPolarity = "neutral"
    entities: list[str] = Field(default_factory=list)
    metrics_mentioned: list[str] = Field(default_factory=list)
    context: str | None = None
    extraction_method: ClaimExtractionMethod = "sentence_heuristic"
    confidence: float = 0.5


def write_structured_jsonl(
    objects: Iterable[StructuredObject],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for obj in objects:
            f.write(obj.to_jsonl_line())
            f.write("\n")


def read_table_jsonl(path: str | Path) -> list[TableObject]:
    return _read_jsonl(path, TableObject)


def read_metric_jsonl(path: str | Path) -> list[MetricObject]:
    return _read_jsonl(path, MetricObject)


def read_claim_jsonl(path: str | Path) -> list[ClaimObject]:
    return _read_jsonl(path, ClaimObject)


def _read_jsonl(path: str | Path, model: type[StructuredObject]) -> list[Any]:
    input_path = Path(path)
    rows = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(model.model_validate_json(stripped))
            except ValueError as exc:
                raise ValueError(f"Invalid structured JSONL at {input_path}:{line_number}") from exc
    return rows
