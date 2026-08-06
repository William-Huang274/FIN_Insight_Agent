from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.canonical_runtime.cell_composition import (  # noqa: E402
    CellArchetype,
    CellCompositionEngine,
    CellCompositionPolicy,
    CellSlotTemplate,
)
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_dynamic_decision_surface_program import (  # noqa: E402
    MANDATORY_PROTECTIONS,
    REQUIRED_FAMILIES,
    S3DynamicSurfaceError,
    compile_s3_dynamic_surface_program,
    load_s3_dynamic_surface_policy,
    revise_dynamic_surface,
    validate_s3_dynamic_surface_program,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_dynamic_decision_surface_policy_v1_0.json"
S1_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
S2_POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s2_research_question_method_contract_policy_v1_0.json"
S2_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"
ACTIVE_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_active_test_suite_successor_v1_0.json"


@lru_cache(maxsize=1)
def _inputs() -> tuple[dict, dict, dict, dict]:
    return (
        load_s3_dynamic_surface_policy(POLICY_PATH),
        json.loads(S1_PATH.read_text(encoding="utf-8")),
        json.loads(S2_POLICY_PATH.read_text(encoding="utf-8")),
        json.loads(S2_PATH.read_text(encoding="utf-8")),
    )


def _compile() -> tuple[dict, dict, dict, dict, dict]:
    policy, s1, s2_policy, s2 = _inputs()
    program = compile_s3_dynamic_surface_program(
        policy=policy,
        s1_decision=s1,
        s2_policy=s2_policy,
        s2_decision=s2,
    )
    return program, policy, s1, s2_policy, s2


def _reseal_surface_and_program(program: dict, surface_index: int) -> None:
    surface = program["surfaces"][surface_index]
    surface["surface_digest"] = canonical_digest(
        {key: value for key, value in surface.items() if key != "surface_digest"}
    )
    program["program_digest"] = canonical_digest(
        {key: value for key, value in program.items() if key != "program_digest"}
    )


def test_three_current_cases_compile_dynamic_target_range_and_all_six_families() -> None:
    program, policy, s1, s2_policy, s2 = _compile()
    validate_s3_dynamic_surface_program(
        program,
        policy=policy,
        s1_decision=s1,
        s2_policy=s2_policy,
        s2_decision=s2,
    )
    assert program["observed_counts"]["cell_counts"] == {
        "DELL": 13,
        "MU": 12,
        "NVDA": 13,
    }
    for surface in program["surfaces"]:
        assert 12 <= len(surface["cells"]) <= 16
        assert surface["canonical_input_validation"]["status"] == "pass"
        assert {
            family
            for cell in surface["cells"]
            for family in cell["family_ids"]
        } == set(REQUIRED_FAMILIES)
        assert set(MANDATORY_PROTECTIONS) <= {
            tag for cell in surface["cells"] for tag in cell["protection_tags"]
        }
        assert all(
            cell["decision_question"]
            and cell["owner_role"]
            and cell["evidence_slots"]
            and cell["stop_rule"]
            and cell["what_would_change"]
            for cell in surface["cells"]
        )


def test_case_delta_is_driven_by_current_typed_gaps_not_a_fixed_title_list() -> None:
    program, *_ = _compile()
    surfaces = {row["case_key"]: row for row in program["surfaces"]}
    assert not any(cell["cell_key"].startswith("gap_resolution__") for cell in surfaces["MU"]["cells"])
    for case_key in ("DELL", "NVDA"):
        gaps = [cell for cell in surfaces[case_key]["cells"] if cell["cell_key"].startswith("gap_resolution__")]
        assert len(gaps) == 1
        assert gaps[0]["origin_pack_refs"] == [f"case-delta-{case_key.lower()}:v1"]
        assert gaps[0]["evidence_binding"]["binding_status"] == "planned_request"
        assert surfaces[case_key]["company_name"].split()[0].lower() in gaps[0]["decision_question"].lower()


def test_current_s1_and_s2_authority_are_bound_without_promoting_planned_slots() -> None:
    program, *_ = _compile()
    bound_cells = [
        cell
        for surface in program["surfaces"]
        for cell in surface["cells"]
        if cell["evidence_binding"]["binding_status"] == "current_governed_pack_bound"
    ]
    planned_cells = [
        cell
        for surface in program["surfaces"]
        for cell in surface["cells"]
        if cell["evidence_binding"]["binding_status"] == "planned_request"
    ]
    assert len(bound_cells) == 9
    assert sum(len(cell["evidence_binding"]["evidence_aliases"]) for cell in bound_cells) == 26
    assert sum(len(cell["evidence_binding"]["gap_aliases"]) for cell in bound_cells) == 2
    assert planned_cells
    assert all(not cell["evidence_binding"]["evidence_aliases"] for cell in planned_cells)


def test_reviewer_can_prune_and_split_but_cannot_silently_remove_protected_boundaries() -> None:
    program, policy, *_ = _compile()
    surface = program["surfaces"][1]
    revised = revise_dynamic_surface(
        surface,
        actions=(
            {"action": "prune", "target_cell_key": "customer_concentration", "reason": "merge into demand"},
            {"action": "split", "target_cell_key": "semicap_capex_cycle", "split_labels": ["spending", "conversion"], "reason": "separate mechanisms"},
        ),
        policy=policy,
    )
    assert revised["revision"] == 2
    assert revised["parent_surface_digest"] == surface["surface_digest"]
    assert len(revised["cells"]) == len(surface["cells"])
    protected = next(cell["cell_key"] for cell in surface["cells"] if "writer_boundary" in cell["protection_tags"])
    with pytest.raises(S3DynamicSurfaceError, match="protected_cell_prune_forbidden"):
        revise_dynamic_surface(
            surface,
            actions=({"action": "prune", "target_cell_key": protected, "reason": "mutation"},),
            policy=policy,
        )


def test_reviewer_can_add_a_complete_case_bound_cell_and_return_the_plan() -> None:
    program, policy, *_ = _compile()
    surface = program["surfaces"][0]
    added = deepcopy(
        next(cell for cell in surface["cells"] if cell["cell_key"] == "customer_concentration")
    )
    added["cell_key"] = "reviewer_added_case_specific_monitor"
    added["decision_question"] = (
        f"Which additional case-specific monitor could change the {surface['company_name']} decision surface?"
    )
    added["dependency_cell_keys"] = []
    added["evidence_binding"] = {
        "case_key": surface["case_key"],
        "evidence_aliases": [],
        "gap_aliases": [],
        "binding_status": "planned_request",
    }
    revised = revise_dynamic_surface(
        surface,
        actions=(
            {"action": "add", "reason": "case-specific monitor", "cell": added},
            {"action": "return", "reason": "request another planning pass"},
        ),
        policy=policy,
    )
    assert revised["checkpoint_status"] == "returned"
    assert len(revised["cells"]) == len(surface["cells"]) + 1
    assert revised["parent_surface_digest"] == surface["surface_digest"]


def test_cross_case_family_wwc_and_upstream_mutations_fail_closed() -> None:
    program, policy, s1, s2_policy, s2 = _compile()
    mutated = deepcopy(program)
    mutated["surfaces"][0]["cells"][0]["evidence_binding"]["case_key"] = "MU"
    _reseal_surface_and_program(mutated, 0)
    with pytest.raises(S3DynamicSurfaceError, match="cross_case_binding"):
        validate_s3_dynamic_surface_program(mutated, policy=policy, s1_decision=s1, s2_policy=s2_policy, s2_decision=s2)

    mutated = deepcopy(program)
    hbm_cell = next(
        cell
        for cell in mutated["surfaces"][0]["cells"]
        if "hbm_demand_supply_pricing_concentration" in cell["family_ids"]
    )
    hbm_cell["family_ids"] = [
        "cross_chain_counterthesis_price_in_what_would_change"
    ]
    _reseal_surface_and_program(mutated, 0)
    with pytest.raises(S3DynamicSurfaceError, match="family_coverage_invalid"):
        validate_s3_dynamic_surface_program(mutated, policy=policy, s1_decision=s1, s2_policy=s2_policy, s2_decision=s2)

    mutated = deepcopy(program)
    mutated["surfaces"][0]["cells"][0]["what_would_change"] = []
    _reseal_surface_and_program(mutated, 0)
    with pytest.raises(S3DynamicSurfaceError, match="cell_incomplete"):
        validate_s3_dynamic_surface_program(mutated, policy=policy, s1_decision=s1, s2_policy=s2_policy, s2_decision=s2)

    stale_s1 = deepcopy(s1)
    stale_s1["acceptance"]["S1"] = "engineering_pass"
    with pytest.raises(S3DynamicSurfaceError, match="upstream_authority_invalid"):
        compile_s3_dynamic_surface_program(policy=policy, s1_decision=stale_s1, s2_policy=s2_policy, s2_decision=s2)


def test_cell_composition_projects_required_what_would_change_into_canonical_seed() -> None:
    slot = CellSlotTemplate(
        slot_key="slot",
        evidence_role="issuer_metric",
        entity_scope=("NVDA",),
        period_scope="current",
        source_policy_ref="official",
        forbidden_substitutions=("proxy",),
        acceptance_role="analyst",
        fact_keys=("fact",),
    )
    result = CellCompositionEngine(
        CellCompositionPolicy(
            policy_ref="test",
            minimum_material_cells=1,
            maximum_material_cells=1,
            allowed_owner_roles=("analyst", "risk"),
        )
    ).compose(
        case_id="case",
        selected_pack_refs=("pack:v1",),
        archetypes=(CellArchetype(
            archetype_id="a",
            source_pack_ref="pack:v1",
            merge_key="cell",
            decision_question="Question",
            owner_role="analyst",
            materiality="high",
            stop_rule="stop",
            slots=(slot,),
            what_would_change=("metric rises", "metric falls"),
            counterevidence_owner_role="risk",
        ),),
    )
    assert result.cells[0].seed.what_would_change == "metric rises; metric falls"


def test_materialized_decision_is_digest_bound_and_honest() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "record_digest"}
    )
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert active["observed_result"] == "207 passed / 1 historical assertion deselected"
    assert decision["acceptance"]["S3_01"] == "engineering_pass"
    assert decision["stage_boundary"]["S3_02"] == "next_not_started"
    assert decision["stage_boundary"]["full_chain"] is False
    assert decision["stage_boundary"]["release"] is False
