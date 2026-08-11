from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.s1_08_candidate_generation_runtime import canonical_digest
from sec_agent.s1_08_search_intent_compiler import (
    CONTRACT_REF as SEARCH_INTENT_CONTRACT_REF,
    EXTERNAL_SLOT_IDS,
    GOLD_TOKEN_PREFIXES,
    LANGUAGES,
    ROUTE_CLASSES,
    SearchIntent,
)


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0"
)
CONTRACT_REF = (
    "fin_0_1_3.S1_08.domestic_provider_wire_projection_and_fair_comparator:v1"
)
PROVIDER_IDS = (
    "tencent_wsa_searchpro_standard",
    "baidu_qianfan_web_search_v2",
    "alibaba_bailian_web_search_mcp",
    "firecrawl_keyless_search",
)


class S108ProviderWireProjectionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderWireRequest:
    provider_id: str
    capability_class: str
    endpoint: str
    intent_id: str
    intent_digest: str
    case_key: str
    evidence_slot_id: str
    evidence_owner_entity_key: str
    claim_direction: str
    source_families: tuple[str, ...]
    language: str
    route_class: str
    compact_query_text: str
    compact_query_units: int
    structured_filter_mode: str
    request_body: Mapping[str, Any]
    wire_schema_status: str
    admission_eligible_after_zero_call_proof: bool
    send_authorized: bool
    request_payload_digest: str
    wire_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "capability_class": self.capability_class,
            "endpoint": self.endpoint,
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "claim_direction": self.claim_direction,
            "source_families": list(self.source_families),
            "language": self.language,
            "route_class": self.route_class,
            "compact_query_text": self.compact_query_text,
            "compact_query_units": self.compact_query_units,
            "structured_filter_mode": self.structured_filter_mode,
            "request_body": json.loads(
                json.dumps(self.request_body, ensure_ascii=False, sort_keys=True)
            ),
            "wire_schema_status": self.wire_schema_status,
            "admission_eligible_after_zero_call_proof": (
                self.admission_eligible_after_zero_call_proof
            ),
            "send_authorized": self.send_authorized,
            "request_payload_digest": self.request_payload_digest,
            "wire_digest": self.wire_digest,
        }


@dataclass(frozen=True)
class ProviderExecutionUnit:
    provider_id: str
    route_class: str
    endpoint: str
    compact_query_text: str
    compact_query_units: int
    structured_filter_mode: str
    request_body: Mapping[str, Any]
    request_payload_digest: str
    consumer_intent_ids: tuple[str, ...]
    consumer_intent_digests: tuple[str, ...]
    send_authorized: bool
    execution_unit_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "route_class": self.route_class,
            "endpoint": self.endpoint,
            "compact_query_text": self.compact_query_text,
            "compact_query_units": self.compact_query_units,
            "structured_filter_mode": self.structured_filter_mode,
            "request_body": json.loads(
                json.dumps(self.request_body, ensure_ascii=False, sort_keys=True)
            ),
            "request_payload_digest": self.request_payload_digest,
            "consumer_intent_ids": list(self.consumer_intent_ids),
            "consumer_intent_digests": list(self.consumer_intent_digests),
            "send_authorized": self.send_authorized,
            "execution_unit_digest": self.execution_unit_digest,
        }


def load_wire_projection_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise S108ProviderWireProjectionError("s1_08_wire_policy_schema_invalid")
    if policy.get("contract_ref") != CONTRACT_REF:
        raise S108ProviderWireProjectionError("s1_08_wire_policy_contract_invalid")
    if (
        policy.get("canonical_search_intent_contract_ref")
        != SEARCH_INTENT_CONTRACT_REF
    ):
        raise S108ProviderWireProjectionError(
            "s1_08_wire_policy_search_intent_contract_invalid"
        )
    try:
        date.fromisoformat(str(policy["as_of_date"]))
        date.fromisoformat(str(policy["search_window_start_date"]))
    except (KeyError, ValueError) as exc:
        raise S108ProviderWireProjectionError(
            "s1_08_wire_policy_date_invalid"
        ) from exc
    if str(policy["search_window_start_date"]) > str(policy["as_of_date"]):
        raise S108ProviderWireProjectionError("s1_08_wire_policy_date_order_invalid")
    ceiling = policy.get("common_comparator_query_unit_ceiling")
    if not isinstance(ceiling, int) or ceiling <= 0:
        raise S108ProviderWireProjectionError(
            "s1_08_wire_policy_query_ceiling_invalid"
        )
    if set(policy.get("providers") or {}) != set(PROVIDER_IDS):
        raise S108ProviderWireProjectionError("s1_08_wire_policy_provider_set_invalid")
    entity_terms = policy.get("compact_entity_terms") or {}
    period_terms = policy.get("compact_period_terms") or {}
    if set(entity_terms) != set(period_terms) or not entity_terms:
        raise S108ProviderWireProjectionError(
            "s1_08_wire_policy_entity_period_profiles_invalid"
        )
    for entity_key in entity_terms:
        for language in LANGUAGES:
            if not str(entity_terms[entity_key].get(language) or "").strip():
                raise S108ProviderWireProjectionError(
                    "s1_08_wire_policy_entity_term_missing"
                )
            if not str(period_terms[entity_key].get(language) or "").strip():
                raise S108ProviderWireProjectionError(
                    "s1_08_wire_policy_period_term_missing"
                )
    source_terms = policy.get("slot_source_terms") or {}
    if set(source_terms) != set(EXTERNAL_SLOT_IDS):
        raise S108ProviderWireProjectionError("s1_08_wire_policy_slot_set_invalid")
    for slot_id in EXTERNAL_SLOT_IDS:
        for language in LANGUAGES:
            values = source_terms[slot_id].get(language)
            if not isinstance(values, list) or not values or any(
                not str(value).strip() for value in values
            ):
                raise S108ProviderWireProjectionError(
                    "s1_08_wire_policy_source_terms_invalid"
                )
    topic_terms = policy.get("entity_slot_topic_terms") or {}
    if not topic_terms or any(key not in entity_terms for key in topic_terms):
        raise S108ProviderWireProjectionError(
            "s1_08_wire_policy_entity_topic_profiles_invalid"
        )
    for entity_key, slot_profiles in topic_terms.items():
        if not isinstance(slot_profiles, dict) or not slot_profiles:
            raise S108ProviderWireProjectionError(
                "s1_08_wire_policy_entity_topic_profiles_invalid"
            )
        for slot_id, language_profiles in slot_profiles.items():
            if slot_id not in EXTERNAL_SLOT_IDS:
                raise S108ProviderWireProjectionError(
                    "s1_08_wire_policy_entity_topic_slot_invalid"
                )
            for language in LANGUAGES:
                values = language_profiles.get(language)
                if not isinstance(values, list) or not values or any(
                    not str(value).strip() for value in values
                ):
                    raise S108ProviderWireProjectionError(
                        "s1_08_wire_policy_entity_topic_terms_invalid"
                    )
    if set(policy.get("route_suffix_terms") or {}) != set(ROUTE_CLASSES):
        raise S108ProviderWireProjectionError("s1_08_wire_policy_route_set_invalid")
    budgets = policy.get("plan_budgets") or {}
    if (
        budgets.get("precise_official_domain_query_ceiling_per_provider") != 36
        or budgets.get("semantic_open_web_query_ceiling_per_provider") != 24
        or budgets.get("combined_intent_identity_ceiling") != 60
        or budgets.get("precise_execution_unit_ceiling_per_provider") != 22
        or budgets.get("semantic_execution_unit_ceiling_per_provider") != 24
        or budgets.get("combined_execution_unit_ceiling_per_provider") != 46
        or budgets.get("exact_payload_coalescing_allowed") is not True
        or budgets.get("automatic_combined_live_execution_allowed") is not False
        or budgets.get("identical_retry_allowed") is not False
        or budgets.get("provider_calls_during_projection_proof") != 0
        or budgets.get("model_calls_during_projection_proof") != 0
    ):
        raise S108ProviderWireProjectionError("s1_08_wire_policy_budget_invalid")
    serialized = json.dumps(policy, ensure_ascii=False).casefold()
    if any(token in serialized for token in ("authorization: bearer ", "secretkey=")):
        raise S108ProviderWireProjectionError("s1_08_wire_policy_credential_forbidden")
    return policy


def weighted_query_units(text: str) -> int:
    return sum(1 if ord(character) < 128 else 2 for character in text)


def compile_wire_requests(
    *,
    intents: Sequence[SearchIntent],
    policy: Mapping[str, Any],
    provider_ids: Sequence[str] = PROVIDER_IDS,
) -> tuple[ProviderWireRequest, ...]:
    if not intents:
        raise S108ProviderWireProjectionError("s1_08_wire_intents_empty")
    requested_providers = tuple(dict.fromkeys(str(value) for value in provider_ids))
    if not requested_providers or any(
        value not in PROVIDER_IDS for value in requested_providers
    ):
        raise S108ProviderWireProjectionError("s1_08_wire_provider_unknown")
    requests = tuple(
        compile_wire_request(intent=intent, provider_id=provider_id, policy=policy)
        for provider_id in requested_providers
        for intent in sorted(intents, key=_intent_sort_key)
    )
    identities = {(row.provider_id, row.intent_id) for row in requests}
    if len(identities) != len(requests):
        raise S108ProviderWireProjectionError("s1_08_wire_request_identity_duplicate")
    return requests


def compile_wire_request(
    *,
    intent: SearchIntent,
    provider_id: str,
    policy: Mapping[str, Any],
) -> ProviderWireRequest:
    if provider_id not in PROVIDER_IDS:
        raise S108ProviderWireProjectionError("s1_08_wire_provider_unknown")
    _validate_intent_digest(intent)
    if str(policy.get("as_of_date")) != intent.as_of_date:
        raise S108ProviderWireProjectionError("s1_08_wire_as_of_mismatch")
    if intent.evidence_owner_entity_key not in policy["compact_entity_terms"]:
        raise S108ProviderWireProjectionError("s1_08_wire_owner_profile_missing")
    if intent.subject_entity_key not in policy["compact_entity_terms"]:
        raise S108ProviderWireProjectionError("s1_08_wire_subject_profile_missing")

    query = _compact_query(intent=intent, policy=policy)
    units = weighted_query_units(query)
    common_ceiling = int(policy["common_comparator_query_unit_ceiling"])
    if units > common_ceiling:
        raise S108ProviderWireProjectionError("s1_08_wire_common_query_limit_exceeded")
    _validate_compact_query_atoms(intent=intent, query=query, policy=policy)

    profile = policy["providers"][provider_id]
    provider_limit = profile.get("published_query_unit_limit")
    if isinstance(provider_limit, int) and units > provider_limit:
        raise S108ProviderWireProjectionError("s1_08_wire_provider_query_limit_exceeded")
    request_body, filter_mode = _provider_request_body(
        intent=intent,
        compact_query=query,
        provider_id=provider_id,
        profile=profile,
        policy=policy,
    )
    request_payload_digest = canonical_digest(
        {
            "provider_id": provider_id,
            "endpoint": str(profile["endpoint"]),
            "route_class": intent.route_class,
            "request_body": request_body,
            "wire_schema_status": str(profile["wire_schema_status"]),
        }
    )
    digest_body = {
        "contract_ref": CONTRACT_REF,
        "provider_id": provider_id,
        "intent_id": intent.intent_id,
        "intent_digest": intent.intent_digest,
        "evidence_owner_entity_key": intent.evidence_owner_entity_key,
        "claim_direction": intent.claim_direction,
        "source_families": list(intent.source_families),
        "endpoint": str(profile["endpoint"]),
        "compact_query_text": query,
        "compact_query_units": units,
        "structured_filter_mode": filter_mode,
        "request_body": request_body,
        "wire_schema_status": str(profile["wire_schema_status"]),
        "admission_eligible_after_zero_call_proof": bool(
            profile["admission_eligible_after_zero_call_proof"]
        ),
        "send_authorized": False,
        "request_payload_digest": request_payload_digest,
    }
    return ProviderWireRequest(
        provider_id=provider_id,
        capability_class=str(profile["capability_class"]),
        endpoint=str(profile["endpoint"]),
        intent_id=intent.intent_id,
        intent_digest=intent.intent_digest,
        case_key=intent.case_key,
        evidence_slot_id=intent.evidence_slot_id,
        evidence_owner_entity_key=intent.evidence_owner_entity_key,
        claim_direction=intent.claim_direction,
        source_families=intent.source_families,
        language=intent.language,
        route_class=intent.route_class,
        compact_query_text=query,
        compact_query_units=units,
        structured_filter_mode=filter_mode,
        request_body=request_body,
        wire_schema_status=str(profile["wire_schema_status"]),
        admission_eligible_after_zero_call_proof=bool(
            profile["admission_eligible_after_zero_call_proof"]
        ),
        send_authorized=False,
        request_payload_digest=request_payload_digest,
        wire_digest=canonical_digest(digest_body),
    )


def validate_wire_request(
    *,
    request: ProviderWireRequest,
    intent: SearchIntent,
    policy: Mapping[str, Any],
) -> None:
    expected = compile_wire_request(
        intent=intent, provider_id=request.provider_id, policy=policy
    )
    if request.as_dict() != expected.as_dict():
        raise S108ProviderWireProjectionError("s1_08_wire_request_drift")


def compile_fair_comparator_plans(
    *, requests: Sequence[ProviderWireRequest], policy: Mapping[str, Any]
) -> dict[str, Any]:
    execution_units = compile_execution_units(requests=requests)
    providers: dict[str, Any] = {}
    semantic_queries_by_intent: dict[str, set[str]] = {}
    for provider_id in PROVIDER_IDS:
        rows = [row for row in requests if row.provider_id == provider_id]
        precise = [
            row for row in rows if row.route_class == "precise_official_domain"
        ]
        semantic = [row for row in rows if row.route_class == "semantic_open_web"]
        provider_units = [
            row for row in execution_units if row.provider_id == provider_id
        ]
        precise_units = [
            row
            for row in provider_units
            if row.route_class == "precise_official_domain"
        ]
        semantic_units = [
            row for row in provider_units if row.route_class == "semantic_open_web"
        ]
        if len(precise) != 36 or len(semantic) != 24:
            raise S108ProviderWireProjectionError("s1_08_wire_plan_count_invalid")
        if len(precise_units) != 22 or len(semantic_units) != 24:
            raise S108ProviderWireProjectionError(
                "s1_08_wire_execution_unit_count_invalid"
            )
        for row in semantic:
            semantic_queries_by_intent.setdefault(row.intent_id, set()).add(
                row.compact_query_text
            )
        providers[provider_id] = {
            "precise_official_domain": {
                "intent_identity_count": len(precise),
                "execution_unit_count": len(precise_units),
                "wire_digests": [row.wire_digest for row in precise],
                "execution_unit_digests": [
                    row.execution_unit_digest for row in precise_units
                ],
                "live_authorized": False,
            },
            "semantic_open_web": {
                "intent_identity_count": len(semantic),
                "execution_unit_count": len(semantic_units),
                "wire_digests": [row.wire_digest for row in semantic],
                "execution_unit_digests": [
                    row.execution_unit_digest for row in semantic_units
                ],
                "live_authorized": False,
            },
            "combined_execution_unit_count": len(provider_units),
            "combined_automatic_execution_allowed": False,
        }
    if len(semantic_queries_by_intent) != 24 or any(
        len(values) != 1 for values in semantic_queries_by_intent.values()
    ):
        raise S108ProviderWireProjectionError("s1_08_wire_semantic_query_parity_failed")
    return {
        "contract_ref": CONTRACT_REF,
        "providers": providers,
        "semantic_query_parity": {
            "intent_count": 24,
            "provider_count": len(PROVIDER_IDS),
            "all_queries_identical_per_intent": True,
            "digest": canonical_digest(
                {
                    key: next(iter(values))
                    for key, values in sorted(semantic_queries_by_intent.items())
                }
            ),
        },
        "provider_calls": 0,
        "network_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
        "automatic_combined_live_execution_allowed": False,
        "plan_digest": canonical_digest(
            {
                "providers": providers,
                "budgets": policy["plan_budgets"],
                "semantic_query_parity": {
                    key: next(iter(values))
                    for key, values in sorted(semantic_queries_by_intent.items())
                },
            }
        ),
    }


def compile_execution_units(
    *, requests: Sequence[ProviderWireRequest]
) -> tuple[ProviderExecutionUnit, ...]:
    if not requests:
        raise S108ProviderWireProjectionError("s1_08_wire_requests_empty")
    groups: dict[tuple[str, str, str], list[ProviderWireRequest]] = {}
    for request in requests:
        groups.setdefault(
            (
                request.provider_id,
                request.route_class,
                request.request_payload_digest,
            ),
            [],
        ).append(request)
    units: list[ProviderExecutionUnit] = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda row: row.intent_id)
        first = rows[0]
        invariant = {
            (
                row.endpoint,
                row.compact_query_text,
                row.compact_query_units,
                row.structured_filter_mode,
                canonical_digest(row.request_body),
                row.request_payload_digest,
            )
            for row in rows
        }
        if len(invariant) != 1:
            raise S108ProviderWireProjectionError(
                "s1_08_wire_payload_digest_collision"
            )
        intent_ids = tuple(row.intent_id for row in rows)
        intent_digests = tuple(row.intent_digest for row in rows)
        unit_body = {
            "contract_ref": CONTRACT_REF,
            "provider_id": first.provider_id,
            "route_class": first.route_class,
            "endpoint": first.endpoint,
            "request_payload_digest": first.request_payload_digest,
            "consumer_intent_ids": list(intent_ids),
            "consumer_intent_digests": list(intent_digests),
            "send_authorized": False,
        }
        units.append(
            ProviderExecutionUnit(
                provider_id=first.provider_id,
                route_class=first.route_class,
                endpoint=first.endpoint,
                compact_query_text=first.compact_query_text,
                compact_query_units=first.compact_query_units,
                structured_filter_mode=first.structured_filter_mode,
                request_body=first.request_body,
                request_payload_digest=first.request_payload_digest,
                consumer_intent_ids=intent_ids,
                consumer_intent_digests=intent_digests,
                send_authorized=False,
                execution_unit_digest=canonical_digest(unit_body),
            )
        )
    return tuple(units)


def _compact_query(*, intent: SearchIntent, policy: Mapping[str, Any]) -> str:
    language = intent.language
    try:
        topic_terms = policy["entity_slot_topic_terms"][
            intent.evidence_owner_entity_key
        ][intent.evidence_slot_id][language]
    except KeyError as exc:
        raise S108ProviderWireProjectionError(
            "s1_08_wire_entity_slot_topic_missing"
        ) from exc
    parts = [
        str(
            policy["compact_entity_terms"][intent.evidence_owner_entity_key][
                language
            ]
        ),
        str(
            policy["compact_period_terms"][intent.evidence_owner_entity_key][
                language
            ]
        ),
        *[str(value) for value in topic_terms],
        *[
            str(value)
            for value in policy["slot_source_terms"][intent.evidence_slot_id][
                language
            ]
        ],
    ]
    if (
        intent.route_class == "semantic_open_web"
        and intent.evidence_owner_entity_key != intent.subject_entity_key
    ):
        parts.append(
            str(
                policy["compact_entity_terms"][intent.subject_entity_key][language]
            )
        )
    parts.extend(
        str(value)
        for value in policy["route_suffix_terms"][intent.route_class][language]
    )
    return " ".join(dict.fromkeys(value.strip() for value in parts if value.strip()))


def _validate_compact_query_atoms(
    *, intent: SearchIntent, query: str, policy: Mapping[str, Any]
) -> None:
    required = [
        str(
            policy["compact_entity_terms"][intent.evidence_owner_entity_key][
                intent.language
            ]
        ),
        str(
            policy["compact_period_terms"][intent.evidence_owner_entity_key][
                intent.language
            ]
        ),
        *[
            str(value)
            for value in policy["entity_slot_topic_terms"][
                intent.evidence_owner_entity_key
            ][intent.evidence_slot_id][intent.language]
        ],
        *[
            str(value)
            for value in policy["slot_source_terms"][intent.evidence_slot_id][
                intent.language
            ]
        ],
        *[
            str(value)
            for value in policy["route_suffix_terms"][intent.route_class][
                intent.language
            ]
        ],
    ]
    if (
        intent.route_class == "semantic_open_web"
        and intent.evidence_owner_entity_key != intent.subject_entity_key
    ):
        required.append(
            str(
                policy["compact_entity_terms"][intent.subject_entity_key][
                    intent.language
                ]
            )
        )
    normalized = query.casefold()
    if any(value.casefold() not in normalized for value in required):
        raise S108ProviderWireProjectionError("s1_08_wire_required_atom_missing")
    if "http://" in normalized or "https://" in normalized or "www." in normalized:
        raise S108ProviderWireProjectionError("s1_08_wire_locator_leakage")
    if any(prefix.casefold() in normalized for prefix in GOLD_TOKEN_PREFIXES):
        raise S108ProviderWireProjectionError("s1_08_wire_gold_token_leakage")


def _provider_request_body(
    *,
    intent: SearchIntent,
    compact_query: str,
    provider_id: str,
    profile: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    precise = intent.route_class == "precise_official_domain"
    start = str(policy["search_window_start_date"])
    end = intent.as_of_date
    if provider_id == "tencent_wsa_searchpro_standard":
        body: dict[str, Any] = {"Query": compact_query}
        if precise:
            body["Site"] = _single_priority_domain(intent=intent, policy=policy)
            body["FromTime"] = _unix_seconds(start, end_of_day=False)
            body["ToTime"] = _unix_seconds(end, end_of_day=True)
            return body, "single_site_and_utc_time_range"
        return body, "none"
    if provider_id == "baidu_qianfan_web_search_v2":
        body = {
            "messages": [{"role": "user", "content": compact_query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": 10}],
        }
        if precise:
            body["search_filter"] = {
                "match": {"site": list(intent.preferred_domains)},
                "range": {"page_time": {"gte": start, "lte": end}},
            }
            return body, "all_preferred_sites_and_iso_time_range"
        return body, "none"
    if provider_id == "alibaba_bailian_web_search_mcp":
        return {"query": compact_query, "count": 10}, "schema_capture_required"
    if provider_id == "firecrawl_keyless_search":
        body = {"query": compact_query, "limit": 10, "sources": ["web"]}
        if precise:
            body["includeDomains"] = list(intent.preferred_domains)
            return body, "all_preferred_sites"
        return body, "none"
    raise S108ProviderWireProjectionError("s1_08_wire_provider_unknown")


def _single_priority_domain(
    *, intent: SearchIntent, policy: Mapping[str, Any]
) -> str:
    domains = tuple(intent.preferred_domains)
    if not domains:
        raise S108ProviderWireProjectionError("s1_08_wire_official_domain_missing")
    priority = policy["official_site_priority"][intent.evidence_slot_id]
    if priority == "regulatory":
        selected = next((value for value in domains if value == "data.sec.gov"), "")
    else:
        selected = next((value for value in domains if value != "data.sec.gov"), "")
    if not selected:
        raise S108ProviderWireProjectionError(
            "s1_08_wire_priority_official_domain_missing"
        )
    return selected


def _unix_seconds(value: str, *, end_of_day: bool) -> int:
    parsed = date.fromisoformat(value)
    wall_time = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return int(datetime.combine(parsed, wall_time, tzinfo=timezone.utc).timestamp())


def _validate_intent_digest(intent: SearchIntent) -> None:
    body = intent.as_dict()
    supplied = str(body.pop("intent_digest"))
    if canonical_digest(body) != supplied:
        raise S108ProviderWireProjectionError("s1_08_wire_intent_digest_invalid")


def _intent_sort_key(intent: SearchIntent) -> tuple[Any, ...]:
    return (
        intent.case_key,
        EXTERNAL_SLOT_IDS.index(intent.evidence_slot_id),
        intent.evidence_owner_entity_key,
        LANGUAGES.index(intent.language),
        ROUTE_CLASSES.index(intent.route_class),
    )
