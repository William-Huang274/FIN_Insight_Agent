from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .contracts import EvidenceRequest, FinancialResearchKernel, RetrievalContractError
from .query_plan import canonical_digest


ROUTE_POLICY_SCHEMA_VERSION = "fin_ia_s1c_query_object_fact_route_policy_v1_1"
ROUTE_POLICY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_query_object_fact_route_policy_v1_2"
)
ROUTE_POLICY_QUERY_ATOM_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_query_object_fact_route_policy_v1_3"
)
ROUTE_POLICY_SCHEMA_VERSIONS = frozenset(
    {
        "fin_ia_s1c_query_object_fact_route_policy_v1_0",
        ROUTE_POLICY_SCHEMA_VERSION,
        ROUTE_POLICY_SUCCESSOR_SCHEMA_VERSION,
        ROUTE_POLICY_QUERY_ATOM_SUCCESSOR_SCHEMA_VERSION,
    }
)
EXECUTION_PLAN_SCHEMA_VERSION = "fin_ia_s1c_retrieval_execution_plan_v1_0"
TYPED_FACT_REQUEST_SCHEMA_VERSION = "fin_ia_typed_fact_request_v1_0"

_ALLOWED_OBJECT_FORMS = frozenset(
    {"claim", "metric_row", "bounded_parent_context"}
)
_REQUIRED_AUTHORITY_POLICY = {
    "candidate_is_not_evidence": True,
    "fact_request_is_not_numeric_fact": True,
    "table_row_is_not_numeric_authority": True,
    "embedding_or_reranker_grants_authority": False,
    "typed_fact_executor_required_for_numeric_authority": True,
    "model_or_training_calls_authorized": False,
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RetrievalContractError(code)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            output.append(normalized)
    return tuple(output)


@dataclass(frozen=True)
class QueryFamilyPolicy:
    family_id: str
    facet_ids: tuple[str, ...]
    allowed_object_forms: tuple[str, ...]
    candidate_routes: tuple[str, ...]


@dataclass(frozen=True)
class MetricRoutePolicy:
    metric_id: str
    aliases: tuple[str, ...]
    authority_domain: str
    storage_route: str
    unit_family: str
    allowed_query_families: tuple[str, ...]
    formula: str | None


@dataclass(frozen=True)
class QueryObjectFactRoutePolicy:
    query_families: tuple[QueryFamilyPolicy, ...]
    metric_routes: tuple[MetricRoutePolicy, ...]
    object_compiler: Mapping[str, Any]
    authority: Mapping[str, bool]
    bound_kernel_ref: str
    bound_kernel_sha256: str

    def family_by_facet(self) -> dict[str, QueryFamilyPolicy]:
        return {
            facet_id: family
            for family in self.query_families
            for facet_id in family.facet_ids
        }

    def metric_by_alias(self) -> dict[str, MetricRoutePolicy]:
        return {
            alias.casefold(): metric
            for metric in self.metric_routes
            for alias in (metric.metric_id, *metric.aliases)
        }


@dataclass(frozen=True)
class NarrativeRouteRequest:
    route_request_id: str
    query_family_id: str
    facet_ids: tuple[str, ...]
    target_entities: tuple[str, ...]
    product_intents: tuple[str, ...]
    metric_context_ids: tuple[str, ...]
    allowed_object_forms: tuple[str, ...]
    candidate_routes: tuple[str, ...]
    candidate_not_evidence: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TypedFactRequest:
    schema_version: str
    fact_request_id: str
    source_evidence_request_id: str
    source_cell_id: str
    case_key: str
    subject_ticker: str
    target_entity: str
    metric_id: str
    query_family_ids: tuple[str, ...]
    research_as_of: str
    period: Mapping[str, Any]
    granularity: str
    requested_unit: str
    unit_family: str
    authority_domain: str
    storage_route: str
    formula: str | None
    execution_status: str
    numeric_fact_authority: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalExecutionPlan:
    schema_version: str
    request_id: str
    cell_id: str
    case_key: str
    narrative_requests: tuple[NarrativeRouteRequest, ...]
    typed_fact_requests: tuple[TypedFactRequest, ...]
    typed_gaps: tuple[Mapping[str, Any], ...]
    authority: Mapping[str, bool]
    plan_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "cell_id": self.cell_id,
            "case_key": self.case_key,
            "narrative_requests": [row.as_dict() for row in self.narrative_requests],
            "typed_fact_requests": [row.as_dict() for row in self.typed_fact_requests],
            "typed_gaps": [dict(row) for row in self.typed_gaps],
            "authority": dict(self.authority),
            "plan_digest": self.plan_digest,
        }


def load_query_object_fact_route_policy(
    payload: Mapping[str, Any],
    kernel: FinancialResearchKernel,
) -> QueryObjectFactRoutePolicy:
    """Load the S1/S2 boundary and fail closed on missing or overlapping routes."""

    _require(
        payload.get("schema_version") in ROUTE_POLICY_SCHEMA_VERSIONS,
        "query_object_fact_route_policy_schema_invalid",
    )
    _require(
        payload.get("status")
        == "provider_neutral_successor_policy_no_model_or_evidence_authority",
        "query_object_fact_route_policy_status_invalid",
    )
    candidate_routes = payload.get("candidate_routes")
    _require(
        isinstance(candidate_routes, list)
        and bool(candidate_routes)
        and len(candidate_routes) == len(set(candidate_routes)),
        "query_object_fact_candidate_routes_invalid",
    )
    candidate_route_ids = frozenset(str(value) for value in candidate_routes)

    raw_families = payload.get("query_families")
    _require(
        isinstance(raw_families, list) and bool(raw_families),
        "query_object_fact_families_invalid",
    )
    families: list[QueryFamilyPolicy] = []
    family_ids: set[str] = set()
    mapped_facets: list[str] = []
    for raw in raw_families:
        _require(isinstance(raw, Mapping), "query_object_fact_family_invalid")
        family_id = str(raw.get("family_id") or "").strip()
        facets = _unique(raw.get("facet_ids") or ())
        forms = _unique(raw.get("allowed_object_forms") or ())
        routes = _unique(raw.get("candidate_routes") or ())
        _require(
            family_id
            and family_id not in family_ids
            and bool(facets)
            and bool(forms)
            and set(forms).issubset(_ALLOWED_OBJECT_FORMS)
            and bool(routes)
            and set(routes).issubset(candidate_route_ids),
            "query_object_fact_family_contract_invalid",
        )
        family_ids.add(family_id)
        mapped_facets.extend(facets)
        families.append(
            QueryFamilyPolicy(
                family_id=family_id,
                facet_ids=facets,
                allowed_object_forms=forms,
                candidate_routes=routes,
            )
        )
    kernel_facets = {
        facet.facet_id for slot in kernel.slots for facet in slot.facets
    }
    _require(
        len(mapped_facets) == len(set(mapped_facets)),
        "query_object_fact_facet_route_overlap",
    )
    _require(
        set(mapped_facets) == kernel_facets,
        "query_object_fact_facet_route_incomplete",
    )

    raw_metrics = payload.get("metric_routes")
    _require(
        isinstance(raw_metrics, list) and bool(raw_metrics),
        "query_object_fact_metric_routes_invalid",
    )
    metrics: list[MetricRoutePolicy] = []
    metric_ids: set[str] = set()
    aliases: set[str] = set()
    for raw in raw_metrics:
        _require(isinstance(raw, Mapping), "query_object_fact_metric_route_invalid")
        metric_id = str(raw.get("metric_id") or "").strip()
        metric_aliases = _unique(raw.get("aliases") or ())
        allowed_families = _unique(raw.get("allowed_query_families") or ())
        all_aliases = {metric_id.casefold(), *(value.casefold() for value in metric_aliases)}
        _require(
            metric_id
            and metric_id not in metric_ids
            and bool(metric_aliases)
            and not aliases.intersection(all_aliases)
            and bool(allowed_families)
            and set(allowed_families).issubset(family_ids)
            and bool(str(raw.get("authority_domain") or "").strip())
            and str(raw.get("storage_route") or "")
            in {"company_financial_fact_mart", "market_snapshot_fact_mart"}
            and bool(str(raw.get("unit_family") or "").strip()),
            "query_object_fact_metric_contract_invalid",
        )
        metric_ids.add(metric_id)
        aliases.update(all_aliases)
        formula = raw.get("formula")
        _require(
            formula is None or bool(str(formula).strip()),
            "query_object_fact_metric_formula_invalid",
        )
        metrics.append(
            MetricRoutePolicy(
                metric_id=metric_id,
                aliases=metric_aliases,
                authority_domain=str(raw["authority_domain"]),
                storage_route=str(raw["storage_route"]),
                unit_family=str(raw["unit_family"]),
                allowed_query_families=allowed_families,
                formula=str(formula).strip() if formula is not None else None,
            )
        )

    compiler = payload.get("object_compiler")
    _require(
        isinstance(compiler, Mapping)
        and 40 <= int(compiler.get("claim_min_characters") or 0)
        < int(compiler.get("claim_max_characters") or 0)
        <= 4000
        and 1 <= int(compiler.get("max_claims_per_source_record") or 0) <= 128
        and 1 <= int(compiler.get("max_metric_rows_per_table") or 0) <= 256
        and 512 <= int(compiler.get("max_model_text_characters") or 0) <= 8000
        and compiler.get("numeric_authority") is False,
        "query_object_fact_object_compiler_invalid",
    )
    segmentation_mode = str(
        compiler.get("claim_segmentation_mode") or "legacy_line_v1"
    )
    overflow_policy = str(
        compiler.get("claim_overflow_policy") or "legacy_silent_limit"
    )
    _require(
        segmentation_mode
        in {
            "legacy_line_v1",
            "sentence_with_wrapped_line_reflow_v1",
            "sentence_with_wrapped_line_reflow_v2",
        }
        and overflow_policy
        in {
            "legacy_silent_limit",
            "emit_typed_diagnostic_and_fail_qualification",
        }
        and (
            segmentation_mode == "legacy_line_v1"
            or overflow_policy
            == "emit_typed_diagnostic_and_fail_qualification"
        ),
        "query_object_fact_claim_segmentation_policy_invalid",
    )
    authority = payload.get("authority")
    _require(
        isinstance(authority, Mapping)
        and dict(authority) == _REQUIRED_AUTHORITY_POLICY,
        "query_object_fact_authority_invalid",
    )
    bound_kernel = payload.get("bound_kernel")
    _require(
        isinstance(bound_kernel, Mapping)
        and str(bound_kernel.get("ref") or "").endswith(".json")
        and len(str(bound_kernel.get("sha256") or "")) == 64,
        "query_object_fact_bound_kernel_invalid",
    )
    return QueryObjectFactRoutePolicy(
        query_families=tuple(families),
        metric_routes=tuple(metrics),
        object_compiler=dict(compiler),
        authority=dict(authority),
        bound_kernel_ref=str(bound_kernel["ref"]),
        bound_kernel_sha256=str(bound_kernel["sha256"]),
    )


def compile_retrieval_execution_plan(
    policy: QueryObjectFactRoutePolicy,
    request: EvidenceRequest,
    *,
    fact_store_availability: Mapping[str, bool] | None = None,
) -> RetrievalExecutionPlan:
    """Split one request into narrative retrieval and exact-fact sibling routes."""

    availability = {
        "company_financial_fact_mart": False,
        "market_snapshot_fact_mart": False,
        **dict(fact_store_availability or {}),
    }
    family_by_facet = policy.family_by_facet()
    selected: dict[str, list[str]] = {}
    for facet_id in request.requested_facet_ids:
        family = family_by_facet.get(facet_id)
        _require(family is not None, "query_object_fact_request_facet_unrouted")
        selected.setdefault(family.family_id, []).append(facet_id)

    metric_by_alias = policy.metric_by_alias()
    resolved: list[MetricRoutePolicy] = []
    typed_gaps: list[dict[str, Any]] = []
    for raw_intent in request.metric_intents:
        metric = metric_by_alias.get(raw_intent.casefold())
        if metric is None:
            typed_gaps.append(
                {
                    "gap_code": "metric_alias_unregistered",
                    "metric_intent": raw_intent,
                    "disposition": request.clarification_policy,
                }
            )
            continue
        allowed_selected = tuple(
            family_id
            for family_id in selected
            if family_id in metric.allowed_query_families
        )
        if not allowed_selected:
            typed_gaps.append(
                {
                    "gap_code": "metric_not_valid_for_selected_query_family",
                    "metric_intent": raw_intent,
                    "metric_id": metric.metric_id,
                    "selected_query_families": list(selected),
                    "disposition": request.clarification_policy,
                }
            )
            continue
        if metric not in resolved:
            resolved.append(metric)

    narratives: list[NarrativeRouteRequest] = []
    for family in policy.query_families:
        facet_ids = selected.get(family.family_id)
        if not facet_ids:
            continue
        metric_context_ids = tuple(
            metric.metric_id
            for metric in resolved
            if family.family_id in metric.allowed_query_families
        )
        identity = {
            "request_id": request.request_id,
            "family_id": family.family_id,
            "facet_ids": facet_ids,
            "targets": request.target_entities,
        }
        narratives.append(
            NarrativeRouteRequest(
                route_request_id=f"NRR::{canonical_digest(identity)[:24]}",
                query_family_id=family.family_id,
                facet_ids=tuple(facet_ids),
                target_entities=request.target_entities,
                product_intents=request.product_intents,
                metric_context_ids=metric_context_ids,
                allowed_object_forms=family.allowed_object_forms,
                candidate_routes=tuple(
                    route
                    for route in family.candidate_routes
                    if route != "typed_exact_fact_lookup"
                ),
                candidate_not_evidence=True,
            )
        )

    facts: list[TypedFactRequest] = []
    period_selection_mode = (
        "latest_on_or_before"
        if request.period.end_date is None
        or request.period.end_date == request.research_as_of
        else "exact_period_end"
    )
    typed_fact_period = {
        **request.period.as_dict(),
        "selection_mode": period_selection_mode,
    }
    for metric in resolved:
        allowed_selected = tuple(
            family_id
            for family_id in selected
            if family_id in metric.allowed_query_families
        )
        for target in request.target_entities:
            identity = {
                "request_id": request.request_id,
                "target_entity": target,
                "metric_id": metric.metric_id,
                "period": typed_fact_period,
                "as_of": request.research_as_of.isoformat(),
            }
            fact_request_id = f"TFR::{canonical_digest(identity)[:24]}"
            available = availability.get(metric.storage_route) is True
            status = "ready_for_typed_fact_executor" if available else "typed_store_unavailable"
            facts.append(
                TypedFactRequest(
                    schema_version=TYPED_FACT_REQUEST_SCHEMA_VERSION,
                    fact_request_id=fact_request_id,
                    source_evidence_request_id=request.request_id,
                    source_cell_id=request.cell_id,
                    case_key=request.case_key,
                    subject_ticker=request.subject_ticker,
                    target_entity=target,
                    metric_id=metric.metric_id,
                    query_family_ids=allowed_selected,
                    research_as_of=request.research_as_of.isoformat(),
                    period=typed_fact_period,
                    granularity=request.granularity,
                    requested_unit=request.unit,
                    unit_family=metric.unit_family,
                    authority_domain=metric.authority_domain,
                    storage_route=metric.storage_route,
                    formula=metric.formula,
                    execution_status=status,
                    numeric_fact_authority=False,
                )
            )
            if not available:
                typed_gaps.append(
                    {
                        "gap_code": "typed_fact_store_unavailable",
                        "fact_request_id": fact_request_id,
                        "metric_id": metric.metric_id,
                        "target_entity": target,
                        "storage_route": metric.storage_route,
                        "owning_stage": "S2",
                        "disposition": request.clarification_policy,
                    }
                )

    unsigned = {
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "request_id": request.request_id,
        "cell_id": request.cell_id,
        "case_key": request.case_key,
        "narrative_requests": [row.as_dict() for row in narratives],
        "typed_fact_requests": [row.as_dict() for row in facts],
        "typed_gaps": typed_gaps,
        "authority": dict(policy.authority),
    }
    return RetrievalExecutionPlan(
        schema_version=EXECUTION_PLAN_SCHEMA_VERSION,
        request_id=request.request_id,
        cell_id=request.cell_id,
        case_key=request.case_key,
        narrative_requests=tuple(narratives),
        typed_fact_requests=tuple(facts),
        typed_gaps=tuple(typed_gaps),
        authority=dict(policy.authority),
        plan_digest=canonical_digest(unsigned),
    )


__all__ = [
    "EXECUTION_PLAN_SCHEMA_VERSION",
    "MetricRoutePolicy",
    "NarrativeRouteRequest",
    "QueryFamilyPolicy",
    "QueryObjectFactRoutePolicy",
    "ROUTE_POLICY_SCHEMA_VERSION",
    "ROUTE_POLICY_QUERY_ATOM_SUCCESSOR_SCHEMA_VERSION",
    "RetrievalExecutionPlan",
    "TYPED_FACT_REQUEST_SCHEMA_VERSION",
    "TypedFactRequest",
    "compile_retrieval_execution_plan",
    "load_query_object_fact_route_policy",
]
