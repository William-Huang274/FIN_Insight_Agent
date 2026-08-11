from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_deterministic_judgment_atom_"
    "planner_and_compiled_contract_invariant_hardening_zero_call_"
    "disposition_v1_0.json"
)
AGGREGATE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_"
    "aggregate_defect_and_proof_strategy_result_v1_0.json"
)
R6_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_"
    "result_r6_exact_live_execution_failure_result_v1_0.json"
)
NEXT = (
    "S4-T06-MU-DETERMINISTIC-JUDGMENT-ATOM-PLANNER-AND-COMPILED-"
    "CONTRACT-INVARIANT-HARDENING-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_disposition_binds_formal_and_quarantined_source_evidence() -> None:
    decision = _load(DECISION)
    source = decision["source_evidence"]

    assert source["formal_R6_failure_sha256"] == _sha256(R6_FAILURE)
    assert source["quarantined_diagnostic_aggregate_sha256"] == _sha256(
        AGGREGATE
    )
    assert source["formal_R6_mutated"] is False
    assert source["diagnostic_interactions"] == 12
    assert source["diagnostic_repair_findings"] == 10
    assert source["diagnostic_quarantined_artifacts"] == 9
    assert source["diagnostic_business_artifact_promotions"] == 0


def test_provider_surface_is_atoms_and_aliases_not_material_truth() -> None:
    decision = _load(DECISION)
    bundle = decision["selected_structural_bundle"]
    families = {
        row["family_id"]: row for row in bundle["provider_contract_families"]
    }

    assert set(families) == {
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    }
    assert "material numeric clause" in families["specialist_fact_atoms"][
        "provider_must_not_return"
    ]
    assert "final cardinality" in families["claim_candidate_atoms"][
        "provider_must_not_own"
    ]
    assert "free numeric threshold" in families["what_would_change_atoms"][
        "provider_must_not_return"
    ]
    assert "validity-aware candidate filtering" in bundle[
        "local_deterministic_planner_owns"
    ]
    assert "all material numeric value period unit scale comparator sign and precision" in (
        bundle["local_deterministic_planner_owns"]
    )


def test_selector_and_compiler_invariants_close_diagnostic_runtime_gaps() -> None:
    decision = _load(DECISION)
    bundle = decision["selected_structural_bundle"]
    selector = bundle["selector_policy"]
    compiler = bundle["compiled_contract_invariants"]

    assert selector["mixed_scope_candidate_disposition"] == (
        "reject_before_final_selection"
    )
    assert selector["over_cardinality_disposition"] == (
        "select_best_valid_subset_not_naive_truncation"
    )
    assert selector["tie_break_is_deterministic"] is True
    assert compiler[
        "provider_text_capacity_and_local_render_capacity_are_separate"
    ]
    assert compiler[
        "local_structured_rendering_must_not_inherit_provider_narrative_max_length"
    ]
    assert compiler["projected_input_cost_unit"] == "estimated_input_tokens"
    assert compiler["utf8_bytes_may_be_used_as_pricing_tokens"] is False
    assert compiler["actual_post_call_usage_cost_hard_cap_retained"] is True


def test_proof_strategy_uses_zero_call_and_contract_family_canaries() -> None:
    decision = _load(DECISION)
    matrix = decision["deterministic_acceptance_matrix"]
    canary = decision["future_provider_canary_policy"]

    assert matrix["paid_live_per_individual_fix"] is False
    assert matrix["three_case_full_fake"]["cases"] == ["DELL", "MU", "NVDA"]
    assert matrix["three_case_full_fake"]["per_case_required"] == {
        "logical_nodes": 6,
        "provider_callbacks": 12,
        "restricted_captures": 12,
        "business_artifacts": 9,
    }
    assert canary[
        "maximum_natural_output_single_node_canaries_per_family"
    ] == 1
    assert canary["maximum_total_single_node_canaries"] == 3
    assert canary["field_level_canary"] is False
    assert canary["automatic_retry"] is False
    assert canary["provider_hopping"] is False


def test_anti_loop_ceiling_and_next_action_are_frozen() -> None:
    decision = _load(DECISION)
    guard = decision["anti_infinite_repair_governance"]

    assert guard["maximum_zero_call_implementation_bundles"] == 1
    assert guard["automatic_follow_on_bundles"] == 0
    assert guard[
        "maximum_single_node_canaries_per_changed_contract_family"
    ] == 1
    assert guard["maximum_final_MU_formal_exact_lives"] == 1
    assert guard["automatic_R8_or_equivalent"] is False
    assert guard["field_by_field_allowlist_patch_loop"] is False
    assert guard["L1_downgrade_to_quality_finding"] is False
    assert decision["next_action"] == NEXT
    assert decision["next_action_authorized"] is False
    assert all(
        count == 0
        for count in decision["observed_counts_this_disposition"].values()
    )
