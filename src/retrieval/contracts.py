from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping


KERNEL_SCHEMA_VERSION = "fin_ia_financial_research_kernel_v1_0"


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


@dataclass(frozen=True)
class EvidenceFacetSpec:
    facet_id: str
    business_question_zh: str
    evidence_owner_scope: str
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
                facet_scope in {"subject", "subject_and_related"},
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
                facet.facet_id and facet.business_question_zh,
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
            )
            _require(
                ticker
                and ticker != subject_ticker
                and entity.legal_name
                and entity.relationship_direction,
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


__all__ = [
    "CaseResearchProfile",
    "EvidenceFacetSpec",
    "EvidenceSlotSpec",
    "FinancialResearchKernel",
    "IndustryPack",
    "KERNEL_SCHEMA_VERSION",
    "RelatedEntity",
    "RetrievalBudgets",
    "RetrievalContractError",
    "load_financial_research_kernel",
]
