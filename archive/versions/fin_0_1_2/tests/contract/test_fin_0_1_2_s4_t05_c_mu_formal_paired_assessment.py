from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_product_surface import (  # noqa: E402
    S4T05CurrentCaseProductSurfaceError,
    validate_current_case_pair_readiness,
)
from scripts.releases.assess_fin_ia_0_1_2_s4_t05_c_mu_current_evidence_product_pair import (  # noqa: E402
    DEFAULT_OUTPUT,
    T05CMUFormalPairedAssessmentError,
    assess,
    validate_formal_paired_assessment,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_c_mu_agent_exact_live_result_and_assessment import (  # noqa: E402
    EXACT_RESULT,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_c_mu_verified_product_surface_and_paired_readiness import (  # noqa: E402
    BASELINE_RESULT,
    DEFAULT_OUTPUT as SURFACE_RESULT,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _redigest(value: dict) -> dict:
    value["assessment_digest"] = canonical_digest(
        {key: row for key, row in value.items() if key != "assessment_digest"}
    )
    return value


def test_mu_formal_pair_records_limited_gain_and_honest_owner_boundary() -> None:
    assessment = assess()
    assert assessment == _load(DEFAULT_OUTPUT)
    validate_formal_paired_assessment(assessment)
    pair = assessment["pair_binding"]
    assert pair["runs_are_distinct"] is True
    assert pair["agent_artifacts"] == 9
    assert pair["deterministic_artifacts"] == 1
    assert pair["baseline_output_body_exposed_to_agent"] is False
    assert assessment["L1_deterministic_integrity"]["status"] == "pass"
    assert assessment["L2_evidence_reliability_and_coverage"][
        "authority_cells"
    ] == 3
    assert assessment["L3_agent_gain"][
        "agent_claim_dependency_conflict_gap_WWC"
    ] == [6, 1, 3, 4, 9]
    assert [
        row["issue"]
        for row in assessment["L3_agent_gain"]["quality_findings"]
    ] == ["RC-P36-119", "RC-P36-122"]
    assert assessment["L4_final_delivery"]["status"] == "pass"
    assert assessment["owner_decision_request"]["material_gain_accepted"] is None
    assert assessment["acceptance_boundary"]["MU_current_R2"] is False
    assert assessment["observed_counts"]["new_model_calls"] == 0
    assert assessment["observed_counts"]["formal_paired_assessments"] == 1


def test_mu_owner_acceptance_cannot_be_inferred_from_continue() -> None:
    changed = deepcopy(_load(DEFAULT_OUTPUT))
    changed["owner_decision_request"]["material_gain_accepted"] = True
    changed["acceptance_boundary"]["MU_current_R2"] = True
    changed["observed_counts"]["owner_decisions"] = 1
    _redigest(changed)
    with pytest.raises(
        T05CMUFormalPairedAssessmentError,
        match="s4_t05_c_mu_paired_owner_boundary_invalid",
    ):
        validate_formal_paired_assessment(changed)


def test_mu_agent_gain_counts_or_quality_findings_cannot_drift() -> None:
    changed = deepcopy(_load(DEFAULT_OUTPUT))
    changed["L3_agent_gain"]["agent_claim_dependency_conflict_gap_WWC"][1] = 2
    _redigest(changed)
    with pytest.raises(
        T05CMUFormalPairedAssessmentError,
        match="s4_t05_c_mu_paired_agent_gain_or_finding_invalid",
    ):
        validate_formal_paired_assessment(changed)


def test_mu_pair_binding_rejects_baseline_input_mutation() -> None:
    exact = _load(EXACT_RESULT)
    baseline = _load(BASELINE_RESULT)
    surface = _load(SURFACE_RESULT)["product_surface"]
    baseline["input_digest"] = "mutated"
    baseline["result_digest"] = canonical_digest(
        {key: value for key, value in baseline.items() if key != "result_digest"}
    )
    with pytest.raises(
        S4T05CurrentCaseProductSurfaceError,
        match="s4_t05_pair_input_binding_mismatch",
    ):
        validate_current_case_pair_readiness(
            exact_result=exact,
            baseline_result=baseline,
            surface_result=surface,
            expected_case_ticker="MU",
        )


def test_mu_paired_assessment_digest_mutation_fails_closed() -> None:
    changed = deepcopy(_load(DEFAULT_OUTPUT))
    changed["L4_final_delivery"]["preview_digest"] = "mutated"
    with pytest.raises(
        T05CMUFormalPairedAssessmentError,
        match="s4_t05_c_mu_paired_assessment_digest_mismatch",
    ):
        validate_formal_paired_assessment(changed)
