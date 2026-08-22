from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping


KERNEL_SCHEMA_VERSION = "fin_ia_financial_research_kernel_v1_0"
EVIDENCE_REQUEST_SCHEMA_VERSION = "fin_ia_evidence_request_v1_0"

_EVIDENCE_DOMAINS = frozenset(
    {
        "financial_research",
        "operating_performance",
        "demand",
        "supply",
        "relationship",
        "risk_policy",
        "valuation",
    }
)
_CLARIFICATION_POLICIES = frozenset(
    {"fail_closed", "return_typed_gap", "request_human_clarification"}
)
_FORBIDDEN_INTENT_FRAGMENTS = (
    "http://",
    "https://",
    "sec.gov",
    "qrel",
    "gold target",
    "target_id",
    "source_record_id",
)
_RELATED_ECONOMIC_ROLES = frozenset(
    {
        "customer_demand_context",
        "supplier_capacity_context",
        "industry_market_context",
        "trusted_analysis_context",
        "channel_configuration_context",
    }
)


class RetrievalContractError(ValueError):
    """Raised when a retrieval contract cannot be interpreted safely."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RetrievalContractError(code)


def _strings(value: object, code: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and bool(value), code)
    normalized = tuple(str(item).strip() for item in value)
    _require(all(normalized) and len(normalized) == len(set(normalized)), code)
    return normalized


def _optional_strings(value: object, code: str) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    normalized = tuple(str(item).strip() for item in value)
    _require(all(normalized) and len(normalized) == len(set(normalized)), code)
    return normalized


def _related_economic_role(item: Mapping[str, Any]) -> str:
    explicit = str(item.get("economic_role") or "").strip()
    if explicit:
        return explicit
    direction = str(item.get("relationship_direction") or "").casefold()
    if any(token in direction for token in ("supplier", "upstream", "foundry")):
        return "supplier_capacity_context"
    return "customer_demand_context"


@dataclass(frozen=True)
class EvidenceFacetSpec:
    facet_id: str
    business_question_zh: str
    evidence_owner_scope: str
    related_economic_roles: tuple[str, ...]
    required_source_roles: tuple[str, ...]
    exact_phrases: tuple[str, ...]
    lexical_terms: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSlotSpec:
    slot_id: str
    business_question_zh: str
    evidence_owner_scope: str
    source_types: tuple[str, ...]
    required_source_roles: tuple[str, ...]
    exact_phrases: tuple[str, ...]
    lexical_terms: tuple[str, ...]
    forbidden_expansions: tuple[str, ...]
    reviewed_pack_slot_ids: tuple[str, ...]
    facets: tuple[EvidenceFacetSpec, ...]


@dataclass(frozen=True)
class RelatedEntity:
    ticker: str
    legal_name: str
    aliases: tuple[str, ...]
    relationship_direction: str
    economic_role: str


@dataclass(frozen=True)
class CaseResearchProfile:
    case_key: str
    subject_ticker: str
    subject_legal_name: str
    subject_aliases: tuple[str, ...]
    research_as_of: date
    industry_pack_id: str
    related_entities: tuple[RelatedEntity, ...]
    slot_terms: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class IndustryPack:
    pack_id: str
    lexical_terms: tuple[str, ...]
    slot_terms: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class RetrievalBudgets:
    candidates_per_slot: int
    candidates_per_document: int
    excerpt_characters: int


@dataclass(frozen=True)
class EvidenceRequestPeriod:
    start_date: date | None
    end_date: date | None
    fiscal_years: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "fiscal_years": list(self.fiscal_years),
        }


@dataclass(frozen=True)
class EvidenceRequest:
    schema_version: str
    request_id: str
    cell_id: str
    requester_role: str
    evidence_domain: str
    case_key: str
    subject_ticker: str
    research_as_of: date
    target_entities: tuple[str, ...]
    requested_facet_ids: tuple[str, ...]
    metric_intents: tuple[str, ...]
    product_intents: tuple[str, ...]
    period: EvidenceRequestPeriod
    granularity: str
    unit: str
    acceptable_sources: tuple[str, ...]
    acceptable_proxy: bool
    forbidden_proxy: tuple[str, ...]
    stop_condition: str
    clarification_policy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "cell_id": self.cell_id,
            "requester_role": self.requester_role,
            "evidence_domain": self.evidence_domain,
            "case_key": self.case_key,
            "subject_ticker": self.subject_ticker,
            "research_as_of": self.research_as_of.isoformat(),
            "target_entities": list(self.target_entities),
            "requested_facet_ids": list(self.requested_facet_ids),
            "metric_intents": list(self.metric_intents),
            "product_intents": list(self.product_intents),
            "period": self.period.as_dict(),
            "granularity": self.granularity,
            "unit": self.unit,
            "acceptable_sources": list(self.acceptable_sources),
            "acceptable_proxy": self.acceptable_proxy,
            "forbidden_proxy": list(self.forbidden_proxy),
            "stop_condition": self.stop_condition,
            "clarification_policy": self.clarification_policy,
        }


@dataclass(frozen=True)
class FinancialResearchKernel:
    slots: tuple[EvidenceSlotSpec, ...]
    industry_packs: Mapping[str, IndustryPack]
    cases: Mapping[str, CaseResearchProfile]
    budgets: RetrievalBudgets

    def slot_by_id(self) -> dict[str, EvidenceSlotSpec]:
        return {slot.slot_id: slot for slot in self.slots}


def load_financial_research_kernel(
    payload: Mapping[str, Any],
) -> FinancialResearchKernel:
    """Parse the provider-neutral S1 contract and fail closed on drift."""

    _require(
        payload.get("schema_version") == KERNEL_SCHEMA_VERSION,
        "retrieval_kernel_schema_invalid",
    )
    _require(
        payload.get("status") == "provider_neutral_s1_retrieval_contract",
        "retrieval_kernel_status_invalid",
    )
    policy = payload.get("policy")
    _require(
        isinstance(policy, Mapping)
        and policy.get("candidate_generation_precedes_relevance_labels") is True
        and policy.get("provider_specific_wire_projection_outside_core") is True
        and policy.get("candidate_is_not_evidence") is True
        and policy.get("as_of_filter_fails_closed") is True,
        "retrieval_kernel_policy_invalid",
    )

    raw_slots = payload.get("evidence_slots")
    _require(isinstance(raw_slots, list) and bool(raw_slots), "retrieval_slots_invalid")
    slots: list[EvidenceSlotSpec] = []
    for raw in raw_slots:
        _require(isinstance(raw, Mapping), "retrieval_slot_invalid")
        scope = str(raw.get("evidence_owner_scope") or "")
        _require(
            scope in {"subject", "subject_and_related"},
            "retrieval_slot_owner_scope_invalid",
        )
        raw_facets = raw.get("facets")
        _require(
            isinstance(raw_facets, list) and bool(raw_facets),
            "retrieval_slot_facets_invalid",
        )
        facets: list[EvidenceFacetSpec] = []
        for raw_facet in raw_facets:
            _require(isinstance(raw_facet, Mapping), "retrieval_facet_invalid")
            facet_scope = str(
                raw_facet.get("evidence_owner_scope") or scope
            )
            _require(
                facet_scope in {"subject", "subject_and_related", "related_only"},
                "retrieval_facet_owner_scope_invalid",
            )
            required_roles = raw_facet.get("required_source_roles") or raw.get(
                "required_source_roles"
            )
            facet = EvidenceFacetSpec(
                facet_id=str(raw_facet.get("facet_id") or "").strip(),
                business_question_zh=str(
                    raw_facet.get("business_question_zh") or ""
                ).strip(),
                evidence_owner_scope=facet_scope,
                related_economic_roles=_optional_strings(
                    raw_facet.get("related_economic_roles") or [],
                    "retrieval_facet_related_economic_roles_invalid",
                ),
                required_source_roles=_strings(
                    required_roles,
                    "retrieval_facet_source_roles_invalid",
                ),
                exact_phrases=_strings(
                    raw_facet.get("exact_phrases"),
                    "retrieval_facet_exact_phrases_invalid",
                ),
                lexical_terms=_strings(
                    raw_facet.get("lexical_terms"),
                    "retrieval_facet_terms_invalid",
                ),
            )
            _require(
                facet.facet_id
                and facet.business_question_zh
                and set(facet.related_economic_roles).issubset(
                    _RELATED_ECONOMIC_ROLES
                )
                and (
                    not facet.related_economic_roles
                    or facet.evidence_owner_scope
                    in {"subject_and_related", "related_only"}
                ),
                "retrieval_facet_identity_invalid",
            )
            facets.append(facet)
        _require(
            len({facet.facet_id for facet in facets}) == len(facets),
            "retrieval_facet_duplicate",
        )
        slot = EvidenceSlotSpec(
            slot_id=str(raw.get("slot_id") or "").strip(),
            business_question_zh=str(raw.get("business_question_zh") or "").strip(),
            evidence_owner_scope=scope,
            source_types=_strings(raw.get("source_types"), "retrieval_slot_source_types_invalid"),
            required_source_roles=_strings(
                raw.get("required_source_roles"),
                "retrieval_slot_source_roles_invalid",
            ),
            exact_phrases=_strings(raw.get("exact_phrases"), "retrieval_slot_exact_phrases_invalid"),
            lexical_terms=_strings(raw.get("lexical_terms"), "retrieval_slot_terms_invalid"),
            forbidden_expansions=_strings(
                raw.get("forbidden_expansions"),
                "retrieval_slot_forbidden_invalid",
            ),
            reviewed_pack_slot_ids=_strings(
                raw.get("reviewed_pack_slot_ids"),
                "retrieval_slot_reviewed_mapping_invalid",
            ),
            facets=tuple(facets),
        )
        _require(slot.slot_id and slot.business_question_zh, "retrieval_slot_identity_invalid")
        slots.append(slot)
    slot_ids = [slot.slot_id for slot in slots]
    _require(len(slot_ids) == len(set(slot_ids)), "retrieval_slot_duplicate")

    raw_packs = payload.get("industry_packs")
    _require(isinstance(raw_packs, list) and bool(raw_packs), "retrieval_industry_packs_invalid")
    industry_packs: dict[str, IndustryPack] = {}
    for raw in raw_packs:
        _require(isinstance(raw, Mapping), "retrieval_industry_pack_invalid")
        pack_id = str(raw.get("pack_id") or "").strip()
        raw_slot_terms = raw.get("slot_terms")
        _require(
            pack_id
            and pack_id not in industry_packs
            and isinstance(raw_slot_terms, Mapping),
            "retrieval_industry_pack_identity_invalid",
        )
        unknown = set(raw_slot_terms) - set(slot_ids)
        _require(not unknown, "retrieval_industry_pack_unknown_slot")
        industry_packs[pack_id] = IndustryPack(
            pack_id=pack_id,
            lexical_terms=_strings(
                raw.get("lexical_terms"),
                "retrieval_industry_pack_terms_invalid",
            ),
            slot_terms={
                str(slot_id): _strings(terms, "retrieval_industry_slot_terms_invalid")
                for slot_id, terms in raw_slot_terms.items()
            },
        )

    raw_cases = payload.get("cases")
    _require(isinstance(raw_cases, list) and bool(raw_cases), "retrieval_cases_invalid")
    cases: dict[str, CaseResearchProfile] = {}
    for raw in raw_cases:
        _require(isinstance(raw, Mapping), "retrieval_case_invalid")
        subject = raw.get("subject")
        related = raw.get("related_entities")
        raw_slot_terms = raw.get("slot_terms")
        _require(
            isinstance(subject, Mapping)
            and isinstance(related, list)
            and isinstance(raw_slot_terms, Mapping),
            "retrieval_case_shape_invalid",
        )
        case_key = str(raw.get("case_key") or "").strip().upper()
        subject_ticker = str(subject.get("ticker") or "").strip().upper()
        industry_pack_id = str(raw.get("industry_pack_id") or "").strip()
        _require(
            case_key
            and case_key == subject_ticker
            and case_key not in cases
            and industry_pack_id in industry_packs,
            "retrieval_case_identity_invalid",
        )
        try:
            research_as_of = date.fromisoformat(str(raw.get("research_as_of") or ""))
        except ValueError as exc:
            raise RetrievalContractError("retrieval_case_as_of_invalid") from exc
        related_entities: list[RelatedEntity] = []
        for item in related:
            _require(isinstance(item, Mapping), "retrieval_related_entity_invalid")
            ticker = str(item.get("ticker") or "").strip().upper()
            entity = RelatedEntity(
                ticker=ticker,
                legal_name=str(item.get("legal_name") or "").strip(),
                aliases=_strings(item.get("aliases"), "retrieval_related_aliases_invalid"),
                relationship_direction=str(item.get("relationship_direction") or "").strip(),
                economic_role=_related_economic_role(item),
            )
            _require(
                ticker
                and ticker != subject_ticker
                and entity.legal_name
                and entity.relationship_direction
                and entity.economic_role in _RELATED_ECONOMIC_ROLES,
                "retrieval_related_entity_identity_invalid",
            )
            related_entities.append(entity)
        _require(
            len({item.ticker for item in related_entities}) == len(related_entities),
            "retrieval_related_entity_duplicate",
        )
        unknown = set(raw_slot_terms) - set(slot_ids)
        _require(not unknown, "retrieval_case_unknown_slot")
        cases[case_key] = CaseResearchProfile(
            case_key=case_key,
            subject_ticker=subject_ticker,
            subject_legal_name=str(subject.get("legal_name") or "").strip(),
            subject_aliases=_strings(subject.get("aliases"), "retrieval_subject_aliases_invalid"),
            research_as_of=research_as_of,
            industry_pack_id=industry_pack_id,
            related_entities=tuple(related_entities),
            slot_terms={
                str(slot_id): _strings(terms, "retrieval_case_slot_terms_invalid")
                for slot_id, terms in raw_slot_terms.items()
            },
        )

    budgets = payload.get("budgets")
    _require(isinstance(budgets, Mapping), "retrieval_budgets_invalid")
    parsed_budgets = RetrievalBudgets(
        candidates_per_slot=int(budgets.get("candidates_per_slot") or 0),
        candidates_per_document=int(budgets.get("candidates_per_document") or 0),
        excerpt_characters=int(budgets.get("excerpt_characters") or 0),
    )
    _require(
        1 <= parsed_budgets.candidates_per_slot <= 20
        and 1 <= parsed_budgets.candidates_per_document <= parsed_budgets.candidates_per_slot
        and 120 <= parsed_budgets.excerpt_characters <= 1200,
        "retrieval_budgets_out_of_range",
    )
    return FinancialResearchKernel(
        slots=tuple(slots),
        industry_packs=industry_packs,
        cases=cases,
        budgets=parsed_budgets,
    )


def load_evidence_request(
    payload: Mapping[str, Any],
    kernel: FinancialResearchKernel,
) -> EvidenceRequest:
    """Parse one S1 request without accepting free-form query authority."""

    expected_fields = {
        "schema_version",
        "request_id",
        "cell_id",
        "requester_role",
        "evidence_domain",
        "case_key",
        "subject_ticker",
        "research_as_of",
        "target_entities",
        "requested_facet_ids",
        "metric_intents",
        "product_intents",
        "period",
        "granularity",
        "unit",
        "acceptable_sources",
        "acceptable_proxy",
        "forbidden_proxy",
        "stop_condition",
        "clarification_policy",
    }
    _require(set(payload) == expected_fields, "evidence_request_fields_invalid")
    _require(
        payload.get("schema_version") == EVIDENCE_REQUEST_SCHEMA_VERSION,
        "evidence_request_schema_invalid",
    )
    case_key = str(payload.get("case_key") or "").strip().upper()
    _require(case_key in kernel.cases, "evidence_request_case_unknown")
    profile = kernel.cases[case_key]
    subject_ticker = str(payload.get("subject_ticker") or "").strip().upper()
    _require(
        subject_ticker == profile.subject_ticker,
        "evidence_request_subject_mismatch",
    )
    try:
        research_as_of = date.fromisoformat(str(payload.get("research_as_of") or ""))
    except ValueError as exc:
        raise RetrievalContractError("evidence_request_as_of_invalid") from exc
    _require(
        research_as_of == profile.research_as_of,
        "evidence_request_as_of_mismatch",
    )

    request_id = str(payload.get("request_id") or "").strip()
    cell_id = str(payload.get("cell_id") or "").strip()
    requester_role = str(payload.get("requester_role") or "").strip()
    evidence_domain = str(payload.get("evidence_domain") or "").strip()
    _require(
        request_id and cell_id and requester_role,
        "evidence_request_identity_invalid",
    )
    _require(
        evidence_domain in _EVIDENCE_DOMAINS,
        "evidence_request_domain_invalid",
    )

    target_entities = tuple(
        value.upper()
        for value in _strings(
            payload.get("target_entities"), "evidence_request_targets_invalid"
        )
    )
    _require(
        len(target_entities) == len(set(target_entities)),
        "evidence_request_targets_invalid",
    )
    allowed_entities = {
        profile.subject_ticker,
        *(entity.ticker for entity in profile.related_entities),
    }
    _require(
        set(target_entities).issubset(allowed_entities),
        "evidence_request_target_out_of_case_scope",
    )

    requested_facets = _strings(
        payload.get("requested_facet_ids"),
        "evidence_request_facets_invalid",
    )
    facets = {
        facet.facet_id: (slot, facet)
        for slot in kernel.slots
        for facet in slot.facets
    }
    _require(
        set(requested_facets).issubset(facets),
        "evidence_request_facet_unknown",
    )
    for facet_id in requested_facets:
        _, facet = facets[facet_id]
        permitted = {profile.subject_ticker}
        if facet.evidence_owner_scope == "related_only":
            permitted.clear()
        if facet.evidence_owner_scope in {"subject_and_related", "related_only"}:
            permitted.update(
                entity.ticker
                for entity in profile.related_entities
                if not facet.related_economic_roles
                or entity.economic_role in facet.related_economic_roles
            )
        _require(
            bool(permitted.intersection(target_entities)),
            f"evidence_request_facet_has_no_target:{facet_id}",
        )

    metric_intents = _optional_strings(
        payload.get("metric_intents"), "evidence_request_metric_intents_invalid"
    )
    product_intents = _optional_strings(
        payload.get("product_intents"), "evidence_request_product_intents_invalid"
    )
    _require(
        bool(metric_intents or product_intents),
        "evidence_request_intent_missing",
    )
    _require(
        len(metric_intents) <= 12
        and len(product_intents) <= 12
        and all(
            len(value) <= 120
            and "\n" not in value
            and "\r" not in value
            and not any(
                fragment in value.casefold()
                for fragment in _FORBIDDEN_INTENT_FRAGMENTS
            )
            for value in (*metric_intents, *product_intents)
        ),
        "evidence_request_intent_surface_invalid",
    )

    raw_period = payload.get("period")
    _require(
        isinstance(raw_period, Mapping)
        and set(raw_period) == {"start_date", "end_date", "fiscal_years"},
        "evidence_request_period_invalid",
    )
    try:
        start_date = (
            date.fromisoformat(str(raw_period["start_date"]))
            if raw_period.get("start_date")
            else None
        )
        end_date = (
            date.fromisoformat(str(raw_period["end_date"]))
            if raw_period.get("end_date")
            else None
        )
    except ValueError as exc:
        raise RetrievalContractError("evidence_request_period_invalid") from exc
    raw_years = raw_period.get("fiscal_years")
    _require(isinstance(raw_years, list), "evidence_request_fiscal_years_invalid")
    fiscal_years = tuple(int(value) for value in raw_years)
    _require(
        len(fiscal_years) == len(set(fiscal_years))
        and all(1990 <= value <= research_as_of.year + 1 for value in fiscal_years),
        "evidence_request_fiscal_years_invalid",
    )
    _require(
        start_date is None or end_date is None or start_date <= end_date,
        "evidence_request_period_order_invalid",
    )
    _require(
        end_date is None or end_date <= research_as_of,
        "evidence_request_period_after_as_of",
    )
    _require(
        bool(start_date or end_date or fiscal_years),
        "evidence_request_period_missing",
    )

    acceptable_sources = _strings(
        payload.get("acceptable_sources"),
        "evidence_request_sources_invalid",
    )
    available_sources = {
        source_type
        for facet_id in requested_facets
        for source_type in facets[facet_id][0].source_types
    }
    _require(
        set(acceptable_sources).issubset(available_sources),
        "evidence_request_source_not_allowed",
    )
    acceptable_proxy = payload.get("acceptable_proxy")
    _require(type(acceptable_proxy) is bool, "evidence_request_proxy_policy_invalid")
    forbidden_proxy = _strings(
        payload.get("forbidden_proxy"),
        "evidence_request_forbidden_proxy_invalid",
    )
    clarification_policy = str(payload.get("clarification_policy") or "").strip()
    _require(
        clarification_policy in _CLARIFICATION_POLICIES,
        "evidence_request_clarification_policy_invalid",
    )
    granularity = str(payload.get("granularity") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    stop_condition = str(payload.get("stop_condition") or "").strip()
    _require(
        granularity and unit and stop_condition,
        "evidence_request_execution_policy_invalid",
    )
    return EvidenceRequest(
        schema_version=EVIDENCE_REQUEST_SCHEMA_VERSION,
        request_id=request_id,
        cell_id=cell_id,
        requester_role=requester_role,
        evidence_domain=evidence_domain,
        case_key=case_key,
        subject_ticker=subject_ticker,
        research_as_of=research_as_of,
        target_entities=target_entities,
        requested_facet_ids=requested_facets,
        metric_intents=metric_intents,
        product_intents=product_intents,
        period=EvidenceRequestPeriod(
            start_date=start_date,
            end_date=end_date,
            fiscal_years=fiscal_years,
        ),
        granularity=granularity,
        unit=unit,
        acceptable_sources=acceptable_sources,
        acceptable_proxy=acceptable_proxy,
        forbidden_proxy=forbidden_proxy,
        stop_condition=stop_condition,
        clarification_policy=clarification_policy,
    )


__all__ = [
    "CaseResearchProfile",
    "EVIDENCE_REQUEST_SCHEMA_VERSION",
    "EvidenceRequest",
    "EvidenceRequestPeriod",
    "EvidenceFacetSpec",
    "EvidenceSlotSpec",
    "FinancialResearchKernel",
    "IndustryPack",
    "KERNEL_SCHEMA_VERSION",
    "RelatedEntity",
    "RetrievalBudgets",
    "RetrievalContractError",
    "load_financial_research_kernel",
    "load_evidence_request",
]
