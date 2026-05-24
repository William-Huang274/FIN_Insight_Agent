from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field


SourceType = Literal["10-K", "10-Q", "8-K", "annual_report"]
SourceTier = Literal["primary_filing", "primary_sec_filing"]


class EvidenceObject(BaseModel):
    evidence_id: str
    source_type: SourceType
    source_tier: SourceTier = "primary_sec_filing"
    license_scope: str = "public"
    redistributable: bool = False

    ticker: str
    company: str | None = None
    fiscal_year: int | None = None
    period_end: str | None = None
    period_type: str | None = None
    duration_months: int | None = None
    fiscal_period: str | None = None
    publication_date: str | None = None

    section: str | None = None
    subsection: str | None = None
    evidence_type: str
    topics: list[str] = Field(default_factory=list)

    text: str = Field(min_length=1)
    source_url: str | None = None
    local_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)


def write_evidence_jsonl(
    evidence_objects: Iterable[EvidenceObject], path: str | Path
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for evidence in evidence_objects:
            f.write(evidence.to_jsonl_line())
            f.write("\n")


def read_evidence_jsonl(path: str | Path) -> list[EvidenceObject]:
    input_path = Path(path)
    records: list[EvidenceObject] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(EvidenceObject.model_validate_json(stripped))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid EvidenceObject JSONL at {input_path}:{line_number}"
                ) from exc
    return records
