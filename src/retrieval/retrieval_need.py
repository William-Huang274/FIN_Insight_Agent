from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Mapping, Sequence

from .contracts import EvidenceRequest
from .financial_intent import concept_aliases, intent_alias_groups
from .query_plan import QueryLane, canonical_digest


RETRIEVAL_NEED_POLICY_SCHEMA_VERSION = (
    "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_0"
)
RETRIEVAL_NEED_POLICY_SCHEMA_VERSIONS = frozenset(
    {
        RETRIEVAL_NEED_POLICY_SCHEMA_VERSION,
        "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_1",
        "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_2",
    }
)
RETRIEVAL_NEED_SET_SCHEMA_VERSION = "fin_ia_s1_vs3_retrieval_need_set_v1_1"
RETRIEVAL_NEED_SET_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1_vs3_retrieval_need_set_v1_2"
)

_FORBIDDEN_QUERY_SURFACES = (
    re.compile(r"\bCOBJ::", re.IGNORECASE),
    re.compile(r"\bCAND::", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
)


class RetrievalNeedError(ValueError):
    """A request-to-retrieval decomposition weakened a hard query boundary."""


@dataclass(frozen=True)
class RetrievalNeed:
    need_id: str
    need_kind: str
    facet_id: str
    evidence_owner_ticker: str
    relationship_direction: str
    intent_terms: tuple[str, ...]
    role_cues: tuple[str, ...]
    exact_phrases: tuple[str, ...]
    lexical_query: str
    semantic_query: str
    constraint_digest: str
    intent_alias_groups: tuple[tuple[str, ...], ...] = ()
    fiscal_years: tuple[int, ...] = ()
    same_basis_comparison_required: bool = False

    def as_dict(self, *, include_temporal: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_temporal:
            value.pop("fiscal_years")
            value.pop("same_basis_comparison_required")
        return value


@dataclass(frozen=True)
class RetrievalNeedSet:
    schema_version: str
    request_id: str
    lane_id: str
    facet_id: str
    needs: tuple[RetrievalNeed, ...]
    need_set_digest: str

    def as_dict(self) -> dict[str, Any]:
        include_temporal = (
            self.schema_version == RETRIEVAL_NEED_SET_SUCCESSOR_SCHEMA_VERSION
        )
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "lane_id": self.lane_id,
            "facet_id": self.facet_id,
            "needs": [
                row.as_dict(include_temporal=include_temporal)
                for row in self.needs
            ],
            "need_set_digest": self.need_set_digest,
        }


def compile_retrieval_needs(
    *,
    request: EvidenceRequest,
    lane: QueryLane,
    policy: Mapping[str, Any],
    intent_ontology: Mapping[str, Any] | None = None,
) -> RetrievalNeedSet:
    """Decompose one approved facet into bounded, provider-neutral search needs.

    The compiler may narrow an approved request into metric/product/role views,
    but it cannot change owner, relationship, period, source class or authority.
    No model, qrel, URL or object identity participates in this step.
    """

    _validate_policy(policy, intent_ontology=intent_ontology)
    materiality_first = (
        policy.get("schema_version")
        == "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_2"
    )
    if len(lane.evidence_owner_tickers) != 1:
        raise RetrievalNeedError("retrieval_need_one_owner_lane_required")
    if tuple(request.requested_facet_ids) != (lane.facet_id,):
        raise RetrievalNeedError("retrieval_need_request_lane_facet_mismatch")
    owner = lane.evidence_owner_tickers[0]
    relationship = lane.relationship_constraints[0]
    facet_policy = (policy.get("facet_role_cues") or {}).get(lane.facet_id)
    if not isinstance(facet_policy, Mapping):
        raise RetrievalNeedError(
            f"retrieval_need_facet_policy_missing:{lane.facet_id}"
        )
    role_cues = _unique(facet_policy.get("lexical") or ())
    semantic_role = str(facet_policy.get("semantic") or "").strip()
    if not role_cues or not semantic_role:
        raise RetrievalNeedError("retrieval_need_facet_role_cues_invalid")

    metrics = _unique(request.metric_intents)
    products = _unique(
        value
        for value in request.product_intents
        if not materiality_first or not _is_period_only_intent(value)
    )
    if (
        intent_ontology is not None
        and request.acceptable_proxy is False
        and policy.get("suppress_unrequested_metric_cues_when_proxy_forbidden")
        is True
    ):
        requested_metric_concepts = {
            concept_aliases(
                value,
                family="metric_concepts",
                ontology=intent_ontology,
            )[0]
            for value in metrics
        }
        filtered: list[str] = []
        for cue in role_cues:
            concept_id, _ = concept_aliases(
                cue,
                family="metric_concepts",
                ontology=intent_ontology,
            )
            if (
                concept_id.startswith("unmapped::")
                or concept_id in requested_metric_concepts
            ):
                filtered.append(cue)
        role_cues = _unique(filtered)
    exact_phrases = (
        _unique((*metrics, *products))
        if materiality_first
        else _unique(
            phrase
            for query in lane.exact_queries
            for phrase in _quoted(query)[1:]
        )
    )
    if not exact_phrases:
        exact_phrases = role_cues[:2]

    specifications: list[tuple[str, tuple[str, ...]]] = []
    if materiality_first:
        # Preserve one independent lane per approved intent before adding
        # cross-products.  Cartesian-first compilation can starve later facets
        # when the bounded maximum is reached.
        specifications.extend(("metric", (metric,)) for metric in metrics)
        specifications.extend(("product", (product,)) for product in products)
        for product in products:
            for metric in metrics:
                specifications.append(("metric_product", (metric, product)))
    else:
        for metric in metrics:
            for product in products:
                specifications.append(("metric_product", (metric, product)))
        specifications.extend(("metric", (metric,)) for metric in metrics)
        specifications.extend(("product", (product,)) for product in products)
    specifications.extend(
        ("exact_phrase", (phrase,))
        for phrase in exact_phrases[: int(policy["maximum_exact_phrase_needs"])]
    )
    if not metrics and not products:
        specifications.append(("facet_role", ()))

    unique_specs: list[tuple[str, tuple[str, ...]]] = []
    seen_specs: set[tuple[str, tuple[str, ...]]] = set()
    for kind, terms in specifications:
        key = kind, tuple(value.casefold() for value in terms)
        if key not in seen_specs:
            seen_specs.add(key)
            unique_specs.append((kind, terms))
    maximum = int(policy["maximum_needs_per_lane"])
    if len(unique_specs) > maximum:
        unique_specs = unique_specs[:maximum]

    constraints = {
        "request_id": request.request_id,
        "facet_id": lane.facet_id,
        "evidence_owner_ticker": owner,
        "relationship_direction": relationship,
        "publication_date_lte": lane.publication_date_lte,
        "source_types": list(lane.source_types),
        "required_source_roles": list(lane.required_source_roles),
        "forbidden_expansions": list(lane.forbidden_expansions),
        "period": request.period.as_dict(),
    }
    constraint_digest = canonical_digest(constraints)
    needs: list[RetrievalNeed] = []
    for index, (kind, terms) in enumerate(unique_specs, start=1):
        alias_groups: tuple[tuple[str, ...], ...] = ()
        if intent_ontology is not None:
            metric_terms: tuple[str, ...] = ()
            product_terms: tuple[str, ...] = ()
            if kind == "metric_product":
                metric_terms = terms[:1]
                product_terms = terms[1:2]
            elif kind == "metric":
                metric_terms = terms
            elif kind == "product":
                product_terms = terms
            alias_groups = intent_alias_groups(
                metric_intents=metric_terms,
                product_intents=product_terms,
                ontology=intent_ontology,
            )
        lexical_terms = _unique(
            role_cues
            if kind == "facet_role"
            else terms
            if materiality_first
            else (*terms, *role_cues)
        )
        lexical_query = " ".join(lexical_terms)
        fiscal_years = (
            tuple(sorted(request.period.fiscal_years))
            if materiality_first
            else ()
        )
        comparison_required = materiality_first and len(fiscal_years) >= 2
        semantic_query = (
            f"Evidence owner: {owner}. Relationship: {relationship}. "
            f"Research facet: {lane.business_question_zh} "
            f"Required evidence role: {semantic_role}. "
            f"Focused intent: {', '.join(terms) if terms else 'facet-level evidence'}."
        )
        if fiscal_years:
            semantic_query += (
                f" Requested fiscal years: {', '.join(str(value) for value in fiscal_years)}."
            )
        if comparison_required:
            semantic_query += (
                " Preserve same issuer, metric, unit and reporting basis across periods."
            )
        _reject_leakage((lexical_query, semantic_query, *terms))
        needs.append(
            RetrievalNeed(
                need_id=f"{lane.lane_id}::need::{index:02d}",
                need_kind=kind,
                facet_id=lane.facet_id,
                evidence_owner_ticker=owner,
                relationship_direction=relationship,
                intent_terms=terms,
                role_cues=role_cues,
                exact_phrases=(terms[0],) if kind == "exact_phrase" else (),
                lexical_query=lexical_query,
                semantic_query=semantic_query,
                constraint_digest=constraint_digest,
                intent_alias_groups=alias_groups,
                fiscal_years=fiscal_years,
                same_basis_comparison_required=comparison_required,
            )
        )
    if not needs:
        raise RetrievalNeedError("retrieval_need_set_empty")
    unsigned = {
        "schema_version": (
            RETRIEVAL_NEED_SET_SUCCESSOR_SCHEMA_VERSION
            if materiality_first
            else RETRIEVAL_NEED_SET_SCHEMA_VERSION
        ),
        "request_id": request.request_id,
        "lane_id": lane.lane_id,
        "facet_id": lane.facet_id,
        "needs": [
            row.as_dict(include_temporal=materiality_first) for row in needs
        ],
    }
    return RetrievalNeedSet(
        schema_version=(
            RETRIEVAL_NEED_SET_SUCCESSOR_SCHEMA_VERSION
            if materiality_first
            else RETRIEVAL_NEED_SET_SCHEMA_VERSION
        ),
        request_id=request.request_id,
        lane_id=lane.lane_id,
        facet_id=lane.facet_id,
        needs=tuple(needs),
        need_set_digest=canonical_digest(unsigned),
    )


def _validate_policy(
    policy: Mapping[str, Any],
    *,
    intent_ontology: Mapping[str, Any] | None,
) -> None:
    if policy.get("schema_version") not in RETRIEVAL_NEED_POLICY_SCHEMA_VERSIONS:
        raise RetrievalNeedError("retrieval_need_policy_schema_invalid")
    if (
        policy.get("schema_version")
        in {
            "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_1",
            "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_2",
        }
        and intent_ontology is None
    ):
        raise RetrievalNeedError("retrieval_need_intent_ontology_missing")
    required = policy.get("authority")
    if not (
        isinstance(required, Mapping)
        and required.get("provider_neutral") is True
        and required.get("labels_joined_after_candidate_generation") is True
        and required.get("hard_constraints_inherited_not_generated") is True
        and required.get("candidate_is_not_evidence") is True
        and required.get("numeric_authority") is False
        and required.get("generation_model_calls") == 0
    ):
        raise RetrievalNeedError("retrieval_need_policy_authority_invalid")
    maximum = policy.get("maximum_needs_per_lane")
    exact_maximum = policy.get("maximum_exact_phrase_needs")
    if not (
        isinstance(maximum, int)
        and 1 <= maximum <= 32
        and isinstance(exact_maximum, int)
        and 0 <= exact_maximum <= maximum
    ):
        raise RetrievalNeedError("retrieval_need_policy_budget_invalid")
    if policy.get("schema_version") == "fin_ia_s1_vs3_retrieval_need_compiler_policy_v1_2":
        successor = policy.get("materiality_first_contract")
        if not (
            isinstance(successor, Mapping)
            and successor.get("standalone_intents_before_cross_products") is True
            and successor.get("typed_lexical_query_excludes_generic_role_cues") is True
            and successor.get("period_only_intent_compiled_as_temporal_constraint") is True
            and successor.get("same_basis_comparison_explicit") is True
        ):
            raise RetrievalNeedError("retrieval_need_materiality_contract_invalid")


def _quoted(value: str) -> tuple[str, ...]:
    return tuple(match.group(1).strip() for match in re.finditer(r'"([^"]+)"', value))


def _is_period_only_intent(value: str) -> bool:
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
    if not normalized:
        return False
    tokens = normalized.split()
    temporal = {
        "compare",
        "compared",
        "comparison",
        "fiscal",
        "fy",
        "period",
        "to",
        "versus",
        "vs",
        "year",
        "yoy",
    }
    return all(
        token in temporal
        or token.isdigit()
        or bool(re.fullmatch(r"fy\d{4}", token))
        for token in tokens
    ) and any(token.isdigit() or re.fullmatch(r"fy\d{4}", token) for token in tokens)


def _unique(values: Iterable[object]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return tuple(output)


def _reject_leakage(values: Sequence[str]) -> None:
    for value in values:
        if any(pattern.search(value) for pattern in _FORBIDDEN_QUERY_SURFACES):
            raise RetrievalNeedError("retrieval_need_gold_or_url_leakage")


__all__ = [
    "RETRIEVAL_NEED_POLICY_SCHEMA_VERSION",
    "RETRIEVAL_NEED_POLICY_SCHEMA_VERSIONS",
    "RETRIEVAL_NEED_SET_SCHEMA_VERSION",
    "RETRIEVAL_NEED_SET_SUCCESSOR_SCHEMA_VERSION",
    "RetrievalNeed",
    "RetrievalNeedError",
    "RetrievalNeedSet",
    "compile_retrieval_needs",
]
