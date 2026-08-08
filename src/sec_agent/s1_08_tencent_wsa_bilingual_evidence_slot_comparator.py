from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_candidate_generation_runtime import evaluator_only_gold_match
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (
    PROMOTION_STATUS,
    canonicalize_candidate_locator,
)
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (
    compile_query_only_request,
)


QUERY_PLAN_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_query_plan_v1_0"
)
SCORING_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_scoring_contract_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_result_v1_0"
)
ASSESSMENT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_assessment_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_authority_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1_08.tencent_wsa_bilingual_evidence_slot_comparator:v1"
RUN_SCOPE = (
    "S1_08_PAID_BROAD_SEARCH_TENCENT_WSA_BILINGUAL_EVIDENCE_SLOT_COMPARATOR"
)
CASES = ("DELL", "MU", "NVDA")
LANGUAGES = ("en", "zh")
SLOTS = (
    "issuer_results_and_management_commentary",
    "regulatory_risk_and_financial_reconciliation",
    "customer_demand_and_deployment_validation",
    "supply_chain_capacity_and_counterevidence",
)
_GOLD_TOKEN_PREFIXES = (
    "DELL_E",
    "MU_E",
    "NVDA_E",
    "DELL_T",
    "MU_T",
    "NVDA_T",
    "SRC_",
)
_DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})[-/]([01]\d)[-/]([0-3]\d)(?!\d)")
_MULTIPART_PUBLIC_SUFFIXES = frozenset(
    {"com.cn", "com.tw", "com.hk", "co.uk", "co.jp", "com.au"}
)


class TencentWSABilingualComparatorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_query_plan(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != QUERY_PLAN_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("status") != "frozen_gold_blind_query_plan"
        or tuple(payload.get("cases") or ()) != CASES
        or tuple(payload.get("languages") or ()) != LANGUAGES
        or tuple(payload.get("external_evidence_slots") or ()) != SLOTS
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_query_plan_identity_invalid"
        )
    wire = payload.get("wire_contract") or {}
    if (
        wire.get("request_body_fields") != ["Query"]
        or wire.get("optional_fields") != []
        or wire.get("result_ceiling_per_query") != 10
        or wire.get("gold_or_expected_url_visible_to_query_compiler") is not False
        or wire.get("identical_retry_allowed") is not False
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_wire_boundary_invalid"
        )
    rows = payload.get("query_rows") or []
    expected_cross_product = {
        (case_key, slot_id, language)
        for case_key in CASES
        for slot_id in SLOTS
        for language in LANGUAGES
    }
    observed_cross_product: set[tuple[str, str, str]] = set()
    query_ids: set[str] = set()
    query_texts: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise TencentWSABilingualComparatorError(
                "tencent_wsa_bilingual_query_row_invalid"
            )
        identity = (
            str(row.get("case_key") or ""),
            str(row.get("slot_id") or ""),
            str(row.get("language") or ""),
        )
        query_id = str(row.get("query_id") or "")
        query_text = str(row.get("query_text") or "").strip()
        serialized = json.dumps(row, ensure_ascii=False)
        if (
            not query_id
            or not query_text
            or query_id in query_ids
            or query_text in query_texts
            or identity in observed_cross_product
            or not row.get("case_markers")
            or not row.get("slot_markers")
            or "http://" in serialized.lower()
            or "https://" in serialized.lower()
            or any(token in serialized for token in _GOLD_TOKEN_PREFIXES)
        ):
            raise TencentWSABilingualComparatorError(
                "tencent_wsa_bilingual_gold_blind_query_invalid"
            )
        request = compile_query_only_request(
            {
                "query_id": query_id,
                "case_key": identity[0],
                "semantic_intent_ref": f"{identity[0]}:{identity[1]}:{identity[2]}",
                "query_text": query_text,
                "request_body_fields": ["Query"],
                "optional_fields": [],
                "result_ceiling": 10,
            }
        )
        if request != {"Query": query_text}:
            raise TencentWSABilingualComparatorError(
                "tencent_wsa_bilingual_query_compilation_invalid"
            )
        query_ids.add(query_id)
        query_texts.add(query_text)
        observed_cross_product.add(identity)
    budget = payload.get("budget") or {}
    if (
        len(rows) != 24
        or observed_cross_product != expected_cross_product
        or budget.get("query_count") != 24
        or budget.get("provider_call_ceiling") != 24
        or budget.get("network_call_ceiling") != 24
        or budget.get("retry_ceiling") != 0
        or budget.get("model_call_ceiling") != 0
        or budget.get("document_fetch_ceiling") != 0
        or float(budget.get("maximum_documented_cost_cny") or 0) != 1.104
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_query_matrix_or_budget_invalid"
        )
    boundary = payload.get("capability_boundary") or {}
    if (
        boundary.get("classification") != "diagnostic_comparator_not_production"
        or boundary.get("sourcehunter_integration_allowed_before_pass") is not False
        or boundary.get("evidence_promotion_allowed") is not False
        or boundary.get("ranking_or_reranker_allowed") is not False
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_query_plan_false_promotion"
        )
    return payload


def load_scoring_contract(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != SCORING_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("visibility")
        != "evaluator_only_load_after_provider_terminal"
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_scoring_contract_invalid"
        )
    targets = payload.get("target_sources_by_case_and_slot") or {}
    if set(targets) != set(CASES):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_target_case_set_invalid"
        )
    for case_key in CASES:
        if set(targets[case_key]) != set(SLOTS) or any(
            not targets[case_key][slot_id] for slot_id in SLOTS
        ):
            raise TencentWSABilingualComparatorError(
                "tencent_wsa_bilingual_target_slot_set_invalid"
            )
    gates = payload.get("hard_gates_before_sourcehunter_integration") or {}
    if (
        gates.get("all_calls_terminalized") != 1.0
        or gates.get("observed_standard_version_rate") != 1.0
        or gates.get("case_slot_target_in_pool_rate_across_language_union") != 1.0
        or gates.get(
            "combined_product_hidden_target_group_recall_with_local_market_control"
        )
        != 1.0
        or gates.get("evidence_promotion_during_comparator") != 0
        or gates.get("reranker_or_document_fetch_during_comparator") != 0
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_scoring_gate_invalid"
        )
    return payload


def load_comparator_authority(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    body = dict(payload)
    digest = body.pop("authority_digest", None)
    if (
        payload.get("schema_version") != AUTHORITY_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("status") != "issued_unconsumed"
        or payload.get("authorized_scope") != RUN_SCOPE
        or digest != canonical_digest(body)
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_authority_identity_invalid"
        )
    execution = payload.get("execution_contract") or {}
    if (
        execution.get("provider_call_ceiling") != 24
        or execution.get("network_call_ceiling") != 24
        or execution.get("retry_ceiling") != 0
        or execution.get("model_call_ceiling") != 0
        or execution.get("document_fetch_ceiling") != 0
        or execution.get("evidence_promotion_allowed") is not False
        or execution.get("sourcehunter_integration_allowed") is not False
        or execution.get("credentials_interactive_hidden_only") is not True
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_authority_boundary_invalid"
        )
    return payload


def build_comparator_terminal_result(
    *,
    admission_id: str,
    source_commit: str,
    query_plan_digest: str,
    call_results: Sequence[Mapping[str, Any]],
    elapsed_ms: int,
    sdk_version: str,
) -> dict[str, Any]:
    if len(call_results) > 24:
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_call_ceiling_exceeded"
        )
    identities = [str(row.get("query_id") or "") for row in call_results]
    if len(identities) != len(set(identities)) or any(not value for value in identities):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_terminal_query_identity_invalid"
        )
    attempted = sum(bool(row.get("network_call_attempted")) for row in call_results)
    if attempted != len(call_results):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_terminal_call_count_invalid"
        )
    succeeded = sum(row.get("status") == "completed" for row in call_results)
    failed = len(call_results) - succeeded
    status = (
        "completed"
        if len(call_results) == 24 and failed == 0
        else "completed_with_typed_failures"
        if len(call_results) == 24
        else "failed_incomplete_terminalization"
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_id": admission_id,
        "admission_consumed": bool(attempted),
        "source_commit": source_commit,
        "status": status,
        "terminal_code": "tencent_wsa_bilingual_comparator_terminal_materialized",
        "query_plan_digest": query_plan_digest,
        "call_results": [deepcopy(dict(row)) for row in call_results],
        "observed_counts": {
            "planned_queries": 24,
            "terminalized_queries": len(call_results),
            "provider_calls": attempted,
            "network_calls": attempted,
            "successful_calls": succeeded,
            "typed_failed_calls": failed,
            "retry_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
        },
        "elapsed_ms": int(elapsed_ms),
        "documented_cost_cny": round(attempted * 0.046, 6),
        "sdk": {"package": "tencentcloud-sdk-python", "version": sdk_version},
        "capability_boundary": {
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
    query_plan: Mapping[str, Any],
    scoring_contract: Mapping[str, Any],
    visible_pack: Mapping[str, Any],
    hidden_scoring: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_result_for_evaluation(result, query_plan=query_plan)
    query_rows = {
        str(row["query_id"]): dict(row) for row in query_plan.get("query_rows") or []
    }
    marker_union = _marker_union(query_rows.values())
    noise_markers = tuple(
        str(value).casefold()
        for value in (
            scoring_contract.get("useful_at_10_contract", {}).get(
                "support_noise_markers"
            )
            or []
        )
    )
    source_registry = {
        _normalize_url(str(row["url"])): dict(row)
        for row in visible_pack.get("source_registry") or []
        if row.get("url")
    }
    source_by_id = {
        str(row["source_id"]): dict(row)
        for row in visible_pack.get("source_registry") or []
    }
    target_manifest = scoring_contract["target_sources_by_case_and_slot"]
    per_query: list[dict[str, Any]] = []
    exact_matches_by_case: dict[str, dict[str, dict[str, Any]]] = {
        case_key: {} for case_key in CASES
    }
    unique_locators_by_case: dict[str, dict[str, dict[str, Any]]] = {
        case_key: {} for case_key in CASES
    }
    for call in result.get("call_results") or []:
        query_id = str(call["query_id"])
        query = query_rows[query_id]
        case_key = str(query["case_key"])
        slot_id = str(query["slot_id"])
        projection = call.get("provider_projection") or {}
        locators = projection.get("locators") or []
        topical_digests: list[str] = []
        eligible_digests: list[str] = []
        matched_target_ids: set[str] = set()
        matched_date_rows: list[bool] = []
        hostnames: set[str] = set()
        domains: set[str] = set()
        for locator in locators:
            canonical_url = _normalize_url(str(locator.get("canonical_url") or ""))
            if not canonical_url:
                continue
            unique_locators_by_case[case_key].setdefault(canonical_url, dict(locator))
            hostname = (urlsplit(canonical_url).hostname or "").lower()
            if hostname:
                hostnames.add(hostname)
                domains.add(_registrable_domain(hostname))
            text = " ".join(
                str(locator.get(field) or "")
                for field in ("title", "passage", "site")
            ).casefold()
            markers = marker_union[(case_key, slot_id)]
            topical = (
                any(marker in text for marker in markers["case"])
                and any(marker in text for marker in markers["slot"])
                and not any(marker in text for marker in noise_markers)
            )
            if topical:
                topical_digests.append(str(locator.get("locator_digest") or canonical_digest(locator)))
            source = source_registry.get(canonical_url)
            if source is None:
                continue
            source_id = str(source["source_id"])
            expected_date = str(source.get("published_on") or "")
            observed_date = _extract_date(str(locator.get("published_at_raw") or ""))
            date_matches = observed_date == expected_date
            matched_date_rows.append(date_matches)
            exact_matches_by_case[case_key][source_id] = {
                "locator": canonical_url,
                "published_on": observed_date,
                "authority": str(source.get("authority") or ""),
            }
            if source_id in set(target_manifest[case_key][slot_id]):
                matched_target_ids.add(source_id)
                if topical and date_matches:
                    eligible_digests.append(
                        str(locator.get("locator_digest") or canonical_digest(locator))
                    )
        denominator = 10
        per_query.append(
            {
                "query_id": query_id,
                "case_key": case_key,
                "slot_id": slot_id,
                "language": query["language"],
                "status": call.get("status"),
                "provider_version": projection.get("provider_version"),
                "locator_count": len(locators),
                "topical_useful_count": len(topical_digests),
                "topical_useful_at_10": round(len(topical_digests) / denominator, 6),
                "evidence_eligible_useful_count": len(eligible_digests),
                "evidence_eligible_useful_at_10": round(
                    len(eligible_digests) / denominator, 6
                ),
                "topical_locator_digests": topical_digests,
                "evidence_eligible_locator_digests": eligible_digests,
                "target_source_ids_found": sorted(matched_target_ids),
                "target_in_pool": bool(matched_target_ids),
                "provider_date_presence_count": int(
                    projection.get("published_date_count") or 0
                ),
                "matched_target_date_count": len(matched_date_rows),
                "matched_target_date_accuracy": (
                    round(sum(matched_date_rows) / len(matched_date_rows), 6)
                    if matched_date_rows
                    else None
                ),
                "unique_hostnames": len(hostnames),
                "unique_registrable_domains": len(domains),
                "elapsed_ms": int(call.get("elapsed_ms") or 0),
                "documented_cost_cny": 0.046
                if call.get("network_call_attempted")
                else 0.0,
            }
        )

    case_language_rows = _case_language_summaries(per_query)
    case_rows = _case_summaries(
        per_query=per_query,
        unique_locators_by_case=unique_locators_by_case,
        target_manifest=target_manifest,
    )
    product_match_inputs = []
    local_market = source_by_id.get("SRC_MARKET_SNAPSHOT_20260806")
    for case_key in CASES:
        accepted = list(exact_matches_by_case[case_key].values())
        if local_market is not None:
            accepted.append(
                {
                    "locator": "current_market_snapshot",
                    "published_on": local_market["published_on"],
                    "authority": local_market["authority"],
                }
            )
        product_match_inputs.append(
            {
                "case_key": case_key,
                "accepted_candidates": accepted,
                "selected_candidates": accepted,
            }
        )
    hidden_match = evaluator_only_gold_match(
        results=product_match_inputs,
        visible_pack=visible_pack,
        hidden_scoring=hidden_scoring,
    )
    latencies = sorted(int(row.get("elapsed_ms") or 0) for row in per_query)
    cost = round(sum(float(row["documented_cost_cny"]) for row in per_query), 6)
    gates_spec = scoring_contract["hard_gates_before_sourcehunter_integration"]
    slot_rate = (
        sum(
            bool(slot_row["target_in_pool_across_language_union"])
            for case_row in case_rows
            for slot_row in case_row["slot_rows"]
        )
        / (len(CASES) * len(SLOTS))
    )
    matched_date_flags = [
        value
        for row in per_query
        for value in _expand_accuracy_flags(
            row["matched_target_date_count"], row["matched_target_date_accuracy"]
        )
    ]
    standard_rate = (
        sum(row["provider_version"] == "standard" for row in per_query) / len(per_query)
        if per_query
        else 0.0
    )
    gate_rows = {
        "all_calls_terminalized": len(per_query) == 24,
        "observed_standard_version_rate": standard_rate
        >= float(gates_spec["observed_standard_version_rate"]),
        "minimum_topical_useful_at_10_per_query": bool(per_query)
        and min(row["topical_useful_at_10"] for row in per_query)
        >= float(gates_spec["minimum_topical_useful_at_10_per_query"]),
        "minimum_mean_topical_useful_at_10_per_case_language": bool(
            case_language_rows
        )
        and min(row["mean_topical_useful_at_10"] for row in case_language_rows)
        >= float(
            gates_spec["minimum_mean_topical_useful_at_10_per_case_language"]
        ),
        "case_slot_target_in_pool_rate_across_language_union": slot_rate
        >= float(gates_spec["case_slot_target_in_pool_rate_across_language_union"]),
        "combined_product_hidden_target_group_recall_with_local_market_control": float(
            hidden_match["summary"]["target_in_pool_recall"]
        )
        >= float(
            gates_spec[
                "combined_product_hidden_target_group_recall_with_local_market_control"
            ]
        ),
        "matched_target_date_accuracy": bool(matched_date_flags)
        and (sum(matched_date_flags) / len(matched_date_flags))
        >= float(gates_spec["matched_target_date_accuracy"]),
        "minimum_independent_registrable_domains_per_case": all(
            row["unique_registrable_domains"]
            >= int(gates_spec["minimum_independent_registrable_domains_per_case"])
            for row in case_rows
        ),
        "maximum_single_ecosystem_share_per_case": all(
            row["largest_registrable_domain_share"]
            <= float(gates_spec["maximum_single_ecosystem_share_per_case"])
            for row in case_rows
        ),
        "maximum_documented_total_cost_cny": cost
        <= float(gates_spec["maximum_documented_total_cost_cny"]),
        "maximum_p95_latency_ms": _percentile(latencies, 0.95)
        <= int(gates_spec["maximum_p95_latency_ms"]),
        "evidence_promotion_during_comparator": int(
            result.get("observed_counts", {}).get("evidence_promotions") or 0
        )
        == 0,
        "reranker_or_document_fetch_during_comparator": int(
            result.get("observed_counts", {}).get("document_fetches") or 0
        )
        == 0,
    }
    passed = all(gate_rows.values())
    body = {
        "schema_version": ASSESSMENT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": "pass" if passed else "fail_diagnostic_only",
        "result_digest": result["result_digest"],
        "query_plan_digest": canonical_digest(query_plan),
        "scoring_contract_digest": canonical_digest(scoring_contract),
        "per_query": per_query,
        "case_language_summaries": case_language_rows,
        "case_summaries": case_rows,
        "combined_product_hidden_target_match": hidden_match,
        "aggregate": {
            "terminalized_queries": len(per_query),
            "observed_standard_version_rate": round(standard_rate, 6),
            "case_slot_target_in_pool_rate_across_language_union": round(
                slot_rate, 6
            ),
            "matched_target_date_observations": len(matched_date_flags),
            "matched_target_date_accuracy": (
                round(sum(matched_date_flags) / len(matched_date_flags), 6)
                if matched_date_flags
                else None
            ),
            "documented_total_cost_cny": cost,
            "latency_ms": {
                "p50": _percentile(latencies, 0.5),
                "p95": _percentile(latencies, 0.95),
                "maximum": max(latencies) if latencies else 0,
                "whole_run": int(result.get("elapsed_ms") or 0),
            },
        },
        "hard_gate_results": gate_rows,
        "sourcehunter_integration_eligible": passed,
        "decision": (
            "eligible_for_separate_integration_decision"
            if passed
            else "remain_diagnostic_only_no_reranker_rescue"
        ),
        "known_boundary": (
            "Provider dates outside exact frozen target matches remain unverified. "
            "Passing this comparator would authorize only a separate adapter integration "
            "decision, not automatic Evidence promotion, Agentic Research or release."
        ),
    }
    return {**body, "assessment_digest": canonical_digest(body)}


def _validate_result_for_evaluation(
    result: Mapping[str, Any], *, query_plan: Mapping[str, Any]
) -> None:
    body = deepcopy(dict(result))
    digest = body.pop("result_digest", None)
    expected_ids = {str(row["query_id"]) for row in query_plan["query_rows"]}
    observed_ids = {str(row.get("query_id") or "") for row in result.get("call_results") or []}
    if (
        result.get("schema_version") != RESULT_SCHEMA
        or result.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(body)
        or result.get("query_plan_digest") != canonical_digest(query_plan)
        or observed_ids != expected_ids
        or len(result.get("call_results") or []) != 24
    ):
        raise TencentWSABilingualComparatorError(
            "tencent_wsa_bilingual_result_not_evaluable"
        )


def _marker_union(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, tuple[str, ...]]]:
    aggregate: dict[tuple[str, str], dict[str, set[str]]] = {}
    for row in rows:
        key = (str(row["case_key"]), str(row["slot_id"]))
        bucket = aggregate.setdefault(key, {"case": set(), "slot": set()})
        bucket["case"].update(str(value).casefold() for value in row["case_markers"])
        bucket["slot"].update(str(value).casefold() for value in row["slot_markers"])
    return {
        key: {
            "case": tuple(sorted(values["case"])),
            "slot": tuple(sorted(values["slot"])),
        }
        for key, values in aggregate.items()
    }


def _case_language_summaries(per_query: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_key in CASES:
        for language in LANGUAGES:
            selected = [
                row
                for row in per_query
                if row["case_key"] == case_key and row["language"] == language
            ]
            rows.append(
                {
                    "case_key": case_key,
                    "language": language,
                    "query_count": len(selected),
                    "mean_topical_useful_at_10": round(
                        sum(float(row["topical_useful_at_10"]) for row in selected)
                        / len(selected),
                        6,
                    )
                    if selected
                    else 0.0,
                    "mean_evidence_eligible_useful_at_10": round(
                        sum(
                            float(row["evidence_eligible_useful_at_10"])
                            for row in selected
                        )
                        / len(selected),
                        6,
                    )
                    if selected
                    else 0.0,
                    "target_in_pool_query_rate": round(
                        sum(bool(row["target_in_pool"]) for row in selected)
                        / len(selected),
                        6,
                    )
                    if selected
                    else 0.0,
                }
            )
    return rows


def _case_summaries(
    *,
    per_query: Sequence[Mapping[str, Any]],
    unique_locators_by_case: Mapping[str, Mapping[str, Mapping[str, Any]]],
    target_manifest: Mapping[str, Mapping[str, Sequence[str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_key in CASES:
        selected = [row for row in per_query if row["case_key"] == case_key]
        locators = unique_locators_by_case[case_key]
        domain_counter: Counter[str] = Counter()
        hostnames: set[str] = set()
        for locator in locators.values():
            hostname = (
                urlsplit(str(locator.get("canonical_url") or "")).hostname or ""
            ).lower()
            if hostname:
                hostnames.add(hostname)
                domain_counter[_registrable_domain(hostname)] += 1
        slot_rows: list[dict[str, Any]] = []
        for slot_id in SLOTS:
            language_rows = [row for row in selected if row["slot_id"] == slot_id]
            found = {
                value
                for row in language_rows
                for value in row["target_source_ids_found"]
            }
            required = set(target_manifest[case_key][slot_id])
            slot_rows.append(
                {
                    "slot_id": slot_id,
                    "target_source_ids_found": sorted(found),
                    "target_source_count_available": len(required),
                    "target_in_pool_across_language_union": bool(found & required),
                }
            )
        largest_share = (
            max(domain_counter.values()) / sum(domain_counter.values())
            if domain_counter
            else 1.0
        )
        rows.append(
            {
                "case_key": case_key,
                "query_count": len(selected),
                "unique_locator_count": len(locators),
                "unique_hostnames": len(hostnames),
                "unique_registrable_domains": len(domain_counter),
                "registrable_domain_counts": dict(sorted(domain_counter.items())),
                "largest_registrable_domain_share": round(largest_share, 6),
                "slot_rows": slot_rows,
            }
        )
    return rows


def _extract_date(value: str) -> str | None:
    match = _DATE_PATTERN.search(value)
    if match is None:
        return None
    normalized = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError:
        return None


def _normalize_url(value: str) -> str:
    try:
        return canonicalize_candidate_locator(value).rstrip("/")
    except Exception:
        return ""


def _registrable_domain(hostname: str) -> str:
    labels = [value for value in hostname.lower().rstrip(".").split(".") if value]
    if len(labels) <= 2:
        return ".".join(labels)
    suffix2 = ".".join(labels[-2:])
    if suffix2 in _MULTIPART_PUBLIC_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return suffix2


def _percentile(values: Sequence[int], probability: float) -> int:
    if not values:
        return 0
    ordered = sorted(int(value) for value in values)
    index = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


def _expand_accuracy_flags(count: int, accuracy: float | None) -> list[bool]:
    if not count or accuracy is None:
        return []
    successes = int(round(float(accuracy) * count))
    return [True] * successes + [False] * (count - successes)


__all__ = [
    "ASSESSMENT_SCHEMA",
    "AUTHORITY_SCHEMA",
    "CASES",
    "CONTRACT_REF",
    "LANGUAGES",
    "QUERY_PLAN_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "SCORING_SCHEMA",
    "SLOTS",
    "TencentWSABilingualComparatorError",
    "build_comparator_terminal_result",
    "evaluate_comparator",
    "load_comparator_authority",
    "load_query_plan",
    "load_scoring_contract",
]
