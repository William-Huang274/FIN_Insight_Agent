from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
RUNTIME = ROOT / "configs" / "runtime"
CONTRACT_TESTS = ROOT / "tests" / "contract"
BASELINE = RELEASES / (
    "fin_ia_0_1_3_repair_closeout_s0_01_delta_inheritance_namespace_"
    "and_current_truth_baseline_v1_0.json"
)
ACTIVE_SUITE = RELEASES / (
    "fin_ia_0_1_3_repair_closeout_s0_01_active_test_suite_successor_v1_0.json"
)
SCRIPT = ROOT / "scripts" / "releases" / (
    "materialize_fin_ia_0_1_3_repair_closeout_s0_01_delta_baseline.py"
)

SPEC = importlib.util.spec_from_file_location("fin013_s001_baseline", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_bindings_and_canonical_active_suite_are_current() -> None:
    baseline = _load(BASELINE)
    for binding in baseline["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        if binding["role"] == "research_content_quality_hard_gate":
            # This is a maintained requirement document. S0-01 preserves its
            # event-time digest; a later stage must issue a successor binding
            # instead of rewriting the historical baseline or requiring the
            # living document to retain old bytes forever.
            assert len(binding["sha256"]) == 64
            int(binding["sha256"], 16)
        else:
            assert _sha256(path) == binding["sha256"]
    active = _load(ACTIVE_SUITE)
    MODULE.validate_baseline(baseline, active)


def test_all_old_FIN_0_1_3_assets_are_classified_by_exact_digest() -> None:
    baseline = _load(BASELINE)
    inventory = baseline["historical_namespace_inventory"]
    observed = [
        path
        for path in [
            *RELEASES.glob("fin_ia_0_1_3*.json"),
            *RUNTIME.glob("fin_ia_0_1_3*.json"),
            *CONTRACT_TESTS.glob("test_fin_0_1_3*.py"),
        ]
        if "repair_closeout" not in path.name
    ]
    assert len(observed) == 47
    rows = {row["ref"]: row for row in inventory["assets"]}
    assert len(rows) == 47
    for path in observed:
        ref = path.relative_to(ROOT).as_posix()
        assert rows[ref]["sha256"] == _sha256(path)
    assert inventory["classification_counts"] == {
        "historical_event_not_current_authority": 18,
        "superseded_projection_not_reusable_as_current_truth": 11,
        "reusable_version_neutral_candidate_pending_013_S0_02": 5,
        "reusable_test_candidate_pending_013_S0_02": 3,
        "historical_test_not_current_gate": 10,
    }


def test_old_namespace_is_not_selected_as_current_authority() -> None:
    active = _load(ACTIVE_SUITE)
    current_refs = [
        ref
        for suite in active["suites"]
        if suite["selected"] and suite["gates_current_release"]
        for ref in suite["test_paths"]
    ]
    assert current_refs == [
        "tests/contract/test_fin_0_1_3_repair_closeout_s0_01_delta_inheritance_namespace_and_current_truth_baseline.py"
    ]
    pending = next(
        suite
        for suite in active["suites"]
        if suite["suite_id"] == "old_FIN_0_1_3_reusable_candidates"
    )
    assert pending["selected"] is False
    assert pending["gates_current_release"] is False
    assert len(pending["candidate_assets"]) == 8


def test_T07_C_projection_is_allowlisted_and_secret_safe() -> None:
    baseline = _load(BASELINE)
    review = baseline["secret_safe_T07_C_current_truth"]
    assert review["private_store_counts"] == {
        "review_sessions": 1,
        "security_events": 4,
        "qualified_decisions": 1,
    }
    projection = review["allowlisted_decision_projection"]
    assert projection["action"] == "accept_exact_version"
    assert projection["bounded_NVDA_R3"] is True
    assert projection["release_qualified"] is False
    serialized = json.dumps(review, ensure_ascii=False).lower()
    for forbidden in (
        "credential_digest",
        "session_id",
        "reviewer_ref",
        "reviewer_note",
    ):
        assert forbidden not in serialized
    assert review["projection_policy"] == {
        "database_open_mode": "read_only",
        "private_identity_projected": False,
        "review_text_projected": False,
        "secret_material_projected": False,
    }


def test_mutation_cannot_promote_old_acceptance_or_old_test_authority() -> None:
    baseline = _load(BASELINE)
    active = _load(ACTIVE_SUITE)
    promoted = deepcopy(baseline)
    promoted["inheritance_policy"][
        "old_R2_R3_auto_promotable_after_changed_input_data_or_contract"
    ] = True
    with pytest.raises(MODULE.S001BaselineError, match="auto_promotion_forbidden"):
        MODULE.validate_baseline(promoted, active)
    stale_suite = deepcopy(active)
    stale_suite["suites"][0]["test_paths"] = [
        "tests/contract/test_fin_0_1_3_s0_t03_host_zero_call_engineering_proof_terminal_honest_block_closeout.py"
    ]
    with pytest.raises(MODULE.S001BaselineError, match="current_gate_ref_invalid"):
        MODULE.validate_baseline(baseline, stale_suite)
