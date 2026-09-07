from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable

from .contracts import EvidenceRequest, FinancialResearchKernel, RetrievalContractError
from .text import tokenize


QUERY_PLAN_SCHEMA_VERSION = "fin_ia_typed_query_facet_plan_v1_0"


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
class OwnerQuery:
    evidence_owner_ticker: str
    relationship_direction: str
    lexical_query: str
    lexical_tokens: tuple[str, ...]
    anchor_token_groups: tuple[tuple[str, ...], ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryLane:
    lane_id: str
    slot_id: str
    facet_id: str
    business_question_zh: str
    execution_mode: str
    subject_ticker: str
    evidence_owner_tickers: tuple[str, ...]
    relationship_constraints: tuple[str, ...]
    publication_date_lte: str
    source_types: tuple[str, ...]
    required_source_roles: tuple[str, ...]
    exact_queries: tuple[str, ...]
    lexical_query: str
    lexical_tokens: tuple[str, ...]
    owner_queries: tuple[OwnerQuery, ...]
    semantic_query: str
    graph_constraints: tuple[str, ...]
    forbidden_expansions: tuple[str, ...]
    candidate_budget: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryFacetPlan:
    schema_version: str
    case_key: str
    subject_ticker: str
    subject_legal_name: str
    research_as_of: str
    industry_pack_id: str
    lanes: tuple[QueryLane, ...]
    plan_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_key": self.case_key,
            "subject_ticker": self.subject_ticker,
            "subject_legal_name": self.subject_legal_name,
            "research_as_of": self.research_as_of,
            "industry_pack_id": self.industry_pack_id,
            "lanes": [lane.as_dict() for lane in self.lanes],
            "plan_digest": self.plan_digest,
        }


def compile_query_facet_plan(
    kernel: FinancialResearchKernel,
    case_key: str,
) -> QueryFacetPlan:
    """Compile one case without provider or ticker branches in core code."""

    return _compile_query_facet_plan(kernel, case_key)


def compile_query_facet_plan_for_request(
    kernel: FinancialResearchKernel,
    request: EvidenceRequest,
) -> QueryFacetPlan:
    """Compile only the approved facets and hard constraints in one request."""

    if request.case_key not in kernel.cases:
        raise RetrievalContractError("evidence_request_case_unknown")
    return _compile_query_facet_plan(
        kernel,
        request.case_key,
        requested_facet_ids=frozenset(request.requested_facet_ids),
        target_entities=frozenset(request.target_entities),
        acceptable_sources=frozenset(request.acceptable_sources),
        request_terms=_unique((*request.metric_intents, *request.product_intents)),
    )


def _compile_query_facet_plan(
    kernel: FinancialResearchKernel,
    case_key: str,
    *,
    requested_facet_ids: frozenset[str] | None = None,
    target_entities: frozenset[str] | None = None,
    acceptable_sources: frozenset[str] | None = None,
    request_terms: tuple[str, ...] | None = None,
) -> QueryFacetPlan:

    key = str(case_key).strip().upper()
    try:
        profile = kernel.cases[key]
    except KeyError as exc:
        raise KeyError(f"retrieval_case_profile_unknown:{key}") from exc
    industry = kernel.industry_packs[profile.industry_pack_id]
    related = {entity.ticker: entity for entity in profile.related_entities}
    lanes: list[QueryLane] = []
    for slot in kernel.slots:
        for facet in slot.facets:
            if (
                requested_facet_ids is not None
                and facet.facet_id not in requested_facet_ids
            ):
                continue
            owners = (
                [profile.subject_ticker]
                if facet.evidence_owner_scope != "related_only"
                else []
            )
            relationships = (
                ["subject_self_disclosure"]
                if facet.evidence_owner_scope != "related_only"
                else []
            )
            if facet.evidence_owner_scope in {"subject_and_related", "related_only"}:
                eligible_related = [
                    entity
                    for entity in profile.related_entities
                    if not facet.related_economic_roles
                    or entity.economic_role in facet.related_economic_roles
                ]
                owners.extend(entity.ticker for entity in eligible_related)
                relationships.extend(
                    entity.relationship_direction for entity in eligible_related
                )
            if target_entities is not None:
                selected_pairs = [
                    pair
                    for pair in zip(owners, relationships)
                    if pair[0] in target_entities
                ]
                if not selected_pairs:
                    raise RetrievalContractError(
                        f"evidence_request_facet_has_no_target:{facet.facet_id}"
                    )
                owners = [pair[0] for pair in selected_pairs]
                relationships = [pair[1] for pair in selected_pairs]
            source_types = slot.source_types
            if acceptable_sources is not None:
                source_types = tuple(
                    value for value in source_types if value in acceptable_sources
                )
                if not source_types:
                    raise RetrievalContractError(
                        f"evidence_request_facet_has_no_source:{facet.facet_id}"
                    )
            common_terms = _unique(
                [
                    *facet.lexical_terms,
                    *industry.lexical_terms,
                    *industry.slot_terms.get(slot.slot_id, ()),
                    *profile.slot_terms.get(slot.slot_id, ()),
                    *(request_terms or ()),
                ]
            )
            lexical_tokens = _unique(
                token
                for term in common_terms
                for token in tokenize(term)
            )
            raw_anchor_terms = _unique(
                [
                    *facet.exact_phrases,
                    *industry.slot_terms.get(slot.slot_id, ()),
                    *profile.slot_terms.get(slot.slot_id, ()),
                ]
            )
            anchor_token_groups = tuple(
                tokens
                for tokens in (
                    _unique(tokenize(term)) for term in raw_anchor_terms
                )
                if tokens
            )
            owner_queries = tuple(
                OwnerQuery(
                    evidence_owner_ticker=owner,
                    relationship_direction=relationship,
                    lexical_query=" ".join(common_terms),
                    lexical_tokens=lexical_tokens,
                    anchor_token_groups=anchor_token_groups,
                )
                for owner, relationship in zip(owners, relationships)
            )
            exact_aliases = _unique(
                alias
                for owner in owners
                for alias in (
                    profile.subject_aliases
                    if owner == profile.subject_ticker
                    else related[owner].aliases
                )
            )
            owner_names = [
                profile.subject_legal_name
                if owner == profile.subject_ticker
                else related[owner].legal_name
                for owner in owners
            ]
            exact_queries = _unique(
                f'"{alias}" "{phrase}"'
                for alias in exact_aliases
                for phrase in facet.exact_phrases
            )
            semantic_query = (
                f"截至 {profile.research_as_of.isoformat()}，回答“{facet.business_question_zh}”。"
                f"研究主体是 {profile.subject_legal_name}；允许使用的披露主体为"
                f"{'、'.join(owner_names)}，但必须区分主体自述、上下游背景和直接关系证据。"
            )
            if request_terms:
                semantic_query += (
                    " 本次类型化请求限定的指标／产品意图为："
                    f"{'、'.join(request_terms)}；这些意图只能扩展语义和词法召回，"
                    "不能改变身份、期间、来源、关系或事实权威。"
                )
            graph_constraints = _unique(
                item
                for pair in zip(owners, relationships)
                for item in (
                    f"evidence_owner={pair[0]}",
                    f"relationship={pair[1]}",
                )
            )
            lanes.append(
                QueryLane(
                    lane_id=(
                        f"{key.lower()}__{slot.slot_id}__"
                        f"{facet.facet_id}__lexical_v1"
                    ),
                    slot_id=slot.slot_id,
                    facet_id=facet.facet_id,
                    business_question_zh=facet.business_question_zh,
                    execution_mode="local_lexical_candidate_generation",
                    subject_ticker=profile.subject_ticker,
                    evidence_owner_tickers=tuple(owners),
                    relationship_constraints=tuple(relationships),
                    publication_date_lte=profile.research_as_of.isoformat(),
                    source_types=source_types,
                    required_source_roles=facet.required_source_roles,
                    exact_queries=exact_queries,
                    lexical_query=" ".join(common_terms),
                    lexical_tokens=lexical_tokens,
                    owner_queries=owner_queries,
                    semantic_query=semantic_query,
                    graph_constraints=graph_constraints,
                    forbidden_expansions=slot.forbidden_expansions,
                    candidate_budget=kernel.budgets.candidates_per_slot,
                )
            )
    if requested_facet_ids is not None and {
        lane.facet_id for lane in lanes
    } != set(requested_facet_ids):
        raise RetrievalContractError("evidence_request_facet_compilation_incomplete")
    unsigned = {
        "schema_version": QUERY_PLAN_SCHEMA_VERSION,
        "case_key": key,
        "subject_ticker": profile.subject_ticker,
        "subject_legal_name": profile.subject_legal_name,
        "research_as_of": profile.research_as_of.isoformat(),
        "industry_pack_id": profile.industry_pack_id,
        "lanes": [lane.as_dict() for lane in lanes],
    }
    return QueryFacetPlan(
        schema_version=QUERY_PLAN_SCHEMA_VERSION,
        case_key=key,
        subject_ticker=profile.subject_ticker,
        subject_legal_name=profile.subject_legal_name,
        research_as_of=profile.research_as_of.isoformat(),
        industry_pack_id=profile.industry_pack_id,
        lanes=tuple(lanes),
        plan_digest=canonical_digest(unsigned),
    )


__all__ = [
    "QUERY_PLAN_SCHEMA_VERSION",
    "OwnerQuery",
    "QueryFacetPlan",
    "QueryLane",
    "canonical_digest",
    "compile_query_facet_plan",
    "compile_query_facet_plan_for_request",
]
