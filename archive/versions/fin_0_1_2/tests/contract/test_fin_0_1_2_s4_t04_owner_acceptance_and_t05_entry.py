from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_r2_"
    "product_owner_acceptance_and_t05_entry_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_49.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_owner_acceptance_is_bound_and_does_not_overclaim_r3_or_t05_execution() -> None:
    decision = _load(DECISION)
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    for binding in decision["immutable_bindings"]:
        assert _sha256(ROOT / binding["ref"]) == binding["sha256"]

    assert decision["authority"]["user_instruction"] == "接受"
    assert decision["authority"]["product_owner_acceptance"] is True
    assert decision["accepted_product_meaning"]["S4_T04"] == (
        "pass_closed_owner_accepted"
    )
    assert decision["accepted_product_meaning"][
        "current_source_grounded_NVDA_R2"
    ] is True
    assert decision["authority"]["qualified_human_review_performed"] is False
    assert decision["authority"]["NVDA_R3_established"] is False
    assert decision["explicit_non_claims"]["S4_T05_execution_started"] is False
    assert all(value == 0 for value in decision["observed_counts"].values())


def test_projection_enters_t05_without_claiming_transfer_results() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    truth = projection["current_truth"]

    assert projection["owner_acceptance"]["decision_digest"] == decision[
        "decision_digest"
    ]
    assert truth["S4_T04"].startswith("pass_closed_owner_accepted")
    assert truth["S4_T05"] == (
        "entry_authorized_scope_decision_pending_execution_not_started"
    )
    assert truth["current_NVDA_R2"] is True
    assert truth["DELL_current_R2"] is False
    assert truth["MU_current_R2"] is False
    assert truth["post_transfer_NVDA_R2"] is False
    assert truth["qualified_human_review"] is False
    assert truth["NVDA_R3"] is False
    assert truth["release"] == "not_qualified"
    assert projection["authority_boundary"]["S4_T05_execution_started"] is False


def test_nonblocking_finding_is_carried_without_reopening_t04() -> None:
    decision = _load(DECISION)
    finding = decision["quality_finding_disposition"]
    assert finding["status"] == "accepted_nonblocking_carried_forward"
    assert finding["reopens_S4_T04"] is False
    assert finding["triggers_R4"] is False
    assert "S4-T08" in finding["assigned_to"]
    assert "S5" in finding["assigned_to"]
