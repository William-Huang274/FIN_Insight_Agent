from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    load_current_fin_0_1_2_s4_t01_case_entry,
)


IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t01_natural_case_entry_and_"
    "exact_binding_zero_call_implementation_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_36.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
NEXT = (
    "FIN-0.1.2-S4-T02-THREE-CASE-RETRIEVAL-EVIDENCE-"
    "DETERMINISTIC-READINESS-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_implementation_bindings_and_three_case_receipts_recompute() -> None:
    implementation = _load(IMPLEMENTATION)
    assert implementation["status"] == (
        "pass_zero_call_runtime_injected_node_level_consumed_"
        "T01_closed_T02_not_started"
    )
    for binding in implementation["implementation_bindings"]:
        path = ROOT / binding["ref"]
        assert binding["sha256"] == _sha256(path)
        assert binding["bytes"] == path.stat().st_size
    expected = {row["case_key"]: row for row in implementation["three_case_results"]}
    for case_key in ("DELL", "MU", "NVDA"):
        compiled = load_current_fin_0_1_2_s4_t01_case_entry(case_key)
        row = expected[case_key]
        assert row == {
            "case_key": case_key,
            "request_digest": compiled.request.request_digest,
            "runtime_binding_digest": compiled.runtime_binding.binding_digest,
            "snapshot_binding_digest": compiled.snapshot_binding.binding_digest,
            "identity_projection_digest": (
                compiled.identity_projection.projection_digest
            ),
            "entry_receipt_digest": compiled.receipt.entry_digest,
        }


def test_t01_pass_does_not_promote_snapshots_or_enter_t02() -> None:
    implementation = _load(IMPLEMENTATION)
    boundary = implementation["snapshot_boundary"]
    assert boundary["snapshots_are_current_Evidence"] is False
    assert boundary["T01_did_not_read_or_return_snapshot_content"] is True
    assert implementation["contract"]["identity_claimed"] is False
    assert implementation["contract"]["T02_authorized"] is False
    assert set(implementation["observed_counts"].values()) == {0}


def test_projection_and_backlog_advance_only_to_t02_zero_call() -> None:
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert projection["S4_T01_closeout"]["implementation_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert projection["current_truth"]["S4_T01"].startswith("pass_closed")
    assert projection["current_truth"]["S4_T02"].startswith("not_started")
    assert projection["current_truth"]["current_NVDA_R2"] is False
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["S4_T02_entry"]["live_search_or_model_authorized"] is False
    assert next_action["item_id"] == NEXT
    assert next_action["current_projection_sha256"] == _sha256(PROJECTION)
    assert next_action["S4_T01_completed"] is True
    assert next_action["S4_T02_started"] is False
    assert next_action["S4_T01_snapshots_are_current_Evidence"] is False


def test_inherited_registry_drift_is_typed_as_pre_t03_not_hidden_or_misattributed() -> None:
    implementation = _load(IMPLEMENTATION)
    issue = implementation["new_issue"]
    assert issue["issue_id"].startswith("RC-P36-113-")
    assert "S4_T03_paid_canary" in issue["blocks"]
    assert "S4_T01_closeout" in issue["does_not_block"]
    assert implementation["verification"][
        "inherited_failure_present_at_clean_HEAD_9026b9f5"
    ] is True
    assert implementation["verification"]["T01_files_caused_inherited_failure"] is False
