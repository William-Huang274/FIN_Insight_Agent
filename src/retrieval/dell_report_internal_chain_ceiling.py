from __future__ import annotations

from collections import Counter
from datetime import date
import re
from typing import Any, Iterable, Mapping, Sequence

from .dell_report_residual_source_program import (
    EXPECTED_HELD_TARGET_IDS,
    EXPECTED_TARGET_SEMANTICS_BY_ID,
)
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v1_0"
SUCCESSOR_POLICY_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_ceiling_policy_v1_1"
)
FAILURE_RECEIPT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_ceiling_failure_receipt_v1_0"
)
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_ceiling_private_result_v1_0"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_ceiling_public_result_v1_0"
)

EXPECTED_UNOVERLAPPED_TARGET_IDS = frozenset(
    set(EXPECTED_TARGET_SEMANTICS_BY_ID) - set(EXPECTED_HELD_TARGET_IDS)
)


class DellReportInternalChainCeilingError(ValueError):
    """Raised when the DELL 03B internal-chain proof is not fail closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingError(code)


def _mapping(value: Any, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return dict(value)


def _sequence(value: Any, code: str) -> list[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return list(value)


def _nonblank(value: Any, code: str) -> str:
    text = str(value or "").strip()
    _require(bool(text), code)
    return text


def _iso_date(value: Any, code: str) -> date:
    try:
        return date.fromisoformat(_nonblank(value, code))
    except ValueError as exc:
        raise DellReportInternalChainCeilingError(code) from exc


def _normalize_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = text.replace("‐", "-").replace("‑", "-").replace("–", "-")
    text = text.replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def _term_hit(text: str, term: str) -> bool:
    return _normalize_text(term) in text


def _group_match(
    text: str,
    group: Mapping[str, Any],
) -> tuple[bool, list[str], list[str]]:
    terms = [_nonblank(value, "dell_03B_rule_term_blank") for value in group.get("terms") or ()]
    regexes = [
        _nonblank(value, "dell_03B_rule_regex_blank")
        for value in group.get("regexes") or ()
    ]
    _require(bool(terms or regexes), "dell_03B_rule_group_empty")
    matched_terms = [term for term in terms if _term_hit(text, term)]
    matched_regexes = [pattern for pattern in regexes if re.search(pattern, text)]
    return bool(matched_terms or matched_regexes), matched_terms, matched_regexes


def _validate_target_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    parsed = dict(contract)
    target_id = _nonblank(parsed.get("target_id"), "dell_03B_target_id_missing")
    _require(
        target_id in EXPECTED_UNOVERLAPPED_TARGET_IDS,
        f"dell_03B_target_not_unoverlapped:{target_id}",
    )
    request_ids = [
        _nonblank(value, f"dell_03B_request_id_blank:{target_id}")
        for value in _sequence(
            parsed.get("request_ids"), f"dell_03B_request_ids_invalid:{target_id}"
        )
    ]
    _require(
        request_ids and len(request_ids) == len(set(request_ids)),
        f"dell_03B_request_ids_duplicate_or_empty:{target_id}",
    )
    allowed_tickers = [
        _nonblank(value, f"dell_03B_ticker_blank:{target_id}").upper()
        for value in _sequence(
            parsed.get("allowed_tickers"),
            f"dell_03B_allowed_tickers_invalid:{target_id}",
        )
    ]
    _require(
        allowed_tickers and len(allowed_tickers) == len(set(allowed_tickers)),
        f"dell_03B_allowed_tickers_duplicate_or_empty:{target_id}",
    )
    start = _iso_date(parsed.get("publication_date_gte"), f"dell_03B_date_gte:{target_id}")
    end = _iso_date(parsed.get("publication_date_lte"), f"dell_03B_date_lte:{target_id}")
    _require(start <= end, f"dell_03B_date_order_invalid:{target_id}")
    groups = [
        _mapping(value, f"dell_03B_group_invalid:{target_id}")
        for value in _sequence(
            parsed.get("semantic_groups"),
            f"dell_03B_groups_invalid:{target_id}",
        )
    ]
    group_ids = [
        _nonblank(group.get("group_id"), f"dell_03B_group_id_blank:{target_id}")
        for group in groups
    ]
    _require(
        group_ids and len(group_ids) == len(set(group_ids)),
        f"dell_03B_group_ids_duplicate_or_empty:{target_id}",
    )
    for group in groups:
        _group_match("", group)
    complete = [str(value) for value in parsed.get("complete_required_group_ids") or ()]
    partial = [str(value) for value in parsed.get("partial_required_group_ids") or ()]
    _require(
        complete and set(complete).issubset(group_ids),
        f"dell_03B_complete_groups_invalid:{target_id}",
    )
    _require(
        partial and set(partial).issubset(group_ids),
        f"dell_03B_partial_groups_invalid:{target_id}",
    )
    _require(
        set(partial).issubset(complete),
        f"dell_03B_partial_not_subset_complete:{target_id}",
    )
    for field in ("forbidden_complete_terms", "forbidden_complete_regexes"):
        values = [str(value).strip() for value in parsed.get(field) or ()]
        _require(
            all(values), f"dell_03B_forbidden_rule_blank:{target_id}:{field}"
        )
    return parsed


def validate_dell_report_internal_chain_ceiling_policy(
    policy: Mapping[str, Any],
    *,
    residual_program: Mapping[str, Any],
    execution_program: Mapping[str, Any],
    runtime_registry: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = dict(policy)
    _require(
        parsed.get("schema_version") == POLICY_SCHEMA_VERSION,
        "dell_03B_policy_schema_invalid",
    )
    _require(
        parsed.get("status") == "scoped_internal_chain_execution_authorized",
        "dell_03B_policy_status_invalid",
    )
    _require(
        parsed.get("program_id") == "FIN-0.1.3-S1-DELL-RSQ-03B-R1"
        and parsed.get("attempt_id") == "dell-rsq-03b-internal-chain-r1",
        "dell_03B_R1_identity_invalid",
    )
    _require(
        residual_program.get("program_id") == "FIN-0.1.3-S1-DELL-RSQ-03A-R2"
        and residual_program.get("program_digest")
        == parsed.get("bound_inputs", {}).get("residual_program_digest"),
        "dell_03B_residual_program_binding_invalid",
    )
    _require(
        residual_program.get("authority", {}).get(
            "03B_internal_chain_execution_authorized"
        )
        is False,
        "dell_03B_predecessor_authority_must_remain_false",
    )
    _require(
        execution_program.get("program_id")
        == parsed.get("bound_inputs", {}).get("execution_program_id"),
        "dell_03B_execution_program_binding_invalid",
    )
    _require(
        runtime_registry.get("registry_id")
        == parsed.get("bound_inputs", {}).get("runtime_registry_id")
        and runtime_registry.get("resource_canonical_digest")
        == parsed.get("bound_inputs", {}).get("runtime_registry_digest"),
        "dell_03B_runtime_registry_binding_invalid",
    )
    _require(
        runtime_binding_receipt.get("result_digest")
        == parsed.get("bound_inputs", {}).get("runtime_binding_receipt_digest"),
        "dell_03B_runtime_receipt_binding_invalid",
    )
    _require(
        runtime_binding_receipt.get("registry_binding", {}).get("registry_id")
        == runtime_registry.get("registry_id"),
        "dell_03B_registry_receipt_identity_invalid",
    )
    target_contracts = [
        _validate_target_contract(_mapping(value, "dell_03B_target_contract_invalid"))
        for value in _sequence(
            parsed.get("target_contracts"), "dell_03B_target_contracts_invalid"
        )
    ]
    target_ids = {str(row["target_id"]) for row in target_contracts}
    _require(
        target_ids == EXPECTED_UNOVERLAPPED_TARGET_IDS,
        "dell_03B_exact_unoverlapped_target_set_invalid",
    )
    _require(
        set(parsed.get("held_target_ids") or ()) == set(EXPECTED_HELD_TARGET_IDS),
        "dell_03B_exact_held_target_set_invalid",
    )
    residual_targets = {
        str(row.get("target_id") or ""): dict(row)
        for row in residual_program.get("route_targets") or ()
        if isinstance(row, Mapping)
    }
    _require(
        set(residual_targets) == set(EXPECTED_TARGET_SEMANTICS_BY_ID),
        "dell_03B_residual_target_population_invalid",
    )
    for target_id in EXPECTED_UNOVERLAPPED_TARGET_IDS:
        _require(
            residual_targets[target_id].get("current_route_state")
            == "planned_for_03B_internal_chain_then_bounded_03C_if_needed",
            f"dell_03B_target_state_invalid:{target_id}",
        )
    for target_id in EXPECTED_HELD_TARGET_IDS:
        _require(
            residual_targets[target_id].get("current_route_state")
            == "held_by_qualified_human_admission",
            f"dell_03B_held_target_state_invalid:{target_id}",
        )
    available_request_ids = {
        str(row.get("request_id") or "")
        for row in execution_program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    scoped_request_ids = {
        request_id
        for contract in target_contracts
        for request_id in contract["request_ids"]
    }
    _require(
        scoped_request_ids.issubset(available_request_ids),
        "dell_03B_scoped_request_not_in_execution_program",
    )
    _require(
        len(scoped_request_ids)
        == int(parsed.get("execution_budget", {}).get("request_count") or 0),
        "dell_03B_request_budget_invalid",
    )
    budget = _mapping(parsed.get("execution_budget"), "dell_03B_budget_invalid")
    _require(
        budget.get("local_embedding_inference_batches_maximum") == 1
        and budget.get("network_calls") == 0
        and budget.get("provider_calls") == 0
        and budget.get("generation_model_calls") == 0
        and budget.get("external_capture_calls") == 0
        and budget.get("4B_embedding_calls") == 0
        and budget.get("reranker_calls") == 0
        and budget.get("retries") == 0,
        "dell_03B_execution_budget_not_bounded",
    )
    authority = _mapping(parsed.get("authority"), "dell_03B_authority_invalid")
    _require(
        authority.get("03B_internal_chain_execution_authorized") is True
        and authority.get("current_0_6B_query_embedding_authorized") is True
        and authority.get("network_authorized") is False
        and authority.get("external_capture_authorized") is False
        and authority.get("4B_embedding_authorized") is False
        and authority.get("reranker_authorized") is False
        and authority.get("candidate_decision_authorized") is False
        and authority.get("evidence_promotion_authorized") is False
        and authority.get("gap_closure_authorized") is False
        and authority.get("public_information_boundary_authorized") is False,
        "dell_03B_authority_surface_invalid",
    )
    token_basis = _mapping(
        parsed.get("TokenBudgetBasis"), "dell_03B_token_budget_basis_missing"
    )
    for field in (
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation",
    ):
        _nonblank(token_basis.get(field), f"dell_03B_token_budget_basis_missing:{field}")
    ceiling_contract = _mapping(
        parsed.get("candidate_ceiling_contract"),
        "dell_03B_candidate_ceiling_contract_missing",
    )
    _require(
        ceiling_contract.get("full_current_compiled_object_corpus_must_be_scanned")
        is True
        and ceiling_contract.get(
            "raw_union_candidate_decision_seed_must_be_joined_to_objects"
        )
        is True
        and ceiling_contract.get("final_review_must_be_a_subset_of_union") is True
        and ceiling_contract.get("source_lineage_must_exist") is True
        and ceiling_contract.get("reranker_useful_at_k") == 10
        and ceiling_contract.get("candidate_or_ranking_score_grants_evidence")
        is False,
        "dell_03B_candidate_ceiling_contract_invalid",
    )
    return parsed


def validate_dell_report_internal_chain_ceiling_successor_policy(
    successor_policy: Mapping[str, Any],
    *,
    predecessor_policy: Mapping[str, Any],
    predecessor_failure_receipt: Mapping[str, Any],
    residual_program: Mapping[str, Any],
    execution_program: Mapping[str, Any],
    runtime_registry: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the non-overwriting R2 authority and return its inherited R1 contract."""

    predecessor = validate_dell_report_internal_chain_ceiling_policy(
        predecessor_policy,
        residual_program=residual_program,
        execution_program=execution_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding_receipt,
    )
    successor = dict(successor_policy)
    _require(
        successor.get("schema_version") == SUCCESSOR_POLICY_SCHEMA_VERSION,
        "dell_03B_R2_policy_schema_invalid",
    )
    _require(
        successor.get("status")
        == "scoped_internal_chain_successor_execution_authorized_after_R1_terminal_failure",
        "dell_03B_R2_policy_status_invalid",
    )
    _require(
        successor.get("program_id") == "FIN-0.1.3-S1-DELL-RSQ-03B-R2"
        and successor.get("attempt_id") == "dell-rsq-03b-internal-chain-r2",
        "dell_03B_R2_identity_invalid",
    )
    unsigned_successor = {
        key: value for key, value in successor.items() if key != "result_digest"
    }
    _require(
        successor.get("result_digest") == canonical_digest(unsigned_successor),
        "dell_03B_R2_policy_digest_invalid",
    )

    lineage = _mapping(
        successor.get("predecessor"), "dell_03B_R2_predecessor_binding_missing"
    )
    _require(
        lineage.get("policy_ref")
        == "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json"
        and lineage.get("failure_receipt_ref")
        == "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_r1_failure_receipt_v1_0.json"
        and re.fullmatch(r"[0-9a-f]{64}", str(lineage.get("policy_sha256") or ""))
        and re.fullmatch(
            r"[0-9a-f]{64}", str(lineage.get("failure_receipt_sha256") or "")
        )
        and lineage.get("program_id") == predecessor.get("program_id")
        and lineage.get("attempt_id") == predecessor.get("attempt_id")
        and lineage.get("policy_canonical_digest")
        == canonical_digest(predecessor),
        "dell_03B_R2_predecessor_policy_invalid",
    )
    failure = dict(predecessor_failure_receipt)
    unsigned_failure = {
        key: value for key, value in failure.items() if key != "result_digest"
    }
    _require(
        failure.get("schema_version") == FAILURE_RECEIPT_SCHEMA_VERSION
        and failure.get("status")
        == "terminal_failed_source_record_identity_field_assumption"
        and failure.get("attempt_id") == predecessor.get("attempt_id")
        and failure.get("result_digest") == canonical_digest(unsigned_failure)
        == lineage.get("failure_receipt_result_digest"),
        "dell_03B_R2_failure_receipt_invalid",
    )
    failure_execution = _mapping(
        failure.get("execution_receipt"),
        "dell_03B_R2_failure_execution_receipt_invalid",
    )
    _require(
        failure_execution.get("local_qwen_0_6B_query_embedding_batch_started")
        is True
        and failure_execution.get("network_calls") == 0
        and failure_execution.get("provider_calls") == 0
        and failure_execution.get("generation_model_calls") == 0
        and failure_execution.get("external_capture_calls") == 0
        and failure_execution.get("4B_embedding_calls") == 0
        and failure_execution.get("reranker_calls") == 0
        and failure_execution.get("candidate_promotions") == 0
        and failure_execution.get("evidence_promotions") == 0
        and failure_execution.get("gap_closures") == 0
        and failure_execution.get("private_output_created") is False
        and failure_execution.get("public_output_created") is False,
        "dell_03B_R2_failure_boundary_invalid",
    )
    _require(
        failure.get("failure_disposition", {}).get(
            "R1_reuse_or_relabel_forbidden"
        )
        is True
        and failure.get("failure_disposition", {}).get(
            "same_attempt_retry_forbidden"
        )
        is True,
        "dell_03B_R2_R1_reuse_boundary_invalid",
    )

    expected_inheritance = [
        "six_unoverlapped_targets_and_three_held_targets",
        "five_exact_request_payloads",
        "target_semantic_contracts_and_date_ticker_bounds",
        "full_R38_source_object_index_SQL_population",
        "BM25_Qwen0_6B_typed_graph_candidate_chain",
        "candidate_union_96_final_review_16_and_useful_at_10",
        "4B_reranker_and_03C_eligibility_rules",
        "zero_network_provider_generation_external_4B_reranker_promotion_and_gap_closure",
        "candidate_not_evidence_and_no_downstream_acceptance",
    ]
    _require(
        successor.get("inherited_without_change") == expected_inheritance,
        "dell_03B_R2_inheritance_contract_invalid",
    )
    _require(
        successor.get("only_successor_changes")
        == {
            "source_store_identity_field": "evidence_id",
            "compiled_object_identity_projection_field": "source_record_id",
            "source_store_source_record_id_alias_accepted": False,
            "source_population_requires_nonblank_unique_evidence_ids": True,
            "source_and_compiled_lineage_populations_require_exact_set_equality": True,
            "R1_query_scores_or_partial_state_reused": False,
            "R1_result_relabelled_as_success": False,
            "fresh_R2_query_embedding_batch_required": True,
        },
        "dell_03B_R2_delta_invalid",
    )
    _require(
        successor.get("execution_budget") == predecessor.get("execution_budget"),
        "dell_03B_R2_execution_budget_drift",
    )
    _require(
        successor.get("authority") == predecessor.get("authority"),
        "dell_03B_R2_authority_drift",
    )
    token_basis = _mapping(
        successor.get("TokenBudgetBasis"),
        "dell_03B_R2_token_budget_basis_missing",
    )
    for field in (
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation",
    ):
        _nonblank(
            token_basis.get(field),
            f"dell_03B_R2_token_budget_basis_missing:{field}",
        )
    implementation_bindings = _sequence(
        successor.get("implementation_bindings"),
        "dell_03B_R2_implementation_bindings_invalid",
    )
    _require(
        {
            str(row.get("path") or "")
            for row in implementation_bindings
            if isinstance(row, Mapping)
        }
        == {
            "src/retrieval/dell_report_internal_chain_ceiling.py",
            "scripts/data_retrieval/run_dell_report_internal_chain_ceiling.py",
        }
        and all(
            isinstance(row, Mapping)
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or ""))
            for row in implementation_bindings
        ),
        "dell_03B_R2_implementation_bindings_invalid",
    )
    return predecessor


def classify_internal_chain_object(
    object_row: Mapping[str, Any],
    target_contract: Mapping[str, Any],
) -> dict[str, Any]:
    target_id = _nonblank(
        target_contract.get("target_id"), "dell_03B_classify_target_id_missing"
    )
    object_id = _nonblank(
        object_row.get("compiled_object_id"),
        f"dell_03B_classify_object_id_missing:{target_id}",
    )
    base = _mapping(
        object_row.get("base_object_view"),
        f"dell_03B_classify_base_view_missing:{object_id}",
    )
    text = _normalize_text(object_row.get("model_text"))
    ticker = _nonblank(base.get("ticker"), f"dell_03B_object_ticker_missing:{object_id}").upper()
    publication_date = _iso_date(
        base.get("publication_date"),
        f"dell_03B_object_publication_date_invalid:{object_id}",
    )
    allowed_tickers = {str(value).upper() for value in target_contract["allowed_tickers"]}
    in_owner_scope = ticker in allowed_tickers
    in_period = (
        _iso_date(target_contract["publication_date_gte"], "dell_03B_contract_date_gte")
        <= publication_date
        <= _iso_date(target_contract["publication_date_lte"], "dell_03B_contract_date_lte")
    )
    matches: dict[str, dict[str, list[str]]] = {}
    for raw_group in target_contract.get("semantic_groups") or ():
        group = _mapping(raw_group, f"dell_03B_group_invalid_at_runtime:{target_id}")
        group_id = str(group["group_id"])
        hit, terms, regexes = _group_match(text, group)
        if hit:
            matches[group_id] = {
                "terms": terms,
                "regexes": regexes,
            }
    forbidden_terms = [
        term
        for term in target_contract.get("forbidden_complete_terms") or ()
        if _term_hit(text, str(term))
    ]
    forbidden_regexes = [
        pattern
        for pattern in target_contract.get("forbidden_complete_regexes") or ()
        if re.search(str(pattern), text)
    ]
    matched_group_ids = set(matches)
    complete_required = set(target_contract["complete_required_group_ids"])
    partial_required = set(target_contract["partial_required_group_ids"])
    complete = (
        in_owner_scope
        and in_period
        and complete_required.issubset(matched_group_ids)
        and not forbidden_terms
        and not forbidden_regexes
    )
    partial = (
        not complete
        and in_owner_scope
        and in_period
        and partial_required.issubset(matched_group_ids)
    )
    classification = (
        "complete_target_semantic_equivalent"
        if complete
        else "partial_context_only"
        if partial
        else "not_target_semantic_equivalent"
    )
    return {
        "target_id": target_id,
        "compiled_object_id": object_id,
        "source_record_id": str(base.get("source_record_id") or ""),
        "lineage_source_record_ids": list(
            object_row.get("lineage_source_record_ids")
            or (base.get("source_record_id"),)
        ),
        "ticker": ticker,
        "source_type": str(base.get("source_type") or ""),
        "source_tier": str(base.get("source_tier") or ""),
        "publication_date": publication_date.isoformat(),
        "period_end": str(base.get("period_end") or ""),
        "section": str(base.get("section") or ""),
        "subsection": str(base.get("subsection") or ""),
        "classification": classification,
        "in_owner_scope": in_owner_scope,
        "in_period": in_period,
        "matched_group_ids": sorted(matched_group_ids),
        "match_detail": matches,
        "forbidden_complete_terms_matched": forbidden_terms,
        "forbidden_complete_regexes_matched": forbidden_regexes,
        "candidate_not_evidence": object_row.get("candidate_not_evidence") is True,
        "evidence_promoted": object_row.get("evidence_promoted") is True,
        "numeric_authority": object_row.get("numeric_authority") is True,
        "model_text": str(object_row.get("model_text") or ""),
    }


def _route_state_counts(request_result: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    truth = request_result.get("route_execution_truth")
    if not isinstance(truth, Mapping):
        return {}
    for family in ("narrative_route_requests", "typed_fact_route_requests"):
        for request in truth.get(family) or ():
            if not isinstance(request, Mapping):
                continue
            for route in request.get("routes") or ():
                if isinstance(route, Mapping):
                    counts[str(route.get("execution_state") or "unknown")] += 1
    return dict(sorted(counts.items()))


def _candidate_trace(
    object_id: str,
    request_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    for request_result in request_results:
        request_id = str(request_result.get("request", {}).get("request_id") or "")
        hybrid = request_result.get("hybrid_object_retrieval") or {}
        for seed in hybrid.get("candidate_decision_seed") or ():
            if str(seed.get("compiled_object_id") or "") != object_id:
                continue
            traces.append(
                {
                    "request_id": request_id,
                    "rank_trace": dict(seed.get("rank_trace") or {}),
                    "route_membership": list(seed.get("route_membership") or ()),
                    "route_ranks": dict(seed.get("route_ranks") or {}),
                    "material_alignment_state": seed.get("material_alignment_state"),
                    "candidate_not_evidence": seed.get("candidate_not_evidence"),
                    "evidence_promoted": seed.get("evidence_promoted"),
                    "numeric_authority": seed.get("numeric_authority"),
                }
            )
    return {
        "request_traces": traces,
        "minimum_raw_union_rank": min(
            (
                int(trace["rank_trace"].get("raw_union_rank"))
                for trace in traces
                if trace["rank_trace"].get("raw_union_rank") is not None
            ),
            default=None,
        ),
        "minimum_final_output_rank": min(
            (
                int(trace["rank_trace"].get("final_output_rank"))
                for trace in traces
                if trace["rank_trace"].get("final_output_rank") is not None
            ),
            default=None,
        ),
    }


def _project_match(
    assessment: Mapping[str, Any],
    trace: Mapping[str, Any],
    *,
    include_text: bool,
) -> dict[str, Any]:
    row = {
        key: assessment.get(key)
        for key in (
            "compiled_object_id",
            "source_record_id",
            "lineage_source_record_ids",
            "ticker",
            "source_type",
            "source_tier",
            "publication_date",
            "period_end",
            "section",
            "subsection",
            "classification",
            "matched_group_ids",
            "match_detail",
            "forbidden_complete_terms_matched",
            "forbidden_complete_regexes_matched",
            "candidate_not_evidence",
            "evidence_promoted",
            "numeric_authority",
        )
    }
    row["candidate_trace"] = dict(trace)
    if include_text:
        row["model_text"] = assessment.get("model_text")
    return row


def validate_dell_report_source_compiled_identity_population(
    *,
    object_rows: Sequence[Mapping[str, Any]],
    source_record_ids: Iterable[str],
    runtime_binding_receipt: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Prove the canonical source population equals the compiled lineage population."""

    objects_by_id = {
        _nonblank(row.get("compiled_object_id"), "dell_03B_object_id_missing"): dict(row)
        for row in object_rows
    }
    _require(
        len(objects_by_id) == len(object_rows), "dell_03B_object_ids_duplicate"
    )
    binding = runtime_binding_receipt.get("source_object_index_lineage") or {}
    _require(
        len(objects_by_id) == int(binding.get("compiled_object_count") or 0),
        "dell_03B_object_population_binding_invalid",
    )
    source_values = list(source_record_ids)
    _require(
        all(
            isinstance(value, str) and value.strip() and value == value.strip()
            for value in source_values
        ),
        "dell_03B_source_identity_population_invalid",
    )
    source_ids = set(source_values)
    _require(
        len(source_ids) == len(source_values),
        "dell_03B_source_identity_population_duplicate",
    )
    _require(
        len(source_ids) == int(binding.get("source_record_count") or 0),
        "dell_03B_source_population_binding_invalid",
    )
    _require(
        binding.get("all_source_records_lineage_bound") is True
        and binding.get("compiled_lineage_ids_outside_bound_source_store") == []
        and binding.get("source_records_missing_from_compiled_lineage") == []
        and int(binding.get("compiled_lineage_source_record_count") or 0)
        == len(source_ids),
        "dell_03B_source_lineage_receipt_invalid",
    )
    compiled_lineage_ids: set[str] = set()
    for object_id, object_row in objects_by_id.items():
        lineage_ids = list(object_row.get("lineage_source_record_ids") or ())
        _require(
            bool(lineage_ids)
            and all(isinstance(value, str) and value.strip() for value in lineage_ids),
            f"dell_03B_object_lineage_invalid:{object_id}",
        )
        compiled_lineage_ids.update(value.strip() for value in lineage_ids)
    _require(
        compiled_lineage_ids == source_ids,
        "dell_03B_source_compiled_lineage_population_mismatch",
    )
    return objects_by_id, source_ids


def compile_dell_report_internal_chain_ceiling_result(
    *,
    policy: Mapping[str, Any],
    residual_program: Mapping[str, Any],
    execution_program: Mapping[str, Any],
    runtime_registry: Mapping[str, Any],
    runtime_binding_receipt: Mapping[str, Any],
    execution: Mapping[str, Any],
    object_rows: Sequence[Mapping[str, Any]],
    source_record_ids: Iterable[str],
    recorded_at: str,
    prepared_from_commit: str,
    attempt_id: str,
    input_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    parsed_policy = validate_dell_report_internal_chain_ceiling_policy(
        policy,
        residual_program=residual_program,
        execution_program=execution_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding_receipt,
    )
    _require(
        execution.get("status") == "current_runtime_request_batch_zero_call_executed",
        "dell_03B_execution_status_invalid",
    )
    execution_summary = _mapping(
        execution.get("summary"), "dell_03B_execution_summary_invalid"
    )
    budget = parsed_policy["execution_budget"]
    _require(
        execution_summary.get("request_count") == budget["request_count"]
        and execution_summary.get("local_embedding_inference_batches") <= 1
        and execution_summary.get("network_calls") == 0
        and execution_summary.get("model_calls") == 0
        and execution_summary.get("generation_model_calls") == 0,
        "dell_03B_execution_exceeded_authority",
    )
    request_results = [
        _mapping(value, "dell_03B_request_result_invalid")
        for value in _sequence(
            execution.get("request_results"), "dell_03B_request_results_invalid"
        )
    ]
    request_results_by_id = {
        str(row.get("request", {}).get("request_id") or ""): row
        for row in request_results
    }
    expected_request_ids = {
        request_id
        for contract in parsed_policy["target_contracts"]
        for request_id in contract["request_ids"]
    }
    _require(
        set(request_results_by_id) == expected_request_ids,
        "dell_03B_executed_request_set_invalid",
    )
    objects_by_id, source_ids = validate_dell_report_source_compiled_identity_population(
        object_rows=object_rows,
        source_record_ids=source_record_ids,
        runtime_binding_receipt=runtime_binding_receipt,
    )
    residual_targets = {
        str(row.get("target_id") or ""): dict(row)
        for row in residual_program.get("route_targets") or ()
        if isinstance(row, Mapping)
    }

    target_results: list[dict[str, Any]] = []
    total_union_occurrences = 0
    total_complete_corpus = 0
    total_complete_union = 0
    total_complete_final = 0
    for contract in sorted(
        parsed_policy["target_contracts"], key=lambda row: str(row["target_id"])
    ):
        target_id = str(contract["target_id"])
        scoped_results = [request_results_by_id[value] for value in contract["request_ids"]]
        union_ids: set[str] = set()
        final_ids: set[str] = set()
        for request_result in scoped_results:
            hybrid = _mapping(
                request_result.get("hybrid_object_retrieval"),
                f"dell_03B_hybrid_result_missing:{target_id}",
            )
            seeds = [
                _mapping(value, f"dell_03B_seed_invalid:{target_id}")
                for value in hybrid.get("candidate_decision_seed") or ()
            ]
            _require(seeds, f"dell_03B_candidate_union_empty:{target_id}")
            union_ids.update(str(seed.get("compiled_object_id") or "") for seed in seeds)
            final_ids.update(
                str(row.get("compiled_object_id") or "")
                for row in hybrid.get("candidates") or ()
            )
        _require(
            "" not in union_ids and union_ids.issubset(objects_by_id),
            f"dell_03B_union_object_binding_invalid:{target_id}",
        )
        _require(
            final_ids.issubset(union_ids),
            f"dell_03B_final_not_subset_union:{target_id}",
        )
        total_union_occurrences += len(union_ids)

        corpus_assessments: dict[str, dict[str, Any]] = {}
        classification_counts: Counter[str] = Counter()
        scan_rows: list[dict[str, Any]] = []
        for object_id, object_row in objects_by_id.items():
            assessment = classify_internal_chain_object(object_row, contract)
            classification_counts[assessment["classification"]] += 1
            scan_rows.append(
                {
                    "compiled_object_id": object_id,
                    "classification": assessment["classification"],
                    "matched_group_ids": assessment["matched_group_ids"],
                    "forbidden_complete_terms_matched": assessment[
                        "forbidden_complete_terms_matched"
                    ],
                    "forbidden_complete_regexes_matched": assessment[
                        "forbidden_complete_regexes_matched"
                    ],
                }
            )
            if assessment["classification"] != "not_target_semantic_equivalent":
                corpus_assessments[object_id] = assessment
        complete_corpus_ids = {
            object_id
            for object_id, row in corpus_assessments.items()
            if row["classification"] == "complete_target_semantic_equivalent"
        }
        partial_corpus_ids = set(corpus_assessments) - complete_corpus_ids
        complete_union_ids = complete_corpus_ids.intersection(union_ids)
        partial_union_ids = partial_corpus_ids.intersection(union_ids)
        complete_final_ids = complete_corpus_ids.intersection(final_ids)
        partial_final_ids = partial_corpus_ids.intersection(final_ids)
        total_complete_corpus += len(complete_corpus_ids)
        total_complete_union += len(complete_union_ids)
        total_complete_final += len(complete_final_ids)

        if not complete_corpus_ids:
            earliest = "local_source_object_corpus_missing_complete_target"
        elif not complete_union_ids:
            earliest = "current_bm25_0_6b_graph_candidate_recall_miss"
        elif not complete_final_ids:
            earliest = "post_union_financial_rank_or_review_cut"
        else:
            earliest = "none_observed_through_final_review"
        embedding_eligible = bool(complete_corpus_ids and not complete_union_ids)
        reranker_useful_at_k = int(
            parsed_policy.get("candidate_ceiling_contract", {}).get(
                "reranker_useful_at_k"
            )
            or 0
        )
        _require(
            reranker_useful_at_k >= 1,
            "dell_03B_reranker_useful_at_k_invalid",
        )
        complete_final_ranks = [
            int(rank)
            for object_id in complete_final_ids
            for rank in (
                _candidate_trace(object_id, scoped_results).get(
                    "minimum_final_output_rank"
                ),
            )
            if rank is not None
        ]
        best_complete_final_rank = min(complete_final_ranks, default=None)
        reranker_eligible = bool(
            complete_union_ids
            and (
                best_complete_final_rank is None
                or best_complete_final_rank > reranker_useful_at_k
            )
        )
        external_required = not complete_corpus_ids

        matched_ids = sorted(
            set(corpus_assessments),
            key=lambda object_id: (
                0
                if corpus_assessments[object_id]["classification"]
                == "complete_target_semantic_equivalent"
                else 1,
                _candidate_trace(object_id, scoped_results)[
                    "minimum_raw_union_rank"
                ]
                or 10**9,
                object_id,
            ),
        )
        private_matches = [
            _project_match(
                corpus_assessments[object_id],
                _candidate_trace(object_id, scoped_results),
                include_text=True,
            )
            for object_id in matched_ids
        ]
        public_matches = [
            _project_match(
                corpus_assessments[object_id],
                _candidate_trace(object_id, scoped_results),
                include_text=False,
            )
            for object_id in matched_ids[:20]
        ]
        union_assessments = []
        for object_id in sorted(
            union_ids,
            key=lambda value: (
                _candidate_trace(value, scoped_results)["minimum_raw_union_rank"]
                or 10**9,
                value,
            ),
        ):
            assessment = classify_internal_chain_object(objects_by_id[object_id], contract)
            union_assessments.append(
                _project_match(
                    assessment,
                    _candidate_trace(object_id, scoped_results),
                    include_text=True,
                )
            )
        matched_source_ids = {
            source_id
            for row in private_matches
            for source_id in row.get("lineage_source_record_ids") or ()
            if source_id
        }
        _require(
            matched_source_ids.issubset(source_ids),
            f"dell_03B_matched_source_missing:{target_id}",
        )
        route_counts: Counter[str] = Counter()
        for row in union_assessments:
            for trace in row["candidate_trace"]["request_traces"]:
                route_counts.update(trace["route_membership"])
        typed_summary = {
            "resolved_count": sum(
                int(row.get("summary", {}).get("typed_fact_resolved_count") or 0)
                for row in scoped_results
            ),
            "gap_count": sum(
                int(row.get("summary", {}).get("typed_fact_gap_count") or 0)
                for row in scoped_results
            ),
            "conflict_count": sum(
                int(row.get("summary", {}).get("typed_fact_conflict_count") or 0)
                for row in scoped_results
            ),
        }
        residual_target = residual_targets[target_id]
        mandatory_external_route_ids = sorted(
            str(route.get("route_contract_id") or "")
            for route in residual_target.get("route_contracts") or ()
            if route.get("mandatory_for_target") is True
            and route.get("route_family_id") != "local_data_object_index_sql"
        )
        target_results.append(
            {
                "target_id": target_id,
                "pack_gap_id": residual_target.get("pack_gap_id"),
                "target_proposition": residual_target.get("target_proposition"),
                "request_ids": list(contract["request_ids"]),
                "local_chain": {
                    "source_record_population": len(source_ids),
                    "compiled_object_population": len(objects_by_id),
                    "all_matched_sources_exist": matched_source_ids.issubset(source_ids),
                    "embedding_index_object_population": int(
                        runtime_binding_receipt.get("embedding_index", {}).get(
                            "object_count"
                        )
                        or 0
                    ),
                    "query_execution_projection_digests": [
                        str(row.get("projection_digest") or "")
                        for row in scoped_results
                    ],
                    "route_execution_state_counts": dict(
                        Counter(
                            state
                            for row in scoped_results
                            for state, count in _route_state_counts(row).items()
                            for _ in range(count)
                        )
                    ),
                    "candidate_route_occurrences": dict(sorted(route_counts.items())),
                    "typed_fact_sibling": typed_summary,
                },
                "candidate_ceiling": {
                    "corpus_classification_counts": dict(
                        sorted(classification_counts.items())
                    ),
                    "complete_target_in_source_object_corpus_count": len(
                        complete_corpus_ids
                    ),
                    "partial_context_in_source_object_corpus_count": len(
                        partial_corpus_ids
                    ),
                    "candidate_union_count": len(union_ids),
                    "complete_target_in_candidate_union_count": len(
                        complete_union_ids
                    ),
                    "partial_context_in_candidate_union_count": len(
                        partial_union_ids
                    ),
                    "final_review_count": len(final_ids),
                    "complete_target_in_final_review_count": len(
                        complete_final_ids
                    ),
                    "partial_context_in_final_review_count": len(partial_final_ids),
                    "reranker_useful_at_k": reranker_useful_at_k,
                    "best_complete_target_final_rank": best_complete_final_rank,
                    "complete_target_useful_at_k": bool(
                        best_complete_final_rank is not None
                        and best_complete_final_rank <= reranker_useful_at_k
                    ),
                    "complete_target_in_pool": bool(complete_union_ids),
                    "complete_target_in_final_review": bool(complete_final_ids),
                    "earliest_observed_limitation": earliest,
                    "corpus_scan_digest": canonical_digest(scan_rows),
                    "candidate_decision_state": "candidate_not_evidence_unadjudicated",
                    "public_information_gap_eligible": False,
                },
                "downstream_disposition": {
                    "03D_4B_embedding_recall_challenger_eligible": embedding_eligible,
                    "03D_same_pool_reranker_challenger_eligible": reranker_eligible,
                    "03C_external_route_required_for_complete_target": external_required,
                    "mandatory_external_route_contract_ids_if_authorized": (
                        mandatory_external_route_ids if external_required else []
                    ),
                    "authority_granted_by_this_result": False,
                },
                "public_top_semantic_matches": public_matches,
                "private_semantic_matches": private_matches,
                "private_union_assessments": union_assessments,
            }
        )

    private_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": "dell_03B_internal_chain_candidate_ceiling_executed",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "input_bindings": dict(input_bindings),
        "runtime_registry": {
            "registry_id": runtime_registry.get("registry_id"),
            "resource_canonical_digest": runtime_registry.get(
                "resource_canonical_digest"
            ),
        },
        "execution_projection_digest": execution.get("projection_digest"),
        "execution_summary": execution_summary,
        "target_results": target_results,
        "summary": {
            "target_count": len(target_results),
            "held_target_execution_count": 0,
            "request_count": len(request_results),
            "candidate_union_occurrence_count": total_union_occurrences,
            "complete_target_corpus_match_count": total_complete_corpus,
            "complete_target_union_match_count": total_complete_union,
            "complete_target_final_match_count": total_complete_final,
            "embedding_challenger_eligible_target_count": sum(
                row["downstream_disposition"][
                    "03D_4B_embedding_recall_challenger_eligible"
                ]
                is True
                for row in target_results
            ),
            "reranker_challenger_eligible_target_count": sum(
                row["downstream_disposition"][
                    "03D_same_pool_reranker_challenger_eligible"
                ]
                is True
                for row in target_results
            ),
            "external_route_required_target_count": sum(
                row["downstream_disposition"][
                    "03C_external_route_required_for_complete_target"
                ]
                is True
                for row in target_results
            ),
            "network_calls": 0,
            "provider_calls": 0,
            "generation_model_calls": 0,
            "external_capture_calls": 0,
            "4B_embedding_calls": 0,
            "reranker_calls": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
            "gap_closures": 0,
        },
        "authority": {
            "03B_internal_chain_execution_consumed": True,
            "03C_external_capture_authorized": False,
            "03D_4B_embedding_authorized": False,
            "03D_reranker_authorized": False,
            "candidate_decision_authorized": False,
            "evidence_promotion_authorized": False,
            "proved_information_boundary_authorized": False,
            "G3_pass": False,
            "S1_pass": False,
            "report_quality_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "This receipt compares six unoverlapped report-material targets with the "
            "exact R38 local source/object/index/SQL and BM25 plus Qwen-0.6B plus "
            "typed-graph candidate chain. Lexical semantic gates are a deterministic "
            "candidate-ceiling diagnostic, not CandidateDecision, Evidence, NumericFact, "
            "a proved public-information boundary, report quality, or execution authority "
            "for 03C/03D. The three admission-held targets were not executed."
        ),
    }
    return {**private_body, "result_digest": canonical_digest(private_body)}


def build_dell_report_internal_chain_ceiling_public_projection(
    *,
    private_result: Mapping[str, Any],
    private_ref: str,
    private_sha256: str,
) -> dict[str, Any]:
    target_rows = []
    for raw in private_result.get("target_results") or ():
        row = dict(raw)
        row.pop("private_semantic_matches", None)
        row.pop("private_union_assessments", None)
        target_rows.append(row)
    body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": private_result.get("status"),
        "attempt_id": private_result.get("attempt_id"),
        "recorded_at": private_result.get("recorded_at"),
        "prepared_from_commit": private_result.get("prepared_from_commit"),
        "case_key": private_result.get("case_key"),
        "input_bindings": dict(private_result.get("input_bindings") or {}),
        "runtime_registry": dict(private_result.get("runtime_registry") or {}),
        "execution_projection_digest": private_result.get(
            "execution_projection_digest"
        ),
        "execution_summary": dict(private_result.get("execution_summary") or {}),
        "target_results": target_rows,
        "summary": dict(private_result.get("summary") or {}),
        "private_result_ref": private_ref,
        "private_result_sha256": private_sha256,
        "private_result_digest": private_result.get("result_digest"),
        "authority": dict(private_result.get("authority") or {}),
        "known_boundary": private_result.get("known_boundary"),
    }
    serialized = repr(body).casefold()
    _require("model_text" not in serialized, "dell_03B_public_model_text_leak")
    _require("http://" not in serialized and "https://" not in serialized, "dell_03B_public_url_leak")
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "DellReportInternalChainCeilingError",
    "EXPECTED_UNOVERLAPPED_TARGET_IDS",
    "FAILURE_RECEIPT_SCHEMA_VERSION",
    "POLICY_SCHEMA_VERSION",
    "SUCCESSOR_POLICY_SCHEMA_VERSION",
    "PRIVATE_RESULT_SCHEMA_VERSION",
    "PUBLIC_RESULT_SCHEMA_VERSION",
    "build_dell_report_internal_chain_ceiling_public_projection",
    "classify_internal_chain_object",
    "compile_dell_report_internal_chain_ceiling_result",
    "validate_dell_report_internal_chain_ceiling_policy",
    "validate_dell_report_internal_chain_ceiling_successor_policy",
    "validate_dell_report_source_compiled_identity_population",
]
