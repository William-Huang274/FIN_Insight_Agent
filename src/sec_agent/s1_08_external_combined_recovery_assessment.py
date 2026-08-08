from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_candidate_generation_runtime import evaluator_only_gold_match
from sec_agent.s1_08_external_combined_assessment import (
    ExternalCombinedAssessmentError,
    _assess_official_lane,
    _assess_shadow_lane,
)


ASSESSMENT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_external_combined_recovery_assessment_v1_0"
)
REQUIRED_EXTERNAL_ROLES = (
    "issuer_results_and_management_commentary",
    "regulatory_risk_and_financial_reconciliation",
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)


def assess_external_combined_recovery_live(
    *,
    result: Mapping[str, Any],
    runtime_root: str | Path,
    visible_pack: Mapping[str, Any],
    hidden_scoring: Mapping[str, Any],
    historical_firecrawl_assessment: Mapping[str, Any],
    historical_tencent_assessment: Mapping[str, Any],
    resolver=None,
) -> dict[str, Any]:
    root = Path(runtime_root)
    public_body = deepcopy(dict(result))
    supplied_public_digest = public_body.pop("public_record_digest", None)
    observed = deepcopy(dict(result.get("observed_counts") or {}))
    if (
        result.get("schema_version")
        != "fin_ia_0_1_3_s1_08_external_combined_terminal_v1_0"
        or result.get("runtime_revision") != "r1_environment_and_quota_recovery_v1"
        or result.get("status") != "completed_with_typed_failures"
        or supplied_public_digest != canonical_digest(public_body)
        or not root.is_dir()
        or observed.get("official_cases_terminalized") != 3
        or observed.get("shadow_queries_terminalized") != 24
        or any(
            observed.get(key) != 0
            for key in (
                "model_calls",
                "embedding_calls",
                "rerank_calls",
                "evidence_promotions",
                "retry_calls",
                "fallback_calls",
            )
        )
    ):
        raise ExternalCombinedAssessmentError(
            "external_combined_recovery_terminal_invalid"
        )

    official = _assess_official_lane(
        rows=result.get("official_case_results") or (),
        root=root / "official",
        resolver=resolver or (lambda _host: ("198.18.1.10",)),
    )
    shadow = _assess_shadow_lane(
        rows=result.get("firecrawl_shadow_results") or (),
        root=root / "firecrawl-shadow",
    )
    candidate_results = [
        dict(row.get("candidate_result") or {})
        for row in result.get("official_case_results") or ()
    ]
    hidden_match = evaluator_only_gold_match(
        results=candidate_results,
        visible_pack=visible_pack,
        hidden_scoring=hidden_scoring,
    )
    official_quality = _official_candidate_quality(candidate_results)
    shadow_semantics = _shadow_stop_semantics(
        result.get("firecrawl_shadow_results") or ()
    )
    historical = _historical_provider_evidence(
        firecrawl=historical_firecrawl_assessment,
        tencent=historical_tencent_assessment,
    )
    official_failure_codes = official["summary"]["failure_codes"]
    query_binding = official["query_facet_binding"]
    runtime_recovery_pass = (
        "official_source_private_network_forbidden" not in official_failure_codes
        and all(
            row.get("status") == "completed"
            for row in result.get("official_case_results") or ()
        )
        and shadow_semantics["systemic_credit_stop_valid"]
        and query_binding["attempt_budget_digests_equal_receipt_bound_digests"]
        and query_binding["effective_query_text_preserved_in_receipts"]
    )
    candidate_ceiling_pass = (
        official_quality["required_external_slot_coverage"] == 1.0
        and hidden_match["summary"]["target_in_pool_recall"] == 1.0
        and official_quality["source_family_diversity"] >= 2
    )

    body = {
        "schema_version": ASSESSMENT_SCHEMA,
        "status": (
            "runtime_recovery_live_pass_external_candidate_ceiling_failed"
            if runtime_recovery_pass and not candidate_ceiling_pass
            else "recovery_assessment_failed"
        ),
        "result_digest": result["terminal_result_digest"],
        "public_record_digest": supplied_public_digest,
        "run_id": result["run_id"],
        "attempt_id": result["attempt_id"],
        "query_variant": result["query_variant"],
        "observed_counts": observed,
        "capture_integrity": {
            "official_content_addressed_objects": official[
                "content_addressed_object_count"
            ],
            "official_content_addresses_valid": official[
                "all_content_addresses_valid"
            ],
            "firecrawl_capture_refs": shadow["capture_ref_count"],
            "firecrawl_capture_refs_sha_valid": shadow[
                "all_capture_ref_hashes_valid"
            ],
            "raw_request_or_response_content_lost": False,
        },
        "runtime_recovery": {
            "pass": runtime_recovery_pass,
            "controlled_synthetic_dns_handshake_live_proven": (
                "official_source_private_network_forbidden"
                not in official_failure_codes
                and observed.get("official_network_calls", 0) > 0
            ),
            "official_cases_completed": [
                sum(
                    row.get("status") == "completed"
                    for row in result.get("official_case_results") or ()
                ),
                3,
            ],
            "official_failure_codes": official_failure_codes,
            "query_facet_binding": query_binding,
            "shadow_systemic_stop": shadow_semantics,
        },
        "official_candidate_quality": official_quality,
        "evaluator_only_candidate_ceiling": hidden_match,
        "historical_provider_evidence": historical,
        "hard_gate_results": {
            "capture_integrity": bool(
                official["all_content_addresses_valid"]
                and shadow["all_capture_ref_hashes_valid"]
            ),
            "runtime_recovery": runtime_recovery_pass,
            "required_external_slot_coverage": (
                official_quality["required_external_slot_coverage"] == 1.0
            ),
            "hidden_target_in_pool_recall": (
                hidden_match["summary"]["target_in_pool_recall"] == 1.0
            ),
            "source_family_diversity": (
                official_quality["source_family_diversity"] >= 2
            ),
            "external_portfolio_product_acceptance": candidate_ceiling_pass,
        },
        "root_cause_disposition": {
            "deepseek_or_model_failure": False,
            "query_facet_contract_failure": False,
            "combined_runtime_environment_defect_live_recurrence": False,
            "firecrawl_credit_constraint_live_recurrence": True,
            "official_source_discovery_and_slot_fit_coverage_insufficient": True,
            "reranker_can_repair_missing_target": False,
        },
        "stage_disposition": {
            "owner_stage": "S1_08_external_candidate_discovery",
            "recovery_run_is_immutable": True,
            "automatic_additional_external_live_allowed": False,
            "current_provider_round": (
                "complete_honest_partial_external_product_gap_preserved"
            ),
            "external_product_capability_accepted": False,
            "external_release_blocker_preserved": True,
            "internal_retrieval_started": False,
            "internal_retrieval_may_start_after_closeout_projection": True,
            "next_scope": "S1_INTERNAL_RETRIEVAL_QUERY_FACET_INTEGRATION",
            "internal_retrieval_backlog_ref": (
                "configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_"
                "external_internal_progression_plan_v1_1.json"
            ),
        },
        "known_boundary": (
            "The recovery live closes the project-owned environment and quota-stop "
            "proof, not external product coverage. Starting internal retrieval is a "
            "work-sequence handoff, not a waiver of the external release blocker. "
            "BGE/fusion/rerank remain forbidden until the internal candidate ceiling passes."
        ),
    }
    if not runtime_recovery_pass or candidate_ceiling_pass:
        raise ExternalCombinedAssessmentError(
            "external_combined_recovery_disposition_unexpected"
        )
    return {**body, "assessment_digest": canonical_digest(body)}


def _official_candidate_quality(
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if {str(row.get("case_key") or "") for row in results} != {
        "DELL",
        "MU",
        "NVDA",
    }:
        raise ExternalCombinedAssessmentError(
            "external_combined_recovery_case_set_invalid"
        )
    slot_counts: Counter[str] = Counter()
    unique_locators: set[str] = set()
    source_families: set[str] = set()
    source_domains: set[str] = set()
    selected_rows: list[dict[str, Any]] = []
    for result in results:
        case_key = str(result["case_key"])
        as_of = date.fromisoformat(str(result["as_of"]))
        for candidate in result.get("selected_candidates") or ():
            row = dict(candidate)
            role = str(row.get("role_id") or "")
            if role not in REQUIRED_EXTERNAL_ROLES:
                continue
            published = date.fromisoformat(str(row.get("published_on") or ""))
            valid = (
                row.get("case_key") == case_key
                and row.get("subject_entity") == case_key
                and bool(row.get("evidence_owner_entity"))
                and row.get("promoted") is True
                and row.get("promotion_decision") == "accepted_candidate"
                and published <= as_of
                and bool(row.get("source_capture_ref"))
                and bool(row.get("parser_capture_ref"))
                and bool(row.get("discovery_capture_ref"))
            )
            if not valid:
                raise ExternalCombinedAssessmentError(
                    "external_combined_recovery_selected_candidate_invalid"
                )
            locator = str(row["locator"])
            slot_counts[role] += 1
            unique_locators.add(locator)
            source_families.add(str(row.get("source_family") or ""))
            domain = (urlparse(locator).hostname or "").lower()
            if domain:
                source_domains.add(domain)
            selected_rows.append(
                {
                    "case_key": case_key,
                    "role_id": role,
                    "evidence_owner_entity": row["evidence_owner_entity"],
                    "source_family": row["source_family"],
                    "authority": row["authority"],
                    "published_on": row["published_on"],
                    "publication_date_kind": row["publication_date_kind"],
                    "publication_date_confidence": row[
                        "publication_date_confidence"
                    ],
                    "locator_digest": canonical_digest(locator),
                }
            )
    required_total = len(results) * len(REQUIRED_EXTERNAL_ROLES)
    covered = len(selected_rows)
    per_case = {
        str(result["case_key"]): sorted(
            str(row.get("role_id"))
            for row in result.get("selected_candidates") or ()
            if row.get("role_id") in REQUIRED_EXTERNAL_ROLES
        )
        for result in results
    }
    return {
        "required_external_roles": list(REQUIRED_EXTERNAL_ROLES),
        "required_external_slots": required_total,
        "selected_required_slots": covered,
        "required_external_slot_coverage": round(covered / required_total, 6),
        "selected_required_roles_by_case": per_case,
        "selected_role_occurrences": dict(sorted(slot_counts.items())),
        "selected_candidates": selected_rows,
        "unique_selected_source_documents": len(unique_locators),
        "source_family_diversity": len(source_families),
        "source_domain_diversity": len(source_domains),
        "all_selected_dates_current_and_typed": True,
        "all_selected_identity_relationship_and_lineage_valid": True,
    }


def _shadow_stop_semantics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempted = [row for row in rows if row.get("network_call_attempted") is True]
    unattempted = [row for row in rows if row.get("network_call_attempted") is False]
    credit = [
        row
        for row in attempted
        if row.get("terminal_code") == "firecrawl_shadow_systemic_credit_exhaustion"
        and row.get("http_status") == 429
    ]
    stopped = all(
        row.get("terminal_code")
        == "firecrawl_shadow_not_attempted_after_systemic_stop"
        and row.get("http_status") == 0
        for row in unattempted
    )
    first_six = list(rows[:6])
    semantics = {
        "attempted_network_queries": len(attempted),
        "credit_exhaustion_terminals": len(credit),
        "unattempted_after_systemic_stop": len(unattempted),
        "remaining_queries_stopped_after_first_credit_exhaustion": stopped,
        "first_three_case_coverage": len(
            {str(row.get("case_key") or "") for row in rows[:3]}
        ),
        "first_six_case_slot_coverage": len(
            {
                (
                    str(row.get("case_key") or ""),
                    str(row.get("evidence_slot_id") or ""),
                )
                for row in first_six
            }
        ),
    }
    semantics["systemic_credit_stop_valid"] = bool(
        len(rows) == 24
        and len(attempted) == 1
        and len(credit) == 1
        and len(unattempted) == 23
        and stopped
    )
    return semantics


def _historical_provider_evidence(
    *, firecrawl: Mapping[str, Any], tencent: Mapping[str, Any]
) -> dict[str, Any]:
    firecrawl_target = (firecrawl.get("aggregate") or {}).get(
        "case_slot_target_in_pool"
    )
    tencent_target = (tencent.get("aggregate") or {}).get(
        "case_slot_target_in_pool"
    )
    if (
        firecrawl.get("status") != "fail_diagnostic_only"
        or firecrawl_target != [5, 6]
        or tencent.get("status") != "fail_diagnostic_only"
        or tencent_target != [0, 6]
    ):
        raise ExternalCombinedAssessmentError(
            "external_combined_recovery_historical_provider_basis_invalid"
        )
    return {
        "evidence_is_separate_from_recovery_run": True,
        "firecrawl_relationship_aware_control": {
            "status": firecrawl["status"],
            "case_slot_target_in_pool": firecrawl_target,
            "matched_target_date_accuracy": firecrawl["aggregate"][
                "matched_target_date_accuracy"
            ],
            "decision": firecrawl["decision"],
            "assessment_digest": firecrawl["assessment_digest"],
        },
        "tencent_same_matrix_control": {
            "status": tencent["status"],
            "case_slot_target_in_pool": tencent_target,
            "decision": tencent["decision"],
            "assessment_digest": tencent["assessment_digest"],
        },
        "production_provider_qualified": False,
    }


__all__ = ["ASSESSMENT_SCHEMA", "assess_external_combined_recovery_live"]
