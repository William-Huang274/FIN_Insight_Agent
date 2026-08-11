from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest


POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_query_facet_integration_policy_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.internal_query_facet_integration:v1"
POLICY_SCHEMA_V1_1 = (
    "fin_ia_0_1_3_s1_internal_query_facet_integration_policy_v1_1"
)
CONTRACT_REF_V1_1 = "fin_0_1_3.S1.internal_query_facet_integration:v1.1"
POLICY_SCHEMA_V1_2 = (
    "fin_ia_0_1_3_s1_internal_query_facet_integration_policy_v1_2"
)
CONTRACT_REF_V1_2 = "fin_0_1_3.S1.internal_query_facet_integration:v1.2"
RUN_SCOPE = "S1_INTERNAL_RETRIEVAL_QUERY_FACET_INTEGRATION"
PROOF_SCHEMA = "fin_ia_0_1_3_s1_internal_query_facet_integration_zero_call_proof_v1_0"
PROOF_SCHEMA_V1_1 = (
    "fin_ia_0_1_3_s1_internal_query_facet_integration_zero_call_proof_v1_1"
)
PROOF_SCHEMA_V1_2 = (
    "fin_ia_0_1_3_s1_internal_query_facet_integration_zero_call_proof_v1_2"
)
CASES = ("DELL", "MU", "NVDA")
LANGUAGES = ("en", "zh")
SLOT_IDS = (
    "issuer_results_and_management_commentary",
    "regulatory_risk_and_financial_reconciliation",
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
ROUTE_IDS = (
    "internal_sql_exact",
    "internal_object_bm25",
    "internal_bm25",
    "internal_milvus_dense",
    "internal_relationship_graph",
)
_YEAR_PATTERN = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_GOLD_TOKEN_PREFIXES = (
    "SRC_",
    "DELL_E",
    "MU_E",
    "NVDA_E",
    "DELL_T",
    "MU_T",
    "NVDA_T",
)


class S1InternalQueryFacetError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class InternalQueryFacetBundle:
    bundle_id: str
    bundle_digest: str
    case_key: str
    evidence_slot_id: str
    evidence_owner_entity_key: str
    subject_entity_key: str
    evidence_owner_ticker: str
    subject_ticker: str
    relationship_direction: str
    canonical_language: str
    alternate_language: str
    source_plan_ids: Mapping[str, str]
    source_plan_digests: Mapping[str, str]
    period_terms: tuple[str, ...]
    fiscal_years: tuple[int, ...]
    as_of_date: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_digest": self.bundle_digest,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "subject_entity_key": self.subject_entity_key,
            "evidence_owner_ticker": self.evidence_owner_ticker,
            "subject_ticker": self.subject_ticker,
            "relationship_direction": self.relationship_direction,
            "canonical_language": self.canonical_language,
            "alternate_language": self.alternate_language,
            "source_plan_ids": dict(self.source_plan_ids),
            "source_plan_digests": dict(self.source_plan_digests),
            "period_terms": list(self.period_terms),
            "fiscal_years": list(self.fiscal_years),
            "as_of_date": self.as_of_date,
        }


@dataclass(frozen=True)
class InternalRouteRequest:
    request_id: str
    request_digest: str
    bundle_id: str
    bundle_digest: str
    case_key: str
    evidence_slot_id: str
    subject_entity_key: str
    subject_ticker: str
    evidence_owner_entity_key: str
    evidence_owner_ticker: str
    relationship_direction: str
    route_id: str
    query_family: str
    query_texts: tuple[str, ...]
    alternate_language_query_texts: tuple[str, ...]
    typed_filters: Mapping[str, Any]
    negative_filters: Mapping[str, Any]
    candidate_budget: int
    authority_boundary: str
    candidate_state: str
    allow_relaxed_identity_period_or_relationship_fallback: bool
    execution_admitted: bool
    embedding_admitted: bool
    rerank_admitted: bool
    evidence_promotion_admitted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "bundle_id": self.bundle_id,
            "bundle_digest": self.bundle_digest,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "subject_entity_key": self.subject_entity_key,
            "subject_ticker": self.subject_ticker,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "evidence_owner_ticker": self.evidence_owner_ticker,
            "relationship_direction": self.relationship_direction,
            "route_id": self.route_id,
            "query_family": self.query_family,
            "query_texts": list(self.query_texts),
            "alternate_language_query_texts": list(
                self.alternate_language_query_texts
            ),
            "typed_filters": dict(self.typed_filters),
            "negative_filters": dict(self.negative_filters),
            "candidate_budget": self.candidate_budget,
            "authority_boundary": self.authority_boundary,
            "candidate_state": self.candidate_state,
            "allow_relaxed_identity_period_or_relationship_fallback": (
                self.allow_relaxed_identity_period_or_relationship_fallback
            ),
            "execution_admitted": self.execution_admitted,
            "embedding_admitted": self.embedding_admitted,
            "rerank_admitted": self.rerank_admitted,
            "evidence_promotion_admitted": self.evidence_promotion_admitted,
        }


def load_internal_query_facet_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    identity = (policy.get("schema_version"), policy.get("contract_ref"))
    if (
        identity
        not in {
            (POLICY_SCHEMA, CONTRACT_REF),
            (POLICY_SCHEMA_V1_1, CONTRACT_REF_V1_1),
            (POLICY_SCHEMA_V1_2, CONTRACT_REF_V1_2),
        }
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile") != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalQueryFacetError("internal_query_facet_policy_identity_invalid")
    projection = policy.get("projection_contract") or {}
    if projection != {
        "source_query_facet_plan_count": 36,
        "bilingual_bundle_count": 18,
        "physical_route_count_per_bundle": 5,
        "physical_request_count": 90,
        "canonical_internal_corpus_language": "en",
        "alternate_language": "zh",
        "alternate_language_execution_state": "retained_not_scheduled_in_this_scope",
    }:
        raise S1InternalQueryFacetError(
            "internal_query_facet_projection_contract_invalid"
        )
    if tuple(policy.get("physical_routes") or {}) != ROUTE_IDS:
        raise S1InternalQueryFacetError("internal_query_facet_route_contract_invalid")
    if set(policy.get("slot_route_filters") or {}) != set(SLOT_IDS):
        raise S1InternalQueryFacetError("internal_query_facet_slot_contract_invalid")
    if set(policy.get("entity_ticker_projection") or {}) != {
        "DELL",
        "MU",
        "NVDA",
        "MSFT",
        "TSMC",
    }:
        raise S1InternalQueryFacetError("internal_query_facet_entity_map_invalid")
    hard = policy.get("hard_boundaries") or {}
    if (
        hard.get("use_evidence_owner_ticker_not_case_ticker_for_internal_content_routes")
        is not True
        or hard.get("subject_and_evidence_owner_remain_distinct") is not True
        or hard.get("period_and_as_of_filters_required") is not True
        or hard.get("relationship_direction_required") is not True
        or hard.get("allow_relaxed_identity_period_or_relationship_fallback")
        is not False
        or hard.get("candidate_state") != "candidate_only_not_evidence"
        or hard.get("execution_admitted") is not False
        or hard.get("bge_fusion_rerank_admitted") is not False
        or hard.get("gold_or_expected_answer_locator_may_enter_query") is not False
    ):
        raise S1InternalQueryFacetError("internal_query_facet_boundary_invalid")
    if any((policy.get("zero_call_boundary") or {}).values()):
        raise S1InternalQueryFacetError("internal_query_facet_zero_call_invalid")
    if _uses_typed_period_roles(policy):
        expected_milvus_period_authority = (
            "reporting_fiscal_years"
            if _uses_milvus_reporting_fiscal_years(policy)
            else "index_filing_calendar_years"
        )
        if policy.get("period_filter_contract") != {
            "reporting_period_field": "reporting_fiscal_years",
            "document_index_period_field": "index_filing_calendar_years",
            "document_index_year_derivation": (
                "cap_reporting_fiscal_year_at_as_of_calendar_year_v1"
            ),
            "sql_period_authority": "reporting_fiscal_years",
            "object_bm25_period_authority": "index_filing_calendar_years",
            "bm25_period_authority": "index_filing_calendar_years",
            "milvus_period_authority": expected_milvus_period_authority,
            "graph_period_state": "intent_preserved_index_unverifiable",
        }:
            raise S1InternalQueryFacetError(
                "internal_query_facet_period_filter_contract_invalid"
            )
        if (
            hard.get("reporting_and_document_index_period_roles_separated")
            is not True
            or hard.get("ambiguous_fiscal_year_filter_allowed") is not False
        ):
            raise S1InternalQueryFacetError(
                "internal_query_facet_period_role_boundary_invalid"
            )
    return policy


def compile_internal_query_facet_requests(
    *, query_facet_proof: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[tuple[InternalQueryFacetBundle, ...], tuple[InternalRouteRequest, ...]]:
    _validate_source_proof(query_facet_proof)
    source_plans = tuple(dict(row) for row in query_facet_proof.get("plans") or [])
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}
    for plan in source_plans:
        _validate_source_plan(plan)
        key = (
            str(plan.get("case_key") or ""),
            str(plan.get("evidence_slot_id") or ""),
            str(plan.get("evidence_owner_entity_key") or ""),
        )
        language = str(plan.get("language") or "")
        if language in grouped.setdefault(key, {}):
            raise S1InternalQueryFacetError(
                "internal_query_facet_duplicate_language_plan"
            )
        grouped[key][language] = plan
    expected_bundle_count = int(policy["projection_contract"]["bilingual_bundle_count"])
    if len(grouped) != expected_bundle_count or any(
        set(localized) != set(LANGUAGES) for localized in grouped.values()
    ):
        raise S1InternalQueryFacetError("internal_query_facet_bilingual_pairing_invalid")

    bundles: list[InternalQueryFacetBundle] = []
    requests: list[InternalRouteRequest] = []
    for key, localized in sorted(grouped.items()):
        english = localized["en"]
        alternate = localized["zh"]
        _require_bilingual_authority_match(english=english, alternate=alternate)
        bundle = _build_bundle(english=english, alternate=alternate, policy=policy)
        bundles.append(bundle)
        requests.extend(
            _build_route_request(
                bundle=bundle,
                english=english,
                alternate=alternate,
                route_id=route_id,
                policy=policy,
            )
            for route_id in ROUTE_IDS
        )
    bundles_tuple = tuple(bundles)
    requests_tuple = tuple(requests)
    _validate_compiled_set(
        bundles=bundles_tuple,
        requests=requests_tuple,
        policy=policy,
    )
    return bundles_tuple, requests_tuple


def validate_internal_route_request(
    request: InternalRouteRequest,
    *,
    bundles: Mapping[str, InternalQueryFacetBundle],
    policy: Mapping[str, Any],
) -> None:
    payload = request.as_dict()
    supplied_id = payload.pop("request_id")
    supplied_digest = payload.pop("request_digest")
    expected = canonical_digest(payload)
    if supplied_digest != expected or supplied_id != f"internal_route_request_{expected[:20]}":
        raise S1InternalQueryFacetError("internal_route_request_owned_identity_invalid")
    bundle = bundles.get(request.bundle_id)
    if bundle is None or bundle.bundle_digest != request.bundle_digest:
        raise S1InternalQueryFacetError("internal_route_request_bundle_binding_invalid")
    if (
        request.case_key,
        request.evidence_slot_id,
        request.subject_entity_key,
        request.subject_ticker,
        request.evidence_owner_entity_key,
        request.evidence_owner_ticker,
        request.relationship_direction,
    ) != (
        bundle.case_key,
        bundle.evidence_slot_id,
        bundle.subject_entity_key,
        bundle.subject_ticker,
        bundle.evidence_owner_entity_key,
        bundle.evidence_owner_ticker,
        bundle.relationship_direction,
    ):
        raise S1InternalQueryFacetError("internal_route_request_scope_drift")
    route_policy = (policy.get("physical_routes") or {}).get(request.route_id)
    if not route_policy or (
        request.query_family,
        request.candidate_budget,
        request.authority_boundary,
    ) != (
        route_policy["query_family"],
        int(route_policy["candidate_budget"]),
        route_policy["authority_boundary"],
    ):
        raise S1InternalQueryFacetError("internal_route_request_policy_mismatch")
    filters = request.typed_filters
    common_filter_drift = (
        filters.get("evidence_owner_ticker") != request.evidence_owner_ticker
        or filters.get("subject_ticker") != request.subject_ticker
        or filters.get("publication_date_on_or_before") != bundle.as_of_date
        or filters.get("relationship_direction") != request.relationship_direction
        or filters.get("allow_relaxed_identity_period_or_relationship_fallback")
        is not False
    )
    if _uses_typed_period_roles(policy):
        expected_index_years = _index_filing_calendar_years(
            bundle.fiscal_years, bundle.as_of_date
        )
        period_filter_drift = (
            "fiscal_years" in filters
            or tuple(filters.get("reporting_fiscal_years") or ())
            != bundle.fiscal_years
            or tuple(filters.get("index_filing_calendar_years") or ())
            != expected_index_years
            or filters.get("period_filter_contract")
            != "reporting_vs_document_index_v1"
        )
        if request.route_id == "internal_milvus_dense":
            period_filter_drift = period_filter_drift or tuple(
                filters.get("years") or ()
            ) != (
                bundle.fiscal_years
                if _uses_milvus_reporting_fiscal_years(policy)
                else expected_index_years
            )
    else:
        period_filter_drift = (
            tuple(filters.get("fiscal_years") or ()) != bundle.fiscal_years
        )
    if common_filter_drift or period_filter_drift:
        raise S1InternalQueryFacetError("internal_route_request_typed_filter_drift")
    if request.route_id != "internal_sql_exact" and not request.query_texts and request.route_id != "internal_relationship_graph":
        raise S1InternalQueryFacetError("internal_route_request_query_missing")
    if request.route_id == "internal_sql_exact" and request.query_texts:
        raise S1InternalQueryFacetError("internal_sql_exact_free_text_forbidden")
    if request.route_id == "internal_relationship_graph" and (
        request.query_texts
        or filters.get("maximum_hops") != 1
        or filters.get("evidence_owner_entity_key") != request.evidence_owner_entity_key
    ):
        raise S1InternalQueryFacetError("internal_graph_typed_query_invalid")
    all_text = " ".join(
        (*request.query_texts, *request.alternate_language_query_texts)
    )
    if any(token in all_text for token in _GOLD_TOKEN_PREFIXES) or "http://" in all_text.lower() or "https://" in all_text.lower():
        raise S1InternalQueryFacetError("internal_route_request_gold_or_url_leak")
    if (
        request.candidate_state != "candidate_only_not_evidence"
        or request.allow_relaxed_identity_period_or_relationship_fallback
        or request.execution_admitted
        or request.embedding_admitted
        or request.rerank_admitted
        or request.evidence_promotion_admitted
    ):
        raise S1InternalQueryFacetError("internal_route_request_authority_invalid")


def build_internal_query_facet_zero_call_proof(
    *,
    bundles: Sequence[InternalQueryFacetBundle],
    requests: Sequence[InternalRouteRequest],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_compiled_set(
        bundles=tuple(bundles), requests=tuple(requests), policy=policy
    )
    route_counts = {
        route_id: sum(request.route_id == route_id for request in requests)
        for route_id in ROUTE_IDS
    }
    cross_entity_requests = [
        request
        for request in requests
        if request.subject_ticker != request.evidence_owner_ticker
    ]
    tsmc_requests = [
        request
        for request in requests
        if request.evidence_owner_entity_key == "TSMC"
    ]
    uses_typed_period_roles = _uses_typed_period_roles(policy)
    serialized_bundles: list[dict[str, Any]] = []
    for bundle in bundles:
        serialized = bundle.as_dict()
        if uses_typed_period_roles:
            serialized.update(
                {
                    "reporting_fiscal_years": list(bundle.fiscal_years),
                    "index_filing_calendar_years": list(
                        _index_filing_calendar_years(
                            bundle.fiscal_years, bundle.as_of_date
                        )
                    ),
                    "period_filter_contract": "reporting_vs_document_index_v1",
                }
            )
        serialized_bundles.append(serialized)
    body = {
        "schema_version": (
            PROOF_SCHEMA_V1_2
            if _uses_milvus_reporting_fiscal_years(policy)
            else PROOF_SCHEMA_V1_1
            if uses_typed_period_roles
            else PROOF_SCHEMA
        ),
        "contract_ref": (
            CONTRACT_REF_V1_2
            if _uses_milvus_reporting_fiscal_years(policy)
            else CONTRACT_REF_V1_1
            if uses_typed_period_roles
            else CONTRACT_REF
        ),
        "run_scope": RUN_SCOPE,
        "status": "zero_call_engineering_pass",
        "source_query_facet_plan_count": 36,
        "bilingual_bundle_count": len(bundles),
        "physical_request_count": len(requests),
        "route_request_counts": route_counts,
        "cross_entity_request_count": len(cross_entity_requests),
        "tsmc_to_tsm_projection_request_count": len(tsmc_requests),
        "bundles": serialized_bundles,
        "requests": [request.as_dict() for request in requests],
        "quality_checks": {
            "all_source_plans_bilingually_paired": True,
            "all_routes_consume_route_specific_query_family": True,
            "all_content_routes_filter_on_evidence_owner_not_case_ticker": True,
            "all_requests_preserve_subject_owner_and_relationship_direction": True,
            "all_requests_preserve_period_and_as_of_filters": True,
            "reporting_and_document_index_period_roles_separated": (
                uses_typed_period_roles
            ),
            "ambiguous_fiscal_year_filter_present": False
            if uses_typed_period_roles
            else True,
            "tsmc_entity_projects_to_local_tsm_ticker": True,
            "cross_case_alias_or_gold_locator_leak_count": 0,
            "alternate_language_retained_but_not_scheduled": True,
            "candidate_ceiling_proven": False,
            "BGE_fusion_rerank_admitted": False,
            "evidence_or_downstream_utilization_proven": False,
        },
        "observed_calls": dict(policy["zero_call_boundary"]),
        "stage_acceptance": {
            "internal_query_facet_projection": True,
            "internal_route_execution": False,
            "candidate_ceiling_and_qrels": False,
            "BGE_fusion_rerank": False,
            "downstream_utilization": False,
            "external_product_coverage": False,
            "release": False,
        },
        "known_boundary": (
            "This proof connects the frozen provider-neutral Query Facet to typed "
            "internal SQL, ObjectBM25, BM25, Milvus and relationship-graph request "
            + (
                "contracts with reporting-fiscal-year and document-index-calendar-year "
                "authority separated. "
                if uses_typed_period_roles
                else "contracts. "
            )
            + "It performs no retrieval, embedding, reranking or Evidence "
            "promotion; it does not prove target-in-pool, close the external provider "
            "coverage blocker, establish downstream research quality or release FIN 0.1.3."
        ),
    }
    return {**body, "proof_digest": canonical_digest(body)}


def _validate_source_proof(proof: Mapping[str, Any]) -> None:
    body = dict(proof)
    supplied = str(body.pop("proof_digest", ""))
    if (
        supplied != canonical_digest(body)
        or proof.get("status") != "zero_call_engineering_pass"
        or proof.get("plan_count") != 36
        or len(proof.get("plans") or ()) != 36
        or proof.get("stage_acceptance", {}).get("internal_retrieval_integration")
        is not False
    ):
        raise S1InternalQueryFacetError("internal_query_facet_source_proof_invalid")


def _validate_source_plan(plan: Mapping[str, Any]) -> None:
    body = dict(plan)
    supplied_id = str(body.pop("plan_id", ""))
    supplied_digest = str(body.pop("plan_digest", ""))
    expected = canonical_digest(body)
    if supplied_digest != expected or supplied_id != f"query_facet_plan_{expected[:20]}":
        raise S1InternalQueryFacetError("internal_query_facet_source_plan_invalid")
    if (
        plan.get("case_key") not in CASES
        or plan.get("evidence_slot_id") not in SLOT_IDS
        or plan.get("language") not in LANGUAGES
        or set(plan.get("eligible_internal_routes") or ())
        != {
            "internal_exact_object_lookup",
            "internal_bm25",
            "internal_dense",
            "internal_relationship_graph",
        }
        or plan.get("route_specific_filters", {}).get("execution_admitted")
        is not False
    ):
        raise S1InternalQueryFacetError("internal_query_facet_source_plan_scope_invalid")


def _require_bilingual_authority_match(
    *, english: Mapping[str, Any], alternate: Mapping[str, Any]
) -> None:
    fields = (
        "case_key",
        "evidence_slot_id",
        "subject_entity_key",
        "evidence_owner_entity_key",
        "evidence_owner_role",
        "relationship_direction",
        "as_of_date",
    )
    if any(english.get(field) != alternate.get(field) for field in fields):
        raise S1InternalQueryFacetError("internal_query_facet_bilingual_authority_drift")
    if english.get("language") != "en" or alternate.get("language") != "zh":
        raise S1InternalQueryFacetError("internal_query_facet_bilingual_language_invalid")


def _build_bundle(
    *,
    english: Mapping[str, Any],
    alternate: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> InternalQueryFacetBundle:
    entity_map = policy["entity_ticker_projection"]
    owner = str(english["evidence_owner_entity_key"])
    subject = str(english["subject_entity_key"])
    try:
        owner_ticker = str(entity_map[owner])
        subject_ticker = str(entity_map[subject])
    except KeyError as exc:
        raise S1InternalQueryFacetError("internal_query_facet_entity_unmapped") from exc
    fiscal_years = _fiscal_years(english.get("period_terms") or ())
    if not fiscal_years:
        raise S1InternalQueryFacetError("internal_query_facet_period_unmapped")
    payload = {
        "case_key": english["case_key"],
        "evidence_slot_id": english["evidence_slot_id"],
        "evidence_owner_entity_key": owner,
        "subject_entity_key": subject,
        "evidence_owner_ticker": owner_ticker,
        "subject_ticker": subject_ticker,
        "relationship_direction": english["relationship_direction"],
        "canonical_language": "en",
        "alternate_language": "zh",
        "source_plan_ids": {
            "en": english["plan_id"],
            "zh": alternate["plan_id"],
        },
        "source_plan_digests": {
            "en": english["plan_digest"],
            "zh": alternate["plan_digest"],
        },
        "period_terms": list(english["period_terms"]),
        "fiscal_years": list(fiscal_years),
        "as_of_date": english["as_of_date"],
    }
    digest = canonical_digest(payload)
    return InternalQueryFacetBundle(
        bundle_id=f"internal_query_facet_bundle_{digest[:20]}",
        bundle_digest=digest,
        case_key=str(payload["case_key"]),
        evidence_slot_id=str(payload["evidence_slot_id"]),
        evidence_owner_entity_key=owner,
        subject_entity_key=subject,
        evidence_owner_ticker=owner_ticker,
        subject_ticker=subject_ticker,
        relationship_direction=str(payload["relationship_direction"]),
        canonical_language="en",
        alternate_language="zh",
        source_plan_ids=payload["source_plan_ids"],
        source_plan_digests=payload["source_plan_digests"],
        period_terms=tuple(payload["period_terms"]),
        fiscal_years=fiscal_years,
        as_of_date=str(payload["as_of_date"]),
    )


def _build_route_request(
    *,
    bundle: InternalQueryFacetBundle,
    english: Mapping[str, Any],
    alternate: Mapping[str, Any],
    route_id: str,
    policy: Mapping[str, Any],
) -> InternalRouteRequest:
    route_policy = policy["physical_routes"][route_id]
    slot_policy = policy["slot_route_filters"][bundle.evidence_slot_id]
    if route_id == "internal_sql_exact":
        query_texts: tuple[str, ...] = ()
        alternate_queries: tuple[str, ...] = ()
    elif route_id == "internal_object_bm25":
        query_texts = tuple(english["exact_lookup_queries"])
        alternate_queries = tuple(alternate["exact_lookup_queries"])
    elif route_id == "internal_bm25":
        query_texts = tuple(english["lexical_queries"])
        alternate_queries = tuple(alternate["lexical_queries"])
    elif route_id == "internal_milvus_dense":
        query_texts = tuple(english["semantic_queries"])
        alternate_queries = tuple(alternate["semantic_queries"])
    elif route_id == "internal_relationship_graph":
        query_texts = ()
        alternate_queries = ()
    else:
        raise S1InternalQueryFacetError("internal_query_facet_route_unknown")

    uses_typed_period_roles = _uses_typed_period_roles(policy)
    index_filing_calendar_years = _index_filing_calendar_years(
        bundle.fiscal_years, bundle.as_of_date
    )
    filters: dict[str, Any] = {
        "case_key": bundle.case_key,
        "subject_entity_key": bundle.subject_entity_key,
        "subject_ticker": bundle.subject_ticker,
        "evidence_owner_entity_key": bundle.evidence_owner_entity_key,
        "evidence_owner_ticker": bundle.evidence_owner_ticker,
        "relationship_direction": bundle.relationship_direction,
        "period_terms": list(bundle.period_terms),
        "publication_date_on_or_before": bundle.as_of_date,
        "allow_relaxed_identity_period_or_relationship_fallback": False,
    }
    if uses_typed_period_roles:
        filters.update(
            {
                "reporting_fiscal_years": list(bundle.fiscal_years),
                "index_filing_calendar_years": list(index_filing_calendar_years),
                "period_filter_contract": "reporting_vs_document_index_v1",
            }
        )
    else:
        filters["fiscal_years"] = list(bundle.fiscal_years)
    if route_id == "internal_sql_exact":
        filters.update(
            {
                "ticker": bundle.evidence_owner_ticker,
                "metric_families": list(slot_policy["metric_families"]),
                "period_roles": ["annual", "quarterly", "instant"],
                "can_enter_evidence_bundle": True,
                "exact_value_authority": True,
            }
        )
    elif route_id in {"internal_object_bm25", "internal_bm25"}:
        filters.update(
            {
                "ticker": bundle.evidence_owner_ticker,
                "form_types": list(slot_policy["form_types"]),
                "source_tiers": list(slot_policy["source_tiers"]),
            }
        )
        if route_id == "internal_object_bm25":
            filters["object_types"] = list(slot_policy["object_types"])
    elif route_id == "internal_milvus_dense":
        filters.update(
            {
                "tickers": [bundle.evidence_owner_ticker],
                "years": list(
                    bundle.fiscal_years
                    if _uses_milvus_reporting_fiscal_years(policy)
                    else index_filing_calendar_years
                    if uses_typed_period_roles
                    else bundle.fiscal_years
                ),
                "filing_types": list(slot_policy["form_types"]),
                "source_tiers": list(slot_policy["source_tiers"]),
                "vector_kinds": list(slot_policy["vector_kinds"]),
                "typed_filter_required": True,
            }
        )
    else:
        graph = dict(english["graph_query"])
        filters.update(
            {
                "query_kind": graph["query_kind"],
                "maximum_hops": graph["maximum_hops"],
                "allowed_source_roles": list(slot_policy["graph_source_roles"]),
                "forbidden_nested_relationships": list(
                    graph["forbidden_nested_relationships"]
                ),
            }
        )

    entity_map = policy["entity_ticker_projection"]
    allowed_entities = {
        bundle.subject_entity_key,
        bundle.evidence_owner_entity_key,
    }
    blocked_entities = sorted(set(entity_map) - allowed_entities)
    negative_filters = {
        "blocked_entity_keys": blocked_entities,
        "blocked_tickers": sorted({str(entity_map[key]) for key in blocked_entities}),
        "forbidden_expansions": list(english["forbidden_expansions"]),
        "source_negative_queries": list(english["negative_queries"]),
    }
    payload = {
        "bundle_id": bundle.bundle_id,
        "bundle_digest": bundle.bundle_digest,
        "case_key": bundle.case_key,
        "evidence_slot_id": bundle.evidence_slot_id,
        "subject_entity_key": bundle.subject_entity_key,
        "subject_ticker": bundle.subject_ticker,
        "evidence_owner_entity_key": bundle.evidence_owner_entity_key,
        "evidence_owner_ticker": bundle.evidence_owner_ticker,
        "relationship_direction": bundle.relationship_direction,
        "route_id": route_id,
        "query_family": route_policy["query_family"],
        "query_texts": list(query_texts),
        "alternate_language_query_texts": list(alternate_queries),
        "typed_filters": filters,
        "negative_filters": negative_filters,
        "candidate_budget": int(route_policy["candidate_budget"]),
        "authority_boundary": route_policy["authority_boundary"],
        "candidate_state": "candidate_only_not_evidence",
        "allow_relaxed_identity_period_or_relationship_fallback": False,
        "execution_admitted": False,
        "embedding_admitted": False,
        "rerank_admitted": False,
        "evidence_promotion_admitted": False,
    }
    digest = canonical_digest(payload)
    return InternalRouteRequest(
        request_id=f"internal_route_request_{digest[:20]}",
        request_digest=digest,
        bundle_id=bundle.bundle_id,
        bundle_digest=bundle.bundle_digest,
        case_key=bundle.case_key,
        evidence_slot_id=bundle.evidence_slot_id,
        subject_entity_key=bundle.subject_entity_key,
        subject_ticker=bundle.subject_ticker,
        evidence_owner_entity_key=bundle.evidence_owner_entity_key,
        evidence_owner_ticker=bundle.evidence_owner_ticker,
        relationship_direction=bundle.relationship_direction,
        route_id=route_id,
        query_family=str(route_policy["query_family"]),
        query_texts=query_texts,
        alternate_language_query_texts=alternate_queries,
        typed_filters=filters,
        negative_filters=negative_filters,
        candidate_budget=int(route_policy["candidate_budget"]),
        authority_boundary=str(route_policy["authority_boundary"]),
        candidate_state="candidate_only_not_evidence",
        allow_relaxed_identity_period_or_relationship_fallback=False,
        execution_admitted=False,
        embedding_admitted=False,
        rerank_admitted=False,
        evidence_promotion_admitted=False,
    )


def _validate_compiled_set(
    *,
    bundles: tuple[InternalQueryFacetBundle, ...],
    requests: tuple[InternalRouteRequest, ...],
    policy: Mapping[str, Any],
) -> None:
    projection = policy["projection_contract"]
    if (
        len(bundles) != int(projection["bilingual_bundle_count"])
        or len({bundle.bundle_id for bundle in bundles}) != len(bundles)
        or len({bundle.bundle_digest for bundle in bundles}) != len(bundles)
        or len(requests) != int(projection["physical_request_count"])
        or len({request.request_id for request in requests}) != len(requests)
        or len({request.request_digest for request in requests}) != len(requests)
    ):
        raise S1InternalQueryFacetError("internal_query_facet_compiled_set_invalid")
    bundle_map = {bundle.bundle_id: bundle for bundle in bundles}
    for bundle in bundles:
        body = bundle.as_dict()
        supplied_id = body.pop("bundle_id")
        supplied_digest = body.pop("bundle_digest")
        expected = canonical_digest(body)
        if supplied_digest != expected or supplied_id != f"internal_query_facet_bundle_{expected[:20]}":
            raise S1InternalQueryFacetError("internal_query_facet_bundle_identity_invalid")
    for request in requests:
        validate_internal_route_request(
            request, bundles=bundle_map, policy=policy
        )
    for bundle in bundles:
        local = [request for request in requests if request.bundle_id == bundle.bundle_id]
        if len(local) != len(ROUTE_IDS) or {request.route_id for request in local} != set(ROUTE_IDS):
            raise S1InternalQueryFacetError("internal_query_facet_route_coverage_invalid")


def _fiscal_years(period_terms: Sequence[Any]) -> tuple[int, ...]:
    values: list[int] = []
    for term in period_terms:
        for match in _YEAR_PATTERN.findall(str(term)):
            value = int(match)
            if value not in values:
                values.append(value)
    return tuple(values)


def _uses_typed_period_roles(policy: Mapping[str, Any]) -> bool:
    return policy.get("schema_version") in {
        POLICY_SCHEMA_V1_1,
        POLICY_SCHEMA_V1_2,
    }


def _uses_milvus_reporting_fiscal_years(policy: Mapping[str, Any]) -> bool:
    return policy.get("schema_version") == POLICY_SCHEMA_V1_2


def _index_filing_calendar_years(
    reporting_fiscal_years: Sequence[int], as_of_date: str
) -> tuple[int, ...]:
    match = _YEAR_PATTERN.search(str(as_of_date))
    if match is None:
        raise S1InternalQueryFacetError("internal_query_facet_as_of_year_invalid")
    as_of_year = int(match.group(1))
    values: list[int] = []
    for reporting_year in reporting_fiscal_years:
        value = min(int(reporting_year), as_of_year)
        if value not in values:
            values.append(value)
    if not values:
        raise S1InternalQueryFacetError(
            "internal_query_facet_index_calendar_year_unmapped"
        )
    return tuple(values)


__all__ = [
    "CONTRACT_REF",
    "CONTRACT_REF_V1_1",
    "CONTRACT_REF_V1_2",
    "POLICY_SCHEMA",
    "POLICY_SCHEMA_V1_1",
    "POLICY_SCHEMA_V1_2",
    "PROOF_SCHEMA",
    "PROOF_SCHEMA_V1_1",
    "PROOF_SCHEMA_V1_2",
    "ROUTE_IDS",
    "RUN_SCOPE",
    "InternalQueryFacetBundle",
    "InternalRouteRequest",
    "S1InternalQueryFacetError",
    "build_internal_query_facet_zero_call_proof",
    "compile_internal_query_facet_requests",
    "load_internal_query_facet_policy",
    "validate_internal_route_request",
]
