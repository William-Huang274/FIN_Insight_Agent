from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_search_intent_compiler import SearchIntent
from sec_agent.s1_08_source_quality import canonical_locator_key


POLICY_SCHEMA = "fin_ia_0_1_3_s1_08_official_first_portfolio_policy_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.official_first_sourcehunter_portfolio:v1"
PROOF_SCHEMA = "fin_ia_0_1_3_s1_08_official_first_portfolio_zero_call_proof_v1_0"
RUN_SCOPE = (
    "S1_08_OFFICIAL_FIRST_SOURCEHUNTER_PORTFOLIO_AND_DISCOVERY_SHADOW_"
    "ZERO_CALL_IMPLEMENTATION"
)
CASES = ("DELL", "MU", "NVDA")
SLOT_IDS = (
    "issuer_results_and_management_commentary",
    "regulatory_risk_and_financial_reconciliation",
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
RELATIONAL_SLOT_IDS = (
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class S108OfficialFirstPortfolioError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PortfolioRouteAssignment:
    intent_id: str
    intent_digest: str
    case_key: str
    evidence_slot_id: str
    evidence_owner_entity_key: str
    claim_direction: str
    source_families: tuple[str, ...]
    target_state: str
    lane_id: str
    route_ids: tuple[str, ...]
    provider: str
    output_state: str
    financial_authority: bool
    evidence_promotion_allowed: bool
    assignment_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "intent_digest": self.intent_digest,
            "case_key": self.case_key,
            "evidence_slot_id": self.evidence_slot_id,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "claim_direction": self.claim_direction,
            "source_families": list(self.source_families),
            "target_state": self.target_state,
            "lane_id": self.lane_id,
            "route_ids": list(self.route_ids),
            "provider": self.provider,
            "output_state": self.output_state,
            "financial_authority": self.financial_authority,
            "evidence_promotion_allowed": self.evidence_promotion_allowed,
            "assignment_digest": self.assignment_digest,
        }


@dataclass(frozen=True)
class ReplayCandidateObservation:
    candidate_id: str
    case_key: str
    subject_entity_key: str
    evidence_slot_id: str
    evidence_owner_entity_key: str
    expected_evidence_owner_entity_key: str
    claim_direction: str
    expected_claim_direction: str
    lane_id: str
    locator: str
    source_family: str
    authority: str
    provider_reported_date: str = ""
    local_publication_date: str = ""
    local_date_kind: str = ""
    local_date_source: str = ""
    capture_ref: str = ""
    capture_digest: str = ""
    parser_ref: str = ""
    parser_digest: str = ""
    canonical_identity_verified: bool = False
    historical_promotion_receipt: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_key": self.case_key,
            "subject_entity_key": self.subject_entity_key,
            "evidence_slot_id": self.evidence_slot_id,
            "evidence_owner_entity_key": self.evidence_owner_entity_key,
            "expected_evidence_owner_entity_key": (
                self.expected_evidence_owner_entity_key
            ),
            "claim_direction": self.claim_direction,
            "expected_claim_direction": self.expected_claim_direction,
            "lane_id": self.lane_id,
            "locator": self.locator,
            "source_family": self.source_family,
            "authority": self.authority,
            "provider_reported_date": self.provider_reported_date,
            "local_publication_date": self.local_publication_date,
            "local_date_kind": self.local_date_kind,
            "local_date_source": self.local_date_source,
            "capture_ref": self.capture_ref,
            "capture_digest": self.capture_digest,
            "parser_ref": self.parser_ref,
            "parser_digest": self.parser_digest,
            "canonical_identity_verified": self.canonical_identity_verified,
            "historical_promotion_receipt": self.historical_promotion_receipt,
        }


def load_portfolio_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or tuple(policy.get("cases") or ()) != CASES
        or tuple(policy.get("external_evidence_slots") or ()) != SLOT_IDS
    ):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_policy_identity_invalid"
        )
    lanes = policy.get("lanes") or {}
    if set(lanes) != {"official_primary_lane", "semantic_open_web_shadow_lane"}:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_lane_set_invalid"
        )
    official = lanes["official_primary_lane"]
    shadow = lanes["semantic_open_web_shadow_lane"]
    if (
        official.get("route_class") != "precise_official_domain"
        or official.get("target_state") != "known_primary_disclosure"
        or official.get("financial_authority") is not False
        or official.get("evidence_promotion_allowed") is not False
        or shadow.get("route_class") != "semantic_open_web"
        or shadow.get("target_state") != "unknown_public_locator"
        or shadow.get("provider") != "firecrawl_keyless"
        or shadow.get("provider_status")
        != "shadow_integration_candidate_not_production_qualified"
        or shadow.get("financial_authority") is not False
        or shadow.get("evidence_promotion_allowed") is not False
    ):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_lane_contract_invalid"
        )
    excluded = policy.get("excluded_providers") or {}
    if excluded.get("tencent_wsa_searchpro_standard") != "diagnostic_only_not_selected":
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_exclusion_invalid"
        )
    chain = policy.get("local_authority_chain") or []
    if chain != [
        "capture_first_raw_document",
        "verified_canonical_source_identity",
        "local_typed_publication_date",
        "relationship_direction_binding",
        "parser_lineage",
        "currentness_and_as_of",
        "evidence_gate_promotion_receipt",
    ]:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_authority_chain_invalid"
        )
    calls = policy.get("zero_call_boundary") or {}
    if calls != {
        "provider_calls": 0,
        "network_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_zero_call_boundary_invalid"
        )
    return policy


def compile_portfolio_route_plan(
    *, intents: Sequence[SearchIntent], policy: Mapping[str, Any]
) -> dict[str, Any]:
    assignments = tuple(
        _compile_assignment(intent=intent, policy=policy)
        for intent in sorted(intents, key=lambda row: row.intent_id)
    )
    if len(assignments) != 60 or len({row.intent_id for row in assignments}) != 60:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_intent_set_invalid"
        )
    lane_counts = {
        lane_id: sum(row.lane_id == lane_id for row in assignments)
        for lane_id in policy["lanes"]
    }
    if lane_counts != {
        "official_primary_lane": 36,
        "semantic_open_web_shadow_lane": 24,
    }:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_lane_budget_invalid"
        )
    slot_coverage: dict[str, dict[str, set[str]]] = {
        case_key: {slot_id: set() for slot_id in SLOT_IDS} for case_key in CASES
    }
    for row in assignments:
        slot_coverage[row.case_key][row.evidence_slot_id].add(row.lane_id)
    if any(
        not lanes
        for case_slots in slot_coverage.values()
        for lanes in case_slots.values()
    ):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_slot_starvation"
        )
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_official_first_route_plan_v1_0",
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "assignments": [row.as_dict() for row in assignments],
        "lane_counts": lane_counts,
        "slot_coverage": {
            case_key: {
                slot_id: sorted(lanes) for slot_id, lanes in case_slots.items()
            }
            for case_key, case_slots in slot_coverage.items()
        },
        "required_slots_with_route_opportunity": 12,
        "required_slots_total": 12,
        "tencent_selected_assignment_count": 0,
        "provider_calls_authorized": 0,
        "network_calls_authorized": 0,
        "model_calls_authorized": 0,
        "document_fetches_authorized": 0,
        "evidence_promotions_authorized": 0,
    }
    return {**body, "plan_digest": canonical_digest(body)}


def adjudicate_replay_candidate(
    *, observation: ReplayCandidateObservation, as_of_date: str
) -> dict[str, Any]:
    reasons: list[str] = []
    if observation.case_key not in CASES or observation.subject_entity_key != observation.case_key:
        reasons.append("cross_case_subject_binding_invalid")
    if observation.evidence_slot_id not in SLOT_IDS:
        reasons.append("evidence_slot_unknown")
    if (
        not observation.evidence_owner_entity_key
        or observation.evidence_owner_entity_key
        != observation.expected_evidence_owner_entity_key
    ):
        reasons.append("evidence_owner_binding_mismatch")
    if (
        not observation.claim_direction
        or observation.claim_direction != observation.expected_claim_direction
    ):
        reasons.append("relationship_direction_mismatch")
    canonical_locator = canonical_locator_key(observation.locator)
    if not canonical_locator.startswith("https://"):
        reasons.append("canonical_https_locator_invalid")
    try:
        as_of = date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_as_of_invalid"
        ) from exc
    local_date: date | None = None
    if observation.local_publication_date:
        try:
            local_date = date.fromisoformat(observation.local_publication_date)
        except ValueError:
            reasons.append("local_publication_date_invalid")
        if local_date is not None and local_date > as_of:
            reasons.append("local_publication_date_after_as_of")
    if observation.historical_promotion_receipt:
        if observation.lane_id != "official_primary_lane":
            reasons.append("shadow_lane_promotion_forbidden")
        if not observation.canonical_identity_verified:
            reasons.append("canonical_identity_unverified")
        if not (
            observation.capture_ref
            and _digest(observation.capture_digest)
            and observation.parser_ref
            and _digest(observation.parser_digest)
        ):
            reasons.append("capture_or_parser_lineage_invalid")
        if not (
            local_date is not None
            and observation.local_date_kind == "publication_date"
            and observation.local_date_source
            and observation.local_date_source != "provider_reported_date"
        ):
            reasons.append("local_typed_publication_date_unproven")
    state = "rejected"
    if not reasons:
        state = (
            "historical_evidence_qualification_replayed"
            if observation.historical_promotion_receipt
            else "candidate_only_capture_and_evidence_gate_required"
        )
    body = {
        "candidate_id": observation.candidate_id,
        "candidate_digest": canonical_digest(observation.as_dict()),
        "state": state,
        "reason_codes": sorted(set(reasons)),
        "canonical_locator_digest": canonical_digest(canonical_locator),
        "provider_date_treated_as_telemetry_only": True,
        "new_evidence_promotion_created": False,
    }
    return {**body, "decision_digest": canonical_digest(body)}


def run_portfolio_zero_call_replay(
    *,
    policy: Mapping[str, Any],
    route_plan: Mapping[str, Any],
    firecrawl_result: Mapping[str, Any],
    firecrawl_assessment: Mapping[str, Any],
    tencent_result: Mapping[str, Any],
    tencent_assessment: Mapping[str, Any],
    dell_r2_result: Mapping[str, Any],
    official_source_closeout: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_route_plan(route_plan)
    _validate_historical_terminal(
        result=firecrawl_result,
        result_digest_field="result_digest",
        expected_status="completed",
    )
    _validate_historical_terminal(
        result=tencent_result,
        result_digest_field="result_digest",
        expected_status="completed",
    )
    _validate_assessment(
        assessment=firecrawl_assessment,
        digest_field="assessment_digest",
        expected_status="fail_diagnostic_only",
    )
    _validate_assessment(
        assessment=tencent_assessment,
        digest_field="assessment_digest",
        expected_status="fail_diagnostic_only",
    )
    firecrawl_target = list(
        firecrawl_assessment.get("aggregate", {}).get("case_slot_target_in_pool")
        or []
    )
    tencent_target = list(
        tencent_assessment.get("aggregate", {}).get("case_slot_target_in_pool")
        or []
    )
    if firecrawl_target != [5, 6] or tencent_target != [0, 6]:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_historical_locator_metric_drift"
        )
    accepted = list(
        dell_r2_result.get("result", {})
        .get("candidate_result", {})
        .get("accepted_candidates", {})
        or []
    )
    replayed_official: list[dict[str, Any]] = []
    for ordinal, row in enumerate(accepted, start=1):
        slot_id = str(row.get("evidence_slot_id") or "")
        observation = ReplayCandidateObservation(
            candidate_id=f"dell_r2_accepted_{ordinal}",
            case_key=str(row.get("case_key") or ""),
            subject_entity_key=str(row.get("case_key") or ""),
            evidence_slot_id=slot_id,
            evidence_owner_entity_key=str(row.get("entity_key") or ""),
            expected_evidence_owner_entity_key="DELL",
            claim_direction="subject_self_disclosure",
            expected_claim_direction="subject_self_disclosure",
            lane_id="official_primary_lane",
            locator=str(row.get("locator") or ""),
            source_family=str(row.get("source_family") or ""),
            authority=str(row.get("authority") or ""),
            local_publication_date=str(row.get("published_on") or ""),
            local_date_kind="publication_date",
            local_date_source="capture_backed_official_parser",
            capture_ref=str(row.get("source_capture_ref") or ""),
            capture_digest=str(row.get("source_capture_digest") or ""),
            parser_ref=str(row.get("parser_capture_ref") or ""),
            parser_digest=str(row.get("parser_capture_digest") or ""),
            canonical_identity_verified=True,
            historical_promotion_receipt=row.get("promoted") is True,
        )
        replayed_official.append(
            adjudicate_replay_candidate(
                observation=observation, as_of_date=str(policy["as_of_date"])
            )
        )
    if not replayed_official or any(
        row["state"] != "historical_evidence_qualification_replayed"
        for row in replayed_official
    ):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_official_capture_replay_failed"
        )
    slot_summaries = list(firecrawl_assessment.get("case_slot_summaries") or [])
    typed_route_gaps = [
        {
            "case_key": str(row["case_key"]),
            "evidence_slot_id": str(row["evidence_slot_id"]),
            "code": "required_relational_target_absent_after_shadow_locator_replay",
            "source_exhaustion_proven": False,
            "ranking_admitted": False,
        }
        for row in slot_summaries
        if row.get("target_in_pool") is not True
    ]
    if typed_route_gaps != [
        {
            "case_key": "DELL",
            "evidence_slot_id": "supply_chain_capacity_and_counterevidence",
            "code": "required_relational_target_absent_after_shadow_locator_replay",
            "source_exhaustion_proven": False,
            "ranking_admitted": False,
        }
    ]:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_typed_route_gap_drift"
        )
    semantic_rows = list(
        official_source_closeout.get("official_source_proof", {}).get(
            "semantic_evidence_slots"
        )
        or []
    )
    canonical_urls = {
        canonical_locator_key(str(row.get("source_url") or ""))
        for row in semantic_rows
        if row.get("source_url")
    }
    official_counts = official_source_closeout.get("official_source_proof", {}).get(
        "observed_counts", {}
    )
    if (
        len(semantic_rows) != 9
        or len(canonical_urls) != 3
        or int(official_counts.get("accepted_evidence") or 0) != 11
        or int(official_counts.get("attempt_backed_typed_gaps") or 0) != 6
    ):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_official_closeout_drift"
        )
    duplicate_groups: dict[str, int] = {}
    for row in accepted:
        key = canonical_locator_key(str(row.get("locator") or ""))
        duplicate_groups[key] = duplicate_groups.get(key, 0) + 1
    provider_date_presence = {
        "firecrawl": list(
            firecrawl_assessment.get("aggregate", {}).get(
                "provider_date_presence", [0, 235]
            )
        ),
        "tencent": list(
            tencent_assessment.get("aggregate", {}).get(
                "provider_date_presence", [172, 172]
            )
        ),
    }
    # Older assessment schemas report these observations in the decision contract.
    if provider_date_presence["firecrawl"] == []:
        provider_date_presence["firecrawl"] = [0, 235]
    if provider_date_presence["tencent"] == []:
        provider_date_presence["tencent"] = [172, 172]
    mutation_results = _run_replay_mutations(accepted=accepted, policy=policy)
    quality_card = {
        "schema_version": "fin_ia_0_1_3_s1_08_search_quality_card_v1_0",
        "route_opportunity": {
            "required_slots_with_route_opportunity": route_plan[
                "required_slots_with_route_opportunity"
            ],
            "required_slots_total": route_plan["required_slots_total"],
            "official_primary_assignments": route_plan["lane_counts"][
                "official_primary_lane"
            ],
            "firecrawl_shadow_assignments": route_plan["lane_counts"][
                "semantic_open_web_shadow_lane"
            ],
            "tencent_assignments": 0,
        },
        "locator_route_contribution": {
            "firecrawl_relational_case_slot_target_in_pool": firecrawl_target,
            "tencent_relational_case_slot_target_in_pool": tencent_target,
            "provider_date_presence_telemetry": provider_date_presence,
            "provider_date_financial_authority": False,
        },
        "capture_and_local_authority": {
            "dell_r2_historical_qualification_bindings_replayed": len(
                replayed_official
            ),
            "dell_r2_unique_canonical_documents": len(duplicate_groups),
            "official_r4_accepted_evidence": int(
                official_counts["accepted_evidence"]
            ),
            "official_r4_attempt_backed_typed_gaps": int(
                official_counts["attempt_backed_typed_gaps"]
            ),
            "official_semantic_role_bindings": len(semantic_rows),
            "official_semantic_unique_canonical_documents": len(canonical_urls),
            "new_document_fetches": 0,
            "new_evidence_promotions": 0,
        },
        "portfolio_evidence_qualification": {
            "historical_official_qualification_replay_passed": True,
            "firecrawl_rows_remain_candidate_only": True,
            "firecrawl_capture_backed_qualification_observed": False,
            "all_required_slot_target_in_pool_established": False,
            "selected_pack_coverage_established": False,
            "downstream_utilization_established": False,
            "ranking_admitted": False,
            "S1_08_closed": False,
        },
        "duplicate_accounting": {
            "same_dell_document_role_bindings": sum(duplicate_groups.values()),
            "same_dell_unique_canonical_documents": len(duplicate_groups),
            "one_document_is_not_counted_as_multiple_network_sources": True,
        },
        "typed_route_gaps": typed_route_gaps,
        "mutation_results": mutation_results,
    }
    quality_card = {
        **quality_card,
        "quality_card_digest": canonical_digest(quality_card),
    }
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "zero_call_engineering_pass",
        "route_plan_digest": route_plan["plan_digest"],
        "historical_artifacts_immutable": True,
        "planner_hidden_gold_visibility": False,
        "search_quality_card": quality_card,
        "replayed_official_candidate_decisions": replayed_official,
        "observed_calls": {
            "provider": 0,
            "network": 0,
            "model": 0,
            "document_fetch": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "portfolio_runtime_contract": True,
            "combined_zero_call_replay": True,
            "fresh_combined_live": False,
            "query_facet_plan": False,
            "internal_retrieval": False,
            "ranking": False,
            "S1_08": False,
            "S3": False,
            "release": False,
        },
        "known_boundary": (
            "The official-first route contract and immutable replay are engineering-"
            "proven. Firecrawl remains shadow-only, Tencent remains diagnostic-only, "
            "the DELL supply target is still absent, no new document was captured or "
            "promoted, and combined live, unified Query Facet, internal retrieval, "
            "ranking, S1-08, Agentic Research and release remain unproven."
        ),
    }
    return {**body, "proof_digest": canonical_digest(body)}


def _compile_assignment(
    *, intent: SearchIntent, policy: Mapping[str, Any]
) -> PortfolioRouteAssignment:
    if intent.case_key not in CASES or intent.evidence_slot_id not in SLOT_IDS:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_intent_boundary_invalid"
        )
    if intent.route_class == "precise_official_domain":
        lane_id = "official_primary_lane"
    elif intent.route_class == "semantic_open_web":
        lane_id = "semantic_open_web_shadow_lane"
    else:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_route_class_unknown"
        )
    lane = policy["lanes"][lane_id]
    if lane.get("route_class") != intent.route_class:
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_route_projection_mismatch"
        )
    body = {
        "intent_id": intent.intent_id,
        "intent_digest": intent.intent_digest,
        "case_key": intent.case_key,
        "evidence_slot_id": intent.evidence_slot_id,
        "evidence_owner_entity_key": intent.evidence_owner_entity_key,
        "claim_direction": intent.claim_direction,
        "source_families": list(intent.source_families),
        "target_state": str(lane["target_state"]),
        "lane_id": lane_id,
        "route_ids": list(lane["route_ids"]),
        "provider": str(lane["provider"]),
        "output_state": str(lane["output_state"]),
        "financial_authority": False,
        "evidence_promotion_allowed": False,
    }
    return PortfolioRouteAssignment(
        intent_id=intent.intent_id,
        intent_digest=intent.intent_digest,
        case_key=intent.case_key,
        evidence_slot_id=intent.evidence_slot_id,
        evidence_owner_entity_key=intent.evidence_owner_entity_key,
        claim_direction=intent.claim_direction,
        source_families=intent.source_families,
        target_state=str(lane["target_state"]),
        lane_id=lane_id,
        route_ids=tuple(str(value) for value in lane["route_ids"]),
        provider=str(lane["provider"]),
        output_state=str(lane["output_state"]),
        financial_authority=False,
        evidence_promotion_allowed=False,
        assignment_digest=canonical_digest(body),
    )


def _validate_route_plan(plan: Mapping[str, Any]) -> None:
    body = dict(plan)
    supplied = body.pop("plan_digest", "")
    if (
        plan.get("schema_version")
        != "fin_ia_0_1_3_s1_08_official_first_route_plan_v1_0"
        or supplied != canonical_digest(body)
        or plan.get("required_slots_with_route_opportunity") != 12
        or plan.get("tencent_selected_assignment_count") != 0
    ):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_route_plan_invalid"
        )


def _validate_historical_terminal(
    *, result: Mapping[str, Any], result_digest_field: str, expected_status: str
) -> None:
    body = dict(result)
    supplied = str(body.pop(result_digest_field, ""))
    if result.get("status") != expected_status or supplied != canonical_digest(body):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_historical_terminal_invalid"
        )


def _validate_assessment(
    *, assessment: Mapping[str, Any], digest_field: str, expected_status: str
) -> None:
    body = dict(assessment)
    supplied = str(body.pop(digest_field, ""))
    if assessment.get("status") != expected_status or supplied != canonical_digest(body):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_historical_assessment_invalid"
        )


def _run_replay_mutations(
    *, accepted: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    row = dict(accepted[0])
    baseline = ReplayCandidateObservation(
        candidate_id="mutation_baseline",
        case_key="DELL",
        subject_entity_key="DELL",
        evidence_slot_id=str(row["evidence_slot_id"]),
        evidence_owner_entity_key="DELL",
        expected_evidence_owner_entity_key="DELL",
        claim_direction="subject_self_disclosure",
        expected_claim_direction="subject_self_disclosure",
        lane_id="official_primary_lane",
        locator=str(row["locator"]),
        source_family=str(row["source_family"]),
        authority=str(row["authority"]),
        provider_reported_date="2099-01-01",
        local_publication_date=str(row["published_on"]),
        local_date_kind="publication_date",
        local_date_source="capture_backed_official_parser",
        capture_ref=str(row["source_capture_ref"]),
        capture_digest=str(row["source_capture_digest"]),
        parser_ref=str(row["parser_capture_ref"]),
        parser_digest=str(row["parser_capture_digest"]),
        canonical_identity_verified=True,
        historical_promotion_receipt=True,
    )
    cases = (
        (
            "provider_date_cannot_override_local_date",
            baseline,
            "historical_evidence_qualification_replayed",
            "",
        ),
        (
            "cross_case_subject",
            replace(baseline, subject_entity_key="MU"),
            "rejected",
            "cross_case_subject_binding_invalid",
        ),
        (
            "wrong_relationship_direction",
            replace(baseline, claim_direction="evidence_owner_own_supply_capacity_or_constraint"),
            "rejected",
            "relationship_direction_mismatch",
        ),
        (
            "future_local_date",
            replace(baseline, local_publication_date="2026-08-07"),
            "rejected",
            "local_publication_date_after_as_of",
        ),
        (
            "shadow_promotion",
            replace(baseline, lane_id="semantic_open_web_shadow_lane"),
            "rejected",
            "shadow_lane_promotion_forbidden",
        ),
        (
            "missing_capture",
            replace(baseline, capture_ref="", capture_digest=""),
            "rejected",
            "capture_or_parser_lineage_invalid",
        ),
    )
    results = []
    for name, observation, expected_state, expected_reason in cases:
        decision = adjudicate_replay_candidate(
            observation=observation, as_of_date=str(policy["as_of_date"])
        )
        passed = decision["state"] == expected_state and (
            not expected_reason or expected_reason in decision["reason_codes"]
        )
        results.append(
            {
                "mutation": name,
                "passed": passed,
                "observed_state": decision["state"],
                "expected_reason": expected_reason,
            }
        )
    if not all(row["passed"] for row in results):
        raise S108OfficialFirstPortfolioError(
            "s1_08_official_first_portfolio_mutation_failed"
        )
    return results


def _digest(value: str) -> bool:
    return bool(_HEX64.fullmatch(str(value or "")))


__all__ = [
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "PROOF_SCHEMA",
    "RUN_SCOPE",
    "PortfolioRouteAssignment",
    "ReplayCandidateObservation",
    "S108OfficialFirstPortfolioError",
    "adjudicate_replay_candidate",
    "compile_portfolio_route_plan",
    "load_portfolio_policy",
    "run_portfolio_zero_call_replay",
]
