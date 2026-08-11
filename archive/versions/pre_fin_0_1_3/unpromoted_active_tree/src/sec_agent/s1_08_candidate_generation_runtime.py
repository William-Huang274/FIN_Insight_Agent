from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit


CATALOG_SCHEMA = (
    "fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0"
)
CONTRACT_REF = "fin_0_1_3.S1_08.current_source_catalog_candidate_generation:v2"
CATALOG_SCHEMA_V3 = (
    "fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0"
)
CONTRACT_REF_V3 = (
    "fin_0_1_3.S1_08.current_source_catalog_relationship_budget_candidate_generation:v3"
)
_SUPPORTED_CONTRACTS = {
    "fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v1_0":
        "fin_0_1_3.S1_08.current_source_catalog_candidate_generation:v1",
    CATALOG_SCHEMA: CONTRACT_REF,
    CATALOG_SCHEMA_V3: CONTRACT_REF_V3,
}
CASES = ("DELL", "MU", "NVDA")
GOLD_TOKEN_PREFIXES = ("SRC_", "DELL_E", "MU_E", "NVDA_E", "DELL_T", "MU_T", "NVDA_T")


class S108CandidateGenerationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def normalize_locator(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("https://"):
        split = urlsplit(text)
        return urlunsplit(
            (split.scheme.lower(), split.netloc.lower(), split.path.rstrip("/"), split.query, "")
        )
    return text


def load_source_catalog(path: str | Path) -> dict[str, Any]:
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        _SUPPORTED_CONTRACTS.get(str(catalog.get("schema_version")))
        != catalog.get("contract_ref")
        or catalog.get("as_of") != "2026-08-06"
    ):
        raise S108CandidateGenerationError("s1_08_source_catalog_identity_invalid")
    serialized = json.dumps(catalog, ensure_ascii=False)
    if any(token in serialized for token in GOLD_TOKEN_PREFIXES):
        raise S108CandidateGenerationError("s1_08_gold_identifier_leaked_into_catalog")
    budgets = catalog.get("budgets") or {}
    if (
        budgets.get("maximum_revisions_per_target") != 2
        or budgets.get("selected_pack_ceiling_per_case") != 8
        or budgets.get("model_calls") != 0
        or budgets.get("identical_retry_forbidden") is not True
    ):
        raise S108CandidateGenerationError("s1_08_source_catalog_budget_invalid")
    if catalog.get("schema_version") == CATALOG_SCHEMA_V3:
        reservations = budgets.get("slot_group_reservations") or {}
        required_reservations = {
            "issuer_and_regulatory_shared": 4,
            "customer_demand": 4,
            "supply_and_counterevidence": 5,
            "market_context": 0,
            "shared_contingency_after_first_round": 3,
        }
        if (
            budgets.get("replacement_network_call_ceiling") != 16
            or budgets.get("maximum_document_fetches_per_attempt") != 2
            or budgets.get("maximum_accepted_unique_documents_per_attempt") != 1
            or reservations != required_reservations
            or sum(reservations.values()) != 16
            or budgets.get("round_robin_first_attempt_required") is not True
        ):
            raise S108CandidateGenerationError("s1_08_v3_slot_budget_invalid")
    entities = catalog.get("entities") or []
    keys = [str(row.get("entity_key") or "") for row in entities]
    if len(keys) != len(set(keys)) or not set(CASES).issubset(keys):
        raise S108CandidateGenerationError("s1_08_source_catalog_entity_set_invalid")
    for entity in entities:
        pages = entity.get("official_landing_pages") or []
        if not pages or any(not str(url).startswith("https://") for url in pages):
            raise S108CandidateGenerationError("s1_08_source_catalog_landing_page_invalid")
    if catalog.get("schema_version") in {CATALOG_SCHEMA, CATALOG_SCHEMA_V3}:
        capabilities = catalog.get("source_provider_capabilities") or []
        route_ids = [str(row.get("route_id") or "") for row in capabilities]
        if not route_ids or len(route_ids) != len(set(route_ids)):
            raise S108CandidateGenerationError("s1_08_source_provider_capability_invalid")
        if any("operational" not in row for row in capabilities):
            raise S108CandidateGenerationError("s1_08_source_provider_operational_state_missing")
        if catalog.get("schema_version") == CATALOG_SCHEMA_V3 and any(
            not {
                "declared",
                "configured",
                "operational",
                "replay_proven",
                "live_proven",
            }.issubset(row)
            for row in capabilities
        ):
            raise S108CandidateGenerationError("s1_08_v3_provider_capability_state_missing")
    return catalog


@dataclass(frozen=True)
class EvidenceSlot:
    slot_id: str
    role_id: str
    required: bool
    source_families: tuple[str, ...]
    route_ids: tuple[str, ...]
    entity_roles: tuple[str, ...]
    currentness_window_days: int
    minimum_qualified_candidates: int
    stop_condition: str
    subject_entity_mode: str = ""
    evidence_owner_entity_mode: str = ""
    claim_direction: str = ""
    allowed_source_owner_roles: tuple[str, ...] = ()
    forbidden_nested_relationships: tuple[str, ...] = ()
    slot_budget_group: str = ""

    def as_dict(self) -> dict[str, Any]:
        body = {
            "slot_id": self.slot_id,
            "role_id": self.role_id,
            "required": self.required,
            "source_families": list(self.source_families),
            "route_ids": list(self.route_ids),
            "entity_roles": list(self.entity_roles),
            "currentness_window_days": self.currentness_window_days,
            "minimum_qualified_candidates": self.minimum_qualified_candidates,
            "stop_condition": self.stop_condition,
        }
        if self.subject_entity_mode:
            body.update(
                {
                    "subject_entity_mode": self.subject_entity_mode,
                    "evidence_owner_entity_mode": self.evidence_owner_entity_mode,
                    "claim_direction": self.claim_direction,
                    "allowed_source_owner_roles": list(
                        self.allowed_source_owner_roles
                    ),
                    "forbidden_nested_relationships": list(
                        self.forbidden_nested_relationships
                    ),
                    "slot_budget_group": self.slot_budget_group,
                }
            )
        return body


@dataclass(frozen=True)
class DiscoveryQuery:
    case_key: str
    target_key: str
    role_id: str
    revision: int
    query_text: str
    route_ids: tuple[str, ...]
    entity_keys: tuple[str, ...]
    prior_reason: str
    query_digest: str
    evidence_slot_id: str = ""
    required: bool = True
    source_families: tuple[str, ...] = ()
    currentness_window_days: int = 550
    minimum_qualified_candidates: int = 1
    stop_condition: str = "candidate_or_typed_gap"
    subject_entity: str = ""
    claim_direction: str = ""
    allowed_source_owner_roles: tuple[str, ...] = ()
    forbidden_nested_relationships: tuple[str, ...] = ()
    slot_budget_group: str = ""

    def as_dict(self) -> dict[str, Any]:
        body = {
            "case_key": self.case_key,
            "target_key": self.target_key,
            "role_id": self.role_id,
            "revision": self.revision,
            "query_text": self.query_text,
            "route_ids": list(self.route_ids),
            "entity_keys": list(self.entity_keys),
            "prior_reason": self.prior_reason,
            "query_digest": self.query_digest,
            "evidence_slot_id": self.evidence_slot_id,
            "required": self.required,
            "source_families": list(self.source_families),
            "currentness_window_days": self.currentness_window_days,
            "minimum_qualified_candidates": self.minimum_qualified_candidates,
            "stop_condition": self.stop_condition,
        }
        if self.subject_entity:
            body.update(
                {
                    "subject_entity": self.subject_entity,
                    "claim_direction": self.claim_direction,
                    "allowed_source_owner_roles": list(
                        self.allowed_source_owner_roles
                    ),
                    "forbidden_nested_relationships": list(
                        self.forbidden_nested_relationships
                    ),
                    "slot_budget_group": self.slot_budget_group,
                }
            )
        return body


@dataclass(frozen=True)
class DiscoveryCandidate:
    case_key: str
    target_key: str
    role_id: str
    entity_key: str
    title: str
    locator: str
    published_on: str
    authority: str
    discovery_capture_ref: str
    discovery_capture_digest: str
    source_capture_ref: str
    source_capture_digest: str
    parser_capture_ref: str
    parser_capture_digest: str
    promoted: bool = True
    evidence_slot_id: str = ""
    source_family: str = ""
    content_quality_score: int = 0
    promotion_decision: str = "accepted_candidate"
    subject_entity: str = ""
    evidence_owner_entity: str = ""
    ecosystem_role: str = ""
    claim_direction: str = ""
    publication_date_kind: str = ""
    publication_date_source: str = ""
    publication_date_confidence: str = ""
    publication_date_conflict_status: str = ""

    @property
    def candidate_digest(self) -> str:
        return canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        body = {
            "case_key": self.case_key,
            "target_key": self.target_key,
            "role_id": self.role_id,
            "entity_key": self.entity_key,
            "title": self.title,
            "locator": self.locator,
            "published_on": self.published_on,
            "authority": self.authority,
            "discovery_capture_ref": self.discovery_capture_ref,
            "discovery_capture_digest": self.discovery_capture_digest,
            "source_capture_ref": self.source_capture_ref,
            "source_capture_digest": self.source_capture_digest,
            "parser_capture_ref": self.parser_capture_ref,
            "parser_capture_digest": self.parser_capture_digest,
            "promoted": self.promoted,
            "evidence_slot_id": self.evidence_slot_id,
            "source_family": self.source_family,
            "content_quality_score": self.content_quality_score,
            "promotion_decision": self.promotion_decision,
        }
        if self.subject_entity:
            body.update(
                {
                    "subject_entity": self.subject_entity,
                    "evidence_owner_entity": self.evidence_owner_entity,
                    "ecosystem_role": self.ecosystem_role,
                    "claim_direction": self.claim_direction,
                    "publication_date_kind": self.publication_date_kind,
                    "publication_date_source": self.publication_date_source,
                    "publication_date_confidence": self.publication_date_confidence,
                    "publication_date_conflict_status": self.publication_date_conflict_status,
                }
            )
        return body


class DiscoveryAdapter(Protocol):
    def discover(self, query: DiscoveryQuery) -> Sequence[DiscoveryCandidate]: ...


def compile_evidence_slots(*, catalog: Mapping[str, Any]) -> tuple[EvidenceSlot, ...]:
    slots: list[EvidenceSlot] = []
    relationship_contract_enabled = (
        catalog.get("schema_version") == CATALOG_SCHEMA_V3
    )
    for role in catalog.get("evidence_role_blueprints") or []:
        role_id = str(role["role_id"])
        slots.append(
            EvidenceSlot(
                slot_id=str(role.get("slot_id") or role_id),
                role_id=role_id,
                required=bool(role.get("required", True)),
                source_families=tuple(
                    str(value)
                    for value in role.get("source_families")
                    or (
                        "regulatory_filing",
                        "issuer_ir_document",
                        "customer_official_disclosure",
                        "issuer_official_page",
                    )
                ),
                route_ids=tuple(str(value) for value in role["source_routes"]),
                entity_roles=tuple(str(value) for value in role["entity_roles"]),
                currentness_window_days=int(role.get("currentness_window_days", 550)),
                minimum_qualified_candidates=int(role.get("minimum_qualified_candidates", 1)),
                stop_condition=str(role.get("stop_condition") or "candidate_or_typed_gap"),
                subject_entity_mode=(
                    str(role.get("subject_entity_mode") or "case_subject")
                    if relationship_contract_enabled
                    else ""
                ),
                evidence_owner_entity_mode=(
                    str(role.get("evidence_owner_entity_mode") or "compiled_entity_key")
                    if relationship_contract_enabled
                    else ""
                ),
                claim_direction=(
                    str(role.get("claim_direction") or "subject_self_disclosure")
                    if relationship_contract_enabled
                    else ""
                ),
                allowed_source_owner_roles=(
                    tuple(
                        str(value)
                        for value in role.get("allowed_source_owner_roles")
                        or role.get("entity_roles")
                        or ()
                    )
                    if relationship_contract_enabled
                    else ()
                ),
                forbidden_nested_relationships=(
                    tuple(
                        str(value)
                        for value in role.get("forbidden_nested_relationships") or ()
                    )
                    if relationship_contract_enabled
                    else ()
                ),
                slot_budget_group=(
                    str(role.get("slot_budget_group") or "issuer_and_regulatory_shared")
                    if relationship_contract_enabled
                    else ""
                ),
            )
        )
    return tuple(slots)


def compile_initial_queries(
    *, catalog: Mapping[str, Any], case_key: str, research_objective: str
) -> tuple[DiscoveryQuery, ...]:
    if case_key not in CASES or not research_objective.strip():
        raise S108CandidateGenerationError("s1_08_query_case_or_objective_invalid")
    queries: list[DiscoveryQuery] = []
    role_by_id = {
        str(row["role_id"]): row for row in catalog.get("evidence_role_blueprints") or []
    }
    for slot in compile_evidence_slots(catalog=catalog):
        role_id = slot.role_id
        role = role_by_id[role_id]
        entity_keys = _entities_for_role(catalog, case_key, slot.entity_roles)
        query_text = " ".join(
            [case_key, research_objective, *[str(term) for term in role["query_terms"]]]
        )
        queries.append(
            _make_query(
                case_key=case_key,
                target_key=f"{case_key.lower()}_{role_id}",
                role_id=role_id,
                revision=0,
                query_text=query_text,
                route_ids=slot.route_ids,
                entity_keys=entity_keys,
                prior_reason="initial_role_plan",
                evidence_slot=slot,
            )
        )
    return tuple(queries)


def compile_revision(
    *, catalog: Mapping[str, Any], prior: DiscoveryQuery, reason: str
) -> DiscoveryQuery:
    maximum = int(catalog["budgets"]["maximum_revisions_per_target"])
    revision = prior.revision + 1
    if revision > maximum:
        raise S108CandidateGenerationError("s1_08_query_revision_budget_exceeded")
    if not reason or reason == "identical_retry":
        raise S108CandidateGenerationError("s1_08_query_revision_reason_invalid")
    suffixes = {
        1: "current quarter official release transcript filing latest available",
        2: "prepared remarks exhibit risk factors capacity customer supplier reconciliation",
    }
    route_ids = prior.route_ids
    blueprint = next(
        (
            row
            for row in catalog.get("evidence_role_blueprints") or []
            if str(row.get("role_id")) == prior.role_id
        ),
        {},
    )
    additions = blueprint.get("revision_route_additions") or {}
    route_ids = tuple(
        dict.fromkeys(
            [*route_ids, *[str(value) for value in additions.get(str(revision), [])]]
        )
    )
    if (
        catalog.get("schema_version")
        not in {CATALOG_SCHEMA, CATALOG_SCHEMA_V3}
        and revision == 1
        and "sec_submissions_discovery" not in route_ids
    ):
        # Historical v1 replay contract: revision one always widened to SEC.
        route_ids = (*route_ids, "sec_submissions_discovery")
    query = _make_query(
        case_key=prior.case_key,
        target_key=prior.target_key,
        role_id=prior.role_id,
        revision=revision,
        query_text=f"{prior.query_text} {suffixes[revision]}",
        route_ids=route_ids,
        entity_keys=prior.entity_keys,
        prior_reason=reason,
        evidence_slot=EvidenceSlot(
            slot_id=prior.evidence_slot_id,
            role_id=prior.role_id,
            required=prior.required,
            source_families=prior.source_families,
            route_ids=route_ids,
            entity_roles=(),
            currentness_window_days=prior.currentness_window_days,
            minimum_qualified_candidates=prior.minimum_qualified_candidates,
            stop_condition=prior.stop_condition,
            subject_entity_mode=("case_subject" if prior.subject_entity else ""),
            evidence_owner_entity_mode=(
                "compiled_entity_key" if prior.subject_entity else ""
            ),
            claim_direction=prior.claim_direction,
            allowed_source_owner_roles=prior.allowed_source_owner_roles,
            forbidden_nested_relationships=prior.forbidden_nested_relationships,
            slot_budget_group=prior.slot_budget_group,
        ),
    )
    if query.query_digest == prior.query_digest or query.query_text == prior.query_text:
        raise S108CandidateGenerationError("s1_08_identical_query_retry_forbidden")
    return query


def run_candidate_generation(
    *,
    catalog: Mapping[str, Any],
    case_key: str,
    research_objective: str,
    adapter: DiscoveryAdapter,
) -> dict[str, Any]:
    if catalog.get("schema_version") == CATALOG_SCHEMA_V3:
        return _run_candidate_generation_round_robin(
            catalog=catalog,
            case_key=case_key,
            research_objective=research_objective,
            adapter=adapter,
        )
    attempts: list[dict[str, Any]] = []
    accepted: dict[str, DiscoveryCandidate] = {}
    rejected: list[dict[str, Any]] = []
    as_of = date.fromisoformat(str(catalog["as_of"]))
    maximum_candidates = int(catalog["budgets"]["maximum_candidates_per_case"])
    for initial in compile_initial_queries(
        catalog=catalog, case_key=case_key, research_objective=research_objective
    ):
        query = initial
        while True:
            try:
                observed = list(adapter.discover(query))
            except Exception as exc:
                attempts.append(
                    {
                        "query": query.as_dict(),
                        "observed_count": 0,
                        "accepted_count": 0,
                        "stop_reason": "unexpected_adapter_failure",
                        "failure_code": getattr(
                            exc, "code", f"unexpected_project_failure:{type(exc).__name__}"
                        ),
                    }
                )
                partial = _build_candidate_result(
                    catalog=catalog,
                    case_key=case_key,
                    attempts=attempts,
                    accepted=accepted,
                    rejected=rejected,
                    adapter=adapter,
                    terminal_status="partial_failed",
                )
                _persist_adapter_checkpoint(adapter, partial)
                raise CandidateGenerationInterrupted(
                    code=attempts[-1]["failure_code"], partial_result=partial
                ) from exc
            accepted_this_attempt = 0
            for candidate in observed:
                reasons = _candidate_rejection_reasons(
                    candidate=candidate,
                    query=query,
                    catalog=catalog,
                    as_of=as_of,
                )
                digest = candidate.candidate_digest
                if digest in accepted:
                    reasons.append("duplicate_candidate")
                if reasons:
                    rejected.append(
                        {"candidate_digest": digest, "reason_codes": sorted(set(reasons))}
                    )
                elif len(accepted) >= maximum_candidates:
                    rejected.append(
                        {"candidate_digest": digest, "reason_codes": ["candidate_case_ceiling_reached"]}
                    )
                else:
                    accepted[digest] = candidate
                    accepted_this_attempt += 1
            attempts.append(
                {
                    "query": query.as_dict(),
                    "observed_count": len(observed),
                    "accepted_count": accepted_this_attempt,
                    "stop_reason": "role_candidate_found" if accepted_this_attempt else "missing_role_candidate",
                }
            )
            _persist_adapter_checkpoint(
                adapter,
                _build_candidate_result(
                    catalog=catalog,
                    case_key=case_key,
                    attempts=attempts,
                    accepted=accepted,
                    rejected=rejected,
                    adapter=adapter,
                    terminal_status="in_progress",
                ),
            )
            if accepted_this_attempt or query.revision == int(
                catalog["budgets"]["maximum_revisions_per_target"]
            ):
                break
            query = compile_revision(
                catalog=catalog,
                prior=query,
                reason="no_qualified_candidate_for_required_role",
            )
    return _build_candidate_result(
        catalog=catalog,
        case_key=case_key,
        attempts=attempts,
        accepted=accepted,
        rejected=rejected,
        adapter=adapter,
        terminal_status="complete",
    )


def _run_candidate_generation_round_robin(
    *,
    catalog: Mapping[str, Any],
    case_key: str,
    research_objective: str,
    adapter: DiscoveryAdapter,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    accepted: dict[str, DiscoveryCandidate] = {}
    rejected: list[dict[str, Any]] = []
    as_of = date.fromisoformat(str(catalog["as_of"]))
    maximum_candidates = int(catalog["budgets"]["maximum_candidates_per_case"])
    maximum_revisions = int(catalog["budgets"]["maximum_revisions_per_target"])
    maximum_document_fetches = int(
        catalog["budgets"]["maximum_document_fetches_per_attempt"]
    )
    maximum_unique_documents = int(
        catalog["budgets"]["maximum_accepted_unique_documents_per_attempt"]
    )
    initial_queries = list(
        compile_initial_queries(
            catalog=catalog,
            case_key=case_key,
            research_objective=research_objective,
        )
    )
    query_by_target = {row.target_key: row for row in initial_queries}
    completed: set[str] = set()
    reservation_config = dict(catalog["budgets"]["slot_group_reservations"])
    contingency = int(reservation_config.pop("shared_contingency_after_first_round"))
    remaining = {key: int(value) for key, value in reservation_config.items()}
    group_slot_count: dict[str, int] = {}
    for query in initial_queries:
        if query.slot_budget_group == "market_context":
            continue
        group_slot_count[query.slot_budget_group] = (
            group_slot_count.get(query.slot_budget_group, 0) + 1
        )

    for round_index in range(maximum_revisions + 1):
        for initial in initial_queries:
            target_key = initial.target_key
            if target_key in completed:
                continue
            query = query_by_target[target_key]
            if query.revision != round_index:
                continue
            group = query.slot_budget_group
            group_remaining = int(remaining.get(group, 0))
            if round_index == 0 and group != "market_context":
                divisor = max(1, group_slot_count.get(group, 1))
                allowance = min(
                    group_remaining,
                    max(1, int(reservation_config.get(group, 0)) // divisor),
                )
            elif group_remaining > 0:
                allowance = group_remaining
            elif group != "market_context" and contingency > 0:
                allowance = 1
            else:
                allowance = 0
            prepare = getattr(adapter, "prepare_attempt", None)
            if callable(prepare):
                prepare(
                    query=query,
                    network_call_allowance=allowance,
                    maximum_document_fetches=maximum_document_fetches,
                )
            before_network = int(getattr(adapter, "network_calls", 0))
            try:
                observed = list(adapter.discover(query))
            except Exception as exc:
                attempts.append(
                    {
                        "query": query.as_dict(),
                        "round_index": round_index,
                        "slot_budget_group": group,
                        "network_call_allowance": allowance,
                        "observed_count": 0,
                        "accepted_count": 0,
                        "stop_reason": "unexpected_adapter_failure",
                        "failure_code": getattr(
                            exc,
                            "code",
                            f"unexpected_project_failure:{type(exc).__name__}",
                        ),
                    }
                )
                partial = _build_candidate_result(
                    catalog=catalog,
                    case_key=case_key,
                    attempts=attempts,
                    accepted=accepted,
                    rejected=rejected,
                    adapter=adapter,
                    terminal_status="partial_failed",
                )
                _persist_adapter_checkpoint(adapter, partial)
                raise CandidateGenerationInterrupted(
                    code=attempts[-1]["failure_code"], partial_result=partial
                ) from exc
            observed.sort(
                key=lambda row: (
                    -int(row.content_quality_score),
                    normalize_locator(row.locator),
                    row.entity_key,
                    row.candidate_digest,
                )
            )
            after_network = int(getattr(adapter, "network_calls", 0))
            network_delta = after_network - before_network
            if network_delta < 0 or network_delta > allowance:
                raise S108CandidateGenerationError(
                    "s1_08_slot_attempt_network_allowance_violated"
                )
            consumed_reserved = min(group_remaining, network_delta)
            if group in remaining:
                remaining[group] -= consumed_reserved
            contingency_spent = network_delta - consumed_reserved
            if contingency_spent:
                if round_index == 0 or contingency_spent > contingency:
                    raise S108CandidateGenerationError(
                        "s1_08_contingency_used_before_first_round_closed"
                    )
                contingency -= contingency_spent

            accepted_this_attempt = 0
            accepted_unique_sources_this_attempt: set[tuple[str, str]] = set()
            for candidate in observed:
                reasons = _candidate_rejection_reasons(
                    candidate=candidate,
                    query=query,
                    catalog=catalog,
                    as_of=as_of,
                )
                digest = candidate.candidate_digest
                if digest in accepted:
                    reasons.append("duplicate_candidate")
                source_key = (
                    normalize_locator(candidate.locator),
                    candidate.source_capture_digest,
                )
                if (
                    source_key not in accepted_unique_sources_this_attempt
                    and len(accepted_unique_sources_this_attempt)
                    >= maximum_unique_documents
                ):
                    reasons.append("accepted_unique_document_attempt_ceiling_reached")
                if reasons:
                    rejected.append(
                        {
                            "candidate_digest": digest,
                            "reason_codes": sorted(set(reasons)),
                        }
                    )
                elif len(accepted) >= maximum_candidates:
                    rejected.append(
                        {
                            "candidate_digest": digest,
                            "reason_codes": ["candidate_case_ceiling_reached"],
                        }
                    )
                else:
                    accepted[digest] = candidate
                    accepted_unique_sources_this_attempt.add(source_key)
                    accepted_this_attempt += 1
            local_terminal = query.slot_budget_group == "market_context"
            exhausted = query.revision == maximum_revisions
            terminal_gap = not accepted_this_attempt and (local_terminal or exhausted)
            attempts.append(
                {
                    "query": query.as_dict(),
                    "round_index": round_index,
                    "slot_budget_group": group,
                    "network_call_allowance": allowance,
                    "network_calls_consumed": network_delta,
                    "document_fetch_ceiling": maximum_document_fetches,
                    "observed_count": len(observed),
                    "accepted_count": accepted_this_attempt,
                    "terminal_gap": terminal_gap,
                    "stop_reason": (
                        "role_candidate_found"
                        if accepted_this_attempt
                        else "typed_gap_no_revision"
                        if local_terminal
                        else "missing_role_candidate"
                    ),
                }
            )
            _persist_adapter_checkpoint(
                adapter,
                _build_candidate_result(
                    catalog=catalog,
                    case_key=case_key,
                    attempts=attempts,
                    accepted=accepted,
                    rejected=rejected,
                    adapter=adapter,
                    terminal_status="in_progress",
                ),
            )
            if accepted_this_attempt or terminal_gap:
                completed.add(target_key)
            else:
                query_by_target[target_key] = compile_revision(
                    catalog=catalog,
                    prior=query,
                    reason="no_qualified_candidate_for_required_role",
                )

    body = _build_candidate_result(
        catalog=catalog,
        case_key=case_key,
        attempts=attempts,
        accepted=accepted,
        rejected=rejected,
        adapter=adapter,
        terminal_status="complete",
    )
    body["slot_budget_summary"] = {
        "reserved_remaining": remaining,
        "contingency_remaining": contingency,
        "first_attempt_order": [
            str(row["query"]["evidence_slot_id"])
            for row in attempts
            if row.get("round_index") == 0
        ],
        "slot_starvation_count": sum(
            1
            for query in initial_queries
            if query.slot_budget_group != "market_context"
            and not any(
                str(row["query"]["target_key"]) == query.target_key
                and int(row.get("network_call_allowance", 0)) > 0
                for row in attempts
            )
        ),
    }
    without_digest = dict(body)
    without_digest.pop("result_digest", None)
    body["result_digest"] = canonical_digest(without_digest)
    return body


class CandidateGenerationInterrupted(RuntimeError):
    def __init__(self, *, code: str, partial_result: Mapping[str, Any]) -> None:
        self.code = code
        self.partial_result = dict(partial_result)
        super().__init__(code)


def _build_candidate_result(
    *,
    catalog: Mapping[str, Any],
    case_key: str,
    attempts: Sequence[Mapping[str, Any]],
    accepted: Mapping[str, DiscoveryCandidate],
    rejected: Sequence[Mapping[str, Any]],
    adapter: DiscoveryAdapter,
    terminal_status: str,
) -> dict[str, Any]:
    ordered = sorted(
        accepted.values(),
        key=lambda row: (row.role_id, row.entity_key, normalize_locator(row.locator), row.candidate_digest),
    )
    selected = ordered[: int(catalog["budgets"]["selected_pack_ceiling_per_case"])]
    final_attempt_by_target = {
        str(row["query"]["target_key"]): row for row in attempts
    }
    typed_gaps = [
        {
            "target_key": target_key,
            "evidence_slot_id": row["query"].get("evidence_slot_id"),
            "code": (
                "candidate_generation_interrupted"
                if row.get("failure_code")
                else "required_evidence_role_not_found_after_bounded_revision"
            ),
            "attempt_failure_code": row.get("failure_code"),
        }
        for target_key, row in final_attempt_by_target.items()
        if row.get("accepted_count", 0) == 0
        and (
            row.get("failure_code")
            or row.get("terminal_gap") is True
            or row["query"]["revision"]
            == int(catalog["budgets"]["maximum_revisions_per_target"])
        )
    ]
    network_calls = int(getattr(adapter, "network_calls", 0))
    unique_source_keys = {
        (normalize_locator(row.locator), row.source_capture_digest) for row in ordered
    }
    unique_network_source_keys = {
        (normalize_locator(row.locator), row.source_capture_digest)
        for row in ordered
        if row.locator.startswith("https://")
    }
    governed_local_source_keys = unique_source_keys - unique_network_source_keys
    qualified_documents = (
        len(unique_network_source_keys)
        if catalog.get("schema_version") == CATALOG_SCHEMA_V3
        else len(ordered)
    )
    yield_ratio = qualified_documents / network_calls if network_calls else 0.0
    role_ids = {str(row["role_id"]) for row in catalog.get("evidence_role_blueprints") or []}
    roles_with_candidate = {row.role_id for row in ordered}
    roles_with_gap = {
        str(row.get("evidence_slot_id") or "").replace("slot_", "") for row in typed_gaps
    }
    quality_metrics = {
        "evidence_roles_total": len(role_ids),
        "evidence_roles_with_candidate_or_typed_gap": len(
            roles_with_candidate | (role_ids & roles_with_gap)
        ),
        "qualified_document_yield": round(yield_ratio, 6),
        "known_navigation_noise_fetches": int(
            getattr(adapter, "known_navigation_noise_fetches", 0)
        ),
    }
    if catalog.get("schema_version") == CATALOG_SCHEMA_V3:
        quality_metrics.update(
            {
                "accepted_unique_source_documents": len(unique_network_source_keys),
                "governed_local_source_bindings": len(governed_local_source_keys),
                "role_bindings_with_candidate": len(ordered),
                "source_family_diversity": len(
                    {row.source_family for row in ordered if row.source_family}
                ),
                "document_fetches_per_accepted_unique_document": (
                    round(
                        int(getattr(adapter, "document_fetches", 0))
                        / len(unique_network_source_keys),
                        6,
                    )
                    if unique_network_source_keys
                    else 0.0
                ),
                "slot_starvation_count": sum(
                    1
                    for role_id in role_ids
                    if role_id != "market_expectation_context"
                    and not any(
                        str(row["query"].get("role_id")) == role_id
                        and int(row.get("network_call_allowance", 0)) > 0
                        for row in attempts
                    )
                ),
            }
        )
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_candidate_generation_result_v2_0"
            if catalog.get("schema_version") == CATALOG_SCHEMA_V3
            else "fin_ia_0_1_3_s1_08_candidate_generation_result_v1_0"
        ),
        "contract_ref": str(catalog.get("contract_ref") or CONTRACT_REF),
        "case_key": case_key,
        "as_of": catalog["as_of"],
        "terminal_status": terminal_status,
        "catalog_digest": canonical_digest(catalog),
        "attempts": list(attempts),
        "accepted_candidates": [row.as_dict() for row in ordered],
        "selected_candidates": [row.as_dict() for row in selected],
        "rejected_candidates": list(rejected),
        "typed_gaps": typed_gaps,
        "quality_metrics": quality_metrics,
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": network_calls,
            "query_attempts": len(attempts),
            "accepted_candidates": len(ordered),
            "selected_candidates": len(selected),
            "rejected_candidates": len(rejected),
        },
        "adapter_receipts": list(getattr(adapter, "receipts", ())),
        "checkpoint_refs": list(getattr(adapter, "checkpoint_refs", ())),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _persist_adapter_checkpoint(adapter: DiscoveryAdapter, snapshot: Mapping[str, Any]) -> None:
    persist = getattr(adapter, "persist_candidate_checkpoint", None)
    if callable(persist):
        persist(snapshot)


def evaluator_only_gold_match(
    *,
    results: Sequence[Mapping[str, Any]],
    visible_pack: Mapping[str, Any],
    hidden_scoring: Mapping[str, Any],
) -> dict[str, Any]:
    source_by_locator: dict[str, dict[str, Any]] = {}
    for source in visible_pack.get("source_registry") or []:
        locator = source.get("url") or source.get("artifact_ref")
        if locator:
            source_by_locator[normalize_locator(str(locator))] = dict(source)
        if source.get("authority") == "non_authoritative_market_context":
            source_by_locator["current_market_snapshot"] = dict(source)
    evidence_source_by_case = {
        str(case["case_key"]): {
            str(row["evidence_id"]): str(row["source_id"])
            for row in case.get("evidence_items") or []
        }
        for case in visible_pack.get("cases") or []
    }
    result_by_case = {str(row["case_key"]): row for row in results}
    cases: list[dict[str, Any]] = []
    for hidden_case in hidden_scoring.get("cases") or []:
        case_key = str(hidden_case["case_key"])
        result = result_by_case[case_key]
        matched_sources = _matched_gold_source_ids(
            result.get("accepted_candidates") or [], source_by_locator
        )
        selected_sources = _matched_gold_source_ids(
            result.get("selected_candidates") or [], source_by_locator
        )
        target_rows: list[dict[str, Any]] = []
        for target in hidden_case.get("required_insights") or []:
            evidence_ids = [str(value) for value in target.get("evidence_ids") or []]
            required_sources = {
                evidence_source_by_case[case_key][evidence_id]
                for evidence_id in evidence_ids
            }
            target_rows.append(
                {
                    "target_digest": canonical_digest(
                        {"case_key": case_key, "target_id": target["target_id"]}
                    ),
                    "required_evidence_count": len(evidence_ids),
                    "target_in_pool": required_sources.issubset(matched_sources),
                    "target_in_selected_pack": required_sources.issubset(selected_sources),
                }
            )
        cases.append(
            {
                "case_key": case_key,
                "matched_source_count": len(matched_sources),
                "target_groups": target_rows,
                "target_in_pool_recall": sum(row["target_in_pool"] for row in target_rows) / len(target_rows),
                "selected_pack_required_slot_coverage": sum(
                    row["target_in_selected_pack"] for row in target_rows
                ) / len(target_rows),
            }
        )
    all_targets = [target for case in cases for target in case["target_groups"]]
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_evaluator_only_candidate_match_v1_0",
        "contract_ref": CONTRACT_REF,
        "cases": cases,
        "summary": {
            "target_groups": len(all_targets),
            "target_in_pool_recall": sum(row["target_in_pool"] for row in all_targets) / len(all_targets),
            "selected_pack_required_slot_coverage": sum(
                row["target_in_selected_pack"] for row in all_targets
            ) / len(all_targets),
            "ranking_metrics_admitted": all(row["target_in_pool"] for row in all_targets),
        },
        "planner_received_hidden_gold": False,
    }
    return {**body, "evaluation_digest": canonical_digest(body)}


def _matched_gold_source_ids(
    candidates: Sequence[Mapping[str, Any]],
    source_by_locator: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    matched: set[str] = set()
    for candidate in candidates:
        locator = normalize_locator(str(candidate.get("locator") or ""))
        source = source_by_locator.get(locator)
        if source is None:
            continue
        if (
            str(candidate.get("published_on") or "")
            != str(source.get("published_on") or "")
            or str(candidate.get("authority") or "")
            != str(source.get("authority") or "")
        ):
            continue
        matched.add(str(source["source_id"]))
    return matched


def _entities_for_role(
    catalog: Mapping[str, Any], case_key: str, requested_roles: Sequence[str]
) -> tuple[str, ...]:
    selected: list[str] = []
    relationship_roles = set(str(value) for value in requested_roles) - {"subject"}
    for entity in catalog.get("entities") or []:
        key = str(entity["entity_key"])
        roles = set(str(value) for value in entity.get("ecosystem_roles") or [])
        if "subject" in requested_roles and key == case_key:
            selected.append(key)
        elif roles.intersection(relationship_roles) and key != case_key:
            selected.append(key)
    return tuple(sorted(set(selected)))


def _make_query(
    *,
    case_key: str,
    target_key: str,
    role_id: str,
    revision: int,
    query_text: str,
    route_ids: tuple[str, ...],
    entity_keys: tuple[str, ...],
    prior_reason: str,
    evidence_slot: EvidenceSlot,
) -> DiscoveryQuery:
    body = {
        "case_key": case_key,
        "target_key": target_key,
        "role_id": role_id,
        "revision": revision,
        "query_text": " ".join(query_text.split()),
        "route_ids": list(route_ids),
        "entity_keys": list(entity_keys),
        "prior_reason": prior_reason,
        "evidence_slot_id": evidence_slot.slot_id,
        "required": evidence_slot.required,
        "source_families": list(evidence_slot.source_families),
        "currentness_window_days": evidence_slot.currentness_window_days,
        "minimum_qualified_candidates": evidence_slot.minimum_qualified_candidates,
        "stop_condition": evidence_slot.stop_condition,
    }
    if evidence_slot.subject_entity_mode:
        body.update(
            {
                "subject_entity": case_key,
                "claim_direction": evidence_slot.claim_direction,
                "allowed_source_owner_roles": list(
                    evidence_slot.allowed_source_owner_roles
                ),
                "forbidden_nested_relationships": list(
                    evidence_slot.forbidden_nested_relationships
                ),
                "slot_budget_group": evidence_slot.slot_budget_group,
            }
        )
    return DiscoveryQuery(
        **{
            key: value
            for key, value in body.items()
            if key
            not in {
                "route_ids",
                "entity_keys",
                "source_families",
                "allowed_source_owner_roles",
                "forbidden_nested_relationships",
            }
        },
        route_ids=route_ids,
        entity_keys=entity_keys,
        source_families=evidence_slot.source_families,
        allowed_source_owner_roles=(
            evidence_slot.allowed_source_owner_roles
            if evidence_slot.subject_entity_mode
            else ()
        ),
        forbidden_nested_relationships=(
            evidence_slot.forbidden_nested_relationships
            if evidence_slot.subject_entity_mode
            else ()
        ),
        query_digest=canonical_digest(body),
    )


def _candidate_rejection_reasons(
    *,
    candidate: DiscoveryCandidate,
    query: DiscoveryQuery,
    catalog: Mapping[str, Any],
    as_of: date,
) -> list[str]:
    reasons: list[str] = []
    known_entities = {str(row["entity_key"]) for row in catalog.get("entities") or []}
    local_locator = not candidate.locator.startswith("https://")
    if candidate.case_key != query.case_key:
        reasons.append("cross_case_candidate")
    if candidate.target_key != query.target_key or candidate.role_id != query.role_id:
        reasons.append("query_binding_mismatch")
    if candidate.entity_key not in known_entities:
        reasons.append("unknown_entity")
    if local_locator and candidate.locator != "current_market_snapshot":
        reasons.append("https_or_governed_local_locator_required")
    try:
        if date.fromisoformat(candidate.published_on) > as_of:
            reasons.append("candidate_after_as_of")
    except ValueError:
        reasons.append("candidate_date_invalid")
    for ref, digest in (
        (candidate.discovery_capture_ref, candidate.discovery_capture_digest),
        (candidate.source_capture_ref, candidate.source_capture_digest),
        (candidate.parser_capture_ref, candidate.parser_capture_digest),
    ):
        if not ref or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            reasons.append("capture_first_lineage_invalid")
            break
    if not candidate.promoted:
        reasons.append("candidate_not_evidence_promoted")
    if catalog.get("schema_version") == CATALOG_SCHEMA_V3:
        if (
            candidate.evidence_slot_id != query.evidence_slot_id
            or candidate.subject_entity != query.subject_entity
            or candidate.evidence_owner_entity != candidate.entity_key
            or candidate.claim_direction != query.claim_direction
        ):
            reasons.append("relationship_binding_mismatch")
        if candidate.entity_key not in set(query.entity_keys):
            reasons.append("evidence_owner_not_compiled_for_slot")
        if (
            query.allowed_source_owner_roles
            and candidate.ecosystem_role not in set(query.allowed_source_owner_roles)
        ):
            reasons.append("evidence_owner_role_not_allowed_for_slot")
        if candidate.source_family not in set(query.source_families):
            reasons.append("source_family_not_allowed_for_evidence_slot")
        if (
            candidate.publication_date_kind
            not in {"published_date", "event_date", "filing_date", "as_of_date"}
            or not candidate.publication_date_source
            or candidate.publication_date_confidence not in {"high", "medium"}
            or candidate.publication_date_conflict_status != "none"
        ):
            reasons.append("typed_publication_date_binding_invalid")
    return reasons


__all__ = [
    "CATALOG_SCHEMA",
    "CATALOG_SCHEMA_V3",
    "CONTRACT_REF",
    "CONTRACT_REF_V3",
    "DiscoveryAdapter",
    "CandidateGenerationInterrupted",
    "DiscoveryCandidate",
    "DiscoveryQuery",
    "EvidenceSlot",
    "S108CandidateGenerationError",
    "canonical_digest",
    "compile_initial_queries",
    "compile_evidence_slots",
    "compile_revision",
    "evaluator_only_gold_match",
    "load_source_catalog",
    "normalize_locator",
    "run_candidate_generation",
]
