from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_firecrawl_semantic_control import (
    ASSESSMENT_SCHEMA as FIRECRAWL_ASSESSMENT_SCHEMA,
    CONTRACT_REF as FIRECRAWL_CONTRACT_REF,
    RESULT_SCHEMA as FIRECRAWL_RESULT_SCHEMA,
    evaluate_semantic_control,
)
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import PROMOTION_STATUS


SCORING_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_scoring_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_result_v1_0"
)
ASSESSMENT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_assessment_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_authority_v1_0"
)
CONTRACT_REF = (
    "fin_0_1_3.S1_08.tencent_relationship_aware_semantic_same_matrix_comparator:v1"
)
RUN_SCOPE = (
    "S1_08_TENCENT_RELATIONSHIP_AWARE_SEMANTIC_SAME_MATRIX_EXACT_LIVE_EXECUTION"
)
CASES = ("DELL", "MU", "NVDA")
SLOTS = (
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)


class S108TencentSemanticComparatorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_scoring_contract(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != SCORING_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("visibility")
        != "evaluator_only_load_after_all_provider_calls_terminal"
    ):
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_scoring_identity_invalid"
        )
    targets = payload.get("target_sources_by_case_and_slot") or {}
    if set(targets) != set(CASES):
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_target_case_set_invalid"
        )
    for case_key in CASES:
        if set(targets[case_key]) != set(SLOTS) or any(
            not targets[case_key][slot_id] for slot_id in SLOTS
        ):
            raise S108TencentSemanticComparatorError(
                "s1_08_tencent_semantic_target_slot_set_invalid"
            )
    common = payload.get("hard_gates_for_semantic_control_qualification") or {}
    provider = payload.get("tencent_provider_specific_hard_gates") or {}
    if (
        common.get("all_planned_calls_terminalized") != 1.0
        or common.get("successful_call_rate") != 1.0
        or common.get("case_slot_target_in_pool_rate") != 1.0
        or common.get("matched_target_date_accuracy") != 1.0
        or common.get("reranker_document_fetch_or_evidence_promotion") != 0
        or provider.get("observed_standard_version_rate") != 1.0
        or float(provider.get("maximum_documented_cost_cny") or 0) != 1.104
    ):
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_scoring_gate_invalid"
        )
    return payload


def load_authority(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    body = dict(payload)
    supplied_digest = body.pop("authority_digest", None)
    execution = payload.get("execution_contract") or {}
    if (
        payload.get("schema_version") != AUTHORITY_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("status") != "issued_unconsumed"
        or payload.get("authorized_scope") != RUN_SCOPE
        or supplied_digest != canonical_digest(body)
        or execution.get("selected_lane") != "semantic_open_web"
        or execution.get("planned_query_count") != 24
        or execution.get("provider_call_ceiling") != 24
        or execution.get("network_call_ceiling") != 24
        or execution.get("retry_ceiling") != 0
        or execution.get("model_call_ceiling") != 0
        or execution.get("document_fetch_ceiling") != 0
        or execution.get("evidence_promotion_allowed") is not False
        or execution.get("sourcehunter_integration_allowed") is not False
        or execution.get("combined_46_unit_execution_allowed") is not False
        or execution.get("credentials_from_environment_only") is not True
    ):
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_authority_invalid"
        )
    return payload


def build_terminal_result(
    *,
    admission_id: str,
    source_commit: str,
    control_plan_digest: str,
    call_results: Sequence[Mapping[str, Any]],
    elapsed_ms: int,
    sdk_version: str,
) -> dict[str, Any]:
    if len(call_results) != 24:
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_terminalization_incomplete"
        )
    identities = [str(row.get("intent_id") or "") for row in call_results]
    if any(not value for value in identities) or len(identities) != len(set(identities)):
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_terminal_identity_invalid"
        )
    attempted = sum(bool(row.get("network_call_attempted")) for row in call_results)
    if attempted > 24:
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_call_ceiling_exceeded"
        )
    succeeded = sum(row.get("status") == "completed" for row in call_results)
    failed = len(call_results) - succeeded
    provider_versions = [
        str((row.get("provider_projection") or {}).get("provider_version") or "")
        for row in call_results
        if row.get("status") == "completed"
    ]
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_id": admission_id,
        "admission_consumed": attempted > 0,
        "source_commit": source_commit,
        "status": "completed" if failed == 0 else "completed_with_typed_failures",
        "terminal_code": "tencent_relationship_aware_semantic_comparator_terminal_materialized",
        "control_plan_digest": control_plan_digest,
        "call_results": [deepcopy(dict(row)) for row in call_results],
        "observed_counts": {
            "planned_queries": 24,
            "terminalized_queries": 24,
            "provider_calls": attempted,
            "network_calls": attempted,
            "successful_calls": succeeded,
            "typed_failed_or_not_attempted_calls": failed,
            "retry_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
        },
        "provider_versions": sorted(set(provider_versions)),
        "elapsed_ms": int(elapsed_ms),
        "documented_cost_cny": round(attempted * 0.046, 6),
        "sdk": {"package": "tencentcloud-sdk-python", "version": sdk_version},
        "capability_boundary": {
            "classification": "domestic_raw_search_locator_comparator_only",
            "promotion_status": PROMOTION_STATUS,
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
            "ranking_or_reranker_allowed": False,
            "sourcehunter_integration_allowed": False,
            "production_capability_claim_allowed": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def evaluate_comparator(
    *,
    result: Mapping[str, Any],
    control_plan: Mapping[str, Any],
    scoring_contract: Mapping[str, Any],
    visible_pack: Mapping[str, Any],
    firecrawl_assessment: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_result(result=result, control_plan=control_plan)
    bridge_body = {
        "schema_version": FIRECRAWL_RESULT_SCHEMA,
        "contract_ref": FIRECRAWL_CONTRACT_REF,
        "admission_id": result["admission_id"],
        "admission_consumed": result["admission_consumed"],
        "source_commit": result["source_commit"],
        "status": result["status"],
        "terminal_code": "provider_neutral_semantic_evaluator_bridge",
        "plan_digest": control_plan["plan_digest"],
        "call_results": deepcopy(list(result.get("call_results") or [])),
        "observed_counts": deepcopy(dict(result.get("observed_counts") or {})),
        "elapsed_ms": int(result.get("elapsed_ms") or 0),
        "credits_used": 0,
        "observed_cash_cost": {
            "currency": "CNY",
            "amount": float(result.get("documented_cost_cny") or 0),
            "basis": "documented_standard_pay_as_you_go_list_price",
        },
        "capability_boundary": {
            "classification": "non_persisted_evaluator_bridge_only",
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
            "ranking_or_reranker_allowed": False,
            "sourcehunter_integration_allowed": False,
            "domestic_provider_capability_established": False,
            "production_capability_claim_allowed": False,
        },
    }
    bridge = {**bridge_body, "result_digest": canonical_digest(bridge_body)}
    common = evaluate_semantic_control(
        result=bridge,
        plan=control_plan,
        scoring_contract=scoring_contract,
        visible_pack=visible_pack,
    )
    common_gates = dict(common["hard_gate_results"])
    common_gates.pop("maximum_total_credits", None)
    completed = [
        row
        for row in result.get("call_results") or []
        if row.get("status") == "completed"
    ]
    standard_count = sum(
        str((row.get("provider_projection") or {}).get("provider_version") or "")
        == "standard"
        for row in completed
    )
    standard_rate = standard_count / len(completed) if completed else 0.0
    provider_gates = scoring_contract["tencent_provider_specific_hard_gates"]
    gate_results = {
        **common_gates,
        "observed_standard_version_rate": standard_rate
        >= float(provider_gates["observed_standard_version_rate"]),
        "maximum_documented_cost_cny": float(result.get("documented_cost_cny") or 0)
        <= float(provider_gates["maximum_documented_cost_cny"]),
    }
    passed = all(gate_results.values())
    firecrawl_aggregate = deepcopy(dict(firecrawl_assessment.get("aggregate") or {}))
    body = {
        "schema_version": ASSESSMENT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": (
            "pass_domestic_candidate_for_independent_integration_authority"
            if passed
            else "fail_diagnostic_only"
        ),
        "result_digest": result["result_digest"],
        "control_plan_digest": control_plan["plan_digest"],
        "scoring_contract_digest": canonical_digest(scoring_contract),
        "per_query": common["per_query"],
        "case_language_summaries": common["case_language_summaries"],
        "case_slot_summaries": common["case_slot_summaries"],
        "case_source_summaries": common["case_source_summaries"],
        "aggregate": {
            **deepcopy(dict(common["aggregate"])),
            "documented_cost_cny": float(result.get("documented_cost_cny") or 0),
            "observed_standard_version_rate": round(standard_rate, 6),
            "standard_version_observations": [standard_count, len(completed)],
        },
        "same_matrix_firecrawl_control": {
            "assessment_schema": FIRECRAWL_ASSESSMENT_SCHEMA,
            "assessment_digest": firecrawl_assessment.get("assessment_digest"),
            "topical_useful": [
                firecrawl_aggregate.get("topical_useful_count"),
                firecrawl_aggregate.get("topical_useful_denominator"),
            ],
            "case_slot_target_in_pool": firecrawl_aggregate.get(
                "case_slot_target_in_pool"
            ),
            "matched_target_date_accuracy": firecrawl_aggregate.get(
                "matched_target_date_accuracy"
            ),
            "latency_ms": firecrawl_aggregate.get("latency_ms"),
        },
        "hard_gate_results": gate_results,
        "same_matrix_domestic_candidate_qualified": passed,
        "sourcehunter_integration_eligible": False,
        "production_capability_established": False,
        "decision": (
            "separate_sourcehunter_adapter_integration_authority_decision_required"
            if passed
            else "remain_diagnostic_only_no_reranker_rescue"
        ),
        "known_boundary": (
            "This comparator measures Tencent locator recall on the exact relationship-aware "
            "24-query semantic matrix used by the Firecrawl control. It does not fetch "
            "documents, promote Evidence, authorize ranking, integrate SourceHunter, run a "
            "model, or establish production research quality."
        ),
    }
    return {**body, "assessment_digest": canonical_digest(body)}


def _validate_result(
    *, result: Mapping[str, Any], control_plan: Mapping[str, Any]
) -> None:
    body = deepcopy(dict(result))
    supplied_digest = body.pop("result_digest", None)
    expected = {str(row["intent_id"]) for row in control_plan["query_rows"]}
    observed = {
        str(row.get("intent_id") or "") for row in result.get("call_results") or []
    }
    counts = result.get("observed_counts") or {}
    if (
        result.get("schema_version") != RESULT_SCHEMA
        or result.get("contract_ref") != CONTRACT_REF
        or supplied_digest != canonical_digest(body)
        or result.get("control_plan_digest") != control_plan.get("plan_digest")
        or expected != observed
        or len(result.get("call_results") or []) != 24
        or int(counts.get("terminalized_queries") or 0) != 24
        or int(counts.get("retry_calls") or 0) != 0
        or int(counts.get("model_calls") or 0) != 0
        or int(counts.get("document_fetches") or 0) != 0
        or int(counts.get("evidence_promotions") or 0) != 0
    ):
        raise S108TencentSemanticComparatorError(
            "s1_08_tencent_semantic_result_not_evaluable"
        )


__all__ = [
    "ASSESSMENT_SCHEMA",
    "AUTHORITY_SCHEMA",
    "CONTRACT_REF",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "SCORING_SCHEMA",
    "S108TencentSemanticComparatorError",
    "build_terminal_result",
    "evaluate_comparator",
    "load_authority",
    "load_scoring_contract",
]
