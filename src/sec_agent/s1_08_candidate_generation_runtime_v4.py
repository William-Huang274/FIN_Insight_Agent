from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.s1_08_candidate_generation_runtime import (
    CATALOG_SCHEMA_V3,
    CONTRACT_REF_V3,
    CandidateGenerationInterrupted,
    DiscoveryAdapter,
    DiscoveryCandidate,
    DiscoveryQuery,
    EvidenceSlot,
    S108CandidateGenerationError,
    _persist_adapter_checkpoint,
    canonical_digest,
    compile_evidence_slots as _compile_evidence_slots_v3,
    compile_initial_queries as _compile_initial_queries_v3,
    compile_revision as _compile_revision_v3,
    run_candidate_generation as _run_candidate_generation_v3,
)


CATALOG_SCHEMA_V4 = (
    "fin_ia_0_1_3_s1_08_current_source_catalog_protected_fetch_cache_policy_v4_0"
)
CONTRACT_REF_V4 = (
    "fin_0_1_3.S1_08.current_source_catalog_relationship_budget_candidate_generation:v4"
)
RESULT_SCHEMA_V4 = "fin_ia_0_1_3_s1_08_candidate_generation_result_v3_0"
CACHE_LINEAGE_SCHEMA = "fin_ia_0_1_3_s1_08_typed_fetch_cache_lineage_v1_0"
CASES = ("DELL", "MU", "NVDA")
GOLD_TOKEN_PREFIXES = (
    "SRC_",
    "DELL_E",
    "MU_E",
    "NVDA_E",
    "DELL_T",
    "MU_T",
    "NVDA_T",
)
_EXPECTED_RESERVATIONS = {
    "issuer_and_regulatory_shared": 4,
    "customer_demand": 4,
    "supply_and_counterevidence": 5,
    "market_context": 0,
    "shared_contingency_after_first_round": 3,
}
_EXPECTED_PROTECTED_FETCH = {
    "minimum_opportunities_per_eligible_attempt": 1,
    "discovery_must_leave_protected_capacity": True,
    "all_real_requests_share_global_ceiling": True,
    "pre_request_local_stop_cross_attempt_cacheable": False,
    "cache_lineage_schema": CACHE_LINEAGE_SCHEMA,
}
_ALLOWED_SOURCE_AUTHORITIES = {
    "regulatory_primary",
    "issuer_primary",
    "industry_primary",
    "non_authoritative_market_context",
}


def load_source_catalog_v4(path: str | Path) -> dict[str, Any]:
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        catalog.get("schema_version") != CATALOG_SCHEMA_V4
        or catalog.get("contract_ref") != CONTRACT_REF_V4
        or catalog.get("as_of") != "2026-08-06"
    ):
        raise S108CandidateGenerationError("s1_08_v4_source_catalog_identity_invalid")
    serialized = json.dumps(catalog, ensure_ascii=False)
    if any(token in serialized for token in GOLD_TOKEN_PREFIXES):
        raise S108CandidateGenerationError("s1_08_gold_identifier_leaked_into_catalog")
    budgets = catalog.get("budgets") or {}
    if (
        budgets.get("maximum_revisions_per_target") != 2
        or budgets.get("maximum_candidates_per_case") != 24
        or budgets.get("selected_pack_ceiling_per_case") != 8
        or budgets.get("replacement_network_call_ceiling") != 16
        or budgets.get("document_ceiling_per_query") != 1
        or budgets.get("maximum_document_fetches_per_attempt") != 2
        or budgets.get("maximum_accepted_unique_documents_per_attempt") != 1
        or budgets.get("round_robin_first_attempt_required") is not True
        or budgets.get("slot_group_reservations") != _EXPECTED_RESERVATIONS
        or sum((budgets.get("slot_group_reservations") or {}).values()) != 16
        or budgets.get("protected_document_fetch") != _EXPECTED_PROTECTED_FETCH
        or budgets.get("model_calls") != 0
        or budgets.get("identical_retry_forbidden") is not True
    ):
        raise S108CandidateGenerationError(
            "s1_08_v4_protected_fetch_cache_policy_invalid"
        )
    entities = catalog.get("entities") or []
    entity_keys = [str(row.get("entity_key") or "") for row in entities]
    if len(entity_keys) != len(set(entity_keys)) or not set(CASES).issubset(
        entity_keys
    ):
        raise S108CandidateGenerationError("s1_08_source_catalog_entity_set_invalid")
    if any(
        not row.get("official_landing_pages")
        or any(
            not str(url).startswith("https://")
            for url in row.get("official_landing_pages") or ()
        )
        for row in entities
    ):
        raise S108CandidateGenerationError("s1_08_source_catalog_landing_page_invalid")
    capabilities = catalog.get("source_provider_capabilities") or []
    route_ids = [str(row.get("route_id") or "") for row in capabilities]
    required_capability_fields = {
        "declared",
        "configured",
        "operational",
        "replay_proven",
        "live_proven",
    }
    if (
        not route_ids
        or len(route_ids) != len(set(route_ids))
        or any(not required_capability_fields.issubset(row) for row in capabilities)
    ):
        raise S108CandidateGenerationError(
            "s1_08_v4_provider_capability_state_invalid"
        )
    return catalog


def _v3_catalog_view(catalog: Mapping[str, Any]) -> dict[str, Any]:
    view = deepcopy(dict(catalog))
    view["schema_version"] = CATALOG_SCHEMA_V3
    view["contract_ref"] = CONTRACT_REF_V3
    view["budgets"].pop("protected_document_fetch", None)
    return view


def compile_evidence_slots_v4(
    *, catalog: Mapping[str, Any]
) -> tuple[EvidenceSlot, ...]:
    _require_v4_catalog(catalog)
    return _compile_evidence_slots_v3(catalog=_v3_catalog_view(catalog))


def compile_initial_queries_v4(
    *, catalog: Mapping[str, Any], case_key: str, research_objective: str
) -> tuple[DiscoveryQuery, ...]:
    _require_v4_catalog(catalog)
    return _compile_initial_queries_v3(
        catalog=_v3_catalog_view(catalog),
        case_key=case_key,
        research_objective=research_objective,
    )


def compile_revision_v4(
    *, catalog: Mapping[str, Any], prior: DiscoveryQuery, reason: str
) -> DiscoveryQuery:
    _require_v4_catalog(catalog)
    return _compile_revision_v3(
        catalog=_v3_catalog_view(catalog), prior=prior, reason=reason
    )


class _ProtectedFetchAdapterProxy:
    def __init__(self, adapter: DiscoveryAdapter, catalog: Mapping[str, Any]) -> None:
        self._adapter = adapter
        self._catalog = dict(catalog)
        self._protected_by_query: dict[str, int] = {}
        self._budget_state_by_query: dict[str, dict[str, Any]] = {}
        self._invalid_authority_digests: set[str] = set()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)

    def prepare_attempt(
        self,
        *,
        query: DiscoveryQuery,
        network_call_allowance: int,
        maximum_document_fetches: int,
    ) -> None:
        protected = (
            min(1, max(0, int(network_call_allowance)))
            if query.slot_budget_group != "market_context"
            else 0
        )
        prepare = getattr(self._adapter, "prepare_attempt", None)
        if not callable(prepare):
            raise S108CandidateGenerationError(
                "s1_08_v4_adapter_protected_fetch_contract_missing"
            )
        try:
            prepare(
                query=query,
                network_call_allowance=network_call_allowance,
                maximum_document_fetches=maximum_document_fetches,
                protected_document_fetches=protected,
            )
        except TypeError as exc:
            raise S108CandidateGenerationError(
                "s1_08_v4_adapter_protected_fetch_contract_missing"
            ) from exc
        self._protected_by_query[query.query_digest] = protected

    def discover(self, query: DiscoveryQuery) -> Sequence[DiscoveryCandidate]:
        rows = list(self._adapter.discover(query))
        state = getattr(self._adapter, "current_attempt_budget_state", None)
        if callable(state):
            self._budget_state_by_query[query.query_digest] = dict(state())
        out: list[DiscoveryCandidate] = []
        for row in rows:
            invalid = row.authority not in _ALLOWED_SOURCE_AUTHORITIES or (
                row.authority == "non_authoritative_market_context"
                and row.locator != "current_market_snapshot"
            )
            if invalid:
                row = replace(
                    row,
                    promoted=False,
                    promotion_decision="rejected_source_authority_binding_invalid",
                )
                self._invalid_authority_digests.add(row.candidate_digest)
            out.append(row)
        return tuple(out)

    def persist_candidate_checkpoint(self, snapshot: Mapping[str, Any]) -> None:
        transformed = _transform_v3_result(
            result=snapshot,
            catalog=self._catalog,
            proxy=self,
            adapter=self._adapter,
        )
        _persist_adapter_checkpoint(self._adapter, transformed)

    def protected_for_query(self, query_digest: str) -> int:
        return int(self._protected_by_query.get(query_digest, 0))

    def budget_state_for_query(self, query_digest: str) -> dict[str, Any] | None:
        state = self._budget_state_by_query.get(query_digest)
        return dict(state) if state is not None else None

    @property
    def invalid_authority_digests(self) -> set[str]:
        return set(self._invalid_authority_digests)


def run_candidate_generation_v4(
    *,
    catalog: Mapping[str, Any],
    case_key: str,
    research_objective: str,
    adapter: DiscoveryAdapter,
) -> dict[str, Any]:
    _require_v4_catalog(catalog)
    proxy = _ProtectedFetchAdapterProxy(adapter, catalog)
    try:
        result = _run_candidate_generation_v3(
            catalog=_v3_catalog_view(catalog),
            case_key=case_key,
            research_objective=research_objective,
            adapter=proxy,
        )
    except CandidateGenerationInterrupted as exc:
        transformed = _transform_v3_result(
            result=exc.partial_result,
            catalog=catalog,
            proxy=proxy,
            adapter=adapter,
        )
        raise CandidateGenerationInterrupted(
            code=exc.code, partial_result=transformed
        ) from exc
    return _transform_v3_result(
        result=result,
        catalog=catalog,
        proxy=proxy,
        adapter=adapter,
    )


def _transform_v3_result(
    *,
    result: Mapping[str, Any],
    catalog: Mapping[str, Any],
    proxy: _ProtectedFetchAdapterProxy,
    adapter: DiscoveryAdapter,
) -> dict[str, Any]:
    body = deepcopy(dict(result))
    body["schema_version"] = RESULT_SCHEMA_V4
    body["contract_ref"] = CONTRACT_REF_V4
    body["catalog_digest"] = canonical_digest(catalog)
    for attempt in body.get("attempts") or []:
        query_digest = str((attempt.get("query") or {}).get("query_digest") or "")
        attempt["protected_document_fetch_allowance"] = proxy.protected_for_query(
            query_digest
        )
        state = proxy.budget_state_for_query(query_digest)
        if state is not None:
            attempt["attempt_budget_state"] = state
    invalid_digests = proxy.invalid_authority_digests
    for rejected in body.get("rejected_candidates") or []:
        if str(rejected.get("candidate_digest") or "") in invalid_digests:
            rejected["reason_codes"] = sorted(
                set(
                    [
                        *(rejected.get("reason_codes") or []),
                        "source_authority_binding_invalid",
                    ]
                )
            )
    metrics = body.setdefault("quality_metrics", {})
    metrics.update(
        {
            "qualified_locator_fetch_opportunities": int(
                getattr(adapter, "qualified_locator_fetch_opportunities", 0)
            ),
            "document_requests_started": int(
                getattr(adapter, "document_fetches", 0)
            ),
            "pre_request_local_stop_cross_attempt_cache_entries": int(
                getattr(
                    adapter,
                    "pre_request_local_stop_cross_attempt_cache_entries",
                    0,
                )
            ),
            "typed_fetch_cache_lineage_events": len(
                getattr(adapter, "cache_lineage", ())
            ),
        }
    )
    body["adapter_cache_lineage"] = list(getattr(adapter, "cache_lineage", ()))
    body.pop("result_digest", None)
    body["result_digest"] = canonical_digest(body)
    return body


def _require_v4_catalog(catalog: Mapping[str, Any]) -> None:
    if (
        catalog.get("schema_version") != CATALOG_SCHEMA_V4
        or catalog.get("contract_ref") != CONTRACT_REF_V4
    ):
        raise S108CandidateGenerationError("s1_08_v4_source_catalog_identity_invalid")


__all__ = [
    "CACHE_LINEAGE_SCHEMA",
    "CATALOG_SCHEMA_V4",
    "CONTRACT_REF_V4",
    "RESULT_SCHEMA_V4",
    "compile_evidence_slots_v4",
    "compile_initial_queries_v4",
    "compile_revision_v4",
    "load_source_catalog_v4",
    "run_candidate_generation_v4",
]
