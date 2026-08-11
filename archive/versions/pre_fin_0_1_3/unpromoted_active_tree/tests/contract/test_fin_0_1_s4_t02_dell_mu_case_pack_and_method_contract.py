from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
R7_BINDING_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_case_runtime_"
    "binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
WWC_TRUNCATION_DISPOSITION = RELEASES / (
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "assembly_fresh_agent_proof_decision_v1_0.json"
)
WWC_ATOM_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_case_runtime_binding_"
    "mismatch_zero_call_root_cause_disposition_v1_0.json"
)
GAP_PROJECTION_R5_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_AUTHORITY = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_"
    "exact_live_execution_and_paired_assessment_authority_decision_v1_0.json"
)
GAP_PROJECTION_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_"
    "fresh_exact_admission_issuance_v1_0.json"
)
GAP_PROJECTION_FRESH_PROOF = RELEASES / (
    "fin_ia_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_"
    "fresh_agent_proof_decision_v1_0.json"
)
DELL = RELEASES / "fin_ia_0_1_s4_t02_dell_oem_exact_case_pack_v1_0.json"
MU = RELEASES / "fin_ia_0_1_s4_t02_mu_hbm_exact_case_pack_v1_0.json"
METHOD = RELEASES / "fin_ia_0_1_s4_t02_financial_method_to_runtime_contract_v1_0.json"
DECISION = RELEASES / (
    "fin_ia_0_1_s4_t02_dell_mu_case_pack_and_financial_method_to_"
    "runtime_contract_decision_v1_0.json"
)
PROGRAM = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
METHOD_REGISTRY = (
    ROOT / "docs" / "project_os" / "financial_research_method_registry.jsonl"
)
R3_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
NUMERIC_AUTHORITY_DISPOSITION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_surface_"
    "zero_call_root_cause_disposition_v1_0.json"
)
NUMERIC_AUTHORITY_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
NUMERIC_AUTHORITY_PROOF = RELEASES / (
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_agent_"
    "proof_decision_v1_0.json"
)
NUMERIC_AUTHORITY_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_exact_"
    "admission_issuance_v1_0.json"
)
NUMERIC_AUTHORITY_DECISION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_exact_live_"
    "execution_and_paired_assessment_authority_decision_v1_0.json"
)
R4_FAILURE_RESULT = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_DISPOSITION = RELEASES / (
    "fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_"
    "zero_call_root_cause_disposition_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _slice(backlog: dict, slice_id: str) -> dict:
    return next(row for row in backlog["slices"] if row["slice_id"] == slice_id)


def test_decision_binds_exact_contract_hashes_and_T02_only_authority() -> None:
    decision = _load(DECISION)

    assert decision["status"] == (
        "pass_zero_call_case_packs_and_method_contract_translated_T03_pending"
    )
    assert decision["authority"]["user_instruction"] == "授权"
    assert decision["case_pack_bindings"]["DELL"]["sha256"] == _sha256(DELL)
    assert decision["case_pack_bindings"]["MU"]["sha256"] == _sha256(MU)
    assert decision["method_contract_binding"]["sha256"] == _sha256(METHOD)
    assert decision["stage_decision"]["S4_T02"] == (
        "pass_zero_call_contract_translated"
    )
    assert decision["stage_decision"]["S4_T03"] == (
        "next_pending_separate_authority"
    )


def test_dell_and_mu_share_runtime_shape_but_keep_distinct_mechanisms() -> None:
    dell = _load(DELL)
    mu = _load(MU)

    assert dell["case_identity"]["ticker"] == "DELL"
    assert mu["case_identity"]["ticker"] == "MU"
    assert dell["case_identity"]["as_of"] == mu["case_identity"]["as_of"]
    assert dell["shared_runtime_contract"]["runtime_family"] == (
        mu["shared_runtime_contract"]["runtime_family"]
    )
    assert dell["shared_runtime_contract"]["program_cell_ids"] == (
        mu["shared_runtime_contract"]["program_cell_ids"]
    )
    assert len(dell["program_cells"]) == len(mu["program_cells"]) == 3

    dell_text = json.dumps(dell["program_cells"])
    mu_text = json.dumps(mu["program_cells"])
    assert "working_capital" in dell_text
    assert "order_or_backlog_to_revenue" in dell_text
    assert "HBM" in mu_text
    assert "memory_cycle" in mu_text


def test_case_packs_freeze_boundaries_without_inventing_facts() -> None:
    for path, ticker in ((DELL, "DELL"), (MU, "MU")):
        case = _load(path)

        assert case["numeric_policy"]["entity_ref_must_equal"] == ticker
        assert case["numeric_policy"]["narrative_fill_authorized"] is False
        assert case["graph_policy"]["graph_edge_is_direct_Evidence"] is False
        assert case["judgment_atom_contract"][
            "model_should_return_judgment_atoms_not_case_pack_structure"
        ]
        assert "ClaimFactLink" in case["judgment_atom_contract"]["local_runtime_owns"]
        factual_rows = {
            name: rows
            for name, rows in case["factual_content_boundary"].items()
            if name
            != "case_pack_contains_questions_policies_and_typed_boundaries_only"
        }
        assert all(not rows for rows in factual_rows.values())
        assert all(cell["typed_cannot_infer_codes"] for cell in case["program_cells"])
        assert all(cell["stop_rule"] for cell in case["program_cells"])
        assert all(cell["what_would_change_targets"] for cell in case["program_cells"])


def test_method_contract_names_existing_consumers_but_stays_non_runtime() -> None:
    contract = _load(METHOD)
    consumers = contract["runtime_consumer_registry"]

    assert contract["status"] == (
        "contract_translated_T03_runtime_injection_and_node_consumption_pending"
    )
    assert len(consumers) == 7
    assert len(contract["methods"]) == 2
    assert all(
        row["S4_T02_state"] == "contract_translated"
        for row in contract["methods"]
    )
    assert contract["T03_implementation_contract"]["status"] == (
        "pending_separate_authority"
    )
    assert contract["T03_implementation_contract"][
        "paid_canary_admission_or_exact_live_allowed"
    ] is False

    for consumer in consumers:
        source = ROOT / consumer["source_ref"]
        assert source.exists()
        text = source.read_text(encoding="utf-8")
        assert consumer["symbol"] in text
        if consumer.get("consume_symbol"):
            assert consumer["consume_symbol"] in text


def test_cross_case_leakage_matrix_and_method_registry_are_explicit() -> None:
    contract = _load(METHOD)
    matrix = set(
        contract["cross_case_leakage_contract"][
            "negative_fixture_matrix_required_in_T03"
        ]
    )
    assert {
        "NVDA_fact_in_DELL_rejected",
        "NVDA_fact_in_MU_rejected",
        "DELL_fact_in_MU_rejected",
        "MU_fact_in_DELL_rejected",
        "three_case_fact_in_SaaS_structural_fixture_rejected",
        "three_case_fact_in_Bank_structural_fixture_rejected",
    } == matrix

    method_ids = {row["method_id"] for row in contract["methods"]}
    latest = {
        row["method_id"]: row
        for row in _jsonl(METHOD_REGISTRY)
        if row["method_id"] in method_ids
    }
    assert set(latest) == method_ids
    assert latest[
        "s4_dell_oem_order_to_revenue_and_working_capital_playbook"
    ]["status"] == (
        "runtime_injected_node_level_consumed_independent_fresh_"
        "engineering_proof_pass_paid_artifact_and_Human_acceptance_pending"
    )
    assert latest[
        "s4_mu_hbm_supply_pricing_and_cycle_playbook"
    ]["status"] == (
        "mapping_and_alignment_fixture_proven_MU_exact_execution_and_"
        "Human_acceptance_not_authorized"
    )


def test_program_preserves_T02_and_advances_after_T03_without_paid_inflation() -> None:
    program = _load(PROGRAM)
    s4 = _slice(program, "S4")
    task_status = {row["item_id"]: row["status"] for row in s4["items"]}
    decision = _load(DECISION)

    assert task_status["S4-T02"] == (
        "pass_zero_call_case_packs_and_method_contract_translated"
    )
    assert task_status["S4-T03"] == (
        "pass_zero_paid_case_runtime_injected_node_consumed_and_leakage_preflight"
    )
    assert program["next_action"]["item_id"] == (
        _load(ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json")["next_action"]
        if R7_BINDING_IMPLEMENTATION.exists()
        else _load(WWC_ATOM_ISSUANCE)["next_action"]
        if WWC_ATOM_ISSUANCE.exists()
        else _load(WWC_TRUNCATION_DISPOSITION)["next_action"]
        if WWC_TRUNCATION_DISPOSITION.exists()
        else
        _load(GAP_PROJECTION_R5_FAILURE_RESULT)["next_action"]
        if GAP_PROJECTION_R5_FAILURE_RESULT.exists()
        else _load(GAP_PROJECTION_AUTHORITY)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if GAP_PROJECTION_AUTHORITY.exists()
        else _load(GAP_PROJECTION_ISSUANCE)["next_action"]
        if GAP_PROJECTION_ISSUANCE.exists()
        else _load(GAP_PROJECTION_FRESH_PROOF)["next_action"]
        if GAP_PROJECTION_FRESH_PROOF.exists()
        else
        _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else _load(GAP_PROJECTION_DISPOSITION)["next_action"]
        if GAP_PROJECTION_DISPOSITION.exists()
        else
        _load(R4_FAILURE_RESULT)["next_action"]
        if R4_FAILURE_RESULT.exists()
        else
        _load(NUMERIC_AUTHORITY_DECISION)["conditional_next_action"][
            "on_authority_decision_complete"
        ]
        if NUMERIC_AUTHORITY_DECISION.exists()
        else
        _load(NUMERIC_AUTHORITY_ISSUANCE)["next_action"]
        if NUMERIC_AUTHORITY_ISSUANCE.exists()
        else _load(NUMERIC_AUTHORITY_PROOF)["next_action"]
        if NUMERIC_AUTHORITY_PROOF.exists()
        else _load(NUMERIC_AUTHORITY_IMPLEMENTATION)["next_action"]
        if NUMERIC_AUTHORITY_IMPLEMENTATION.exists()
        else
        _load(NUMERIC_AUTHORITY_DISPOSITION)["next_action"]
        if NUMERIC_AUTHORITY_DISPOSITION.exists()
        else _load(R3_FAILURE_RESULT)["next_action"]
        if R3_FAILURE_RESULT.exists()
        else
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-"
        "PREFLIGHT-ZERO-CALL-IMPLEMENTATION"
    )
    assert program["next_action"]["current_S4_T03_authorized"] is True
    assert program["next_action"]["current_S4_T03_completed"] is True
    assert program["next_action"]["current_S4_T04_authorized"] is True
    assert program["next_action"]["current_S4_T04_decision_completed"] is True
    assert program["next_action"]["current_S4_T04_completed"] is True
    assert program["next_action"]["current_S4_T04_admission_issued"] is True
    assert program["next_action"]["current_S4_T04_admission_consumed"] is True
    assert program["next_action"]["current_S4_T04_execution_started"] is True
    assert program["next_action"]["current_S4_case_execution_authorized"] is True
    assert all(value == 0 for value in decision["observed_counts"].values())
    assert decision["stage_decision"]["DELL_R2"] == "not_started"
    assert decision["stage_decision"]["MU_R2"] == "not_started"
    assert decision["stage_decision"]["NVDA_R3"] == "not_started"
    assert decision["stage_decision"]["S4_pass"] is False
