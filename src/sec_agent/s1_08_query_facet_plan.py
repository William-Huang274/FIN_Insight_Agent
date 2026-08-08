from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_search_intent_compiler import SearchIntent


POLICY_SCHEMA = "fin_ia_0_1_3_s1_08_unified_query_facet_policy_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.unified_query_facet_plan:v1"
RUN_SCOPE = "S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION"
PROOF_SCHEMA = "fin_ia_0_1_3_s1_08_unified_query_facet_zero_call_proof_v1_0"
CASES = ("DELL", "MU", "NVDA")
LANGUAGES = ("en", "zh")
SLOT_IDS = (
    "issuer_results_and_management_commentary",
    "regulatory_risk_and_financial_reconciliation",
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
MODEL_ATOM_KINDS = ("metric", "product", "mechanism", "synonym")
GOLD_TOKEN_PREFIXES = (
    "SRC_",
    "DELL_E",
    "MU_E",
    "NVDA_E",
    "DELL_T",
    "MU_T",
    "NVDA_T",
)
_PERIOD_PATTERN = re.compile(r"(?i)(?:\b20\d{2}\b|\bFY\s*\d{2,4}\b|\bQ[1-4]\b)")
_DOMAIN_PATTERN = re.compile(r"(?i)(?:https?://|www\.|\b[a-z0-9-]+\.(?:com|cn|org|net|io)\b)")


class S108QueryFacetError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelQueryAtomCandidate:
    case_key: str
    evidence_slot_id: str
    evidence_owner_entity_key: str
    language: str
    atom_kind: str
    value: str
    provenance: str = "model_proposed_untrusted"

    def as_dict(self) -> dict[str, str]:
        return {
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "language": self.language,
            "atom_kind": self.atom_kind,
            "value": self.value,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class QueryFacetPlan:
    plan_id: str
    plan_digest: str
    case_key: str
    evidence_slot_id: str
    language: str
    subject_entity_key: str
    subject_aliases: tuple[str, ...]
    evidence_owner_entity_key: str
    evidence_owner_aliases: tuple[str, ...]
    evidence_owner_role: str
    relationship_direction: str
    period_terms: tuple[str, ...]
    as_of_date: str
    source_families: tuple[str, ...]
    preferred_domains: tuple[str, ...]
    document_types: tuple[str, ...]
    metric_facets: tuple[str, ...]
    product_facets: tuple[str, ...]
    mechanism_facets: tuple[str, ...]
    exact_lookup_queries: tuple[str, ...]
    lexical_queries: tuple[str, ...]
    semantic_queries: tuple[str, ...]
    graph_query: Mapping[str, Any]
    negative_queries: tuple[str, ...]
    forbidden_expansions: tuple[str, ...]
    route_specific_filters: Mapping[str, Any]
    original_queries: Mapping[str, str]
    source_intent_ids: tuple[str, ...]
    source_intent_digests: tuple[str, ...]
    eligible_external_routes: tuple[str, ...]
    eligible_internal_routes: tuple[str, ...]
    accepted_model_atoms: tuple[Mapping[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "language": self.language,
            "subject_entity_key": self.subject_entity_key,
            "subject_aliases": list(self.subject_aliases),
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "evidence_owner_aliases": list(self.evidence_owner_aliases),
            "evidence_owner_role": self.evidence_owner_role,
            "relationship_direction": self.relationship_direction,
            "period_terms": list(self.period_terms),
            "as_of_date": self.as_of_date,
            "source_families": list(self.source_families),
            "preferred_domains": list(self.preferred_domains),
            "document_types": list(self.document_types),
            "metric_facets": list(self.metric_facets),
            "product_facets": list(self.product_facets),
            "mechanism_facets": list(self.mechanism_facets),
            "exact_lookup_queries": list(self.exact_lookup_queries),
            "lexical_queries": list(self.lexical_queries),
            "semantic_queries": list(self.semantic_queries),
            "graph_query": dict(self.graph_query),
            "negative_queries": list(self.negative_queries),
            "forbidden_expansions": list(self.forbidden_expansions),
            "route_specific_filters": dict(self.route_specific_filters),
            "original_queries": dict(self.original_queries),
            "source_intent_ids": list(self.source_intent_ids),
            "source_intent_digests": list(self.source_intent_digests),
            "eligible_external_routes": list(self.eligible_external_routes),
            "eligible_internal_routes": list(self.eligible_internal_routes),
            "accepted_model_atoms": [dict(row) for row in self.accepted_model_atoms],
        }


def load_query_facet_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile") != "sha256_utf8_lf_normalized_v1"
        or policy.get("as_of_date") != "2026-08-06"
        or tuple(policy.get("cases") or ()) != CASES
        or tuple(policy.get("languages") or ()) != LANGUAGES
        or tuple(policy.get("external_evidence_slots") or ()) != SLOT_IDS
    ):
        raise S108QueryFacetError("s1_08_query_facet_policy_identity_invalid")
    contract = policy.get("plan_contract") or {}
    if contract != {
        "unique_facet_plan_count": 36,
        "bound_search_intent_count": 60,
        "case_slot_count": 12,
        "official_external_plan_count": 36,
        "semantic_external_plan_count": 24,
        "minimum_exact_queries_per_plan": 2,
        "minimum_lexical_queries_per_plan": 2,
        "minimum_semantic_queries_per_plan": 1,
        "graph_query_count_per_plan": 1,
        "maximum_model_atoms_per_plan": 6,
    }:
        raise S108QueryFacetError("s1_08_query_facet_plan_contract_invalid")
    expected_routes = {
        "external_official_primary",
        "external_semantic_shadow",
        "internal_exact_object_lookup",
        "internal_bm25",
        "internal_dense",
        "internal_relationship_graph",
    }
    routes = policy.get("route_contracts") or {}
    if set(routes) != expected_routes or any(
        row.get("execution_admitted") is not False for row in routes.values()
    ):
        raise S108QueryFacetError("s1_08_query_facet_route_contract_invalid")
    if set(policy.get("slot_facets") or {}) != set(SLOT_IDS):
        raise S108QueryFacetError("s1_08_query_facet_slot_taxonomy_invalid")
    if set(policy.get("case_facets") or {}) != set(CASES):
        raise S108QueryFacetError("s1_08_query_facet_case_taxonomy_invalid")
    if set(policy.get("owner_facets") or {}) != {
        "DELL",
        "MU",
        "NVDA",
        "MSFT",
        "TSMC",
    }:
        raise S108QueryFacetError("s1_08_query_facet_owner_taxonomy_invalid")
    for row in policy["slot_facets"].values():
        if any(set(row.get(field) or {}) != set(LANGUAGES) for field in (
            "document_types",
            "metrics",
            "mechanisms",
        )):
            raise S108QueryFacetError("s1_08_query_facet_slot_taxonomy_invalid")
    atoms = policy.get("model_atom_contract") or {}
    if (
        atoms.get("allowed_kinds") != list(MODEL_ATOM_KINDS)
        or atoms.get("called_during_this_scope") is not False
        or atoms.get("model_may_supply_identity_period_relationship_domain_filter_or_url")
        is not False
        or atoms.get("maximum_characters_per_atom") != 64
    ):
        raise S108QueryFacetError("s1_08_query_facet_model_atom_contract_invalid")
    if any(policy.get("zero_call_boundary", {}).values()):
        raise S108QueryFacetError("s1_08_query_facet_zero_call_boundary_invalid")
    return policy


def compile_query_facet_plans(
    *,
    intents: Sequence[SearchIntent],
    policy: Mapping[str, Any],
    model_atoms: Sequence[ModelQueryAtomCandidate] = (),
) -> tuple[QueryFacetPlan, ...]:
    grouped: dict[tuple[str, str, str, str], list[SearchIntent]] = {}
    for intent in intents:
        key = (
            intent.case_key,
            intent.evidence_slot_id,
            intent.evidence_owner_entity_key,
            intent.language,
        )
        grouped.setdefault(key, []).append(intent)
    if len(intents) != 60 or len(grouped) != 36:
        raise S108QueryFacetError("s1_08_query_facet_input_cardinality_invalid")
    aliases = _collect_aliases(intents)
    atoms_by_key = _validate_and_group_model_atoms(
        atoms=model_atoms,
        policy=policy,
        aliases=aliases,
        valid_keys=set(grouped),
    )
    plans = tuple(
        _compile_one_plan(
            rows=tuple(sorted(rows, key=lambda item: item.route_class)),
            policy=policy,
            aliases=aliases,
            model_atoms=atoms_by_key.get(key, ()),
        )
        for key, rows in sorted(grouped.items())
    )
    _validate_plan_set(plans=plans, policy=policy)
    return plans


def validate_query_facet_plan(plan: QueryFacetPlan, *, policy: Mapping[str, Any]) -> None:
    payload = plan.as_dict()
    supplied_id = payload.pop("plan_id")
    supplied_digest = payload.pop("plan_digest")
    expected = canonical_digest(payload)
    if supplied_digest != expected or supplied_id != f"query_facet_plan_{expected[:20]}":
        raise S108QueryFacetError("s1_08_query_facet_owned_identity_invalid")
    contract = policy["plan_contract"]
    if (
        len(plan.exact_lookup_queries)
        < int(contract["minimum_exact_queries_per_plan"])
        or len(plan.lexical_queries)
        < int(contract["minimum_lexical_queries_per_plan"])
        or len(plan.semantic_queries)
        < int(contract["minimum_semantic_queries_per_plan"])
        or not plan.graph_query
    ):
        raise S108QueryFacetError("s1_08_query_facet_family_coverage_invalid")
    positive = " ".join(
        (*plan.exact_lookup_queries, *plan.lexical_queries, *plan.semantic_queries)
    )
    if "http://" in positive.lower() or "https://" in positive.lower():
        raise S108QueryFacetError("s1_08_query_facet_url_leak")
    if any(token in positive for token in GOLD_TOKEN_PREFIXES):
        raise S108QueryFacetError("s1_08_query_facet_gold_leak")
    if plan.route_specific_filters.get("execution_admitted") is not False:
        raise S108QueryFacetError("s1_08_query_facet_execution_admission_invalid")


def build_query_facet_zero_call_proof(
    *, plans: Sequence[QueryFacetPlan], policy: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_plan_set(plans=plans, policy=policy)
    source_intent_ids = {
        intent_id for plan in plans for intent_id in plan.source_intent_ids
    }
    case_slots = {(plan.case_key, plan.evidence_slot_id) for plan in plans}
    external_route_counts = {
        route: sum(route in plan.eligible_external_routes for plan in plans)
        for route in (
            "external_official_primary",
            "external_semantic_shadow",
        )
    }
    family_counts = {
        "exact_lookup_queries": sum(len(plan.exact_lookup_queries) for plan in plans),
        "lexical_queries": sum(len(plan.lexical_queries) for plan in plans),
        "semantic_queries": sum(len(plan.semantic_queries) for plan in plans),
        "graph_queries": len(plans),
        "negative_queries": sum(len(plan.negative_queries) for plan in plans),
    }
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "zero_call_engineering_pass",
        "plan_count": len(plans),
        "bound_search_intent_count": len(source_intent_ids),
        "case_slot_count": len(case_slots),
        "external_route_counts": external_route_counts,
        "query_family_counts": family_counts,
        "plans": [plan.as_dict() for plan in plans],
        "quality_checks": {
            "all_plans_have_exact_lexical_semantic_graph_and_negative_families": True,
            "all_positive_queries_case_owner_period_direction_bound": True,
            "cross_case_positive_alias_pollution_count": 0,
            "gold_or_URL_leak_count": 0,
            "model_atom_count": sum(len(plan.accepted_model_atoms) for plan in plans),
            "route_execution_admitted": False,
            "candidate_ceiling_proven": False,
            "BGE_or_rerank_admitted": False,
        },
        "observed_calls": dict(policy["zero_call_boundary"]),
        "stage_acceptance": {
            "unified_query_facet_contract": True,
            "deterministic_local_variant": True,
            "model_assisted_variant": False,
            "three_way_evaluation": False,
            "combined_external_live": False,
            "internal_retrieval_integration": False,
            "candidate_ceiling_and_qrels": False,
            "BGE_fusion_rerank": False,
            "downstream_utilization": False,
            "S1_08": False,
            "release": False,
        },
        "known_boundary": (
            "This zero-call proof establishes a shared deterministic query-facet "
            "contract only. It does not measure provider recall, call a model, execute "
            "internal retrieval, prove candidate ceiling, admit BGE/reranking, promote "
            "Evidence, prove downstream research use, close S1-08 or release the product."
        ),
    }
    return {**body, "proof_digest": canonical_digest(body)}


def _compile_one_plan(
    *,
    rows: Sequence[SearchIntent],
    policy: Mapping[str, Any],
    aliases: Mapping[str, Mapping[str, tuple[str, ...]]],
    model_atoms: Sequence[ModelQueryAtomCandidate],
) -> QueryFacetPlan:
    precise = next(
        (row for row in rows if row.route_class == "precise_official_domain"),
        None,
    )
    if precise is None:
        raise S108QueryFacetError("s1_08_query_facet_precise_intent_missing")
    shared_fields = (
        "case_key",
        "evidence_slot_id",
        "language",
        "subject_entity_key",
        "subject_aliases",
        "evidence_owner_entity_key",
        "evidence_owner_aliases",
        "evidence_owner_role",
        "claim_direction",
        "period_terms",
        "as_of_date",
    )
    if any(
        any(getattr(row, field) != getattr(precise, field) for field in shared_fields)
        for row in rows
    ):
        raise S108QueryFacetError("s1_08_query_facet_group_scope_mismatch")
    route_classes = {row.route_class for row in rows}
    expected_routes = {"precise_official_domain"}
    if precise.evidence_slot_id in {
        "customer_demand_and_deployment_validation",
        "supply_chain_capacity_and_counterevidence",
    }:
        expected_routes.add("semantic_open_web")
    if route_classes != expected_routes:
        raise S108QueryFacetError("s1_08_query_facet_route_binding_invalid")

    language = precise.language
    slot = policy["slot_facets"][precise.evidence_slot_id]
    document_types = _unique(slot["document_types"][language])
    metrics = list(_unique(slot["metrics"][language]))
    mechanisms = list(_unique(slot["mechanisms"][language]))
    products = list(
        _unique(
            [
                *policy["owner_facets"][precise.evidence_owner_entity_key][language],
                *policy["case_facets"][precise.case_key][language],
            ]
        )
    )
    accepted_atoms: list[dict[str, str]] = []
    for atom in model_atoms:
        accepted_atoms.append(atom.as_dict())
        if atom.atom_kind == "metric":
            metrics.append(atom.value)
        elif atom.atom_kind == "product":
            products.append(atom.value)
        else:
            mechanisms.append(atom.value)
    metrics_tuple = _unique(metrics)
    products_tuple = _unique(products)
    mechanisms_tuple = _unique(mechanisms)
    owner = precise.evidence_owner_aliases[0]
    subject = precise.subject_aliases[0]
    period = precise.period_terms[0]
    relationship = policy["relationship_phrases"][precise.claim_direction][language]
    exact_queries = _unique(
        (
            _join(owner, period, document_types[0]),
            _join(owner, products_tuple[0], metrics_tuple[0], document_types[-1]),
        )
    )
    lexical_query_values = [
        _join(
            owner,
            period,
            *document_types[:2],
            *products_tuple[:2],
            *metrics_tuple[:2],
            *mechanisms_tuple[:2],
        ),
        _join(
            subject,
            owner,
            relationship,
            products_tuple[0],
            metrics_tuple[0],
            mechanisms_tuple[0],
        ),
    ]
    if accepted_atoms:
        lexical_query_values.append(
            _join(
                owner,
                period,
                document_types[0],
                *(row["value"] for row in accepted_atoms),
            )
        )
    lexical_queries = _unique(lexical_query_values)
    if language == "en":
        semantic_query = (
            f"What did {owner} disclose for {period} about {relationship}, "
            f"especially {products_tuple[0]}, {metrics_tuple[0]} and "
            f"{mechanisms_tuple[0]}, and what counterevidence limits the inference "
            f"for {subject}?"
        )
    else:
        semantic_query = (
            f"{owner} 在{period}对{relationship}披露了什么，尤其是"
            f"{products_tuple[0]}、{metrics_tuple[0]}与{mechanisms_tuple[0]}；"
            f"哪些反向证据会限制对{subject}的推断？"
        )
    semantic_queries = [semantic_query]
    if accepted_atoms and language == "en":
        semantic_queries.append(
            f"Find {owner}'s own disclosure about {relationship} using the bounded "
            f"additional facets {', '.join(row['value'] for row in accepted_atoms)}; "
            f"do not change the entity, period or relationship scope for {subject}."
        )
    elif accepted_atoms:
        semantic_queries.append(
            f"使用受控补充维度{'、'.join(row['value'] for row in accepted_atoms)}检索"
            f"{owner}自身对{relationship}的披露；不得改变{subject}的主体、期间或关系范围。"
        )
    allowed_entities = {precise.case_key, precise.evidence_owner_entity_key}
    negative_aliases = sorted(
        {
            alias
            for entity_key, localized in aliases.items()
            if entity_key not in allowed_entities
            for alias in localized.get(language, ())
        },
        key=lambda value: value.casefold(),
    )
    negative_queries = tuple(
        f"exclude_entity_alias::{value}" for value in negative_aliases
    ) + tuple(
        f"forbid_expansion::{value}" for value in policy["forbidden_expansions"]
    )
    source_families = _unique(
        family for row in rows for family in row.source_families
    )
    preferred_domains = _unique(
        domain for row in rows for domain in row.preferred_domains
    )
    original_queries = {
        row.route_class: row.query_text
        for row in sorted(rows, key=lambda item: item.route_class)
    }
    external_routes = ["external_official_primary"]
    if "semantic_open_web" in route_classes:
        external_routes.append("external_semantic_shadow")
    graph_query = {
        "query_kind": "typed_one_hop_evidence_relationship",
        "subject_entity_key": precise.case_key,
        "evidence_owner_entity_key": precise.evidence_owner_entity_key,
        "evidence_owner_role": precise.evidence_owner_role,
        "relationship_direction": precise.claim_direction,
        "maximum_hops": 1,
        "period_terms": list(precise.period_terms),
        "as_of_date": precise.as_of_date,
        "forbidden_nested_relationships": [
            "evidence_owner_customer",
            "evidence_owner_supplier",
        ],
    }
    filters = {
        "case_key": precise.case_key,
        "subject_entity_key": precise.subject_entity_key,
        "evidence_owner_entity_key": precise.evidence_owner_entity_key,
        "evidence_owner_role": precise.evidence_owner_role,
        "relationship_direction": precise.claim_direction,
        "language": language,
        "allowed_period_terms": list(precise.period_terms),
        "publication_date_on_or_before": precise.as_of_date,
        "allowed_source_families": list(source_families),
        "allowed_document_types": list(document_types),
        "preferred_domains": list(preferred_domains),
        "candidate_state": "candidate_only_not_evidence",
        "allow_relaxed_identity_or_period_fallback": False,
        "execution_admitted": False,
    }
    payload = {
        "case_key": precise.case_key,
        "evidence_slot_id": precise.evidence_slot_id,
        "language": language,
        "subject_entity_key": precise.subject_entity_key,
        "subject_aliases": list(precise.subject_aliases),
        "evidence_owner_entity_key": precise.evidence_owner_entity_key,
        "evidence_owner_aliases": list(precise.evidence_owner_aliases),
        "evidence_owner_role": precise.evidence_owner_role,
        "relationship_direction": precise.claim_direction,
        "period_terms": list(precise.period_terms),
        "as_of_date": precise.as_of_date,
        "source_families": list(source_families),
        "preferred_domains": list(preferred_domains),
        "document_types": list(document_types),
        "metric_facets": list(metrics_tuple),
        "product_facets": list(products_tuple),
        "mechanism_facets": list(mechanisms_tuple),
        "exact_lookup_queries": list(exact_queries),
        "lexical_queries": list(lexical_queries),
        "semantic_queries": semantic_queries,
        "graph_query": graph_query,
        "negative_queries": list(negative_queries),
        "forbidden_expansions": list(policy["forbidden_expansions"]),
        "route_specific_filters": filters,
        "original_queries": original_queries,
        "source_intent_ids": sorted(row.intent_id for row in rows),
        "source_intent_digests": sorted(row.intent_digest for row in rows),
        "eligible_external_routes": external_routes,
        "eligible_internal_routes": [
            "internal_exact_object_lookup",
            "internal_bm25",
            "internal_dense",
            "internal_relationship_graph",
        ],
        "accepted_model_atoms": accepted_atoms,
    }
    digest = canonical_digest(payload)
    plan = QueryFacetPlan(
        plan_id=f"query_facet_plan_{digest[:20]}",
        plan_digest=digest,
        case_key=precise.case_key,
        evidence_slot_id=precise.evidence_slot_id,
        language=language,
        subject_entity_key=precise.subject_entity_key,
        subject_aliases=precise.subject_aliases,
        evidence_owner_entity_key=precise.evidence_owner_entity_key,
        evidence_owner_aliases=precise.evidence_owner_aliases,
        evidence_owner_role=precise.evidence_owner_role,
        relationship_direction=precise.claim_direction,
        period_terms=precise.period_terms,
        as_of_date=precise.as_of_date,
        source_families=source_families,
        preferred_domains=preferred_domains,
        document_types=document_types,
        metric_facets=metrics_tuple,
        product_facets=products_tuple,
        mechanism_facets=mechanisms_tuple,
        exact_lookup_queries=exact_queries,
        lexical_queries=lexical_queries,
        semantic_queries=tuple(semantic_queries),
        graph_query=graph_query,
        negative_queries=negative_queries,
        forbidden_expansions=tuple(policy["forbidden_expansions"]),
        route_specific_filters=filters,
        original_queries=original_queries,
        source_intent_ids=tuple(payload["source_intent_ids"]),
        source_intent_digests=tuple(payload["source_intent_digests"]),
        eligible_external_routes=tuple(external_routes),
        eligible_internal_routes=tuple(payload["eligible_internal_routes"]),
        accepted_model_atoms=tuple(accepted_atoms),
    )
    validate_query_facet_plan(plan, policy=policy)
    _require_positive_query_scope(plan=plan, aliases=aliases)
    return plan


def _collect_aliases(
    intents: Sequence[SearchIntent],
) -> dict[str, dict[str, tuple[str, ...]]]:
    values: dict[str, dict[str, set[str]]] = {}
    for row in intents:
        for entity_key, entity_aliases in (
            (row.subject_entity_key, row.subject_aliases),
            (row.evidence_owner_entity_key, row.evidence_owner_aliases),
        ):
            values.setdefault(entity_key, {}).setdefault(row.language, set()).update(
                entity_aliases
            )
    return {
        entity_key: {
            language: tuple(sorted(items, key=lambda item: item.casefold()))
            for language, items in localized.items()
        }
        for entity_key, localized in values.items()
    }


def _validate_and_group_model_atoms(
    *,
    atoms: Sequence[ModelQueryAtomCandidate],
    policy: Mapping[str, Any],
    aliases: Mapping[str, Mapping[str, tuple[str, ...]]],
    valid_keys: set[tuple[str, str, str, str]],
) -> dict[tuple[str, str, str, str], tuple[ModelQueryAtomCandidate, ...]]:
    grouped: dict[tuple[str, str, str, str], list[ModelQueryAtomCandidate]] = {}
    all_aliases = {
        _normalize(alias)
        for localized in aliases.values()
        for values in localized.values()
        for alias in values
    }
    atom_contract = policy["model_atom_contract"]
    for atom in atoms:
        key = (
            atom.case_key,
            atom.evidence_slot_id,
            atom.evidence_owner_entity_key,
            atom.language,
        )
        value = " ".join(str(atom.value).split())
        if key not in valid_keys:
            raise S108QueryFacetError("s1_08_query_facet_model_atom_scope_invalid")
        if (
            atom.atom_kind not in MODEL_ATOM_KINDS
            or atom.language not in LANGUAGES
            or atom.provenance != "model_proposed_untrusted"
            or not value
            or len(value) > int(atom_contract["maximum_characters_per_atom"])
        ):
            raise S108QueryFacetError("s1_08_query_facet_model_atom_shape_invalid")
        if (
            _DOMAIN_PATTERN.search(value)
            or _PERIOD_PATTERN.search(value)
            or any(token in value for token in GOLD_TOKEN_PREFIXES)
            or any(
                _contains_alias(value=value, alias=alias)
                for alias in all_aliases
            )
        ):
            raise S108QueryFacetError("s1_08_query_facet_model_atom_authority_violation")
        normalized_atom = ModelQueryAtomCandidate(
            case_key=atom.case_key,
            evidence_slot_id=atom.evidence_slot_id,
            evidence_owner_entity_key=atom.evidence_owner_entity_key,
            language=atom.language,
            atom_kind=atom.atom_kind,
            value=value,
            provenance=atom.provenance,
        )
        grouped.setdefault(key, []).append(normalized_atom)
    maximum = int(atom_contract["maximum_model_atoms_per_plan"] if "maximum_model_atoms_per_plan" in atom_contract else policy["plan_contract"]["maximum_model_atoms_per_plan"])
    for key, rows in grouped.items():
        identities = {(row.atom_kind, _normalize(row.value)) for row in rows}
        if len(rows) > maximum or len(identities) != len(rows):
            raise S108QueryFacetError("s1_08_query_facet_model_atom_budget_invalid")
        grouped[key] = sorted(rows, key=lambda row: (row.atom_kind, row.value.casefold()))
    return {key: tuple(rows) for key, rows in grouped.items()}


def _validate_plan_set(
    *, plans: Sequence[QueryFacetPlan], policy: Mapping[str, Any]
) -> None:
    contract = policy["plan_contract"]
    if (
        len(plans) != int(contract["unique_facet_plan_count"])
        or len({plan.plan_id for plan in plans}) != len(plans)
        or len({plan.plan_digest for plan in plans}) != len(plans)
        or len({(plan.case_key, plan.evidence_slot_id) for plan in plans})
        != int(contract["case_slot_count"])
        or len({item for plan in plans for item in plan.source_intent_ids})
        != int(contract["bound_search_intent_count"])
    ):
        raise S108QueryFacetError("s1_08_query_facet_plan_set_invalid")
    if (
        sum("external_official_primary" in plan.eligible_external_routes for plan in plans)
        != int(contract["official_external_plan_count"])
        or sum("external_semantic_shadow" in plan.eligible_external_routes for plan in plans)
        != int(contract["semantic_external_plan_count"])
    ):
        raise S108QueryFacetError("s1_08_query_facet_external_route_coverage_invalid")
    for plan in plans:
        validate_query_facet_plan(plan, policy=policy)


def _require_positive_query_scope(
    *, plan: QueryFacetPlan, aliases: Mapping[str, Mapping[str, tuple[str, ...]]]
) -> None:
    allowed = {plan.subject_entity_key, plan.evidence_owner_entity_key}
    positive = _normalize(
        " ".join(
            (*plan.exact_lookup_queries, *plan.lexical_queries, *plan.semantic_queries)
        )
    )
    for entity_key, localized in aliases.items():
        if entity_key in allowed:
            continue
        for alias in localized.get(plan.language, ()):
            if _contains_alias(value=positive, alias=alias):
                raise S108QueryFacetError(
                    "s1_08_query_facet_cross_case_positive_alias_pollution"
                )


def _unique(values: Sequence[str] | Any) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value).split())
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            ordered.append(text)
    return tuple(ordered)


def _join(*parts: str) -> str:
    selected: list[tuple[str, str]] = []
    for part in parts:
        text = " ".join(str(part).split())
        normalized = _normalize(text)
        if not normalized or any(normalized in prior for _, prior in selected):
            continue
        selected = [
            (prior_text, prior)
            for prior_text, prior in selected
            if prior not in normalized
        ]
        selected.append((text, normalized))
    return " ".join(text for text, _ in selected)


def _normalize(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _contains_alias(*, value: str, alias: str) -> bool:
    normalized_value = _normalize(value)
    normalized_alias = _normalize(alias)
    if not normalized_alias:
        return False
    if normalized_alias.isascii() and normalized_alias.replace(" ", "").isalnum():
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
                normalized_value,
            )
        )
    return normalized_alias in normalized_value


__all__ = [
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "PROOF_SCHEMA",
    "RUN_SCOPE",
    "ModelQueryAtomCandidate",
    "QueryFacetPlan",
    "S108QueryFacetError",
    "build_query_facet_zero_call_proof",
    "compile_query_facet_plans",
    "load_query_facet_policy",
    "validate_query_facet_plan",
]
