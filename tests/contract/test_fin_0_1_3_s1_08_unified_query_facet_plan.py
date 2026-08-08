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
from sec_agent.s1_08_query_facet_plan import (  # noqa: E402
    ModelQueryAtomCandidate,
    S108QueryFacetError,
    compile_query_facet_plans,
    load_query_facet_policy,
    validate_query_facet_plan,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_unified_query_facet_policy_v1_0.json"
)
SEARCH_POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
)
CATALOG_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
PROOF_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_unified_query_facet_zero_call_proof_v1_0.json"
)
QUERY_SCOPE = "S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION"
CLEAN_SCOPE = "S1_08_OFFICIAL_FIRST_PORTFOLIO_CLEAN_INDEPENDENT_ZERO_CALL_PROOF"
THREE_WAY_SCOPE = "S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.fixture(scope="module")
def compiled() -> tuple[dict, tuple]:
    policy = load_query_facet_policy(POLICY_PATH)
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(CATALOG_PATH),
        policy=load_search_intent_policy(SEARCH_POLICY_PATH),
        research_objectives=objectives,
    )
    return policy, compile_query_facet_plans(intents=intents, policy=policy)


def test_policy_binds_clean_predecessor_and_all_inputs_portably() -> None:
    policy = load_query_facet_policy(POLICY_PATH)
    assert policy["binding_hash_profile"] == "sha256_utf8_lf_normalized_v1"
    refs = policy["immutable_inputs"]
    for stem in (
        "search_intent_policy",
        "source_catalog",
        "model_visible_case_pack",
        "progression_plan",
        "clean_portfolio_proof",
    ):
        assert _normalized_sha256(ROOT / refs[f"{stem}_ref"]) == refs[
            f"{stem}_sha256"
        ]
    clean = _load(ROOT / refs["clean_portfolio_proof_ref"])
    assert clean["status"] == (
        "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible"
    )
    assert clean["decision"]["next_scope"] == QUERY_SCOPE


def test_sixty_route_intents_coalesce_into_thirty_six_shared_facet_plans(
    compiled: tuple[dict, tuple],
) -> None:
    _, plans = compiled
    assert len(plans) == 36
    assert len({item for plan in plans for item in plan.source_intent_ids}) == 60
    assert len({(plan.case_key, plan.evidence_slot_id) for plan in plans}) == 12
    assert sum(
        "external_official_primary" in plan.eligible_external_routes
        for plan in plans
    ) == 36
    assert sum(
        "external_semantic_shadow" in plan.eligible_external_routes
        for plan in plans
    ) == 24
    assert all(
        set(plan.eligible_internal_routes)
        == {
            "internal_exact_object_lookup",
            "internal_bm25",
            "internal_dense",
            "internal_relationship_graph",
        }
        for plan in plans
    )


def test_queries_prioritize_the_evidence_owner_and_financial_mechanism(
    compiled: tuple[dict, tuple],
) -> None:
    _, plans = compiled

    def one(case: str, slot: str, owner: str, language: str = "en"):
        return next(
            plan
            for plan in plans
            if (
                plan.case_key,
                plan.evidence_slot_id,
                plan.evidence_owner_entity_key,
                plan.language,
            )
            == (case, slot, owner, language)
        )

    dell_customer = one(
        "DELL", "customer_demand_and_deployment_validation", "MSFT"
    )
    assert dell_customer.product_facets[0] == "Azure AI infrastructure"
    assert "Microsoft" in dell_customer.exact_lookup_queries[0]
    assert "capital expenditure" in " ".join(dell_customer.lexical_queries)

    mu_issuer = one("MU", "issuer_results_and_management_commentary", "MU")
    assert mu_issuer.product_facets[0] == "HBM output"
    assert "HBM" in " ".join(mu_issuer.exact_lookup_queries)
    assert "gross margin" in " ".join(mu_issuer.lexical_queries)

    nvda_memory = one(
        "NVDA", "supply_chain_capacity_and_counterevidence", "MU"
    )
    assert nvda_memory.product_facets[0] == "HBM output"
    assert "supply ramp" in nvda_memory.semantic_queries[0]

    nvda_foundry = one(
        "NVDA", "supply_chain_capacity_and_counterevidence", "TSMC"
    )
    assert nvda_foundry.product_facets[0] == "CoWoS capacity"
    assert "TSMC" in nvda_foundry.exact_lookup_queries[0]


def test_every_plan_has_route_specific_queries_filters_and_graph_scope(
    compiled: tuple[dict, tuple],
) -> None:
    _, plans = compiled
    for plan in plans:
        assert len(plan.exact_lookup_queries) >= 2
        assert len(plan.lexical_queries) >= 2
        assert len(plan.semantic_queries) >= 1
        assert plan.negative_queries
        filters = plan.route_specific_filters
        assert filters["case_key"] == plan.case_key
        assert filters["subject_entity_key"] == plan.subject_entity_key
        assert filters["evidence_owner_entity_key"] == plan.evidence_owner_entity_key
        assert filters["relationship_direction"] == plan.relationship_direction
        assert filters["publication_date_on_or_before"] == plan.as_of_date
        assert filters["execution_admitted"] is False
        assert filters["allow_relaxed_identity_or_period_fallback"] is False
        graph = plan.graph_query
        assert graph["subject_entity_key"] == plan.case_key
        assert graph["evidence_owner_entity_key"] == plan.evidence_owner_entity_key
        assert graph["relationship_direction"] == plan.relationship_direction
        assert graph["maximum_hops"] == 1


def test_model_atoms_can_only_add_bounded_non_authoritative_facets(
    compiled: tuple[dict, tuple],
) -> None:
    policy, base_plans = compiled
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(CATALOG_PATH),
        policy=load_search_intent_policy(SEARCH_POLICY_PATH),
        research_objectives=objectives,
    )
    atom = ModelQueryAtomCandidate(
        case_key="NVDA",
        evidence_slot_id="supply_chain_capacity_and_counterevidence",
        evidence_owner_entity_key="TSMC",
        language="en",
        atom_kind="mechanism",
        value="liquid cooling constraint",
    )
    assisted = compile_query_facet_plans(
        intents=intents, policy=policy, model_atoms=(atom,)
    )
    base = next(
        plan
        for plan in base_plans
        if (
            plan.case_key,
            plan.evidence_slot_id,
            plan.evidence_owner_entity_key,
            plan.language,
        )
        == ("NVDA", "supply_chain_capacity_and_counterevidence", "TSMC", "en")
    )
    changed = next(plan for plan in assisted if plan.accepted_model_atoms)
    assert changed.subject_entity_key == base.subject_entity_key
    assert changed.evidence_owner_entity_key == base.evidence_owner_entity_key
    assert changed.period_terms == base.period_terms
    assert changed.relationship_direction == base.relationship_direction
    assert changed.route_specific_filters == base.route_specific_filters
    assert "liquid cooling constraint" in changed.mechanism_facets
    assert "liquid cooling constraint" in " ".join(changed.lexical_queries)
    assert "liquid cooling constraint" in " ".join(changed.semantic_queries)
    assert changed.plan_digest != base.plan_digest


@pytest.mark.parametrize(
    "atoms,expected",
    [
        (
            (
                ModelQueryAtomCandidate(
                    case_key="DELL",
                    evidence_slot_id="customer_demand_and_deployment_validation",
                    evidence_owner_entity_key="TSMC",
                    language="en",
                    atom_kind="metric",
                    value="capacity",
                ),
            ),
            "s1_08_query_facet_model_atom_scope_invalid",
        ),
        (
            (
                ModelQueryAtomCandidate(
                    case_key="DELL",
                    evidence_slot_id="customer_demand_and_deployment_validation",
                    evidence_owner_entity_key="MSFT",
                    language="en",
                    atom_kind="product",
                    value="https://example.com/answer",
                ),
            ),
            "s1_08_query_facet_model_atom_authority_violation",
        ),
        (
            (
                ModelQueryAtomCandidate(
                    case_key="DELL",
                    evidence_slot_id="customer_demand_and_deployment_validation",
                    evidence_owner_entity_key="MSFT",
                    language="en",
                    atom_kind="metric",
                    value="FY2028 capital expenditure",
                ),
            ),
            "s1_08_query_facet_model_atom_authority_violation",
        ),
        (
            (
                ModelQueryAtomCandidate(
                    case_key="DELL",
                    evidence_slot_id="customer_demand_and_deployment_validation",
                    evidence_owner_entity_key="MSFT",
                    language="en",
                    atom_kind="synonym",
                    value="Microsoft",
                ),
            ),
            "s1_08_query_facet_model_atom_authority_violation",
        ),
    ],
)
def test_model_atom_identity_period_url_and_scope_mutations_fail_closed(
    compiled: tuple[dict, tuple], atoms: tuple, expected: str
) -> None:
    policy, _ = compiled
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(CATALOG_PATH),
        policy=load_search_intent_policy(SEARCH_POLICY_PATH),
        research_objectives=objectives,
    )
    with pytest.raises(S108QueryFacetError, match=expected):
        compile_query_facet_plans(
            intents=intents,
            policy=policy,
            model_atoms=atoms,
        )


def test_duplicate_and_over_budget_model_atoms_fail_closed(
    compiled: tuple[dict, tuple],
) -> None:
    policy, _ = compiled
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(CATALOG_PATH),
        policy=load_search_intent_policy(SEARCH_POLICY_PATH),
        research_objectives=objectives,
    )

    def atom(value: str) -> ModelQueryAtomCandidate:
        return ModelQueryAtomCandidate(
            case_key="MU",
            evidence_slot_id="issuer_results_and_management_commentary",
            evidence_owner_entity_key="MU",
            language="en",
            atom_kind="mechanism",
            value=value,
        )

    with pytest.raises(
        S108QueryFacetError, match="s1_08_query_facet_model_atom_budget_invalid"
    ):
        compile_query_facet_plans(
            intents=intents, policy=policy, model_atoms=(atom("yield ramp"),) * 2
        )
    with pytest.raises(
        S108QueryFacetError, match="s1_08_query_facet_model_atom_budget_invalid"
    ):
        compile_query_facet_plans(
            intents=intents,
            policy=policy,
            model_atoms=tuple(atom(f"mechanism {index}") for index in range(7)),
        )


def test_input_permutation_is_stable_and_plan_mutation_is_rejected(
    compiled: tuple[dict, tuple],
) -> None:
    policy, plans = compiled
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(CATALOG_PATH),
        policy=load_search_intent_policy(SEARCH_POLICY_PATH),
        research_objectives=objectives,
    )
    reversed_plans = compile_query_facet_plans(
        intents=tuple(reversed(intents)), policy=policy
    )
    assert [plan.plan_digest for plan in reversed_plans] == [
        plan.plan_digest for plan in plans
    ]
    mutated = replace(
        plans[0], lexical_queries=plans[0].lexical_queries + ("cross case leak",)
    )
    with pytest.raises(
        S108QueryFacetError, match="s1_08_query_facet_owned_identity_invalid"
    ):
        validate_query_facet_plan(mutated, policy=policy)


def test_materialized_proof_is_digest_bound_zero_call_and_honest() -> None:
    proof = _load(PROOF_PATH)
    body = dict(proof)
    supplied = body.pop("proof_digest")
    assert supplied == canonical_digest(body)
    assert proof["status"] == "zero_call_engineering_pass"
    assert proof["plan_count"] == 36
    assert proof["bound_search_intent_count"] == 60
    assert proof["external_route_counts"] == {
        "external_official_primary": 36,
        "external_semantic_shadow": 24,
    }
    assert proof["query_family_counts"] == {
        "exact_lookup_queries": 72,
        "lexical_queries": 72,
        "semantic_queries": 36,
        "graph_queries": 36,
        "negative_queries": 754,
    }
    assert not any(proof["observed_calls"].values())
    assert proof["quality_checks"]["model_atom_count"] == 0
    assert proof["quality_checks"]["candidate_ceiling_proven"] is False
    assert proof["quality_checks"]["BGE_or_rerank_admitted"] is False
    assert proof["stage_acceptance"]["three_way_evaluation"] is False
    assert proof["stage_acceptance"]["combined_external_live"] is False
    assert proof["stage_acceptance"]["internal_retrieval_integration"] is False


def test_project_os_advances_from_query_facet_to_three_way_evaluation() -> None:
    completed = run_project_os_preflight(ROOT, run_scope=CLEAN_SCOPE)
    assert completed["status"] == "blocked"
    assert completed["contract_errors"] == []
    implemented = run_project_os_preflight(ROOT, run_scope=QUERY_SCOPE)
    assert implemented["status"] == "blocked"
    assert implemented["contract_errors"] == []
    current = run_project_os_preflight(ROOT, run_scope=THREE_WAY_SCOPE)
    assert current["status"] == "pass"
    assert current["contract_errors"] == []
