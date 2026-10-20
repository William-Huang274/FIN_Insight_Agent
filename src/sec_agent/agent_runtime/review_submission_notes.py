"""Lossless review annotations; never infer verdicts from prose or unknown keys."""
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

from .evidence_resolution import parsing_record


class AssessmentNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_field: str = Field(min_length=1, max_length=100)
    original_path: str = Field(min_length=1, max_length=500)
    text: str = Field(max_length=5000)


def preserve_assessment_notes(arguments):
    """Relocate only a known textual annotation, leaving unsafe fields to schema.

    Never drop/overwrite a conflicting note, decode nested values, coerce types,
    or treat annotation text as completion, finding status or severity.
    """
    value = deepcopy(arguments)
    records = []
    review = value.get("review") if isinstance(value, dict) else None
    rows = review.get("assessments") if isinstance(review, dict) else None
    if not isinstance(rows, list):
        return value, records
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or "verdict_note" not in row:
            continue
        text = row["verdict_note"]
        if not isinstance(text, str) or len(text) > 5000:
            continue
        notes = row.get("supplemental_notes", [])
        if not isinstance(notes, list):
            continue
        path = f"/review/assessments/{index}/verdict_note"
        note = {"original_field": "verdict_note", "original_path": path, "text": text}
        # Different content under the same provenance is an explicit conflict.
        if any(isinstance(n, dict) and n.get("original_path") == path and n != note for n in notes):
            continue
        if note not in notes:
            notes = [*notes, note]
        row["supplemental_notes"] = notes
        del row["verdict_note"]
        records.append(parsing_record("assessment_note_preservation_v1", {"verdict_note": text}, deepcopy(note),
            field_path=path, paper_id=row.get("paper_id"), text_unchanged=True,
            decision_fields_unchanged=True, full_validation_required=True))
    return value, records
