from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_official_first_portfolio import (  # noqa: E402
    RUN_SCOPE,
    ReplayCandidateObservation,
    S108OfficialFirstPortfolioError,
    adjudicate_replay_candidate,
    compile_portfolio_route_plan,
    load_portfolio_policy,
    run_portfolio_zero_call_replay,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


PORTFOLIO_POLICY = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_official_first_portfolio_policy_v1_0.json"
)
SEARCH_POLICY = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
)
CATALOG = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
VISIBLE = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
FIRECRAWL_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json"
FIRECRAWL_ASSESSMENT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
TENCENT_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_result_v1_0.json"
TENCENT_ASSESSMENT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_assessment_v1_0.json"
DELL_R2 = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0.json"
OFFICIAL_CLOSEOUT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_freshness_reopen_s1_02_numeric_successor_and_s1_03_official_source_closeout_v1_0.json"
PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_official_first_portfolio_zero_call_proof_v1_0.json"
CLEAN_PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_official_first_portfolio_clean_independent_zero_call_proof_v1_0.json"
PROGRESSION_PLAN = ROOT / "configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_0.json"
CLEAN_PROOF_SCOPE = (
    "S1_08_OFFICIAL_FIRST_PORTFOLIO_CLEAN_INDEPENDENT_ZERO_CALL_PROOF"
)
QUERY_FACET_SCOPE = "S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


@pytest.fixture(scope="module")
def compiled() -> tuple[dict, dict]:
    policy = load_portfolio_policy(PORTFOLIO_POLICY)
    visible = _load(VISIBLE)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(CATALOG),
        policy=load_search_intent_policy(SEARCH_POLICY),
        research_objectives=objectives,
    )
    return policy, compile_portfolio_route_plan(intents=intents, policy=policy)


def test_policy_is_bound_to_immutable_inputs_and_excludes_tencent() -> None:
    policy = load_portfolio_policy(PORTFOLIO_POLICY)
    assert policy["binding_hash_profile"] == "sha256_utf8_lf_normalized_v1"
    refs = policy["immutable_replay_inputs"]
    pairs = (
        (refs["firecrawl_result_ref"], refs["firecrawl_result_sha256"]),
        (refs["firecrawl_assessment_ref"], refs["firecrawl_assessment_sha256"]),
        (refs["tencent_result_ref"], refs["tencent_result_sha256"]),
        (refs["tencent_assessment_ref"], refs["tencent_assessment_sha256"]),
        (refs["dell_r2_ref"], refs["dell_r2_sha256"]),
        (
            refs["official_source_closeout_ref"],
            refs["official_source_closeout_sha256"],
        ),
    )
    assert all(_sha256(ROOT / ref) == expected for ref, expected in pairs)
    assert policy["excluded_providers"]["tencent_wsa_searchpro_standard"] == (
        "diagnostic_only_not_selected"
    )
    assert policy["lanes"]["semantic_open_web_shadow_lane"][
        "evidence_promotion_allowed"
    ] is False


def test_route_plan_gives_every_slot_an_opportunity_without_granting_authority(
    compiled: tuple[dict, dict],
) -> None:
    _, plan = compiled
    assert plan["lane_counts"] == {
        "official_primary_lane": 36,
        "semantic_open_web_shadow_lane": 24,
    }
    assert plan["required_slots_with_route_opportunity"] == 12
    assert plan["required_slots_total"] == 12
    assert plan["tencent_selected_assignment_count"] == 0
    assert all(
        row["financial_authority"] is False
        and row["evidence_promotion_allowed"] is False
        for row in plan["assignments"]
    )
    assert all(
        set(slots) == {
            "issuer_results_and_management_commentary",
            "regulatory_risk_and_financial_reconciliation",
            "customer_demand_and_deployment_validation",
            "supply_chain_capacity_and_counterevidence",
        }
        for slots in plan["slot_coverage"].values()
    )
    serialized = json.dumps(plan, ensure_ascii=False)
    assert "SRC_" not in serialized
    assert all(
        "tencent" not in str(row["provider"]).lower()
        and "tencent" not in " ".join(row["route_ids"]).lower()
        for row in plan["assignments"]
    )


def test_portfolio_replay_separates_locator_recall_from_evidence_qualification(
    compiled: tuple[dict, dict],
) -> None:
    policy, plan = compiled
    result = run_portfolio_zero_call_replay(
        policy=policy,
        route_plan=plan,
        firecrawl_result=_load(FIRECRAWL_RESULT),
        firecrawl_assessment=_load(FIRECRAWL_ASSESSMENT),
        tencent_result=_load(TENCENT_RESULT),
        tencent_assessment=_load(TENCENT_ASSESSMENT),
        dell_r2_result=_load(DELL_R2),
        official_source_closeout=_load(OFFICIAL_CLOSEOUT),
    )
    card = result["search_quality_card"]
    assert card["locator_route_contribution"][
        "firecrawl_relational_case_slot_target_in_pool"
    ] == [5, 6]
    assert card["locator_route_contribution"][
        "tencent_relational_case_slot_target_in_pool"
    ] == [0, 6]
    assert card["locator_route_contribution"][
        "provider_date_financial_authority"
    ] is False
    assert card["capture_and_local_authority"] == {
        "dell_r2_historical_qualification_bindings_replayed": 2,
        "dell_r2_unique_canonical_documents": 1,
        "official_r4_accepted_evidence": 11,
        "official_r4_attempt_backed_typed_gaps": 6,
        "official_semantic_role_bindings": 9,
        "official_semantic_unique_canonical_documents": 3,
        "new_document_fetches": 0,
        "new_evidence_promotions": 0,
    }
    assert card["typed_route_gaps"] == [
        {
            "case_key": "DELL",
            "evidence_slot_id": "supply_chain_capacity_and_counterevidence",
            "code": "required_relational_target_absent_after_shadow_locator_replay",
            "source_exhaustion_proven": False,
            "ranking_admitted": False,
        }
    ]
    assert card["portfolio_evidence_qualification"]["ranking_admitted"] is False
    assert result["observed_calls"] == {
        "provider": 0,
        "network": 0,
        "model": 0,
        "document_fetch": 0,
        "evidence_promotion": 0,
    }


def _baseline_observation() -> ReplayCandidateObservation:
    digest = "a" * 64
    return ReplayCandidateObservation(
        candidate_id="baseline",
        case_key="DELL",
        subject_entity_key="DELL",
        evidence_slot_id="issuer_results_and_management_commentary",
        evidence_owner_entity_key="DELL",
        expected_evidence_owner_entity_key="DELL",
        claim_direction="subject_self_disclosure",
        expected_claim_direction="subject_self_disclosure",
        lane_id="official_primary_lane",
        locator="https://www.sec.gov/Archives/example.htm",
        source_family="regulatory_filing",
        authority="regulatory_primary",
        provider_reported_date="2099-01-01",
        local_publication_date="2026-07-06",
        local_date_kind="publication_date",
        local_date_source="capture_backed_official_parser",
        capture_ref="objects/source.json",
        capture_digest=digest,
        parser_ref="objects/parser.json",
        parser_digest=digest,
        canonical_identity_verified=True,
        historical_promotion_receipt=True,
    )


def test_provider_date_cannot_override_local_date_and_mutations_fail_closed() -> None:
    baseline = _baseline_observation()
    accepted = adjudicate_replay_candidate(
        observation=baseline, as_of_date="2026-08-06"
    )
    assert accepted["state"] == "historical_evidence_qualification_replayed"
    assert accepted["provider_date_treated_as_telemetry_only"] is True
    cases = (
        (replace(baseline, subject_entity_key="MU"), "cross_case_subject_binding_invalid"),
        (
            replace(baseline, evidence_owner_entity_key="MU"),
            "evidence_owner_binding_mismatch",
        ),
        (
            replace(baseline, claim_direction="wrong_direction"),
            "relationship_direction_mismatch",
        ),
        (
            replace(baseline, lane_id="semantic_open_web_shadow_lane"),
            "shadow_lane_promotion_forbidden",
        ),
        (
            replace(baseline, local_publication_date="2026-08-07"),
            "local_publication_date_after_as_of",
        ),
    )
    for mutation, expected_reason in cases:
        rejected = adjudicate_replay_candidate(
            observation=mutation, as_of_date="2026-08-06"
        )
        assert rejected["state"] == "rejected"
        assert expected_reason in rejected["reason_codes"]


def test_shadow_candidate_without_capture_stays_candidate_only() -> None:
    row = replace(
        _baseline_observation(),
        candidate_id="shadow",
        evidence_slot_id="supply_chain_capacity_and_counterevidence",
        evidence_owner_entity_key="MU",
        expected_evidence_owner_entity_key="MU",
        claim_direction="evidence_owner_own_supply_capacity_or_constraint",
        expected_claim_direction="evidence_owner_own_supply_capacity_or_constraint",
        lane_id="semantic_open_web_shadow_lane",
        local_publication_date="",
        local_date_kind="",
        local_date_source="",
        capture_ref="",
        capture_digest="",
        parser_ref="",
        parser_digest="",
        canonical_identity_verified=False,
        historical_promotion_receipt=False,
    )
    result = adjudicate_replay_candidate(observation=row, as_of_date="2026-08-06")
    assert result["state"] == "candidate_only_capture_and_evidence_gate_required"
    assert result["new_evidence_promotion_created"] is False


def test_materialized_proof_is_digest_bound_and_honest() -> None:
    proof = _load(PROOF)
    body = dict(proof)
    supplied = body.pop("proof_digest")
    assert supplied == canonical_digest(body)
    assert proof["status"] == "zero_call_engineering_pass"
    assert proof["stage_acceptance"] == {
        "portfolio_runtime_contract": True,
        "combined_zero_call_replay": True,
        "fresh_combined_live": False,
        "query_facet_plan": False,
        "internal_retrieval": False,
        "ranking": False,
        "S1_08": False,
        "S3": False,
        "release": False,
    }


def test_clean_independent_proof_is_digest_bound_and_honest() -> None:
    proof = _load(CLEAN_PROOF)
    body = dict(proof)
    supplied = body.pop("result_digest")
    assert supplied == canonical_digest(body)
    assert proof["status"] == (
        "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible"
    )
    assert proof["source_commit"] == {
        "branch": "codex/layered-data-source-expansion",
        "clean": True,
        "commit": "5599219361dd0dd742a308f8230c57c26fa427f4",
        "synced": True,
        "upstream_commit": "5599219361dd0dd742a308f8230c57c26fa427f4",
    }
    independent = proof["independent_proof"]
    assert independent["clean_git_archives"] == 2
    assert independent["fresh_python_processes"] == 2
    assert independent["normalized_outputs_equal"] is True
    assert independent["worker_result"]["pytest"]["passed"] == 45
    assert not any(proof["observed_calls"].values())
    assert proof["decision"]["next_scope"] == QUERY_FACET_SCOPE


def test_external_then_internal_query_facet_and_rerank_sequence_is_durable() -> None:
    plan = _load(PROGRESSION_PLAN)
    scope_registry = _load(
        ROOT
        / "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json"
    )
    body = dict(plan)
    supplied = body.pop("plan_digest")
    assert supplied == canonical_digest(body)
    rows = plan["execution_sequence"]
    assert [row["order"] for row in rows] == list(range(1, 10))
    assert rows[4]["work_item"] == (
        "S1_08_OFFICIAL_ROUTES_PLUS_FIRECRAWL_SHADOW_COMBINED_LIVE"
    )
    assert rows[5]["work_item"] == "S1_INTERNAL_RETRIEVAL_QUERY_FACET_INTEGRATION"
    assert rows[7]["work_item"] == "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
    assert rows[7]["status"] == "not_admitted_until_candidate_ceiling_passes"
    assert plan["hard_gates"]["target_absent_from_pool"] == (
        "ranking_not_admitted"
    )
    assert all(
        row["work_item"] in scope_registry["scopes"]
        for row in rows
    )
    assert not any(plan["calls_authorized_by_this_plan"].values())


def test_current_project_os_scope_allows_only_the_query_facet_successor() -> None:
    completed = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert completed["status"] == "blocked"
    assert completed["contract_errors"] == []
    clean_proof = run_project_os_preflight(ROOT, run_scope=CLEAN_PROOF_SCOPE)
    assert clean_proof["status"] == "blocked"
    assert clean_proof["contract_errors"] == []
    successor = run_project_os_preflight(ROOT, run_scope=QUERY_FACET_SCOPE)
    assert successor["status"] == "pass"
    assert successor["contract_errors"] == []


def test_route_plan_digest_mutation_is_rejected(compiled: tuple[dict, dict]) -> None:
    policy, plan = compiled
    mutated = json.loads(json.dumps(plan))
    mutated["required_slots_with_route_opportunity"] = 11
    with pytest.raises(
        S108OfficialFirstPortfolioError,
        match="s1_08_official_first_portfolio_route_plan_invalid",
    ):
        run_portfolio_zero_call_replay(
            policy=policy,
            route_plan=mutated,
            firecrawl_result=_load(FIRECRAWL_RESULT),
            firecrawl_assessment=_load(FIRECRAWL_ASSESSMENT),
            tencent_result=_load(TENCENT_RESULT),
            tencent_assessment=_load(TENCENT_ASSESSMENT),
            dell_r2_result=_load(DELL_R2),
            official_source_closeout=_load(OFFICIAL_CLOSEOUT),
        )
