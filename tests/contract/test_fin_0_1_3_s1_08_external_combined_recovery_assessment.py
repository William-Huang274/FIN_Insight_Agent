from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.s1_08_external_combined_assessment import (
    ExternalCombinedAssessmentError,
)
from sec_agent.s1_08_external_combined_recovery_assessment import (
    assess_external_combined_recovery_live,
)


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_result_v1_1.json"
RUNTIME = ROOT / ".codex_runtime/fin013_s1_08/external_combined/live-r2"
VISIBLE = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
HIDDEN = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
FIRECRAWL = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
TENCENT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_assessment_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assess(result: dict | None = None) -> dict:
    return assess_external_combined_recovery_live(
        result=result or _load(RESULT),
        runtime_root=RUNTIME,
        visible_pack=_load(VISIBLE),
        hidden_scoring=_load(HIDDEN),
        historical_firecrawl_assessment=_load(FIRECRAWL),
        historical_tencent_assessment=_load(TENCENT),
        resolver=lambda _host: ("198.18.1.10",),
    )


def test_recovery_live_closes_runtime_defect_but_fails_candidate_ceiling() -> None:
    assessment = _assess()
    assert assessment["status"] == (
        "runtime_recovery_live_pass_external_candidate_ceiling_failed"
    )
    assert assessment["runtime_recovery"]["pass"] is True
    assert assessment["runtime_recovery"][
        "controlled_synthetic_dns_handshake_live_proven"
    ] is True
    assert assessment["runtime_recovery"]["shadow_systemic_stop"] == {
        "attempted_network_queries": 1,
        "credit_exhaustion_terminals": 1,
        "unattempted_after_systemic_stop": 23,
        "remaining_queries_stopped_after_first_credit_exhaustion": True,
        "first_three_case_coverage": 3,
        "first_six_case_slot_coverage": 6,
        "systemic_credit_stop_valid": True,
    }
    assert assessment["official_candidate_quality"]["selected_required_slots"] == 4
    assert assessment["official_candidate_quality"]["required_external_slots"] == 12
    assert assessment["official_candidate_quality"][
        "required_external_slot_coverage"
    ] == 0.333333
    assert assessment["official_candidate_quality"]["source_family_diversity"] == 1
    assert assessment["evaluator_only_candidate_ceiling"]["summary"] == {
        "target_groups": 12,
        "target_in_pool_recall": 0.0,
        "selected_pack_required_slot_coverage": 0.0,
        "ranking_metrics_admitted": False,
    }
    assert assessment["historical_provider_evidence"][
        "production_provider_qualified"
    ] is False
    assert assessment["hard_gate_results"][
        "external_portfolio_product_acceptance"
    ] is False
    assert assessment["stage_disposition"]["internal_retrieval_started"] is False
    assert assessment["stage_disposition"][
        "internal_retrieval_may_start_after_closeout_projection"
    ] is True


def test_recovery_assessment_fails_closed_on_public_result_mutation() -> None:
    mutated = deepcopy(_load(RESULT))
    mutated["observed_counts"]["model_calls"] = 1
    with pytest.raises(
        ExternalCombinedAssessmentError,
        match="external_combined_recovery_terminal_invalid",
    ):
        _assess(mutated)
