from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
import unicodedata

from sec_agent.canonical_runtime.models import canonical_digest


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_query_facet_three_way_evaluation_policy_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1_08.query_facet_three_way_evaluation:v1"
RUN_SCOPE = "S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION"
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_08_query_facet_three_way_zero_call_proof_v1_0"
)
CASES = ("DELL", "MU", "NVDA")
LANGUAGES = ("en", "zh")
VARIANTS = (
    "user_raw_query",
    "deterministic_local_compiler",
    "deepseek_query_atoms_plus_deterministic_local_compiler",
)
FACET_GROUPS = (
    "evidence_owner",
    "subject",
    "period",
    "document_type",
    "metric",
    "product",
    "mechanism",
    "relationship_direction",
)
SEMANTIC_SLOTS = (
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
GOLD_TOKEN_PATTERN = re.compile(
    r"(?:SRC_|DELL_E|MU_E|NVDA_E|DELL_T|MU_T|NVDA_T)"
)
URL_PATTERN = re.compile(r"(?i)(?:https?://|www\.)")
SECRET_PATTERN = re.compile(
    r"(?i)(?:AKID[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{20,}|"
    r"(?:secretkey|api[_-]?key|authorization)\s*[:=]\s*[A-Za-z0-9_./+-]{16,})"
)
PERIOD_PATTERN = re.compile(
    r"(?i)(?:\b20\d{2}(?:[-/]\d{2}[-/]\d{2})?\b|\bFY\s*\d{2,4}\b|\bQ[1-4]\b)"
)
EN_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
EN_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "and",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "especially",
        "evidence",
        "find",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "own",
        "research",
        "the",
        "their",
        "this",
        "through",
        "to",
        "using",
        "what",
        "which",
        "with",
    }
)


class S108QueryFacetThreeWayError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_three_way_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
        or policy.get("as_of_date") != "2026-08-06"
        or tuple(policy.get("cases") or ()) != CASES
        or tuple(policy.get("languages") or ()) != LANGUAGES
        or tuple(policy.get("variants") or ()) != VARIANTS
        or tuple(policy.get("facet_groups") or ()) != FACET_GROUPS
    ):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_policy_identity_invalid"
        )
    variants = policy.get("variant_contracts") or {}
    if set(variants) != set(VARIANTS):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_variant_contract_invalid"
        )
    raw = variants["user_raw_query"]
    model = variants[
        "deepseek_query_atoms_plus_deterministic_local_compiler"
    ]
    if (
        raw.get("source") != "verbatim_case_research_objective"
        or raw.get("translation_or_owner_period_injection_allowed") is not False
        or model.get("natural_atom_result_required") is not True
        or model.get(
            "model_may_emit_final_query_URL_identity_period_relationship_domain_route_or_gold"
        )
        is not False
        or model.get("activation_state") != "not_called_not_admitted"
    ):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_variant_authority_invalid"
        )
    replay = policy.get("replay_contract") or {}
    if (
        replay.get("historical_pool_is_variant_neutral") is not False
        or replay.get("historical_target_in_pool_may_be_attributed_to_new_variant")
        is not False
        or replay.get("candidate_generation_or_live_recall_proven") is not False
        or replay.get("cross_case_canonical_document_reuse_allowed") is not True
        or replay.get("cross_case_role_binding_must_remain_explicit") is not True
    ):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_replay_boundary_invalid"
        )
    calls = policy.get("calls_authorized_by_this_policy") or {}
    if set(calls) != {
        "network",
        "provider",
        "model",
        "document_fetch",
        "evidence_promotion",
        "retrieval",
        "embedding",
        "rerank",
    } or any(calls.values()):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_zero_call_boundary_invalid"
        )
    return policy


def build_three_way_zero_call_evaluation(
    *,
    policy: Mapping[str, Any],
    query_facet_proof: Mapping[str, Any],
    model_visible_case_pack: Mapping[str, Any],
    firecrawl_result: Mapping[str, Any],
    firecrawl_assessment: Mapping[str, Any],
    firecrawl_scoring: Mapping[str, Any],
    model_assisted_plans: Sequence[Mapping[str, Any]] | None = None,
    deterministic_permutation_stable: bool = False,
) -> dict[str, Any]:
    deterministic_plans = tuple(
        dict(row) for row in query_facet_proof.get("plans") or []
    )
    _validate_inputs(
        policy=policy,
        query_facet_proof=query_facet_proof,
        model_visible_case_pack=model_visible_case_pack,
        firecrawl_result=firecrawl_result,
        firecrawl_assessment=firecrawl_assessment,
        firecrawl_scoring=firecrawl_scoring,
        deterministic_plans=deterministic_plans,
    )
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in model_visible_case_pack["cases"]
    }
    all_aliases = _entity_aliases(deterministic_plans)
    assisted_by_key = _validate_and_index_assisted_plans(
        deterministic_plans=deterministic_plans,
        model_assisted_plans=model_assisted_plans,
    )
    per_plan: list[dict[str, Any]] = []
    for plan in deterministic_plans:
        plan_key = _plan_key(plan)
        variant_queries: dict[str, tuple[str, ...] | None] = {
            "user_raw_query": (objectives[plan["case_key"]],),
            "deterministic_local_compiler": _positive_queries(plan),
            "deepseek_query_atoms_plus_deterministic_local_compiler": None,
        }
        assisted = assisted_by_key.get(plan_key)
        if assisted is not None:
            variant_queries[
                "deepseek_query_atoms_plus_deterministic_local_compiler"
            ] = _positive_queries(assisted)
        variant_rows: dict[str, Any] = {}
        for variant, queries in variant_queries.items():
            if queries is None:
                variant_rows[variant] = {
                    "status": "not_observed_no_natural_model_atoms",
                    "query_count": 0,
                    "facet_coverage": None,
                    "contamination_count": None,
                    "duplicate_query_rate": None,
                    "query_digest": None,
                }
                continue
            coverage = _facet_coverage(plan=plan, queries=queries)
            contamination = _contamination_events(
                plan=plan,
                queries=queries,
                all_aliases=all_aliases,
            )
            variant_rows[variant] = {
                "status": "evaluated",
                "query_count": len(queries),
                "facet_coverage": coverage,
                "contamination_count": len(contamination),
                "contamination_codes": sorted(set(contamination)),
                "duplicate_query_rate": _duplicate_rate(queries),
                "query_digest": canonical_digest(list(queries)),
                "accepted_model_atom_count": (
                    len(assisted.get("accepted_model_atoms") or [])
                    if variant
                    == "deepseek_query_atoms_plus_deterministic_local_compiler"
                    and assisted is not None
                    else 0
                ),
            }
        per_plan.append(
            {
                "plan_key": list(plan_key),
                "base_plan_id": plan["plan_id"],
                "base_plan_digest": plan["plan_digest"],
                "variants": variant_rows,
            }
        )

    variant_summary = {
        variant: _aggregate_variant(
            variant=variant,
            per_plan=per_plan,
            model_variant_observed=bool(assisted_by_key),
        )
        for variant in VARIANTS
    }
    target_opportunity = _target_route_opportunity(
        policy=policy,
        plans=deterministic_plans,
        model_visible_case_pack=model_visible_case_pack,
        firecrawl_scoring=firecrawl_scoring,
    )
    addressability = _english_target_addressability_proxy(
        plans=deterministic_plans,
        assisted_by_key=assisted_by_key,
        objectives=objectives,
        model_visible_case_pack=model_visible_case_pack,
        firecrawl_scoring=firecrawl_scoring,
    )
    historical_replay = _historical_replay_summary(
        firecrawl_result=firecrawl_result,
        firecrawl_assessment=firecrawl_assessment,
    )
    thresholds = policy["decision_thresholds"]
    local = variant_summary["deterministic_local_compiler"]
    raw = variant_summary["user_raw_query"]
    local_structure_pass = (
        local["mean_facet_coverage"]
        >= float(thresholds["minimum_local_mean_facet_coverage"])
        and local["mean_facet_coverage"] - raw["mean_facet_coverage"]
        >= float(thresholds["minimum_local_coverage_gain_over_raw"])
        and local["contamination_count"]
        <= int(
            thresholds[
                "maximum_wrong_entity_period_direction_or_secret_leak_count"
            ]
        )
        and local["duplicate_query_rate"]
        <= float(thresholds["maximum_duplicate_query_rate"])
        and deterministic_permutation_stable
    )
    model_observed = bool(assisted_by_key)
    model_decision = _model_variant_decision(
        thresholds=thresholds,
        variant_summary=variant_summary,
        addressability=addressability,
        model_observed=model_observed,
    )
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": (
            "zero_call_A_B_pass_model_atom_observation_pending"
            if local_structure_pass and not model_observed
            else (
                "three_way_replay_proxy_complete"
                if local_structure_pass and model_observed
                else "zero_call_evaluation_failed"
            )
        ),
        "plan_count": len(deterministic_plans),
        "variant_summary": variant_summary,
        "target_route_opportunity": target_opportunity,
        "english_target_addressability_proxy": addressability,
        "historical_capture_replay": historical_replay,
        "per_plan": per_plan,
        "quality_gates": {
            "deterministic_local_structure_pass": local_structure_pass,
            "raw_query_not_misrepresented_as_compiled": True,
            "historical_target_in_pool_attributed_to_new_variant": False,
            "all_six_semantic_slots_have_direct_acceptable_target_owner_route": (
                target_opportunity["slot_direct_opportunity"] == [6, 6]
            ),
            "all_target_documents_have_global_owner_route": (
                target_opportunity["global_document_owner_opportunity"]
                == [10, 10]
            ),
            "model_variant_observed": model_observed,
            "model_variant_runtime_admitted": model_decision["runtime_admitted"],
            "deterministic_permutation_stability": (
                1.0 if deterministic_permutation_stable else 0.0
            ),
            "fresh_provider_recall_proven": False,
        },
        "decision": {
            "deterministic_local_compiler": (
                "retain_as_external_and_internal_query_baseline"
                if local_structure_pass
                else "blocked_structure_or_pollution"
            ),
            "deepseek_query_atoms": model_decision,
            "next": (
                "bounded_deepseek_query_atom_canary_authority_decision"
                if local_structure_pass and not model_observed
                else "post_three_way_combined_live_readiness_decision"
            ),
            "combined_external_live_authorized": False,
            "internal_retrieval_authorized": False,
            "BGE_fusion_rerank_authorized": False,
        },
        "observed_calls": dict(policy["calls_authorized_by_this_policy"]),
        "stage_acceptance": {
            "query_facet_A_B_zero_call_evaluation": local_structure_pass,
            "natural_model_atom_variant": model_observed,
            "three_way_effectiveness_evaluation": model_observed,
            "fresh_combined_external_live": False,
            "internal_retrieval_query_facet": False,
            "candidate_ceiling_and_qrels": False,
            "BGE_fusion_rerank": False,
            "downstream_utilization": False,
            "S1_08": False,
            "release": False,
        },
        "known_boundary": (
            "The frozen Firecrawl pools were generated by historical relationship-aware "
            "queries and are not variant-neutral. Their observed five-of-six slot "
            "target-in-pool result is retained as historical evidence only. This proof "
            "measures query structure and an English target-addressability proxy; it "
            "does not prove that a new query would generate the same candidates, fresh "
            "provider recall, internal retrieval quality, BGE/rerank value, Evidence "
            "promotion, downstream research quality, S1-08 acceptance or release."
        ),
    }
    return {**body, "evaluation_digest": canonical_digest(body)}


def _validate_inputs(
    *,
    policy: Mapping[str, Any],
    query_facet_proof: Mapping[str, Any],
    model_visible_case_pack: Mapping[str, Any],
    firecrawl_result: Mapping[str, Any],
    firecrawl_assessment: Mapping[str, Any],
    firecrawl_scoring: Mapping[str, Any],
    deterministic_plans: Sequence[Mapping[str, Any]],
) -> None:
    proof_body = dict(query_facet_proof)
    supplied_proof_digest = proof_body.pop("proof_digest", "")
    if (
        query_facet_proof.get("status") != "zero_call_engineering_pass"
        or supplied_proof_digest != canonical_digest(proof_body)
        or len(deterministic_plans) != 36
        or query_facet_proof.get("bound_search_intent_count") != 60
    ):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_base_proof_invalid"
        )
    if (
        set(row.get("case_key") for row in model_visible_case_pack.get("cases") or [])
        != set(CASES)
        or len(model_visible_case_pack.get("source_registry") or []) != 10
        or firecrawl_result.get("status") != "completed"
        or firecrawl_result.get("observed_counts", {}).get("terminalized_queries")
        != 24
        or firecrawl_assessment.get("aggregate", {}).get(
            "case_slot_target_in_pool"
        )
        != [5, 6]
        or firecrawl_scoring.get("visibility")
        != "evaluator_only_load_after_all_provider_calls_terminal"
    ):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_replay_input_invalid"
        )
    if any(policy.get("calls_authorized_by_this_policy", {}).values()):
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_call_boundary_invalid"
        )


def _validate_and_index_assisted_plans(
    *,
    deterministic_plans: Sequence[Mapping[str, Any]],
    model_assisted_plans: Sequence[Mapping[str, Any]] | None,
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    if not model_assisted_plans:
        return {}
    base = {_plan_key(row): row for row in deterministic_plans}
    assisted = {_plan_key(row): dict(row) for row in model_assisted_plans}
    if set(assisted) != set(base) or len(assisted) != 36:
        raise S108QueryFacetThreeWayError(
            "s1_08_query_facet_three_way_model_plan_set_invalid"
        )
    protected_fields = (
        "case_key",
        "evidence_slot_id",
        "language",
        "subject_entity_key",
        "subject_aliases",
        "evidence_owner_entity_key",
        "evidence_owner_aliases",
        "evidence_owner_role",
        "relationship_direction",
        "period_terms",
        "as_of_date",
        "source_families",
        "preferred_domains",
        "graph_query",
        "negative_queries",
        "forbidden_expansions",
        "route_specific_filters",
        "source_intent_ids",
        "source_intent_digests",
        "eligible_external_routes",
        "eligible_internal_routes",
    )
    for key, row in assisted.items():
        if any(
            row.get(field) != base[key].get(field) for field in protected_fields
        ):
            raise S108QueryFacetThreeWayError(
                "s1_08_query_facet_three_way_model_plan_authority_drift"
            )
    return assisted


def _plan_key(plan: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(plan["case_key"]),
        str(plan["evidence_slot_id"]),
        str(plan["evidence_owner_entity_key"]),
        str(plan["language"]),
    )


def _positive_queries(plan: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(value)
        for field in (
            "exact_lookup_queries",
            "lexical_queries",
            "semantic_queries",
        )
        for value in plan.get(field) or []
    )


def _entity_aliases(
    plans: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    rows: dict[str, set[str]] = {}
    for plan in plans:
        rows.setdefault(str(plan["subject_entity_key"]), set()).update(
            str(value) for value in plan["subject_aliases"]
        )
        rows.setdefault(str(plan["evidence_owner_entity_key"]), set()).update(
            str(value) for value in plan["evidence_owner_aliases"]
        )
    return {
        key: tuple(sorted(values, key=lambda value: value.casefold()))
        for key, values in sorted(rows.items())
    }


def _facet_coverage(
    *, plan: Mapping[str, Any], queries: Sequence[str]
) -> dict[str, Any]:
    text = " \n ".join(queries)
    hits = {
        "evidence_owner": _contains_any(text, plan["evidence_owner_aliases"]),
        "subject": _contains_any(text, plan["subject_aliases"]),
        "period": _contains_any(text, plan["period_terms"]),
        "document_type": _contains_any(text, plan["document_types"]),
        "metric": _contains_any(text, plan["metric_facets"]),
        "product": _contains_any(text, plan["product_facets"]),
        "mechanism": _contains_any(text, plan["mechanism_facets"]),
        "relationship_direction": False,
    }
    if plan["subject_entity_key"] == plan["evidence_owner_entity_key"]:
        hits["relationship_direction"] = hits["evidence_owner"] and (
            hits["document_type"] or hits["metric"]
        )
    else:
        hits["relationship_direction"] = (
            hits["evidence_owner"]
            and hits["subject"]
            and (hits["product"] or hits["mechanism"])
        )
    score = round(sum(hits.values()) / len(FACET_GROUPS), 6)
    return {
        "score": score,
        "covered": sorted(key for key, value in hits.items() if value),
        "missing": sorted(key for key, value in hits.items() if not value),
    }


def _contamination_events(
    *,
    plan: Mapping[str, Any],
    queries: Sequence[str],
    all_aliases: Mapping[str, Sequence[str]],
) -> list[str]:
    text = " \n ".join(queries)
    events: list[str] = []
    allowed = {plan["subject_entity_key"], plan["evidence_owner_entity_key"]}
    for entity_key, aliases in all_aliases.items():
        if entity_key not in allowed and _contains_any(text, aliases):
            events.append(f"wrong_entity::{entity_key}")
    if GOLD_TOKEN_PATTERN.search(text):
        events.append("gold_identifier_leak")
    if URL_PATTERN.search(text):
        events.append("URL_leak")
    if SECRET_PATTERN.search(text):
        events.append("secret_like_surface")
    allowed_period_text = " ".join(
        [*plan["period_terms"], str(plan["as_of_date"])]
    ).casefold()
    for observed in PERIOD_PATTERN.findall(text):
        if observed.casefold() not in allowed_period_text:
            events.append("period_outside_typed_filter")
            break
    return events


def _aggregate_variant(
    *, variant: str, per_plan: Sequence[Mapping[str, Any]], model_variant_observed: bool
) -> dict[str, Any]:
    rows = [row["variants"][variant] for row in per_plan]
    evaluated = [row for row in rows if row["status"] == "evaluated"]
    if not evaluated:
        return {
            "status": "not_observed_no_natural_model_atoms",
            "plan_count": 0,
            "query_count": 0,
            "mean_facet_coverage": None,
            "minimum_facet_coverage": None,
            "contamination_count": None,
            "duplicate_query_rate": None,
            "accepted_model_atom_count": 0,
            "model_variant_observed": model_variant_observed,
        }
    all_digests = [row["query_digest"] for row in evaluated]
    return {
        "status": "evaluated",
        "plan_count": len(evaluated),
        "query_count": sum(int(row["query_count"]) for row in evaluated),
        "mean_facet_coverage": round(
            sum(float(row["facet_coverage"]["score"]) for row in evaluated)
            / len(evaluated),
            6,
        ),
        "minimum_facet_coverage": min(
            float(row["facet_coverage"]["score"]) for row in evaluated
        ),
        "contamination_count": sum(
            int(row["contamination_count"]) for row in evaluated
        ),
        "duplicate_query_rate": _duplicate_rate(all_digests),
        "accepted_model_atom_count": sum(
            int(row["accepted_model_atom_count"]) for row in evaluated
        ),
        "model_variant_observed": model_variant_observed,
    }


def _target_route_opportunity(
    *,
    policy: Mapping[str, Any],
    plans: Sequence[Mapping[str, Any]],
    model_visible_case_pack: Mapping[str, Any],
    firecrawl_scoring: Mapping[str, Any],
) -> dict[str, Any]:
    source_registry = {
        str(row["source_id"]): dict(row)
        for row in model_visible_case_pack["source_registry"]
    }
    owner_map = policy["source_owner_entity_map"]
    plan_keys = {_plan_key(row) for row in plans}
    global_owners = {str(row["evidence_owner_entity_key"]) for row in plans}
    rows: list[dict[str, Any]] = []
    for case_key, slots in sorted(
        firecrawl_scoring["target_sources_by_case_and_slot"].items()
    ):
        for slot_id, source_ids in sorted(slots.items()):
            for source_id in sorted(source_ids):
                source = source_registry[source_id]
                owner = owner_map.get(source["publisher"])
                if not owner:
                    raise S108QueryFacetThreeWayError(
                        "s1_08_query_facet_three_way_source_owner_unmapped"
                    )
                direct = any(
                    (case_key, slot_id, owner, language) in plan_keys
                    for language in LANGUAGES
                )
                rows.append(
                    {
                        "case_key": case_key,
                        "evidence_slot_id": slot_id,
                        "source_id": source_id,
                        "source_owner_entity_key": owner,
                        "direct_case_slot_owner_route": direct,
                        "global_canonical_document_owner_route": owner
                        in global_owners,
                    }
                )
    slot_rows: list[dict[str, Any]] = []
    for case_key in CASES:
        for slot_id in SEMANTIC_SLOTS:
            selected = [
                row
                for row in rows
                if row["case_key"] == case_key
                and row["evidence_slot_id"] == slot_id
            ]
            slot_rows.append(
                {
                    "case_key": case_key,
                    "evidence_slot_id": slot_id,
                    "acceptable_target_count": len(selected),
                    "direct_acceptable_target_owner_route": any(
                        row["direct_case_slot_owner_route"] for row in selected
                    ),
                    "global_canonical_document_owner_route": any(
                        row["global_canonical_document_owner_route"]
                        for row in selected
                    ),
                }
            )
    return {
        "target_source_rows": rows,
        "target_source_direct_opportunity": [
            sum(row["direct_case_slot_owner_route"] for row in rows),
            len(rows),
        ],
        "slot_direct_opportunity": [
            sum(row["direct_acceptable_target_owner_route"] for row in slot_rows),
            len(slot_rows),
        ],
        "global_document_owner_opportunity": [
            sum(row["global_canonical_document_owner_route"] for row in rows),
            len(rows),
        ],
        "slot_rows": slot_rows,
        "missing_direct_alternatives": [
            {
                "case_key": row["case_key"],
                "evidence_slot_id": row["evidence_slot_id"],
                "source_id": row["source_id"],
                "source_owner_entity_key": row["source_owner_entity_key"],
            }
            for row in rows
            if not row["direct_case_slot_owner_route"]
        ],
        "interpretation": (
            "Target sources within a case-slot are acceptable alternatives under the "
            "frozen scoring contract. Every semantic slot has at least one direct "
            "acceptable owner route. A document obtained by another case's owner route "
            "may be reused only through an explicit case-slot role binding."
        ),
    }


def _english_target_addressability_proxy(
    *,
    plans: Sequence[Mapping[str, Any]],
    assisted_by_key: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    objectives: Mapping[str, str],
    model_visible_case_pack: Mapping[str, Any],
    firecrawl_scoring: Mapping[str, Any],
) -> dict[str, Any]:
    source_registry = {
        str(row["source_id"]): dict(row)
        for row in model_visible_case_pack["source_registry"]
    }
    case_topics: dict[tuple[str, str], set[str]] = {}
    for case in model_visible_case_pack["cases"]:
        case_key = str(case["case_key"])
        for evidence in case.get("evidence_items") or []:
            key = (case_key, str(evidence["source_id"]))
            for topic in evidence.get("topics") or []:
                case_topics.setdefault(key, set()).update(
                    _english_tokens(str(topic).replace("_", " "))
                )
    owner_by_source = _source_owner_map_from_plans_and_registry(
        plans=plans,
        source_registry=source_registry,
    )
    plan_by_key = {_plan_key(row): row for row in plans}
    rows: list[dict[str, Any]] = []
    for case_key, slots in sorted(
        firecrawl_scoring["target_sources_by_case_and_slot"].items()
    ):
        for slot_id, source_ids in sorted(slots.items()):
            for source_id in sorted(source_ids):
                owner = owner_by_source[source_id]
                key = (case_key, slot_id, owner, "en")
                plan = plan_by_key.get(key)
                if plan is None:
                    rows.append(
                        {
                            "case_key": case_key,
                            "evidence_slot_id": slot_id,
                            "source_id": source_id,
                            "source_owner_entity_key": owner,
                            "status": "no_direct_case_slot_owner_plan_global_reuse_only",
                            "variants": {},
                        }
                    )
                    continue
                variant_plans = {
                    "user_raw_query": None,
                    "deterministic_local_compiler": plan,
                    "deepseek_query_atoms_plus_deterministic_local_compiler": (
                        assisted_by_key.get(key)
                    ),
                }
                variant_rows: dict[str, Any] = {}
                for variant, variant_plan in variant_plans.items():
                    if variant == "user_raw_query":
                        queries = (objectives[case_key],)
                    elif variant_plan is None:
                        variant_rows[variant] = {
                            "status": "not_observed_no_natural_model_atoms"
                        }
                        continue
                    else:
                        queries = _positive_queries(variant_plan)
                    variant_rows[variant] = _target_addressability(
                        plan=plan,
                        queries=queries,
                        source=source_registry[source_id],
                        topic_tokens=case_topics.get((case_key, source_id), set()),
                    )
                rows.append(
                    {
                        "case_key": case_key,
                        "evidence_slot_id": slot_id,
                        "source_id": source_id,
                        "source_owner_entity_key": owner,
                        "status": "direct_plan_evaluated",
                        "variants": variant_rows,
                    }
                )
    summary: dict[str, Any] = {}
    direct = [row for row in rows if row["status"] == "direct_plan_evaluated"]
    for variant in VARIANTS:
        observed = [
            row["variants"].get(variant)
            for row in direct
            if row["variants"].get(variant, {}).get("status") == "evaluated"
        ]
        if not observed:
            summary[variant] = {
                "status": "not_observed_no_natural_model_atoms",
                "addressable": None,
                "mean_score": None,
            }
            continue
        summary[variant] = {
            "status": "evaluated",
            "addressable": [
                sum(row["addressable"] for row in observed),
                len(observed),
            ],
            "mean_score": round(
                sum(float(row["score"]) for row in observed) / len(observed),
                6,
            ),
        }
    return {
        "language": "en",
        "proxy_definition": (
            "Owner and typed period must be present, plus at least one title or "
            "case-source topic token. This measures locator addressability against "
            "frozen evaluator metadata, not provider candidate generation."
        ),
        "direct_target_rows": rows,
        "variant_summary": summary,
    }


def _source_owner_map_from_plans_and_registry(
    *,
    plans: Sequence[Mapping[str, Any]],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    publisher_aliases: dict[str, str] = {}
    for plan in plans:
        owner = str(plan["evidence_owner_entity_key"])
        for alias in plan["evidence_owner_aliases"]:
            publisher_aliases[_normalized(str(alias))] = owner
    result: dict[str, str] = {}
    for source_id, source in source_registry.items():
        publisher = _normalized(str(source.get("publisher") or ""))
        matches = {
            owner
            for alias, owner in publisher_aliases.items()
            if alias and (alias in publisher or publisher in alias)
        }
        if not matches and source.get("artifact_ref"):
            continue
        if len(matches) != 1:
            raise S108QueryFacetThreeWayError(
                "s1_08_query_facet_three_way_source_owner_inference_invalid"
            )
        result[source_id] = next(iter(matches))
    return result


def _target_addressability(
    *,
    plan: Mapping[str, Any],
    queries: Sequence[str],
    source: Mapping[str, Any],
    topic_tokens: set[str],
) -> dict[str, Any]:
    text = " ".join(queries)
    tokens = _english_tokens(text)
    title_tokens = _english_tokens(str(source.get("title") or ""))
    title_signal = title_tokens - EN_STOPWORDS - {
        "financial",
        "fiscal",
        "results",
    }
    period_tokens = set()
    for value in [*plan["period_terms"], str(source.get("published_on") or "")]:
        period_tokens.update(
            token
            for token in _english_tokens(str(value))
            if any(character.isdigit() for character in token)
        )
    owner_match = _contains_any(text, plan["evidence_owner_aliases"])
    period_match = bool(tokens & period_tokens)
    title_overlap = sorted(tokens & title_signal)
    topic_overlap = sorted(tokens & topic_tokens)
    components = (
        owner_match,
        period_match,
        bool(title_overlap),
        bool(topic_overlap),
    )
    return {
        "status": "evaluated",
        "addressable": bool(owner_match and period_match and (title_overlap or topic_overlap)),
        "score": round(sum(components) / len(components), 6),
        "owner_match": owner_match,
        "period_match": period_match,
        "title_token_overlap": title_overlap,
        "topic_token_overlap": topic_overlap,
    }


def _historical_replay_summary(
    *,
    firecrawl_result: Mapping[str, Any],
    firecrawl_assessment: Mapping[str, Any],
) -> dict[str, Any]:
    aggregate = firecrawl_assessment["aggregate"]
    counts = firecrawl_result["observed_counts"]
    unique_locators = {
        str(locator["canonical_url"])
        for call in firecrawl_result.get("call_results") or []
        for locator in call.get("provider_projection", {}).get("locators") or []
    }
    return {
        "generator": "historical_relationship_aware_semantic_queries_not_the_new_variants",
        "query_pools": counts["terminalized_queries"],
        "unique_locators": len(unique_locators),
        "case_slot_target_in_pool": aggregate["case_slot_target_in_pool"],
        "case_slot_target_in_pool_rate": aggregate[
            "case_slot_target_in_pool_rate"
        ],
        "credits_used": aggregate["credits_used"],
        "observed_cash_cost": aggregate["observed_cash_cost"],
        "latency_ms": aggregate["latency_ms"],
        "attributable_to_user_raw_query": False,
        "attributable_to_deterministic_local_compiler": False,
        "attributable_to_model_atoms": False,
        "use": "frozen_capture_shape_and_addressability_proxy_only",
    }


def _model_variant_decision(
    *,
    thresholds: Mapping[str, Any],
    variant_summary: Mapping[str, Mapping[str, Any]],
    addressability: Mapping[str, Any],
    model_observed: bool,
) -> dict[str, Any]:
    if not model_observed:
        return {
            "status": "pending_natural_atom_observation",
            "runtime_admitted": False,
            "reason": (
                "No natural DeepSeek atom result exists. Fixture atoms cannot establish "
                "model value or compliance."
            ),
        }
    local = variant_summary["deterministic_local_compiler"]
    model = variant_summary[
        "deepseek_query_atoms_plus_deterministic_local_compiler"
    ]
    local_proxy = addressability["variant_summary"][
        "deterministic_local_compiler"
    ]
    model_proxy = addressability["variant_summary"][
        "deepseek_query_atoms_plus_deterministic_local_compiler"
    ]
    addressability_gain = (
        model_proxy["addressable"][0] - local_proxy["addressable"][0]
    )
    pollution_increase = model["contamination_count"] > local["contamination_count"]
    duplicate_increase = model["duplicate_query_rate"] > local["duplicate_query_rate"]
    proxy_candidate = (
        addressability_gain > 0
        and not pollution_increase
        and not duplicate_increase
    )
    return {
        "status": (
            "shadow_candidate_fresh_provider_proof_required"
            if proxy_candidate
            else "rejected_no_incremental_addressability_or_quality_regression"
        ),
        "runtime_admitted": False,
        "addressability_gain": addressability_gain,
        "pollution_increase": pollution_increase,
        "duplicate_rate_increase": duplicate_increase,
        "fresh_provider_live_still_required": bool(
            thresholds["fresh_provider_live_required_before_runtime_activation"]
        ),
    }


def _contains_any(text: str, values: Sequence[str]) -> bool:
    return any(_contains_phrase(text, str(value)) for value in values if str(value))


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalized(text)
    normalized_phrase = _normalized(phrase)
    if not normalized_phrase:
        return False
    if all(ord(character) < 128 for character in normalized_phrase):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
                normalized_text,
            )
        )
    return normalized_phrase in normalized_text


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _duplicate_rate(values: Sequence[str]) -> float:
    normalized = [_normalized(str(value)) for value in values]
    if not normalized:
        return 0.0
    return round((len(normalized) - len(set(normalized))) / len(normalized), 6)


def _english_tokens(value: str) -> set[str]:
    return {
        token
        for token in EN_TOKEN_PATTERN.findall(_normalized(value))
        if len(token) > 1 and token not in EN_STOPWORDS
    }
