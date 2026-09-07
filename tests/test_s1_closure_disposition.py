from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.s1_closure_disposition import (
    S1ClosureDispositionError,
    validate_s1_closure_disposition,
)


ROOT = Path(__file__).resolve().parents[1]
DISPOSITION = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_current_closure_disposition_v1_0.json"
)


def _payload() -> dict:
    return json.loads(DISPOSITION.read_text(encoding="utf-8"))


def test_current_s1_closure_disposes_every_predecessor_gap_once() -> None:
    value = validate_s1_closure_disposition(ROOT, _payload())

    assert len(value["dispositions"]) == 20
    assert len({row["gap_id"] for row in value["dispositions"]}) == 20
    assert value["current_gates"]["closed_internal_gap_ids"] == [
        "S1-A-GAP-002",
        "S1-C-GAP-001",
        "S1-D-GAP-001",
    ]
    assert value["acceptance"]["current_internal_closure_complete"] is False
    assert value["acceptance"]["external_qualification_complete"] is False
    assert value["acceptance"]["s1_qualified_stable"] is False


def test_s1_closure_keeps_product_and_cross_stage_owners_distinct() -> None:
    value = validate_s1_closure_disposition(ROOT, _payload())
    rows = {row["gap_id"]: row for row in value["dispositions"]}

    assert rows["S1-E-GAP-001"]["disposition_state"] == "reallocated_cross_stage"
    assert rows["S1-E-GAP-001"]["current_owner"].startswith("S3_")
    assert rows["S1-H-GAP-001"]["product_internal_blocking"] is True
    assert rows["S1-J-GAP-002"]["qualification_blocking"] is True


def test_s1_closure_fails_closed_if_one_predecessor_gap_is_removed() -> None:
    value = deepcopy(_payload())
    value["dispositions"].pop()

    with pytest.raises(S1ClosureDispositionError):
        validate_s1_closure_disposition(ROOT, value)


def test_s1_closure_fails_closed_if_s1_is_relabelled_passed() -> None:
    value = deepcopy(_payload())
    value["acceptance"]["s1_qualified_stable"] = True

    with pytest.raises(S1ClosureDispositionError):
        validate_s1_closure_disposition(ROOT, value)
