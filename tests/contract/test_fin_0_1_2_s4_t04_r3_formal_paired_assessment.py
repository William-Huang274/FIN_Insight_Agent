from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.assess_fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_verified_product_pair import (  # noqa: E402
    S4T04PairedAssessmentError,
    validate_pair_binding,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EXACT = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t04-nvda-current-evidence-capacity-reproof-exact-live-r3/"
    "execution-result.json"
)
BASELINE = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t04-nvda-current-evidence-deterministic-baseline-r1/"
    "execution-result.json"
)
SURFACE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
    "verified_product_surface_and_read_only_assessment_v1_0.json"
)
ASSESSMENT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
    "formal_paired_assessment_and_owner_decision_request_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_formal_pair_is_same_input_distinct_run_and_owner_honest() -> None:
    exact = _load(EXACT)
    baseline = _load(BASELINE)
    surface = _load(SURFACE)
    validate_pair_binding(
        exact_result=exact,
        baseline_result=baseline,
        surface_record=surface,
    )
    assessment = _load(ASSESSMENT)
    assert assessment["assessment_digest"] == canonical_digest(
        {
            key: value
            for key, value in assessment.items()
            if key != "assessment_digest"
        }
    )
    assert assessment["status"] == "paired_L1_L4_pass_owner_decision_required"
    assert assessment["pair_binding"]["runs_are_distinct"] is True
    assert assessment["acceptance_boundary"]["formal_paired_L1_L4"] == "pass"
    assert assessment["L1_deterministic_integrity"]["status"] == "pass"
    assert assessment["L2_evidence_reliability_and_coverage"][
        "status"
    ].startswith("pass_")
    assert assessment["L3_agent_gain"]["status"].startswith("pass_")
    assert assessment["L4_final_delivery"]["status"] == "pass"
    assert assessment["owner_decision_request"]["material_gain_accepted"] is None
    assert assessment["acceptance_boundary"][
        "current_source_grounded_NVDA_R2"
    ] is False
    assert baseline["observed_counts"]["model_calls"] == 0
    assert baseline["observed_counts"]["provider_calls"] == 0


def test_pair_binding_rejects_baseline_input_mutation() -> None:
    baseline = deepcopy(_load(BASELINE))
    baseline["input_digest"] = "mutated"
    baseline["result_digest"] = canonical_digest(
        {key: value for key, value in baseline.items() if key != "result_digest"}
    )
    with pytest.raises(
        S4T04PairedAssessmentError,
        match="s4_t04_pair_input_digest_mismatch",
    ):
        validate_pair_binding(
            exact_result=_load(EXACT),
            baseline_result=baseline,
            surface_record=_load(SURFACE),
        )
