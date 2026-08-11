from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from sec_agent.s1_08_candidate_generation_runtime import (
    CATALOG_SCHEMA_V3,
    CONTRACT_REF_V3,
    canonical_digest,
    normalize_locator,
)


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0"
)
CONTRACT_REF = (
    "fin_0_1_3.S1_08.relationship_aware_search_intent_and_source_equivalence:v1"
)
CASES = ("DELL", "MU", "NVDA")
LANGUAGES = ("en", "zh")
ROUTE_CLASSES = ("precise_official_domain", "semantic_open_web")
EXTERNAL_SLOT_IDS = (
    "issuer_results_and_management_commentary",
    "regulatory_risk_and_financial_reconciliation",
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
GOLD_TOKEN_PREFIXES = (
    "SRC_",
    "DELL_E",
    "MU_E",
    "NVDA_E",
    "DELL_T",
    "MU_T",
    "NVDA_T",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SEC_ACCESSION = re.compile(r"^[0-9]{18}$")


class S108SearchIntentError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SearchIntent:
    intent_id: str
    case_key: str
    evidence_slot_id: str
    language: str
    route_class: str
    subject_entity_key: str
    subject_aliases: tuple[str, ...]
    evidence_owner_entity_key: str
    evidence_owner_aliases: tuple[str, ...]
    evidence_owner_role: str
    claim_direction: str
    period_terms: tuple[str, ...]
    as_of_date: str
    source_families: tuple[str, ...]
    preferred_domains: tuple[str, ...]
    budget_group: str
    research_objective_digest: str
    query_text: str
    intent_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "language": self.language,
            "route_class": self.route_class,
            "subject_entity_key": self.subject_entity_key,
            "subject_aliases": list(self.subject_aliases),
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "evidence_owner_aliases": list(self.evidence_owner_aliases),
            "evidence_owner_role": self.evidence_owner_role,
            "claim_direction": self.claim_direction,
            "period_terms": list(self.period_terms),
            "as_of_date": self.as_of_date,
            "source_families": list(self.source_families),
            "preferred_domains": list(self.preferred_domains),
            "budget_group": self.budget_group,
            "research_objective_digest": self.research_objective_digest,
            "query_text": self.query_text,
            "intent_digest": self.intent_digest,
        }


@dataclass(frozen=True)
class SourceIdentity:
    identity_id: str
    case_key: str
    evidence_owner_entity_key: str
    source_family: str
    document_kind: str
    published_on: str
    authority: str
    locator: str
    sec_accession: str = ""
    canonical_locator: str = ""
    canonical_locator_verified: bool = False
    redirect_final_locator: str = ""
    redirect_verified: bool = False
    content_sha256: str = ""
    content_identity_verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "case_key": self.case_key,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "source_family": self.source_family,
            "document_kind": self.document_kind,
            "published_on": self.published_on,
            "authority": self.authority,
            "locator": self.locator,
            "sec_accession": self.sec_accession,
            "canonical_locator": self.canonical_locator,
            "canonical_locator_verified": self.canonical_locator_verified,
            "redirect_final_locator": self.redirect_final_locator,
            "redirect_verified": self.redirect_verified,
            "content_sha256": self.content_sha256,
            "content_identity_verified": self.content_identity_verified,
        }


def load_search_intent_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("source_catalog_schema_version") != CATALOG_SCHEMA_V3
        or policy.get("source_catalog_contract_ref") != CONTRACT_REF_V3
        or policy.get("as_of_date") != "2026-08-06"
        or tuple(policy.get("cases") or ()) != CASES
        or tuple(policy.get("languages") or ()) != LANGUAGES
        or tuple(policy.get("external_evidence_slots") or ())
        != EXTERNAL_SLOT_IDS
    ):
        raise S108SearchIntentError("s1_08_search_intent_policy_identity_invalid")
    serialized = json.dumps(policy, ensure_ascii=False)
    if (
        "http://" in serialized.lower()
        or "https://" in serialized.lower()
        or any(token in serialized for token in GOLD_TOKEN_PREFIXES)
    ):
        raise S108SearchIntentError("s1_08_search_intent_policy_gold_or_url_leak")
    route_classes = policy.get("route_classes") or {}
    if set(route_classes) != set(ROUTE_CLASSES):
        raise S108SearchIntentError("s1_08_search_intent_route_class_invalid")
    for route_class, row in route_classes.items():
        if (
            row.get("route_class") != route_class
            or row.get("domain_mode")
            not in {"evidence_owner_official", "none"}
            or set(row.get("query_terms") or {}) != set(LANGUAGES)
        ):
            raise S108SearchIntentError("s1_08_search_intent_route_contract_invalid")
    slots = policy.get("slot_contracts") or {}
    if set(slots) != set(EXTERNAL_SLOT_IDS):
        raise S108SearchIntentError("s1_08_search_intent_slot_contract_invalid")
    for slot_id, row in slots.items():
        if (
            row.get("slot_id") != slot_id
            or not row.get("claim_direction")
            or not row.get("allowed_source_owner_roles")
            or not row.get("source_families")
            or not row.get("route_classes")
            or not set(row.get("route_classes") or ()).issubset(ROUTE_CLASSES)
            or set(row.get("query_terms") or {}) != set(LANGUAGES)
        ):
            raise S108SearchIntentError("s1_08_search_intent_slot_contract_invalid")
    profiles = policy.get("entity_search_profiles") or {}
    if not profiles:
        raise S108SearchIntentError("s1_08_search_intent_entity_profiles_missing")
    alias_owners: dict[tuple[str, str], str] = {}
    for entity_key, profile in profiles.items():
        aliases = profile.get("localized_aliases") or {}
        periods = profile.get("period_terms") or {}
        if set(aliases) != set(LANGUAGES) or set(periods) != set(LANGUAGES):
            raise S108SearchIntentError("s1_08_search_intent_entity_profile_invalid")
        for language in LANGUAGES:
            if not aliases[language] or not periods[language]:
                raise S108SearchIntentError(
                    "s1_08_search_intent_entity_profile_invalid"
                )
            for alias in aliases[language]:
                key = (language, _normalize_alias(str(alias)))
                prior = alias_owners.get(key)
                if not key[1] or (prior is not None and prior != entity_key):
                    raise S108SearchIntentError(
                        "s1_08_search_intent_alias_collision"
                    )
                alias_owners[key] = entity_key
    budgets = policy.get("query_plan_budgets") or {}
    if (
        budgets.get("precise_official_domain_query_ceiling") != 36
        or budgets.get("semantic_open_web_query_ceiling") != 24
        or budgets.get("combined_zero_call_intent_ceiling") != 60
        or budgets.get("result_ceiling_per_query") != 10
        or budgets.get("identical_retry_allowed") is not False
        or budgets.get("provider_calls_during_compiler_proof") != 0
        or budgets.get("model_calls_during_compiler_proof") != 0
    ):
        raise S108SearchIntentError("s1_08_search_intent_budget_invalid")
    equivalence = policy.get("source_equivalence_contract") or {}
    if (
        equivalence.get("allowed_bases")
        != [
            "exact_locator",
            "sec_accession",
            "verified_canonical_locator",
            "verified_redirect_final_locator",
            "verified_content_identity",
        ]
        or equivalence.get("same_event_or_period_alone_is_equivalent") is not False
        or equivalence.get("provider_date_is_financial_date_authority") is not False
    ):
        raise S108SearchIntentError("s1_08_source_equivalence_policy_invalid")
    return policy


def compile_search_intents(
    *,
    catalog: Mapping[str, Any],
    policy: Mapping[str, Any],
    research_objectives: Mapping[str, str],
) -> tuple[SearchIntent, ...]:
    _validate_catalog_and_policy_binding(
        catalog=catalog, policy=policy, research_objectives=research_objectives
    )
    entities = {
        str(row["entity_key"]): dict(row) for row in catalog.get("entities") or []
    }
    blueprints = {
        str(row["slot_id"]): dict(row)
        for row in catalog.get("evidence_role_blueprints") or []
        if str(row.get("slot_id") or "") in EXTERNAL_SLOT_IDS
    }
    intents: list[SearchIntent] = []
    for case_key in CASES:
        for slot_id in EXTERNAL_SLOT_IDS:
            slot = policy["slot_contracts"][slot_id]
            blueprint = blueprints[slot_id]
            owner_rows = _owner_rows_for_slot(
                entities=entities,
                case_key=case_key,
                allowed_roles=tuple(slot["allowed_source_owner_roles"]),
            )
            for owner_key, owner_role in owner_rows:
                for language in LANGUAGES:
                    for route_class in slot["route_classes"]:
                        intents.append(
                            _build_search_intent(
                                entities=entities,
                                policy=policy,
                                blueprint=blueprint,
                                case_key=case_key,
                                slot_id=slot_id,
                                owner_key=owner_key,
                                owner_role=owner_role,
                                language=language,
                                route_class=str(route_class),
                                research_objective=str(
                                    research_objectives[case_key]
                                ),
                            )
                        )
    ordered = tuple(sorted(intents, key=_intent_sort_key))
    if len({row.intent_id for row in ordered}) != len(ordered):
        raise S108SearchIntentError("s1_08_search_intent_identity_collision")
    for row in ordered:
        validate_search_intent(
            intent=row,
            catalog=catalog,
            policy=policy,
            research_objective=str(research_objectives[row.case_key]),
        )
    compile_bounded_query_plans(intents=ordered, policy=policy)
    return ordered


def compile_bounded_query_plans(
    *, intents: Sequence[SearchIntent], policy: Mapping[str, Any]
) -> dict[str, Any]:
    grouped = {
        route_class: tuple(
            sorted(
                (row for row in intents if row.route_class == route_class),
                key=_intent_sort_key,
            )
        )
        for route_class in ROUTE_CLASSES
    }
    budgets = policy["query_plan_budgets"]
    expected = {
        "precise_official_domain": int(
            budgets["precise_official_domain_query_ceiling"]
        ),
        "semantic_open_web": int(budgets["semantic_open_web_query_ceiling"]),
    }
    if any(len(grouped[key]) != expected[key] for key in ROUTE_CLASSES):
        raise S108SearchIntentError(
            "s1_08_search_intent_fanout_budget_not_closed"
        )
    if sum(len(value) for value in grouped.values()) != int(
        budgets["combined_zero_call_intent_ceiling"]
    ):
        raise S108SearchIntentError(
            "s1_08_search_intent_combined_budget_not_closed"
        )
    coverage: dict[str, dict[str, set[tuple[str, str]]]] = {}
    for route_class, rows in grouped.items():
        for row in rows:
            case_bucket = coverage.setdefault(row.case_key, {})
            slot_bucket = case_bucket.setdefault(row.evidence_slot_id, set())
            slot_bucket.add((row.evidence_owner_entity_key, row.language))
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_relationship_aware_bounded_query_plans_v1_0"
        ),
        "contract_ref": CONTRACT_REF,
        "plans": {
            route_class: {
                "query_count": len(rows),
                "intent_ids": [row.intent_id for row in rows],
                "intent_digests": [row.intent_digest for row in rows],
            }
            for route_class, rows in grouped.items()
        },
        "coverage": {
            case_key: {
                slot_id: [list(value) for value in sorted(values)]
                for slot_id, values in sorted(slots.items())
            }
            for case_key, slots in sorted(coverage.items())
        },
        "provider_calls_authorized": 0,
        "model_calls_authorized": 0,
    }
    return {**body, "plan_digest": canonical_digest(body)}


def validate_search_intent(
    *,
    intent: SearchIntent,
    catalog: Mapping[str, Any],
    policy: Mapping[str, Any],
    research_objective: str,
) -> None:
    entities = {
        str(row["entity_key"]): dict(row) for row in catalog.get("entities") or []
    }
    if intent.case_key not in CASES or intent.subject_entity_key != intent.case_key:
        raise S108SearchIntentError("s1_08_search_intent_cross_case_subject")
    if intent.evidence_slot_id not in EXTERNAL_SLOT_IDS:
        raise S108SearchIntentError("s1_08_search_intent_slot_unknown")
    slot = policy["slot_contracts"][intent.evidence_slot_id]
    blueprint = next(
        (
            dict(row)
            for row in catalog.get("evidence_role_blueprints") or []
            if str(row.get("slot_id") or "") == intent.evidence_slot_id
        ),
        None,
    )
    if blueprint is None:
        raise S108SearchIntentError("s1_08_search_intent_slot_unknown")
    allowed = dict(
        _owner_rows_for_slot(
            entities=entities,
            case_key=intent.case_key,
            allowed_roles=tuple(slot["allowed_source_owner_roles"]),
        )
    )
    if (
        intent.evidence_owner_entity_key not in allowed
        or allowed[intent.evidence_owner_entity_key] != intent.evidence_owner_role
        or intent.claim_direction != slot["claim_direction"]
    ):
        raise S108SearchIntentError("s1_08_search_intent_wrong_relationship_direction")
    try:
        intent_as_of = date.fromisoformat(intent.as_of_date)
        policy_as_of = date.fromisoformat(str(policy["as_of_date"]))
    except ValueError as exc:
        raise S108SearchIntentError("s1_08_search_intent_as_of_invalid") from exc
    if intent_as_of > policy_as_of:
        raise S108SearchIntentError("s1_08_search_intent_future_as_of")
    expected = _build_search_intent(
        entities=entities,
        policy=policy,
        blueprint=blueprint,
        case_key=intent.case_key,
        slot_id=intent.evidence_slot_id,
        owner_key=intent.evidence_owner_entity_key,
        owner_role=intent.evidence_owner_role,
        language=intent.language,
        route_class=intent.route_class,
        research_objective=research_objective,
    )
    if intent != expected:
        raise S108SearchIntentError("s1_08_search_intent_projection_mismatch")


def match_source_identity(
    *, candidate: SourceIdentity, reference: SourceIdentity, as_of_date: str
) -> dict[str, Any]:
    _validate_source_identity(reference, as_of_date=as_of_date, reference=True)
    candidate_error = _validate_source_identity(
        candidate, as_of_date=as_of_date, reference=False
    )
    if candidate_error:
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="no_match",
            basis=candidate_error,
        )
    boundary_fields = (
        "case_key",
        "evidence_owner_entity_key",
        "source_family",
        "document_kind",
        "published_on",
        "authority",
    )
    if any(
        getattr(candidate, field) != getattr(reference, field)
        for field in boundary_fields
    ):
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="no_match",
            basis="source_identity_boundary_mismatch",
        )
    candidate_locator = normalize_locator(candidate.locator)
    reference_locator = normalize_locator(reference.locator)
    if candidate_locator and candidate_locator == reference_locator:
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="exact_locator_match",
            basis="exact_locator",
        )
    if (
        candidate.sec_accession
        and reference.sec_accession
        and _normalize_accession(candidate.sec_accession)
        == _normalize_accession(reference.sec_accession)
    ):
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="typed_source_equivalent_match",
            basis="sec_accession",
        )
    reference_locators = {
        value
        for value in (
            reference_locator,
            normalize_locator(reference.canonical_locator),
        )
        if value
    }
    if (
        candidate.canonical_locator_verified
        and normalize_locator(candidate.canonical_locator) in reference_locators
    ):
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="typed_source_equivalent_match",
            basis="verified_canonical_locator",
        )
    if (
        candidate.redirect_verified
        and normalize_locator(candidate.redirect_final_locator) in reference_locators
    ):
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="typed_source_equivalent_match",
            basis="verified_redirect_final_locator",
        )
    if (
        candidate.content_identity_verified
        and reference.content_identity_verified
        and candidate.content_sha256
        and candidate.content_sha256 == reference.content_sha256
    ):
        return _match_result(
            candidate=candidate,
            reference=reference,
            match_class="typed_source_equivalent_match",
            basis="verified_content_identity",
        )
    return _match_result(
        candidate=candidate,
        reference=reference,
        match_class="no_match",
        basis="no_typed_source_identity_equivalence",
    )


def evaluate_source_equivalence(
    *,
    candidates: Sequence[SourceIdentity],
    references: Sequence[SourceIdentity],
    as_of_date: str,
) -> dict[str, Any]:
    remaining = {row.identity_id: row for row in references}
    match_rows: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda row: row.identity_id):
        possible = [
            match_source_identity(
                candidate=candidate, reference=reference, as_of_date=as_of_date
            )
            for reference in remaining.values()
        ]
        ranked = sorted(
            (row for row in possible if row["match_class"] != "no_match"),
            key=lambda row: (
                0 if row["match_class"] == "exact_locator_match" else 1,
                _equivalence_basis_rank(str(row["basis"])),
                str(row["reference_identity_digest"]),
            ),
        )
        if ranked:
            selected = ranked[0]
            reference = next(
                row
                for row in remaining.values()
                if canonical_digest(row.as_dict())
                == selected["reference_identity_digest"]
            )
            remaining.pop(reference.identity_id)
            match_rows.append(selected)
        else:
            match_rows.append(
                {
                    "candidate_identity_digest": canonical_digest(
                        candidate.as_dict()
                    ),
                    "reference_identity_digest": "",
                    "match_class": "no_match",
                    "basis": (
                        possible[0]["basis"]
                        if possible
                        else "no_reference_available"
                    ),
                }
            )
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_typed_source_equivalence_evaluation_v1_0"
        ),
        "contract_ref": CONTRACT_REF,
        "as_of_date": as_of_date,
        "matches": match_rows,
        "unmatched_reference_identity_digests": sorted(
            canonical_digest(row.as_dict()) for row in remaining.values()
        ),
        "summary": {
            "candidate_count": len(candidates),
            "reference_count": len(references),
            "exact_locator_matches": sum(
                row["match_class"] == "exact_locator_match" for row in match_rows
            ),
            "typed_source_equivalent_matches": sum(
                row["match_class"] == "typed_source_equivalent_match"
                for row in match_rows
            ),
            "no_matches": sum(
                row["match_class"] == "no_match" for row in match_rows
            ),
        },
        "same_event_or_period_alone_is_equivalent": False,
        "provider_date_is_financial_date_authority": False,
    }
    return {**body, "evaluation_digest": canonical_digest(body)}


def _validate_catalog_and_policy_binding(
    *,
    catalog: Mapping[str, Any],
    policy: Mapping[str, Any],
    research_objectives: Mapping[str, str],
) -> None:
    if (
        catalog.get("schema_version") != CATALOG_SCHEMA_V3
        or catalog.get("contract_ref") != CONTRACT_REF_V3
        or policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("as_of_date") != catalog.get("as_of")
        or set(research_objectives) != set(CASES)
        or any(not str(value).strip() for value in research_objectives.values())
    ):
        raise S108SearchIntentError("s1_08_search_intent_input_binding_invalid")
    entity_keys = {str(row["entity_key"]) for row in catalog.get("entities") or []}
    if set(policy.get("entity_search_profiles") or {}) != entity_keys:
        raise S108SearchIntentError("s1_08_search_intent_entity_profile_set_invalid")
    entities = {
        str(row["entity_key"]): dict(row) for row in catalog.get("entities") or []
    }
    for language in LANGUAGES:
        alias_owners: dict[str, str] = {}
        for entity_key, entity in entities.items():
            aliases = _compiled_aliases(
                entity=entity,
                profile=policy["entity_search_profiles"][entity_key],
                language=language,
            )
            for alias in aliases:
                normalized = _normalize_alias(alias)
                prior = alias_owners.get(normalized)
                if prior is not None and prior != entity_key:
                    raise S108SearchIntentError(
                        "s1_08_search_intent_alias_collision"
                    )
                alias_owners[normalized] = entity_key


def _owner_rows_for_slot(
    *,
    entities: Mapping[str, Mapping[str, Any]],
    case_key: str,
    allowed_roles: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    allowed = set(str(value) for value in allowed_roles)
    rows: list[tuple[str, str]] = []
    for entity_key, entity in entities.items():
        roles = set(str(value) for value in entity.get("ecosystem_roles") or [])
        if "subject" in allowed:
            if entity_key == case_key:
                rows.append((entity_key, "subject"))
            continue
        intersection = sorted(roles.intersection(allowed))
        if entity_key != case_key and intersection:
            rows.append((entity_key, intersection[0]))
    if not rows:
        raise S108SearchIntentError("s1_08_search_intent_no_evidence_owner")
    return tuple(sorted(rows))


def _build_search_intent(
    *,
    entities: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    case_key: str,
    slot_id: str,
    owner_key: str,
    owner_role: str,
    language: str,
    route_class: str,
    research_objective: str,
) -> SearchIntent:
    if language not in LANGUAGES or route_class not in ROUTE_CLASSES:
        raise S108SearchIntentError("s1_08_search_intent_language_or_route_invalid")
    slot = policy["slot_contracts"][slot_id]
    if route_class not in slot["route_classes"]:
        raise S108SearchIntentError("s1_08_search_intent_route_not_allowed_for_slot")
    subject_aliases = _compiled_aliases(
        entity=entities[case_key], profile=policy["entity_search_profiles"][case_key], language=language
    )
    owner_aliases = _compiled_aliases(
        entity=entities[owner_key], profile=policy["entity_search_profiles"][owner_key], language=language
    )
    period_terms = tuple(
        str(value)
        for value in policy["entity_search_profiles"][owner_key]["period_terms"][language]
    )
    source_families = tuple(str(value) for value in slot["source_families"])
    preferred_domains = _official_domains(entities[owner_key])
    intent_id = "::".join(
        (
            "search_intent",
            case_key,
            slot_id,
            owner_key,
            language,
            route_class,
        )
    )
    objective_digest = canonical_digest(
        {"case_key": case_key, "research_objective": research_objective.strip()}
    )
    query_text = _render_query(
        policy=policy,
        slot_id=slot_id,
        language=language,
        route_class=route_class,
        case_key=case_key,
        owner_key=owner_key,
        subject_aliases=subject_aliases,
        owner_aliases=owner_aliases,
        period_terms=period_terms,
    )
    body = {
        "intent_id": intent_id,
        "case_key": case_key,
        "evidence_slot_id": slot_id,
        "language": language,
        "route_class": route_class,
        "subject_entity_key": case_key,
        "subject_aliases": list(subject_aliases),
        "evidence_owner_entity_key": owner_key,
        "evidence_owner_aliases": list(owner_aliases),
        "evidence_owner_role": owner_role,
        "claim_direction": str(slot["claim_direction"]),
        "period_terms": list(period_terms),
        "as_of_date": str(policy["as_of_date"]),
        "source_families": list(source_families),
        "preferred_domains": list(preferred_domains),
        "budget_group": str(blueprint["slot_budget_group"]),
        "research_objective_digest": objective_digest,
        "query_text": query_text,
    }
    return SearchIntent(
        intent_id=intent_id,
        case_key=case_key,
        evidence_slot_id=slot_id,
        language=language,
        route_class=route_class,
        subject_entity_key=case_key,
        subject_aliases=subject_aliases,
        evidence_owner_entity_key=owner_key,
        evidence_owner_aliases=owner_aliases,
        evidence_owner_role=owner_role,
        claim_direction=str(slot["claim_direction"]),
        period_terms=period_terms,
        as_of_date=str(policy["as_of_date"]),
        source_families=source_families,
        preferred_domains=preferred_domains,
        budget_group=str(blueprint["slot_budget_group"]),
        research_objective_digest=objective_digest,
        query_text=query_text,
        intent_digest=canonical_digest(body),
    )


def _compiled_aliases(
    *, entity: Mapping[str, Any], profile: Mapping[str, Any], language: str
) -> tuple[str, ...]:
    values = [
        *[str(value) for value in profile["localized_aliases"][language]],
        str(entity["entity_key"]),
        str(entity["legal_name"]),
        *[str(value) for value in entity.get("aliases") or []],
    ]
    deduplicated: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_alias(value)
        if normalized and normalized not in seen:
            deduplicated.append(value.strip())
            seen.add(normalized)
    return tuple(deduplicated[:4])


def _render_query(
    *,
    policy: Mapping[str, Any],
    slot_id: str,
    language: str,
    route_class: str,
    case_key: str,
    owner_key: str,
    subject_aliases: Sequence[str],
    owner_aliases: Sequence[str],
    period_terms: Sequence[str],
) -> str:
    slot = policy["slot_contracts"][slot_id]
    route = policy["route_classes"][route_class]
    direction_terms = policy["claim_direction_terms"][slot["claim_direction"]][language]
    source_terms = policy["source_family_terms"][language]
    parts = [
        *owner_aliases[:2],
        *period_terms,
        *[str(value) for value in direction_terms],
        *[str(value) for value in slot["query_terms"][language]],
        *[str(value) for value in source_terms],
        *[str(value) for value in route["query_terms"][language]],
    ]
    if owner_key != case_key:
        context_term = "research context" if language == "en" else "研究关联背景"
        parts.extend((subject_aliases[0], case_key, context_term))
    cutoff_term = "through" if language == "en" else "截至"
    parts.extend((cutoff_term, str(policy["as_of_date"])))
    return " ".join(dict.fromkeys(value.strip() for value in parts if value.strip()))


def _official_domains(entity: Mapping[str, Any]) -> tuple[str, ...]:
    domains = {
        (urlsplit(str(value)).hostname or "").lower()
        for value in entity.get("official_landing_pages") or []
    }
    return tuple(sorted(value for value in domains if value))


def _intent_sort_key(intent: SearchIntent) -> tuple[Any, ...]:
    return (
        CASES.index(intent.case_key),
        EXTERNAL_SLOT_IDS.index(intent.evidence_slot_id),
        intent.evidence_owner_entity_key,
        LANGUAGES.index(intent.language),
        ROUTE_CLASSES.index(intent.route_class),
    )


def _normalize_alias(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_accession(value: str) -> str:
    normalized = re.sub(r"[^0-9]", "", value)
    return normalized if _SEC_ACCESSION.fullmatch(normalized) else ""


def _validate_source_identity(
    identity: SourceIdentity, *, as_of_date: str, reference: bool
) -> str:
    try:
        published = date.fromisoformat(identity.published_on)
        as_of = date.fromisoformat(as_of_date)
    except ValueError as exc:
        if reference:
            raise S108SearchIntentError("s1_08_source_reference_date_invalid") from exc
        return "candidate_publication_date_invalid"
    if published > as_of:
        if reference:
            raise S108SearchIntentError("s1_08_source_reference_after_as_of")
        return "candidate_after_as_of"
    if not normalize_locator(identity.locator):
        if reference:
            raise S108SearchIntentError("s1_08_source_reference_locator_invalid")
        return "candidate_locator_invalid"
    for enabled, value, code in (
        (
            identity.canonical_locator_verified,
            identity.canonical_locator,
            "canonical_locator_verification_without_locator",
        ),
        (
            identity.redirect_verified,
            identity.redirect_final_locator,
            "redirect_verification_without_locator",
        ),
        (
            identity.content_identity_verified,
            identity.content_sha256,
            "content_verification_without_digest",
        ),
    ):
        if enabled and not value:
            if reference:
                raise S108SearchIntentError(f"s1_08_source_reference_{code}")
            return code
    if identity.content_sha256 and not _HEX64.fullmatch(identity.content_sha256):
        if reference:
            raise S108SearchIntentError("s1_08_source_reference_content_digest_invalid")
        return "candidate_content_digest_invalid"
    if identity.sec_accession and not _normalize_accession(identity.sec_accession):
        if reference:
            raise S108SearchIntentError("s1_08_source_reference_accession_invalid")
        return "candidate_accession_invalid"
    return ""


def _match_result(
    *,
    candidate: SourceIdentity,
    reference: SourceIdentity,
    match_class: str,
    basis: str,
) -> dict[str, Any]:
    return {
        "candidate_identity_digest": canonical_digest(candidate.as_dict()),
        "reference_identity_digest": canonical_digest(reference.as_dict()),
        "match_class": match_class,
        "basis": basis,
    }


def _equivalence_basis_rank(value: str) -> int:
    ordered = (
        "exact_locator",
        "sec_accession",
        "verified_canonical_locator",
        "verified_redirect_final_locator",
        "verified_content_identity",
    )
    return ordered.index(value) if value in ordered else len(ordered)


__all__ = [
    "CASES",
    "CONTRACT_REF",
    "EXTERNAL_SLOT_IDS",
    "LANGUAGES",
    "POLICY_SCHEMA",
    "ROUTE_CLASSES",
    "S108SearchIntentError",
    "SearchIntent",
    "SourceIdentity",
    "compile_bounded_query_plans",
    "compile_search_intents",
    "evaluate_source_equivalence",
    "load_search_intent_policy",
    "match_source_identity",
    "validate_search_intent",
]
