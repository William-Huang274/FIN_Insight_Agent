from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .query_plan import canonical_digest


SCHEMA_VERSION = "fin_ia_s1_current_closure_disposition_v1_0"


class S1ClosureDispositionError(ValueError):
    """Raised when the S1 closure ledger loses a predecessor gap or its owner."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1ClosureDispositionError(code)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_s1_closure_disposition(
    repository_root: str | Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    value = dict(payload)
    result_digest = str(value.pop("result_digest", ""))
    _require(
        value.get("schema_version") == SCHEMA_VERSION
        and value.get("status") == "current_s1_closure_audited_not_qualified"
        and result_digest == canonical_digest(value),
        "s1_closure_disposition_identity_invalid",
    )
    predecessor = value.get("predecessor_matrix") or {}
    predecessor_ref = str(predecessor.get("ref") or "")
    predecessor_path = (root / predecessor_ref).resolve()
    try:
        predecessor_path.relative_to(root)
    except ValueError as exc:
        raise S1ClosureDispositionError(
            "s1_closure_predecessor_ref_escape"
        ) from exc
    _require(
        predecessor_path.is_file()
        and _sha256(predecessor_path) == predecessor.get("sha256"),
        "s1_closure_predecessor_binding_drift",
    )
    matrix = json.loads(predecessor_path.read_text(encoding="utf-8"))
    predecessor_gaps = {
        str(gap["gap_id"])
        for row in matrix.get("rows") or ()
        for gap in row.get("known_gaps") or ()
    }
    rows = value.get("dispositions")
    _require(isinstance(rows, list) and bool(rows), "s1_closure_rows_invalid")
    gap_ids = [str(row.get("gap_id") or "") for row in rows]
    _require(
        len(gap_ids) == len(set(gap_ids))
        and set(gap_ids) == predecessor_gaps,
        "s1_closure_predecessor_gap_coverage_invalid",
    )
    allowed_states = {
        "closed_current_internal",
        "development_proven_qualification_open",
        "open_internal",
        "open_external_qualification",
        "reallocated_cross_stage",
        "requirement_corrected_open_internal",
    }
    for row in rows:
        _require(
            isinstance(row, Mapping)
            and row.get("disposition_state") in allowed_states
            and bool(str(row.get("current_owner") or ""))
            and isinstance(row.get("evidence_refs"), list)
            and bool(row.get("evidence_refs")),
            f"s1_closure_row_invalid:{row.get('gap_id')}",
        )
        for ref in row["evidence_refs"]:
            path = (root / str(ref)).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise S1ClosureDispositionError(
                    f"s1_closure_evidence_ref_escape:{row.get('gap_id')}"
                ) from exc
            _require(
                path.is_file(),
                f"s1_closure_evidence_ref_missing:{row.get('gap_id')}:{ref}",
            )
    acceptance = value.get("acceptance") or {}
    _require(
        acceptance.get("all_predecessor_gaps_dispositioned_once") is True
        and acceptance.get("current_internal_closure_complete") is False
        and acceptance.get("external_qualification_complete") is False
        and acceptance.get("s1_qualified_stable") is False,
        "s1_closure_acceptance_invalid",
    )
    return {**value, "result_digest": result_digest}


__all__ = [
    "SCHEMA_VERSION",
    "S1ClosureDispositionError",
    "validate_s1_closure_disposition",
]
