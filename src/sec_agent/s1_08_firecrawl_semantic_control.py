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
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (
    canonicalize_candidate_locator,
)


PLAN_SCHEMA = (
    "fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0"
)
SCORING_SCHEMA = (
    "fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0"
)
ASSESSMENT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_authority_v1_0"
)
CONTRACT_REF = (
    "fin_0_1_3.S1_08.firecrawl_relationship_aware_semantic_control:v1"
)
RUN_SCOPE = (
    "S1_08_FIRECRAWL_RELATIONSHIP_AWARE_SEMANTIC_CONTROL_EXACT_LIVE_EXECUTION"
)
CASES = ("DELL", "MU", "NVDA")
LANGUAGES = ("en", "zh")
SEMANTIC_SLOTS = (
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
_DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})[-/]([01]\d)[-/]([0-3]\d)(?!\d)")
_MULTIPART_PUBLIC_SUFFIXES = frozenset(
    {"com.cn", "com.tw", "com.hk", "co.uk", "co.jp", "com.au"}
)


class S108FirecrawlSemanticControlError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_plan(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    body = dict(payload)
    supplied_digest = body.pop("plan_digest", None)
    if (
        payload.get("schema_version") != PLAN_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("status") != "frozen_gold_blind_semantic_control_plan"
        or supplied_digest != canonical_digest(body)
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_plan_identity_invalid"
        )
    rows = payload.get("query_rows") or []
    identities: set[str] = set()
    unit_digests: set[str] = set()
    query_texts: set[str] = set()
    for row in rows:
        serialized = json.dumps(row, ensure_ascii=False)
        intent_id = str(row.get("intent_id") or "")
        unit_digest = str(row.get("execution_unit_digest") or "")
        query_text = str(row.get("query_text") or "").strip()
        request_body = row.get("request_body") or {}
        if (
            not intent_id
            or not unit_digest
            or not query_text
            or intent_id in identities
            or unit_digest in unit_digests
            or query_text in query_texts
            or row.get("provider_id") != "firecrawl_keyless_search"
            or row.get("route_class") != "semantic_open_web"
            or row.get("case_key") not in CASES
            or row.get("evidence_slot_id") not in SEMANTIC_SLOTS
            or row.get("language") not in LANGUAGES
            or not row.get("evidence_owner_entity_key")
            or not row.get("claim_direction")
            or not row.get("owner_markers")
            or not row.get("topic_markers")
            or request_body
            != {"limit": 10, "query": query_text, "sources": ["web"]}
            or "http://" in serialized.casefold()
            or "https://" in serialized.casefold()
            or any(token in serialized for token in GOLD_TOKEN_PREFIXES)
        ):
            raise S108FirecrawlSemanticControlError(
                "s1_08_firecrawl_semantic_plan_row_invalid"
            )
        identities.add(intent_id)
        unit_digests.add(unit_digest)
        query_texts.add(query_text)
    budget = payload.get("execution_budget") or {}
    if (
        len(rows) != 24
        or len(identities) != 24
        or budget.get("planned_queries") != 24
        or budget.get("provider_call_ceiling") != 24
        or budget.get("network_call_ceiling") != 24
        or budget.get("retry_ceiling") != 0
        or budget.get("model_call_ceiling") != 0
        or budget.get("document_fetch_ceiling") != 0
        or budget.get("evidence_promotion_ceiling") != 0
        or budget.get("result_ceiling_per_query") != 10
        or budget.get("combined_precise_and_semantic_run_allowed") is not False
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_plan_budget_invalid"
        )
    boundary = payload.get("capability_boundary") or {}
    if (
        boundary.get("classification")
        != "diagnostic_semantic_search_control_not_production"
        or boundary.get("gold_visible_to_query_compiler") is not False
        or boundary.get("sourcehunter_integration_allowed") is not False
        or boundary.get("ranking_or_reranker_allowed") is not False
        or boundary.get("evidence_promotion_allowed") is not False
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_plan_false_promotion"
        )
    return payload


def load_scoring_contract(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != SCORING_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("visibility")
        != "evaluator_only_load_after_all_provider_calls_terminal"
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_scoring_identity_invalid"
        )
    targets = payload.get("target_sources_by_case_and_slot") or {}
    if set(targets) != set(CASES):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_target_case_set_invalid"
        )
    for case_key in CASES:
        if set(targets[case_key]) != set(SEMANTIC_SLOTS) or any(
            not targets[case_key][slot_id] for slot_id in SEMANTIC_SLOTS
        ):
            raise S108FirecrawlSemanticControlError(
                "s1_08_firecrawl_semantic_target_slot_set_invalid"
            )
    gates = payload.get("hard_gates_for_semantic_control_qualification") or {}
    if (
        gates.get("all_planned_calls_terminalized") != 1.0
        or gates.get("successful_call_rate") != 1.0
        or gates.get("case_slot_target_in_pool_rate") != 1.0
        or gates.get("matched_target_date_accuracy") != 1.0
        or gates.get("maximum_total_credits") != 48
        or gates.get("reranker_document_fetch_or_evidence_promotion") != 0
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_scoring_gate_invalid"
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
        or execution.get("provider_call_ceiling") != 24
        or execution.get("network_call_ceiling") != 24
        or execution.get("retry_ceiling") != 0
        or execution.get("model_call_ceiling") != 0
        or execution.get("document_fetch_ceiling") != 0
        or execution.get("evidence_promotion_allowed") is not False
        or execution.get("sourcehunter_integration_allowed") is not False
        or execution.get("combined_46_unit_execution_allowed") is not False
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_authority_invalid"
        )
    return payload


def normalize_firecrawl_response(
    payload: Mapping[str, Any], *, result_ceiling: int = 10
) -> dict[str, Any]:
    if payload.get("success") is not True:
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_provider_success_false"
        )
    data = payload.get("data") or {}
    rows = data.get("web") or []
    if not isinstance(rows, list):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_provider_shape_invalid"
        )
    locators: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows[:result_ceiling]:
        if not isinstance(raw, Mapping):
            continue
        normalized_url = _normalize_url(str(raw.get("url") or ""))
        if not normalized_url or normalized_url in seen:
            continue
        seen.add(normalized_url)
        hostname = (urlsplit(normalized_url).hostname or "").lower()
        published_raw = str(
            raw.get("publishedDate")
            or raw.get("published_date")
            or raw.get("date")
            or ""
        )
        locator_body = {
            "provider_rank": int(raw.get("position") or len(locators) + 1),
            "canonical_url": normalized_url,
            "source_domain": hostname,
            "title": str(raw.get("title") or "")[:500],
            "passage": str(raw.get("description") or "")[:1500],
            "published_at_raw": published_raw[:100],
            "promotion_status": "candidate_locator_diagnostic_only",
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
        }
        locators.append(
            {**locator_body, "locator_digest": canonical_digest(locator_body)}
        )
    credits_raw = payload.get("creditsUsed")
    try:
        credits = int(credits_raw or 0)
    except (TypeError, ValueError):
        credits = 0
    return {
        "provider": "Firecrawl Search",
        "provider_request_id": str(payload.get("id") or ""),
        "normalized_unique_locator_count": len(locators),
        "published_date_count": sum(
            bool(row["published_at_raw"]) for row in locators
        ),
        "credits_used": credits,
        "locators": locators,
    }


def build_terminal_result(
    *,
    admission_id: str,
    source_commit: str,
    plan_digest: str,
    call_results: Sequence[Mapping[str, Any]],
    elapsed_ms: int,
) -> dict[str, Any]:
    if len(call_results) != 24:
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_terminalization_incomplete"
        )
    identities = [str(row.get("intent_id") or "") for row in call_results]
    if any(not value for value in identities) or len(identities) != len(set(identities)):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_terminal_identity_invalid"
        )
    attempted = sum(bool(row.get("network_call_attempted")) for row in call_results)
    succeeded = sum(row.get("status") == "completed" for row in call_results)
    failed = len(call_results) - succeeded
    credits = sum(
        int((row.get("provider_projection") or {}).get("credits_used") or 0)
        for row in call_results
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_id": admission_id,
        "admission_consumed": attempted > 0,
        "source_commit": source_commit,
        "status": "completed" if failed == 0 else "completed_with_typed_failures",
        "terminal_code": "firecrawl_semantic_control_terminal_materialized",
        "plan_digest": plan_digest,
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
        "elapsed_ms": int(elapsed_ms),
        "credits_used": credits,
        "observed_cash_cost": {
            "currency": "USD",
            "amount": 0.0,
            "basis": "keyless_control_no_payment_instrument_or_api_key_used",
            "credits_are_not_treated_as_zero_economic_cost": True,
        },
        "capability_boundary": {
            "classification": "diagnostic_locator_control_only",
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
    return {**body, "result_digest": canonical_digest(body)}


def evaluate_semantic_control(
    *,
    result: Mapping[str, Any],
    plan: Mapping[str, Any],
    scoring_contract: Mapping[str, Any],
    visible_pack: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_result(result=result, plan=plan)
    rows_by_intent = {
        str(row["intent_id"]): dict(row) for row in plan.get("query_rows") or []
    }
    source_registry = {
        _normalize_url(str(row.get("url") or "")): dict(row)
        for row in visible_pack.get("source_registry") or []
        if row.get("url")
    }
    target_manifest = scoring_contract["target_sources_by_case_and_slot"]
    noise_markers = tuple(
        str(value).casefold()
        for value in scoring_contract["useful_at_10_contract"][
            "support_noise_markers"
        ]
    )
    per_query: list[dict[str, Any]] = []
    unique_by_case: dict[str, dict[str, dict[str, Any]]] = {
        case_key: {} for case_key in CASES
    }
    date_flags: list[bool] = []
    for call in result.get("call_results") or []:
        intent_id = str(call["intent_id"])
        query = rows_by_intent[intent_id]
        case_key = str(query["case_key"])
        slot_id = str(query["evidence_slot_id"])
        allowed_targets = set(target_manifest[case_key][slot_id])
        owner_markers = tuple(
            str(value).casefold() for value in query["owner_markers"]
        )
        topic_markers = tuple(
            str(value).casefold() for value in query["topic_markers"]
        )
        locators = (call.get("provider_projection") or {}).get("locators") or []
        topical: list[str] = []
        targets_found: set[str] = set()
        exact_date_flags: list[bool] = []
        for locator in locators:
            canonical_url = _normalize_url(str(locator.get("canonical_url") or ""))
            if not canonical_url:
                continue
            unique_by_case[case_key].setdefault(canonical_url, dict(locator))
            text = " ".join(
                str(locator.get(field) or "")
                for field in ("title", "passage", "source_domain")
            ).casefold()
            is_topical = (
                any(marker in text for marker in owner_markers)
                and any(marker in text for marker in topic_markers)
                and not any(marker in text for marker in noise_markers)
            )
            if is_topical:
                topical.append(str(locator.get("locator_digest") or ""))
            source = source_registry.get(canonical_url)
            if source is None:
                continue
            source_id = str(source.get("source_id") or "")
            if source_id not in allowed_targets:
                continue
            targets_found.add(source_id)
            observed_date = _extract_date(str(locator.get("published_at_raw") or ""))
            date_matches = bool(observed_date) and observed_date == str(
                source.get("published_on") or ""
            )
            exact_date_flags.append(date_matches)
            date_flags.append(date_matches)
        per_query.append(
            {
                "intent_id": intent_id,
                "case_key": case_key,
                "evidence_slot_id": slot_id,
                "evidence_owner_entity_key": query[
                    "evidence_owner_entity_key"
                ],
                "language": query["language"],
                "status": call.get("status"),
                "locator_count": len(locators),
                "topical_useful_count": len(set(topical)),
                "topical_useful_at_10": round(len(set(topical)) / 10, 6),
                "target_source_ids_found": sorted(targets_found),
                "target_in_pool": bool(targets_found),
                "provider_date_presence_count": sum(
                    bool(row.get("published_at_raw")) for row in locators
                ),
                "matched_target_date_count": len(exact_date_flags),
                "matched_target_date_accuracy": (
                    round(sum(exact_date_flags) / len(exact_date_flags), 6)
                    if exact_date_flags
                    else None
                ),
                "credits_used": int(
                    (call.get("provider_projection") or {}).get("credits_used") or 0
                ),
                "elapsed_ms": int(call.get("elapsed_ms") or 0),
            }
        )
    case_slot_rows = _case_slot_summaries(
        per_query=per_query,
        target_manifest=target_manifest,
    )
    case_rows = _case_source_summaries(unique_by_case)
    case_language_rows = _case_language_summaries(per_query)
    latencies = sorted(int(row["elapsed_ms"]) for row in per_query)
    credits = int(result.get("credits_used") or 0)
    target_rate = sum(row["target_in_pool"] for row in case_slot_rows) / len(
        case_slot_rows
    )
    gates = scoring_contract["hard_gates_for_semantic_control_qualification"]
    observed = result.get("observed_counts") or {}
    gate_results = {
        "all_planned_calls_terminalized": len(per_query) == 24,
        "successful_call_rate": (
            int(observed.get("successful_calls") or 0) / 24
            >= float(gates["successful_call_rate"])
        ),
        "minimum_topical_useful_at_10_per_query": bool(per_query)
        and min(row["topical_useful_at_10"] for row in per_query)
        >= float(gates["minimum_topical_useful_at_10_per_query"]),
        "minimum_mean_topical_useful_at_10_per_case_language": bool(
            case_language_rows
        )
        and min(row["mean_topical_useful_at_10"] for row in case_language_rows)
        >= float(gates["minimum_mean_topical_useful_at_10_per_case_language"]),
        "case_slot_target_in_pool_rate": target_rate
        >= float(gates["case_slot_target_in_pool_rate"]),
        "matched_target_date_accuracy": bool(date_flags)
        and (sum(date_flags) / len(date_flags))
        >= float(gates["matched_target_date_accuracy"]),
        "minimum_independent_registrable_domains_per_case": all(
            row["unique_registrable_domains"]
            >= int(gates["minimum_independent_registrable_domains_per_case"])
            for row in case_rows
        ),
        "maximum_single_ecosystem_share_per_case": all(
            row["largest_registrable_domain_share"]
            <= float(gates["maximum_single_ecosystem_share_per_case"])
            for row in case_rows
        ),
        "maximum_total_credits": credits <= int(gates["maximum_total_credits"]),
        "maximum_p95_latency_ms": _percentile(latencies, 0.95)
        <= int(gates["maximum_p95_latency_ms"]),
        "reranker_document_fetch_or_evidence_promotion": (
            int(observed.get("retry_calls") or 0)
            + int(observed.get("model_calls") or 0)
            + int(observed.get("document_fetches") or 0)
            + int(observed.get("evidence_promotions") or 0)
        )
        == int(gates["reranker_document_fetch_or_evidence_promotion"]),
    }
    passed = all(gate_results.values())
    body = {
        "schema_version": ASSESSMENT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": "pass_control_lane" if passed else "fail_diagnostic_only",
        "result_digest": result["result_digest"],
        "plan_digest": plan["plan_digest"],
        "scoring_contract_digest": canonical_digest(scoring_contract),
        "per_query": per_query,
        "case_language_summaries": case_language_rows,
        "case_slot_summaries": case_slot_rows,
        "case_source_summaries": case_rows,
        "aggregate": {
            "terminalized_queries": len(per_query),
            "successful_calls": int(observed.get("successful_calls") or 0),
            "topical_useful_count": sum(
                row["topical_useful_count"] for row in per_query
            ),
            "topical_useful_denominator": 240,
            "case_slot_target_in_pool": [
                sum(row["target_in_pool"] for row in case_slot_rows),
                len(case_slot_rows),
            ],
            "case_slot_target_in_pool_rate": round(target_rate, 6),
            "matched_target_date_observations": len(date_flags),
            "matched_target_date_accuracy": (
                round(sum(date_flags) / len(date_flags), 6)
                if date_flags
                else None
            ),
            "credits_used": credits,
            "observed_cash_cost": result.get("observed_cash_cost"),
            "latency_ms": {
                "p50": _percentile(latencies, 0.5),
                "p95": _percentile(latencies, 0.95),
                "maximum": max(latencies) if latencies else 0,
                "whole_run": int(result.get("elapsed_ms") or 0),
            },
        },
        "historical_a4_comparison": scoring_contract[
            "historical_generic_query_baseline"
        ],
        "hard_gate_results": gate_results,
        "semantic_control_lane_qualified": passed,
        "sourcehunter_integration_eligible": False,
        "domestic_provider_capability_established": False,
        "decision": (
            "eligible_for_same_matrix_domestic_provider_comparison_only"
            if passed
            else "remain_diagnostic_only_no_reranker_rescue"
        ),
        "known_boundary": (
            "This control evaluates only the relationship-aware customer and supply "
            "semantic lane. It cannot establish the domestic provider goal, the precise "
            "official lane, document quality, Evidence promotion, Agentic Research, "
            "SourceHunter integration or release readiness."
        ),
    }
    return {**body, "assessment_digest": canonical_digest(body)}


def _validate_result(*, result: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    body = deepcopy(dict(result))
    supplied_digest = body.pop("result_digest", None)
    expected = {str(row["intent_id"]) for row in plan["query_rows"]}
    observed = {
        str(row.get("intent_id") or "") for row in result.get("call_results") or []
    }
    if (
        result.get("schema_version") != RESULT_SCHEMA
        or result.get("contract_ref") != CONTRACT_REF
        or supplied_digest != canonical_digest(body)
        or result.get("plan_digest") != plan.get("plan_digest")
        or expected != observed
        or len(result.get("call_results") or []) != 24
        or int((result.get("observed_counts") or {}).get("terminalized_queries") or 0)
        != 24
    ):
        raise S108FirecrawlSemanticControlError(
            "s1_08_firecrawl_semantic_result_not_evaluable"
        )


def _case_slot_summaries(
    *,
    per_query: Sequence[Mapping[str, Any]],
    target_manifest: Mapping[str, Mapping[str, Sequence[str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_key in CASES:
        for slot_id in SEMANTIC_SLOTS:
            selected = [
                row
                for row in per_query
                if row["case_key"] == case_key
                and row["evidence_slot_id"] == slot_id
            ]
            found = {
                source_id
                for row in selected
                for source_id in row["target_source_ids_found"]
            }
            required = set(target_manifest[case_key][slot_id])
            rows.append(
                {
                    "case_key": case_key,
                    "evidence_slot_id": slot_id,
                    "query_count": len(selected),
                    "target_source_ids_found": sorted(found),
                    "target_source_ids_required": sorted(required),
                    "target_in_pool": bool(found & required),
                }
            )
    return rows


def _case_language_summaries(
    per_query: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
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
                        sum(row["topical_useful_at_10"] for row in selected)
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


def _case_source_summaries(
    unique_by_case: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_key in CASES:
        locators = unique_by_case[case_key]
        domains: Counter[str] = Counter()
        hostnames: set[str] = set()
        for locator in locators.values():
            hostname = (
                urlsplit(str(locator.get("canonical_url") or "")).hostname or ""
            ).lower()
            if hostname:
                hostnames.add(hostname)
                domains[_registrable_domain(hostname)] += 1
        total = sum(domains.values())
        rows.append(
            {
                "case_key": case_key,
                "unique_locator_count": len(locators),
                "unique_hostnames": len(hostnames),
                "unique_registrable_domains": len(domains),
                "registrable_domain_counts": dict(sorted(domains.items())),
                "largest_registrable_domain_share": round(
                    max(domains.values()) / total if total else 1.0, 6
                ),
            }
        )
    return rows


def _normalize_url(value: str) -> str:
    try:
        return canonicalize_candidate_locator(value).rstrip("/")
    except Exception:
        return ""


def _extract_date(value: str) -> str | None:
    match = _DATE_PATTERN.search(value)
    if match is None:
        return None
    candidate = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def _registrable_domain(hostname: str) -> str:
    labels = [value for value in hostname.lower().rstrip(".").split(".") if value]
    if len(labels) <= 2:
        return ".".join(labels)
    suffix2 = ".".join(labels[-2:])
    if suffix2 in _MULTIPART_PUBLIC_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return suffix2


def _percentile(values: Sequence[int], quantile: float) -> int:
    if not values:
        return 0
    ordered = sorted(int(value) for value in values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]
