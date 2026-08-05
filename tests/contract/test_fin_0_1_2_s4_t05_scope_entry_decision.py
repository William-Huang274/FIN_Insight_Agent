from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_dell_mu_post_transfer_"
    "nvda_scope_entry_decision_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_50.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_decision_preserves_historical_bindings_without_rebasing_live_source() -> None:
    decision = _load(DECISION)
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    for binding in decision["immutable_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert len(binding["sha256"]) == 64
        int(binding["sha256"], 16)
        if not binding["role"].endswith("_surface_at_entry"):
            assert _sha256(path) == binding["sha256"]
    assert decision["entry_audit"]["T03_executable_search"].startswith("NVDA_only")
    assert decision["entry_audit"]["T04_current_evidence_research"].startswith(
        "NVDA_only"
    )
    assert decision["entry_audit"]["direct_DELL_or_MU_live_eligible_now"] is False


def test_T05_sequence_requires_one_zero_call_transfer_package_before_live() -> None:
    decision = _load(DECISION)
    sequence = decision["fixed_T05_sequence"]
    assert [item["order"] for item in sequence] == [1, 2, 3, 4]
    assert sequence[0]["slice"] == "T05-A"
    assert sequence[0]["mode"] == "zero_call"
    assert sequence[1]["slice"] == "T05-B"
    assert sequence[2]["precondition"] == "DELL current R2 accepted"
    assert sequence[3]["precondition"] == "DELL and MU current R2 accepted"
    assert decision["reuse_policy"][
        "forbidden_as_FIN_0_1_2_current_product_proof"
    ]
    assert all(value == 0 for value in decision["observed_counts"].values())


def test_stop_policy_prevents_another_unbounded_repair_chain() -> None:
    decision = _load(DECISION)
    policy = decision["stop_and_failure_policy"]
    ceiling = decision["prospective_ceiling_not_execution_authority"]
    assert policy["maximum_automatic_structural_repair_packages_after_this_decision"] == 0
    assert policy["maximum_automatic_replacement_exact_runs_after_this_decision"] == 0
    assert policy["new_product_version_on_failure"] is False
    assert ceiling["automatic_retry_fallback_replay_relaunch_or_repair"] is False
    assert ceiling["these_ceilings_authorize_execution"] is False


def test_projection_preserves_current_NVDA_and_unproven_transfer_cases() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    truth = projection["current_truth"]
    assert projection["T05_scope"]["decision_digest"] == decision["decision_digest"]
    assert truth["current_NVDA_R2"] is True
    assert truth["DELL_current_R2"] is False
    assert truth["MU_current_R2"] is False
    assert truth["post_transfer_NVDA_R2"] is False
    assert truth["S4_T05"] == "in_progress_T05_A_zero_call_transfer_package_pending"
    assert truth["S4_T06_T08"] == "not_started"
    assert truth["release"] == "not_qualified"
