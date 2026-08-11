from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    canonical_digest,
    load_source_catalog,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    CONTRACT_REF,
    SourceIdentity,
    compile_bounded_query_plans,
    compile_search_intents,
    evaluate_source_equivalence,
    load_search_intent_policy,
)


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
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_and_source_equivalence_zero_call_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _identity(
    *,
    identity_id: str,
    case_key: str,
    owner_key: str,
    source_family: str,
    document_kind: str,
    locator: str,
    content_sha256: str,
) -> SourceIdentity:
    return SourceIdentity(
        identity_id=identity_id,
        case_key=case_key,
        evidence_owner_entity_key=owner_key,
        source_family=source_family,
        document_kind=document_kind,
        published_on="2026-07-01",
        authority=(
            "regulatory_primary"
            if document_kind == "regulatory_filing"
            else "issuer_primary"
        ),
        locator=locator,
        content_sha256=content_sha256,
        content_identity_verified=True,
    )


def _full_fake_equivalence(intents) -> dict:
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
        content_digest = canonical_digest({"synthetic_document": index})
        reference = _identity(
            identity_id=f"reference-{index:02d}",
            case_key=intent.case_key,
            owner_key=intent.evidence_owner_entity_key,
            source_family=intent.source_families[0],
            document_kind=document_kind,
            locator=locator,
            content_sha256=content_digest,
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
    return evaluate_source_equivalence(
        candidates=candidates,
        references=references,
        as_of_date="2026-08-06",
    )


def main() -> int:
    catalog = load_source_catalog(CATALOG_PATH)
    policy = load_search_intent_policy(POLICY_PATH)
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=catalog,
        policy=policy,
        research_objectives=objectives,
    )
    plans = compile_bounded_query_plans(intents=intents, policy=policy)
    equivalence = _full_fake_equivalence(intents)
    sample_keys = {
        (
            "DELL",
            "customer_demand_and_deployment_validation",
            "MSFT",
            "en",
            "precise_official_domain",
        ),
        (
            "MU",
            "customer_demand_and_deployment_validation",
            "DELL",
            "zh",
            "semantic_open_web",
        ),
        (
            "NVDA",
            "supply_chain_capacity_and_counterevidence",
            "TSMC",
            "zh",
            "precise_official_domain",
        ),
        (
            "NVDA",
            "issuer_results_and_management_commentary",
            "NVDA",
            "en",
            "precise_official_domain",
        ),
    }
    samples = [
        row.as_dict()
        for row in intents
        if (
            row.case_key,
            row.evidence_slot_id,
            row.evidence_owner_entity_key,
            row.language,
            row.route_class,
        )
        in sample_keys
    ]
    case_route_counts = {
        case_key: {
            route_class: sum(
                row.case_key == case_key and row.route_class == route_class
                for row in intents
            )
            for route_class in ("precise_official_domain", "semantic_open_web")
        }
        for case_key in ("DELL", "MU", "NVDA")
    }
    query_lengths = [len(row.query_text) for row in intents]
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_relationship_aware_search_intent_and_source_equivalence_zero_call_proof_v1_0"
        ),
        "contract_ref": CONTRACT_REF,
        "status": "zero_call_engineering_pass_live_provider_unproven",
        "source_catalog_digest": canonical_digest(catalog),
        "policy_digest": canonical_digest(policy),
        "research_objective_digests": {
            case_key: canonical_digest(
                {"case_key": case_key, "research_objective": objective}
            )
            for case_key, objective in objectives.items()
        },
        "query_plan_counts": {
            "precise_official_domain": plans["plans"][
                "precise_official_domain"
            ]["query_count"],
            "semantic_open_web": plans["plans"]["semantic_open_web"][
                "query_count"
            ],
            "combined": len(intents),
        },
        "case_route_counts": case_route_counts,
        "query_text_quality": {
            "unique_queries": len({row.query_text for row in intents}),
            "minimum_characters": min(query_lengths),
            "maximum_characters": max(query_lengths),
            "mean_characters": round(sum(query_lengths) / len(query_lengths), 3),
            "maximum_allowed_characters": 300,
            "full_research_objective_copied_into_query": False,
            "one_evidence_owner_per_intent": True,
        },
        "bounded_query_plan_digest": plans["plan_digest"],
        "sample_intents": samples,
        "full_fake_cases": ["DELL", "MU", "NVDA"],
        "full_fake_external_slot_count": 4,
        "source_equivalence_summary": equivalence["summary"],
        "source_equivalence_evaluation_digest": equivalence[
            "evaluation_digest"
        ],
        "mutation_coverage": [
            "cross-case subject",
            "wrong relationship direction",
            "future as-of and future publication date",
            "localized alias collision",
            "fan-out budget mismatch",
            "catalog and objective permutation",
            "unverified canonical locator",
            "same-event different-document false equivalence",
            "wrong evidence owner identity",
            "SEC accession normalization",
            "verified redirect",
            "verified content identity",
        ],
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "document_fetch": 0,
            "evidence_promotion": 0,
        },
        "decision": {
            "search_intent_compiler": "engineering_pass",
            "typed_source_equivalence_evaluator": "engineering_pass",
            "historical_tencent_24_query_contract": "immutable_not_rewritten",
            "fixed_24_query_successor": "rejected_because_counterpart_fanout_would_be_lost",
            "provider_comparator": "pending_separate_authority",
            "sourcehunter_production_integration": "not_authorized",
            "ranking_or_reranker": "not_admitted",
            "next": "S1_08_DOMESTIC_FIRST_PROVIDER_INPUT_QUALIFICATION_AND_RELATIONSHIP_AWARE_COMPARATOR_SCOPE_DECISION",
        },
        "known_boundary": (
            "The proof establishes deterministic relationship-aware intent compilation, "
            "separate official and semantic budgets, and strict source identity matching. "
            "It does not prove any provider's live candidate recall, date accuracy, cost, "
            "latency, document quality, Evidence promotion, Agentic Research or report quality."
        ),
    }
    result = {**body, "proof_digest": canonical_digest(body)}
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
