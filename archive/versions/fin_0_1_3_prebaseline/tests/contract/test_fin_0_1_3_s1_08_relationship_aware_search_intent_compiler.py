from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from sec_agent.s1_08_candidate_generation_runtime import (
    canonical_digest,
    load_source_catalog,
)
from sec_agent.s1_08_search_intent_compiler import (
    CASES,
    EXTERNAL_SLOT_IDS,
    S108SearchIntentError,
    SourceIdentity,
    compile_bounded_query_plans,
    compile_search_intents,
    evaluate_source_equivalence,
    load_search_intent_policy,
    match_source_identity,
    validate_search_intent,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
PROOF_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_and_source_equivalence_zero_call_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict[str, str]]:
    catalog = load_source_catalog(CATALOG_PATH)
    policy = load_search_intent_policy(POLICY_PATH)
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    return catalog, policy, objectives


def _intents():
    catalog, policy, objectives = _inputs()
    return (
        catalog,
        policy,
        objectives,
        compile_search_intents(
            catalog=catalog,
            policy=policy,
            research_objectives=objectives,
        ),
    )


def _source_identity(
    *,
    identity_id: str,
    locator: str,
    case_key: str = "DELL",
    owner_key: str = "DELL",
    source_family: str = "issuer_ir_document",
    document_kind: str = "earnings_release",
    published_on: str = "2026-07-01",
    authority: str = "issuer_primary",
    **kwargs,
) -> SourceIdentity:
    return SourceIdentity(
        identity_id=identity_id,
        case_key=case_key,
        evidence_owner_entity_key=owner_key,
        source_family=source_family,
        document_kind=document_kind,
        published_on=published_on,
        authority=authority,
        locator=locator,
        **kwargs,
    )


def test_compiler_fans_out_by_counterpart_and_separates_route_budgets() -> None:
    _, policy, _, intents = _intents()
    plans = compile_bounded_query_plans(intents=intents, policy=policy)
    assert len(intents) == 60
    assert plans["plans"]["precise_official_domain"]["query_count"] == 36
    assert plans["plans"]["semantic_open_web"]["query_count"] == 24
    assert plans["provider_calls_authorized"] == 0
    assert plans["model_calls_authorized"] == 0

    expected_owners = {
        ("DELL", "customer_demand_and_deployment_validation"): {"MSFT"},
        ("DELL", "supply_chain_capacity_and_counterevidence"): {
            "MU",
            "NVDA",
            "TSMC",
        },
        ("MU", "customer_demand_and_deployment_validation"): {"DELL", "MSFT"},
        ("MU", "supply_chain_capacity_and_counterevidence"): {"NVDA", "TSMC"},
        ("NVDA", "customer_demand_and_deployment_validation"): {"DELL", "MSFT"},
        ("NVDA", "supply_chain_capacity_and_counterevidence"): {"MU", "TSMC"},
    }
    for key, owners in expected_owners.items():
        observed = {
            row.evidence_owner_entity_key
            for row in intents
            if (row.case_key, row.evidence_slot_id) == key
        }
        assert observed == owners


def test_provider_visible_queries_bind_owner_subject_direction_period_and_language() -> None:
    _, policy, objectives, intents = _intents()
    serialized = json.dumps([row.as_dict() for row in intents], ensure_ascii=False)
    assert "https://" not in serialized
    assert "SRC_" not in serialized
    assert "DELL_E" not in serialized
    assert all(objective not in serialized for objective in objectives.values())
    assert len({row.query_text for row in intents}) == len(intents)
    assert max(len(row.query_text) for row in intents) <= 300
    for intent in intents:
        folded = intent.query_text.casefold()
        assert any(alias.casefold() in folded for alias in intent.evidence_owner_aliases)
        assert all(term.casefold() in folded for term in intent.period_terms)
        direction_terms = policy["claim_direction_terms"][intent.claim_direction][
            intent.language
        ]
        assert all(str(term).casefold() in folded for term in direction_terms)
        if intent.evidence_owner_entity_key != intent.subject_entity_key:
            assert any(alias.casefold() in folded for alias in intent.subject_aliases)
        assert len(intent.research_objective_digest) == 64
        assert intent.preferred_domains


def test_input_permutation_does_not_change_intents_or_plan_digest() -> None:
    catalog, policy, objectives, first = _intents()
    mutated_catalog = deepcopy(catalog)
    mutated_catalog["entities"] = list(reversed(mutated_catalog["entities"]))
    mutated_catalog["evidence_role_blueprints"] = list(
        reversed(mutated_catalog["evidence_role_blueprints"])
    )
    second = compile_search_intents(
        catalog=mutated_catalog,
        policy=deepcopy(policy),
        research_objectives=dict(reversed(list(objectives.items()))),
    )
    assert [row.as_dict() for row in first] == [row.as_dict() for row in second]
    assert compile_bounded_query_plans(
        intents=first, policy=policy
    ) == compile_bounded_query_plans(intents=second, policy=policy)


def test_alias_collision_fails_before_compilation(tmp_path: Path) -> None:
    policy = _load(POLICY_PATH)
    policy["entity_search_profiles"]["MSFT"]["localized_aliases"]["en"].append(
        "Dell"
    )
    path = tmp_path / "alias_collision.json"
    path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(S108SearchIntentError) as exc:
        load_search_intent_policy(path)
    assert exc.value.code == "s1_08_search_intent_alias_collision"


def test_cross_case_wrong_direction_future_and_budget_mutations_fail_closed() -> None:
    catalog, policy, objectives, intents = _intents()
    customer = next(
        row
        for row in intents
        if row.case_key == "DELL"
        and row.evidence_slot_id == "customer_demand_and_deployment_validation"
        and row.language == "en"
        and row.route_class == "precise_official_domain"
    )
    with pytest.raises(S108SearchIntentError) as exc:
        validate_search_intent(
            intent=replace(customer, subject_entity_key="MU"),
            catalog=catalog,
            policy=policy,
            research_objective=objectives["DELL"],
        )
    assert exc.value.code == "s1_08_search_intent_cross_case_subject"

    with pytest.raises(S108SearchIntentError) as exc:
        validate_search_intent(
            intent=replace(
                customer,
                evidence_owner_entity_key="TSMC",
                evidence_owner_role="foundry",
            ),
            catalog=catalog,
            policy=policy,
            research_objective=objectives["DELL"],
        )
    assert exc.value.code == "s1_08_search_intent_wrong_relationship_direction"

    with pytest.raises(S108SearchIntentError) as exc:
        validate_search_intent(
            intent=replace(customer, as_of_date="2026-08-07"),
            catalog=catalog,
            policy=policy,
            research_objective=objectives["DELL"],
        )
    assert exc.value.code == "s1_08_search_intent_future_as_of"

    lower_budget = deepcopy(policy)
    lower_budget["query_plan_budgets"][
        "precise_official_domain_query_ceiling"
    ] = 35
    with pytest.raises(S108SearchIntentError) as exc:
        compile_bounded_query_plans(intents=intents, policy=lower_budget)
    assert exc.value.code == "s1_08_search_intent_fanout_budget_not_closed"


@pytest.mark.parametrize(
    ("candidate", "expected_class", "expected_basis"),
    [
        (
            _source_identity(
                identity_id="candidate-exact",
                locator="https://issuer.example/report",
            ),
            "exact_locator_match",
            "exact_locator",
        ),
        (
            _source_identity(
                identity_id="candidate-canonical",
                locator="https://issuer.example/alias",
                canonical_locator="https://issuer.example/report",
                canonical_locator_verified=True,
            ),
            "typed_source_equivalent_match",
            "verified_canonical_locator",
        ),
        (
            _source_identity(
                identity_id="candidate-redirect",
                locator="https://issuer.example/redirect",
                redirect_final_locator="https://issuer.example/report",
                redirect_verified=True,
            ),
            "typed_source_equivalent_match",
            "verified_redirect_final_locator",
        ),
        (
            _source_identity(
                identity_id="candidate-content",
                locator="https://cdn.example/report.pdf",
                content_sha256="a" * 64,
                content_identity_verified=True,
            ),
            "typed_source_equivalent_match",
            "verified_content_identity",
        ),
    ],
)
def test_typed_source_equivalence_accepts_only_auditable_bases(
    candidate: SourceIdentity, expected_class: str, expected_basis: str
) -> None:
    reference = _source_identity(
        identity_id="reference",
        locator="https://issuer.example/report",
        content_sha256="a" * 64,
        content_identity_verified=True,
    )
    result = match_source_identity(
        candidate=candidate, reference=reference, as_of_date="2026-08-06"
    )
    assert result["match_class"] == expected_class
    assert result["basis"] == expected_basis


def test_sec_accession_equivalence_is_typed_and_identity_bound() -> None:
    reference = _source_identity(
        identity_id="reference-sec",
        locator="https://www.sec.gov/Archives/reference.htm",
        source_family="regulatory_filing",
        document_kind="10-Q",
        authority="regulatory_primary",
        sec_accession="000157199626000008",
    )
    candidate = replace(
        reference,
        identity_id="candidate-sec",
        locator="https://issuer.example/sec-mirror.htm",
        sec_accession="0001571996-26-000008",
    )
    result = match_source_identity(
        candidate=candidate, reference=reference, as_of_date="2026-08-06"
    )
    assert result["match_class"] == "typed_source_equivalent_match"
    assert result["basis"] == "sec_accession"


def test_same_event_unverified_alias_wrong_identity_and_future_date_do_not_match() -> None:
    reference = _source_identity(
        identity_id="reference",
        locator="https://issuer.example/prepared-remarks",
        document_kind="prepared_remarks",
    )
    same_event_different_document = _source_identity(
        identity_id="same-event",
        locator="https://issuer.example/press-release",
        document_kind="press_release",
    )
    assert match_source_identity(
        candidate=same_event_different_document,
        reference=reference,
        as_of_date="2026-08-06",
    )["basis"] == "source_identity_boundary_mismatch"

    unverified_alias = replace(
        reference,
        identity_id="unverified",
        locator="https://issuer.example/alias",
        canonical_locator=reference.locator,
        canonical_locator_verified=False,
    )
    assert match_source_identity(
        candidate=unverified_alias,
        reference=reference,
        as_of_date="2026-08-06",
    )["basis"] == "no_typed_source_identity_equivalence"

    wrong_owner = replace(
        reference,
        identity_id="wrong-owner",
        locator="https://other.example/report",
        evidence_owner_entity_key="MSFT",
    )
    assert match_source_identity(
        candidate=wrong_owner, reference=reference, as_of_date="2026-08-06"
    )["basis"] == "source_identity_boundary_mismatch"

    future = replace(
        reference,
        identity_id="future",
        locator="https://issuer.example/future",
        published_on="2026-08-07",
    )
    assert match_source_identity(
        candidate=future, reference=reference, as_of_date="2026-08-06"
    )["basis"] == "candidate_after_as_of"


def test_three_case_full_fake_source_equivalence_is_deterministic() -> None:
    _, _, _, intents = _intents()
    official = [
        row for row in intents if row.route_class == "precise_official_domain"
    ]
    references: list[SourceIdentity] = []
    candidates: list[SourceIdentity] = []
    for index, intent in enumerate(official):
        locator = f"https://official.example/{index}/document"
        document_kind = (
            "regulatory_filing"
            if intent.evidence_slot_id
            == "regulatory_risk_and_financial_reconciliation"
            else "official_disclosure"
        )
        content_digest = canonical_digest({"document": index})
        reference = _source_identity(
            identity_id=f"reference-{index:02d}",
            locator=locator,
            case_key=intent.case_key,
            owner_key=intent.evidence_owner_entity_key,
            source_family=intent.source_families[0],
            document_kind=document_kind,
            content_sha256=content_digest,
            content_identity_verified=True,
        )
        references.append(reference)
        if index % 3 == 0:
            candidate = replace(reference, identity_id=f"candidate-{index:02d}")
        elif index % 3 == 1:
            candidate = replace(
                reference,
                identity_id=f"candidate-{index:02d}",
                locator=f"https://alias.example/{index}",
                canonical_locator=locator,
                canonical_locator_verified=True,
                content_sha256="",
                content_identity_verified=False,
            )
        else:
            candidate = replace(
                reference,
                identity_id=f"candidate-{index:02d}",
                locator=f"https://cdn.example/{index}.pdf",
            )
        candidates.append(candidate)
    first = evaluate_source_equivalence(
        candidates=candidates,
        references=references,
        as_of_date="2026-08-06",
    )
    second = evaluate_source_equivalence(
        candidates=list(reversed(candidates)),
        references=list(reversed(references)),
        as_of_date="2026-08-06",
    )
    assert first == second
    assert first["summary"] == {
        "candidate_count": 36,
        "reference_count": 36,
        "exact_locator_matches": 12,
        "typed_source_equivalent_matches": 24,
        "no_matches": 0,
    }


def test_materialized_proof_is_digest_bound_and_does_not_claim_live_search() -> None:
    proof = _load(PROOF_PATH)
    body = dict(proof)
    observed = body.pop("proof_digest")
    assert observed == canonical_digest(body)
    assert proof["status"] == "zero_call_engineering_pass_live_provider_unproven"
    assert proof["query_plan_counts"] == {
        "precise_official_domain": 36,
        "semantic_open_web": 24,
        "combined": 60,
    }
    assert proof["source_equivalence_summary"]["no_matches"] == 0
    assert proof["observed_calls"] == {
        "network": 0,
        "provider": 0,
        "model": 0,
        "document_fetch": 0,
        "evidence_promotion": 0,
    }
    assert proof["decision"]["provider_comparator"] == "pending_separate_authority"
